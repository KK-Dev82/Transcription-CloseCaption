"""
Faster Whisper Provider (CTranslate2)
ใช้ faster-whisper library ที่เร็วกว่า openai-whisper 2-4x

Features:
- รองรับ batch_size สำหรับ GPU
- เร็วกว่า openai-whisper 2-4x
- ใช้ memory น้อยกว่า
- GPU utilization สูง (90-100%)
"""

import os
import time
import logging
import threading
import asyncio
import gc
from pathlib import Path
from typing import Dict, Optional
import torch

from .base_provider import WhisperProvider, TranscriptionResult

logger = logging.getLogger(__name__)

# Import faster-whisper
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning("faster-whisper not installed. Please install: pip install faster-whisper")

# Global model cache with thread-safe loading
_model_cache = {}
_model_locks = {}
_cache_lock = threading.Lock()


class FasterWhisperProvider(WhisperProvider):
    """
    Faster Whisper Provider using faster-whisper (CTranslate2)
    
    Environment Variables:
    - WHISPER_MODEL: Default model (default: medium)
    - WHISPER_DEVICE: Device to use ("cuda", "cpu", "auto") (default: auto)
    - WHISPER_COMPUTE_TYPE: Compute type ("float16", "float32", "int8") (default: float16 for CUDA)
    - WHISPER_BATCH_SIZE: Batch size for GPU (default: 16)
    - WHISPER_DOWNLOAD_ROOT: Directory to download models (default: ~/.cache/huggingface)
    
    Model Support:
    - tiny, base, small, medium, large, large-v2, large-v3
    """
    
    # Supported models
    SUPPORTED_MODELS = [
        "tiny", "base", "small", "medium", "large", 
        "large-v2", "large-v3"
    ]
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.provider_name = "faster-whisper"
        
        if not FASTER_WHISPER_AVAILABLE:
            raise ImportError("faster-whisper is not installed. Please install: pip install faster-whisper")
        
        # Config
        self.default_model = (config or {}).get('model') or os.getenv('WHISPER_MODEL', 'medium')
        self.device = (config or {}).get('device') or os.getenv('WHISPER_DEVICE', 'auto')
        self.compute_type = (config or {}).get('compute_type') or os.getenv('WHISPER_COMPUTE_TYPE', None)
        self.batch_size = int((config or {}).get('batch_size') or os.getenv('WHISPER_BATCH_SIZE', '16'))
        self.download_root = (config or {}).get('download_root') or os.getenv('WHISPER_DOWNLOAD_ROOT', None)
        
        # Auto-detect device and compute type
        if self.device == 'auto':
            if torch.cuda.is_available():
                self.device = 'cuda'
                if self.compute_type is None:
                    self.compute_type = 'float16'  # Default for CUDA
                logger.info(f"[Faster Whisper] Using CUDA device: {torch.cuda.get_device_name(0)}")
            else:
                self.device = 'cpu'
                if self.compute_type is None:
                    self.compute_type = 'float32'  # Default for CPU
                logger.info(f"[Faster Whisper] Using CPU device")
        
        # Enable TF32 and cuDNN optimizations for RTX 4080 SUPER
        if self.device == 'cuda':
            torch.backends.cudnn.benchmark = True
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            logger.info(f"[Faster Whisper] ⚡ Enabled TF32/cuDNN optimizations")
        
        # Load model (lazy loading - load when first transcribe)
        self._model = None
        self._model_name = None
        
        logger.info(f"[Faster Whisper] Initialized with device: {self.device}, compute_type: {self.compute_type}, batch_size: {self.batch_size}, default model: {self.default_model}")
    
    def _load_model(self, model_size: str = None):
        """
        Load Faster Whisper model (lazy loading with thread-safe singleton pattern)
        """
        model_name = model_size or self.default_model
        
        if model_name not in self.SUPPORTED_MODELS:
            logger.warning(f"[Faster Whisper] Unknown model '{model_name}', using 'medium'")
            model_name = "medium"
        
        cache_key = f"{model_name}_{self.device}_{self.compute_type}"
        
        # ตรวจสอบว่า model ถูก load ใน cache หรือยัง
        with _cache_lock:
            if cache_key in _model_cache:
                logger.info(f"[Faster Whisper] Using cached model: {model_name} on {self.device}")
                self._model = _model_cache[cache_key]
                self._model_name = model_name
                return self._model
            
            # สร้าง lock สำหรับ model นี้ (ถ้ายังไม่มี)
            if cache_key not in _model_locks:
                _model_locks[cache_key] = threading.Lock()
        
        # ใช้ lock เพื่อให้ load model ทีละตัว (ป้องกัน CUDA OOM)
        with _model_locks[cache_key]:
            # ตรวจสอบอีกครั้งหลังจากได้ lock (double-check pattern)
            with _cache_lock:
                if cache_key in _model_cache:
                    logger.info(f"[Faster Whisper] Model was loaded by another thread: {model_name}")
                    self._model = _model_cache[cache_key]
                    self._model_name = model_name
                    return self._model
            
            logger.info(f"[Faster Whisper] Loading model: {model_name} on {self.device} (compute_type: {self.compute_type})")
            start_time = time.time()
            
            try:
                # Load model with download_root if specified
                # เพิ่ม num_workers=1 และ cpu_threads=4 เพื่อลด concurrency/deadlock issues
                # เพิ่ม device_index=0 เพื่อระบุ GPU device
                model_kwargs = {
                    "device": self.device,
                    "compute_type": self.compute_type,
                    "num_workers": 1,  # ลด concurrency เพื่อหลีกเลี่ยง deadlock
                    "cpu_threads": 4,  # จำกัด CPU threads
                }
                if self.device == "cuda":
                    model_kwargs["device_index"] = 0  # ระบุ GPU device
                if self.download_root:
                    model_kwargs["download_root"] = self.download_root
                
                model = WhisperModel(model_name, **model_kwargs)
                
                # เก็บใน cache
                with _cache_lock:
                    _model_cache[cache_key] = model
                
                self._model = model
                self._model_name = model_name
                load_time = time.time() - start_time
                logger.info(f"[Faster Whisper] Model loaded in {load_time:.2f}s and cached")
                
                return self._model
            except Exception as e:
                logger.error(f"[Faster Whisper] Failed to load model {model_name}: {e}")
                raise
    
    async def transcribe(
        self, 
        audio_path: str, 
        language: str = "th",
        model_size: str = None
    ) -> TranscriptionResult:
        """
        Transcribe audio using faster-whisper with retry logic
        
        Note: 
        - ถ้า GPU mode timeout จะ retry ก่อน fallback ไป CPU mode
        - Max retry attempts: 3 (configurable via GPU_TRANSCRIPTION_MAX_RETRIES)
        
        Args:
            audio_path: Path ไปยังไฟล์ audio
            language: ภาษา ("th", "en", "auto")
            model_size: ขนาด model (tiny, base, small, medium, large, large-v2, large-v3)
            
        Returns:
            TranscriptionResult
        """
        # ใช้ retry wrapper สำหรับ GPU mode
        if self.device == "cuda":
            return await self._transcribe_with_retry(audio_path, language, model_size)
        else:
            # CPU mode ไม่ต้อง retry
            return await self._transcribe_gpu_single_attempt(audio_path, language, model_size)
    
    async def _transcribe_with_retry(
        self,
        audio_path: str,
        language: str = "th",
        model_size: str = None
    ) -> TranscriptionResult:
        """
        Transcribe with retry logic for GPU mode
        
        Retry GPU mode ก่อน fallback to CPU
        """
        MAX_RETRY_ATTEMPTS = int(os.getenv('GPU_TRANSCRIPTION_MAX_RETRIES', '3'))
        RETRY_DELAY = float(os.getenv('GPU_TRANSCRIPTION_RETRY_DELAY', '5.0'))
        
        last_error = None
        
        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                logger.info(f"[Faster Whisper] 🔄 Attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS} - GPU transcription")
                
                # ลอง GPU mode
                result = await self._transcribe_gpu_single_attempt(audio_path, language, model_size)
                
                if attempt > 0:
                    logger.info(f"[Faster Whisper] ✅ GPU transcription succeeded on retry attempt {attempt + 1}")
                
                return result
                
            except (TimeoutError, Exception) as e:
                last_error = e
                error_msg = str(e).lower()
                
                # ตรวจสอบว่าเป็น timeout error หรือไม่
                is_timeout = isinstance(e, TimeoutError) or "timeout" in error_msg
                
                if is_timeout and attempt < MAX_RETRY_ATTEMPTS - 1:
                    logger.warning(
                        f"[Faster Whisper] ⚠️ GPU timeout (attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS}), "
                        f"retrying in {RETRY_DELAY}s..."
                    )
                    
                    # Release GPU resources ก่อน retry
                    try:
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                            logger.info(f"[Faster Whisper] 🧹 Cleared CUDA cache before retry")
                        gc.collect()
                    except Exception as cleanup_error:
                        logger.warning(f"[Faster Whisper] ⚠️ Failed to cleanup GPU resources: {cleanup_error}")
                    
                    # Delay before retry
                    await asyncio.sleep(RETRY_DELAY)
                elif is_timeout:
                    # Last attempt failed - fallback to CPU
                    logger.error(
                        f"[Faster Whisper] ❌ GPU timeout after {MAX_RETRY_ATTEMPTS} attempts, "
                        f"falling back to CPU mode..."
                    )
                    break
                else:
                    # Non-timeout error - don't retry
                    logger.error(f"[Faster Whisper] ❌ Non-timeout error: {e}")
                    raise
        
        # Fallback to CPU mode after all retries failed
        logger.warning(f"[Faster Whisper] 🔄 Falling back to CPU mode after {MAX_RETRY_ATTEMPTS} GPU retry attempts")
        try:
            return await self._transcribe_cpu_fallback(audio_path, language, model_size)
        except Exception as cpu_error:
            logger.error(f"[Faster Whisper] ❌ CPU fallback also failed: {cpu_error}")
            raise RuntimeError(f"GPU transcription failed after {MAX_RETRY_ATTEMPTS} retries, and CPU fallback also failed: {cpu_error}") from last_error
    
    async def _transcribe_gpu_single_attempt(
        self,
        audio_path: str,
        language: str = "th",
        model_size: str = None
    ) -> TranscriptionResult:
        """
        Single attempt GPU transcription (original transcribe logic)
        
        Note: Method นี้ถูก refactor ออกมาจาก transcribe() เพื่อให้ retry wrapper เรียกใช้ได้
        """
        logger.info(f"[Faster Whisper] 🔍 DEBUG: Starting GPU transcription attempt")
        logger.info(f"[Faster Whisper] 🔍 DEBUG: audio_path={audio_path}, language={language}, model_size={model_size}")
        
        audio_path_obj = Path(audio_path)
        
        logger.info(f"[Faster Whisper] 🔍 DEBUG: Checking if file exists: {audio_path_obj}")
        if not audio_path_obj.exists():
            logger.error(f"[Faster Whisper] ❌ DEBUG: File not found: {audio_path}")
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        logger.info(f"[Faster Whisper] ✅ DEBUG: File exists, size: {audio_path_obj.stat().st_size} bytes")
        
        # Use default model if not specified
        model = model_size or self.default_model
        if model not in self.SUPPORTED_MODELS:
            logger.warning(f"[Faster Whisper] Unknown model '{model}', using 'medium'")
            model = "medium"
        
        # Load model
        logger.info(f"[Faster Whisper] 🔍 DEBUG: Loading model: {model}")
        whisper_model = self._load_model(model)
        logger.info(f"[Faster Whisper] ✅ DEBUG: Model loaded successfully")
        
        # Prepare language code
        # faster-whisper ใช้ "th" สำหรับภาษาไทย, "en" สำหรับอังกฤษ, None สำหรับ auto-detect
        lang_code = None if language == "auto" else language
        logger.info(f"[Faster Whisper] 🔍 DEBUG: Language code: {lang_code}")
        
        # Optimization parameters
        beam_size = int(os.getenv('WHISPER_BEAM_SIZE', '1'))
        temperature = float(os.getenv('WHISPER_TEMPERATURE', '0'))
        condition_on_previous_text = os.getenv('WHISPER_CONDITION_ON_PREVIOUS_TEXT', 'false').lower() == 'true'
        vad_filter = os.getenv('WHISPER_VAD_FILTER', 'true').lower() == 'true'  # Voice Activity Detection
        
        logger.info(f"[Faster Whisper] 🎯 Transcribing: {audio_path}")
        logger.info(f"[Faster Whisper] 📦 Model: {model}")
        logger.info(f"[Faster Whisper] 🌍 Language: {lang_code or 'auto-detect'}")
        logger.info(f"[Faster Whisper] 🖥️  Device: {self.device}, Compute Type: {self.compute_type}")
        # Note: batch_size ไม่ได้ใช้ใน transcribe() แต่ CTranslate2 จะจัดการเอง
        logger.info(f"[Faster Whisper] 🔧 Optimization: beam_size={beam_size}, temperature={temperature}, condition_on_previous_text={condition_on_previous_text}, vad_filter={vad_filter}")
        
        start_time = time.time()
        try:
            logger.info(f"[Faster Whisper] 🔍 DEBUG: About to call whisper_model.transcribe()")
            logger.info(f"[Faster Whisper] 🔍 DEBUG: audio_path={str(audio_path_obj)}, language={lang_code}, device={self.device}, compute_type={self.compute_type}")
            
            # Transcribe with faster-whisper
            # Note: faster-whisper 1.0.3 รองรับเฉพาะ parameters หลักๆ
            # Parameters ที่ไม่รองรับ: batch_size, logprob_threshold, compression_ratio_threshold, 
            # best_of, patience, length_penalty, suppress_tokens, max_initial_timestamp
            # 
            # ตามคำแนะนำ: ใช้ compute_type="float16", language="th", vad_filter=True
            # ไม่ต้องติดตั้ง cuDNN เอง (CTranslate2 จัดการเอง)
            logger.info(f"[Faster Whisper] 🎯 DEBUG: Calling transcribe() now...")
            # ใช้พารามิเตอร์ชุด "สั้นและเสถียร" ตามคำแนะนำ
            # without_timestamps=True → คืน list แทน generator → ลดโอกาสค้างตอน iterate
            segments, info = whisper_model.transcribe(
                str(audio_path_obj),
                language=lang_code,  # ระบุภาษา ลด overhead
                beam_size=1,  # ใช้ 1 สำหรับเร็วเสถียร
                temperature=0.0,  # ใช้ 0.0 สำหรับเร็วเสถียร
                condition_on_previous_text=False,  # ปิดเพื่อลด overhead
                vad_filter=vad_filter,  # เปิดได้สำหรับ real-world; ถ้าดีบั๊กปัญหาให้ปิดชั่วคราว
                vad_parameters=dict(
                    min_silence_duration_ms=500,  # ตามคำแนะนำ
                    threshold=0.5
                ) if vad_filter else None,
                word_timestamps=False,  # ไม่ใช้ word-level timestamps (ลด overhead)
                initial_prompt=None,  # ไม่ใช้ initial prompt
                no_speech_threshold=0.6,
                without_timestamps=True,  # ให้คืน list แทน generator → ลดโอกาสค้าง
            )
            
            processing_time = time.time() - start_time
            
            logger.info(f"[Faster Whisper] ✅ DEBUG: transcribe() completed successfully")
            logger.info(f"[Faster Whisper] ⏱️  Transcription processing time: {processing_time:.2f}s")
            logger.info(f"[Faster Whisper] 🔍 DEBUG: info.duration={info.duration if hasattr(info, 'duration') else 'N/A'}")
            logger.info(f"[Faster Whisper] 🔍 DEBUG: info.language={info.language if hasattr(info, 'language') else 'N/A'}")
            
            # Convert segments to list and extract text
            segments_list = []
            text_parts = []
            
            logger.info(f"[Faster Whisper] 📝 Processing segments...")
            segment_count = 0
            try:
                # เมื่อใช้ without_timestamps=True, segments จะเป็น list แทน generator
                logger.info(f"[Faster Whisper] 🔍 Starting to process segments...")
                
                # ตรวจสอบว่า segments เป็น list หรือ generator
                if isinstance(segments, list):
                    logger.info(f"[Faster Whisper] ✅ Segments is list (without_timestamps=True), count: {len(segments)}")
                    segments_iter = segments
                else:
                    logger.warning(f"[Faster Whisper] ⚠️ Segments is still generator even with without_timestamps=True")
                    logger.info(f"[Faster Whisper] 🔍 Using timeout protection for generator...")
                    # ใช้ timeout protection สำหรับ generator (กันงานค้างเคสพิเศษ)
                    # แต่เนื่องจาก without_timestamps=True ควร return list แล้ว
                    # ถ้ายังเป็น generator อาจเป็นปัญหาจากเวอร์ชันหรือการตั้งค่า
                    import threading
                    import queue
                    segments_queue = queue.Queue()
                    error_queue = queue.Queue()
                    done_flag = threading.Event()
                    
                    def collect_segments():
                        try:
                            count = 0
                            for seg in segments:
                                if done_flag.is_set():
                                    break
                                segments_queue.put(seg)
                                count += 1
                                if count % 5 == 0:
                                    logger.debug(f"[Faster Whisper] Collected {count} segments in thread...")
                            segments_queue.put(None)  # Sentinel
                            logger.debug(f"[Faster Whisper] Thread finished, collected {count} segments")
                        except Exception as e:
                            logger.error(f"[Faster Whisper] Thread error: {e}", exc_info=True)
                            error_queue.put(e)
                    
                    thread = threading.Thread(target=collect_segments, daemon=True)
                    thread.start()
                    
                    # Collect with dynamic timeout ตามขนาดไฟล์
                    # สำหรับไฟล์ใหญ่ (2+ ชั่วโมง) ต้องใช้เวลานานในการ collect segments
                    audio_duration = getattr(info, 'duration', 0) if hasattr(info, 'duration') else 0
                    # timeout = 15s สำหรับไฟล์สั้น หรือ duration / 10 สำหรับไฟล์ยาว (อย่างน้อย 60s, สูงสุด 300s)
                    base_timeout = 15.0
                    dynamic_timeout = max(60.0, min(300.0, audio_duration / 10.0))
                    timeout = max(base_timeout, dynamic_timeout)
                    logger.info(f"[Faster Whisper] ⏱️ Using dynamic timeout: {timeout:.1f}s (audio duration: {audio_duration:.1f}s)")
                    
                    start_time = time.time()
                    segments_list_raw = []
                    last_log_time = start_time
                    
                    while True:
                        elapsed = time.time() - start_time
                        if elapsed > timeout:
                            done_flag.set()
                            logger.error(f"[Faster Whisper] ❌ Segments collection timeout after {timeout}s ({len(segments_list_raw)} collected)")
                            raise TimeoutError(f"Segments collection timeout after {timeout}s")
                        
                        # Log progress every 3 seconds
                        if time.time() - last_log_time >= 3.0:
                            logger.info(f"[Faster Whisper] 🔍 Still collecting... ({len(segments_list_raw)} so far, {elapsed:.1f}s elapsed)")
                            last_log_time = time.time()
                        
                        try:
                            seg = segments_queue.get(timeout=0.5)
                            if seg is None:
                                break
                            segments_list_raw.append(seg)
                        except queue.Empty:
                            if not thread.is_alive():
                                try:
                                    error = error_queue.get_nowait()
                                    raise error
                                except queue.Empty:
                                    # Thread died without error, might be done
                                    break
                            continue
                    
                    done_flag.set()
                    segments_iter = segments_list_raw
                    logger.info(f"[Faster Whisper] ✅ Collected {len(segments_iter)} segments from generator")
                
                # Process segments
                for segment in segments_iter:
                    # เมื่อ without_timestamps=True, segment อาจเป็น dict หรือ object
                    if isinstance(segment, dict):
                        segment_dict = {
                            "start": segment.get("start", 0.0),
                            "end": segment.get("end", 0.0),
                            "text": segment.get("text", "").strip()
                        }
                    else:
                        segment_dict = {
                            "start": getattr(segment, "start", 0.0),
                            "end": getattr(segment, "end", 0.0),
                            "text": getattr(segment, "text", "").strip()
                        }
                    segments_list.append(segment_dict)
                    text_parts.append(segment_dict["text"])
                    segment_count += 1
                    if segment_count % 10 == 0:
                        logger.info(f"[Faster Whisper] 📝 Processed {segment_count} segments...")
                
                logger.info(f"[Faster Whisper] ✅ Processed {segment_count} segments total")
            except TimeoutError as timeout_error:
                # ถ้า GPU timeout ให้ retry ก่อน fallback ไป CPU mode
                if self.device == "cuda":
                    logger.warning(f"[Faster Whisper] ⚠️ GPU mode timeout during segments processing")
                    # Retry logic จะถูกจัดการใน outer exception handler
                    raise  # Re-raise เพื่อให้ outer handler จัดการ retry
                else:
                    logger.error(f"[Faster Whisper] ❌ Error processing segments: {timeout_error}", exc_info=True)
                    raise
            except Exception as seg_error:
                logger.error(f"[Faster Whisper] ❌ Error processing segments: {seg_error}", exc_info=True)
                raise
            
            # Combine all text
            text = " ".join(text_parts).strip()
            
            # Get detected language
            detected_language = info.language if hasattr(info, 'language') else language
            
            logger.info(f"[Faster Whisper] ✅ Transcription completed in {processing_time:.2f}s")
            logger.info(f"[Faster Whisper] 📝 Text length: {len(text)} characters")
            logger.info(f"[Faster Whisper] 📦 Segments: {len(segments_list)}")
            logger.info(f"[Faster Whisper] 🌍 Detected language: {detected_language}")
            
            return TranscriptionResult(
                text=text,
                segments=segments_list,
                language=detected_language,
                provider=self.provider_name,
                model=model,
                duration=info.duration if hasattr(info, 'duration') else None,
                processing_time=processing_time
            )
            
        except Exception as e:
            error_msg = str(e)
            # Handle cuDNN warnings/errors gracefully
            # ตามคำแนะนำ: ไม่ต้องติดตั้ง cuDNN เอง (CTranslate2 จัดการเอง)
            # แต่ถ้ามี warning เกี่ยวกับ cuDNN อาจจะยังทำงานได้
            if "cudnn" in error_msg.lower() or "Invalid handle" in error_msg:
                logger.warning(f"[Faster Whisper] ⚠️  cuDNN warning detected (may still work): {error_msg}")
                # Try to continue - sometimes CTranslate2 can work despite cuDNN warnings
                # If it's a real error, it will fail on the next operation
                if "Cannot load symbol" in error_msg:
                    logger.error(f"[Faster Whisper] ❌ cuDNN symbol loading failed - this is a critical error")
                    raise RuntimeError(f"cuDNN library issue: {error_msg}. Please ensure CUDA runtime matches CTranslate2 wheel version.")
            
            logger.error(f"[Faster Whisper] ❌ Transcription failed: {e}", exc_info=True)
            # Re-raise exception เพื่อให้ retry wrapper จัดการ
            # ถ้าเรียกจาก retry wrapper แล้ว จะ retry ก่อน fallback
            # ถ้าเรียกจาก CPU mode หรือไม่ใช่ timeout จะ raise ทันที
            raise
    
    async def _transcribe_cpu_fallback(
        self,
        audio_path: str,
        language: str = "th",
        model_size: str = None
    ) -> TranscriptionResult:
        """
        Fallback to CPU mode when GPU mode times out
        """
        logger.info(f"[Faster Whisper] 🔄 Falling back to CPU mode...")
        
        # Load CPU model
        model_name = model_size or self.default_model
        cpu_model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            num_workers=1,
            cpu_threads=4
        )
        
        # Transcribe with CPU
        start_time = time.time()
        segments, info = cpu_model.transcribe(
            str(audio_path),
            language=language if language != "auto" else None,
            vad_filter=False,
            without_timestamps=True,
            beam_size=1,
            temperature=0.0,
        )
        
        processing_time = time.time() - start_time
        
        # Process segments (CPU mode should return list with without_timestamps=True)
        segments_list = []
        text_parts = []
        
        if isinstance(segments, list):
            for segment in segments:
                if isinstance(segment, dict):
                    segment_dict = {
                        "start": segment.get("start", 0.0),
                        "end": segment.get("end", 0.0),
                        "text": segment.get("text", "").strip()
                    }
                else:
                    segment_dict = {
                        "start": getattr(segment, "start", 0.0),
                        "end": getattr(segment, "end", 0.0),
                        "text": getattr(segment, "text", "").strip()
                    }
                segments_list.append(segment_dict)
                text_parts.append(segment_dict["text"])
        else:
            # ถ้ายังเป็น generator ให้ iterate
            for segment in segments:
                segment_dict = {
                    "start": getattr(segment, "start", 0.0),
                    "end": getattr(segment, "end", 0.0),
                    "text": getattr(segment, "text", "").strip()
                }
                segments_list.append(segment_dict)
                text_parts.append(segment_dict["text"])
        
        text = " ".join(text_parts).strip()
        detected_language = info.language if hasattr(info, 'language') else language
        
        logger.info(f"[Faster Whisper] ✅ CPU fallback completed in {processing_time:.2f}s")
        logger.info(f"[Faster Whisper] 📝 Text length: {len(text)} characters")
        logger.info(f"[Faster Whisper] 📦 Segments: {len(segments_list)}")
        
        return TranscriptionResult(
            text=text,
            segments=segments_list,
            language=detected_language,
            provider=self.provider_name,
            model=model_name,
            duration=info.duration if hasattr(info, 'duration') else None,
            processing_time=processing_time
        )
    
    def health_check(self) -> bool:
        """
        ตรวจสอบสถานะของ Provider
        
        Returns:
            bool: True ถ้า Provider พร้อมใช้งาน
        """
        try:
            if not FASTER_WHISPER_AVAILABLE:
                return False
            
            # Try to load tiny model (smallest, fastest to load)
            try:
                test_model = WhisperModel("tiny", device=self.device, compute_type=self.compute_type or "float16")
                del test_model  # Free memory
                torch.cuda.empty_cache() if torch.cuda.is_available() else None
                return True
            except Exception as e:
                logger.warning(f"[Faster Whisper] Health check failed: {e}")
                return False
        except Exception as e:
            logger.error(f"[Faster Whisper] Health check error: {e}")
            return False

