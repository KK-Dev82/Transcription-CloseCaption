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
                model_kwargs = {
                    "device": self.device,
                    "compute_type": self.compute_type,
                }
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
        Transcribe audio using faster-whisper
        
        Args:
            audio_path: Path ไปยังไฟล์ audio
            language: ภาษา ("th", "en", "auto")
            model_size: ขนาด model (tiny, base, small, medium, large, large-v2, large-v3)
            
        Returns:
            TranscriptionResult
        """
        logger.info(f"[Faster Whisper] 🔍 DEBUG: Starting transcribe()")
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
            segments, info = whisper_model.transcribe(
                str(audio_path_obj),
                language=lang_code,  # ระบุภาษา ลด overhead
                beam_size=beam_size,
                temperature=temperature,
                condition_on_previous_text=condition_on_previous_text,
                vad_filter=vad_filter,  # Voice Activity Detection - ตัดเงียบ → เร็วขึ้น
                vad_parameters=dict(
                    min_silence_duration_ms=500,  # ตามคำแนะนำ
                    threshold=0.5
                ) if vad_filter else None,
                word_timestamps=False,  # ไม่ใช้ word-level timestamps (ลด overhead)
                initial_prompt=None,  # ไม่ใช้ initial prompt
                no_speech_threshold=0.6,
                without_timestamps=False,  # ยังคงใช้ timestamps (สำหรับ segments)
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
                # Process segments directly from generator with timeout protection
                logger.info(f"[Faster Whisper] 🔍 Starting to iterate segments...")
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Segments iteration timeout")
                
                # Set timeout to 30 seconds for segments processing
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)
                
                try:
                    for segment in segments:
                        segment_dict = {
                            "start": segment.start,
                            "end": segment.end,
                            "text": segment.text.strip()
                        }
                        segments_list.append(segment_dict)
                        text_parts.append(segment.text.strip())
                        segment_count += 1
                        if segment_count % 10 == 0:
                            logger.info(f"[Faster Whisper] 📝 Processed {segment_count} segments...")
                    
                    signal.alarm(0)  # Cancel timeout
                    logger.info(f"[Faster Whisper] ✅ Processed {segment_count} segments total")
                except TimeoutError:
                    logger.error(f"[Faster Whisper] ❌ Timeout processing segments after {segment_count} segments")
                    signal.alarm(0)
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
            raise
    
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

