"""
OpenAI Whisper Provider (Python Library)
ใช้ openai-whisper Python library โดยตรง (ไม่ต้องใช้ whisper.cpp หรือ API)

Features:
- รองรับ model: tiny, base, small, medium, large, large-v2, large-v3
- ใช้ Python library โดยตรง - ไม่ต้องมี whisper-cli หรือ Docker service
- เหมาะสำหรับ Local Direct Mode และ RunPod Direct Mode
- ประสิทธิภาพดีกว่า whisper.cpp (ใช้ PyTorch optimization)
- รองรับ GPU acceleration (CUDA) ถ้ามี
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

# Import openai-whisper (optional — ใช้ faster-whisper เป็น default)
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.debug("openai-whisper not installed (optional; use faster-whisper as default)")

# Global model cache with thread-safe loading
_model_cache = {}
_model_locks = {}
_cache_lock = threading.Lock()

# Lock สำหรับการใช้ model (ป้องกัน race condition เมื่อหลาย threads ใช้ model พร้อมกัน)
# ⚠️ NOTE: สำหรับ parallel processing ควรใช้ multiple model instances แทน lock
# Lock นี้จะทำให้ transcription เป็น sequential (1 chunk ต่อครั้ง)
_model_usage_locks = {}
_usage_lock = threading.Lock()

# Thread-local model instances สำหรับ parallel processing
# แต่ละ thread จะมี model instance ของตัวเอง (ไม่ต้องใช้ lock)
_thread_local_models = threading.local()


class OpenAIWhisperProvider(WhisperProvider):
    """
    OpenAI Whisper Provider using openai-whisper Python library
    
    Environment Variables:
    - WHISPER_MODEL: Default model (default: base)
    - WHISPER_DEVICE: Device to use ("cuda", "cpu", "auto") (default: auto)
    - WHISPER_DOWNLOAD_ROOT: Directory to download models (default: ~/.cache/whisper)
    
    Model Support:
    - tiny: เร็วสุด, ความแม่นยำต่ำ (~39M parameters)
    - base: เร็ว, ความแม่นยำปานกลาง (~74M parameters) (default)
    - small: ปานกลาง, ความแม่นยำดี (~244M parameters)
    - medium: ช้า, ความแม่นยำดีมาก (~769M parameters)
    - large: ช้าสุด, ความแม่นยำสูงสุด (~1550M parameters)
    - large-v2: OpenAI Whisper large v2
    - large-v3: OpenAI Whisper large v3
    """
    
    # Supported models
    SUPPORTED_MODELS = [
        "tiny", "base", "small", "medium", "large", 
        "large-v2", "large-v3"
    ]
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.provider_name = "openai-whisper"
        
        if not WHISPER_AVAILABLE:
            raise ImportError("openai-whisper is not installed. Please install: pip install openai-whisper")
        
        # Config
        self.default_model = (config or {}).get('model') or os.getenv('WHISPER_MODEL', 'base')
        self.device = (config or {}).get('device') or os.getenv('WHISPER_DEVICE', 'auto')
        self.download_root = (config or {}).get('download_root') or os.getenv('WHISPER_DOWNLOAD_ROOT', None)
        
        # Auto-detect device
        if self.device == 'auto':
            if torch.cuda.is_available():
                self.device = 'cuda'
                logger.info(f"[OpenAI Whisper] Using CUDA device: {torch.cuda.get_device_name(0)}")
                
                # ⚡ Enable TF32 and cuDNN optimizations for RTX 4080 SUPER
                # เพิ่มความเร็ว 15-30% สำหรับ FP16 และ FP32
                torch.backends.cudnn.benchmark = True
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
                logger.info(f"[OpenAI Whisper] ⚡ Enabled TF32/cuDNN optimizations for better performance")
            else:
                self.device = 'cpu'
                logger.info(f"[OpenAI Whisper] Using CPU device")
        
        # Load model (lazy loading - load when first transcribe)
        self._model = None
        self._model_name = None
        
        logger.info(f"[OpenAI Whisper] Initialized with device: {self.device}, default model: {self.default_model}")
    
    def _load_model(self, model_size: str = None, use_thread_local: bool = True):
        """
        Load Whisper model (lazy loading with thread-safe singleton pattern)
        
        Args:
            model_size: Model size to load
            use_thread_local: If True, each thread gets its own model instance (for parallel processing)
                            If False, all threads share the same model instance (requires lock)
        """
        model_name = model_size or self.default_model
        
        if model_name not in self.SUPPORTED_MODELS:
            logger.warning(f"[OpenAI Whisper] Unknown model '{model_name}', using 'base'")
            model_name = "base"
        
        cache_key = f"{model_name}_{self.device}"
        
        # สำหรับ parallel processing: ใช้ thread-local model instances
        if use_thread_local:
            # ตรวจสอบว่า thread นี้มี model instance หรือยัง
            if not hasattr(_thread_local_models, 'models'):
                _thread_local_models.models = {}
            
            if cache_key in _thread_local_models.models:
                logger.debug(f"[OpenAI Whisper] Using thread-local model: {model_name} on {self.device}")
                self._model = _thread_local_models.models[cache_key]
                self._model_name = model_name
                return self._model
            
            # Load model สำหรับ thread นี้
            logger.info(f"[OpenAI Whisper] Loading thread-local model: {model_name} on {self.device} (for parallel processing)")
            start_time = time.time()
            
            try:
                # Load model with download_root if specified
                if self.download_root:
                    model = whisper.load_model(model_name, device=self.device, download_root=self.download_root)
                else:
                    model = whisper.load_model(model_name, device=self.device)
                
                # เก็บใน thread-local storage
                _thread_local_models.models[cache_key] = model
                
                self._model = model
                self._model_name = model_name
                load_time = time.time() - start_time
                logger.info(f"[OpenAI Whisper] Thread-local model loaded in {load_time:.2f}s")
                
                return self._model
            except Exception as e:
                logger.error(f"[OpenAI Whisper] Failed to load thread-local model {model_name}: {e}")
                raise
        
        # สำหรับ sequential processing: ใช้ shared model instance (เดิม)
        # ถ้า model ถูก load อยู่แล้วและเป็น model เดียวกัน ไม่ต้อง load ใหม่
        if self._model is not None and self._model_name == model_name:
            return self._model
        
        # ตรวจสอบว่า model ถูก load ใน cache หรือยัง
        with _cache_lock:
            if cache_key in _model_cache:
                logger.info(f"[OpenAI Whisper] Using cached model: {model_name} on {self.device}")
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
                    logger.info(f"[OpenAI Whisper] Model was loaded by another thread: {model_name}")
                    self._model = _model_cache[cache_key]
                    self._model_name = model_name
                    return self._model
            
            logger.info(f"[OpenAI Whisper] Loading model: {model_name} on {self.device} (thread-safe)")
            start_time = time.time()
            
            try:
                # Load model with download_root if specified
                if self.download_root:
                    model = whisper.load_model(model_name, device=self.device, download_root=self.download_root)
                else:
                    model = whisper.load_model(model_name, device=self.device)
                
                # เก็บใน cache
                with _cache_lock:
                    _model_cache[cache_key] = model
                
                self._model = model
                self._model_name = model_name
                load_time = time.time() - start_time
                logger.info(f"[OpenAI Whisper] Model loaded in {load_time:.2f}s and cached")
                
                return self._model
            except Exception as e:
                logger.error(f"[OpenAI Whisper] Failed to load model {model_name}: {e}")
                raise
    
    async def transcribe(
        self, 
        audio_path: str, 
        language: str = "th",
        model_size: str = None
    ) -> TranscriptionResult:
        """
        Transcribe audio using openai-whisper Python library
        
        Args:
            audio_path: Path ไปยังไฟล์ audio
            language: ภาษา ("th", "en", "auto")
            model_size: ขนาด model (tiny, base, small, medium, large, large-v2, large-v3)
            
        Returns:
            TranscriptionResult
        """
        audio_path_obj = Path(audio_path)
        
        if not audio_path_obj.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Use default model if not specified
        model = model_size or self.default_model
        if model not in self.SUPPORTED_MODELS:
            logger.warning(f"[OpenAI Whisper] Unknown model '{model}', using 'base'")
            model = "base"
        
        # Load model
        # ใช้ thread-local models สำหรับ parallel processing (default: True)
        # แต่ละ thread จะมี model instance ของตัวเอง → ไม่ต้องใช้ lock
        use_thread_local = os.getenv('WHISPER_USE_THREAD_LOCAL', 'true').lower() == 'true'
        whisper_model = self._load_model(model, use_thread_local=use_thread_local)
        
        # Prepare language code
        # openai-whisper ใช้ "th" สำหรับภาษาไทย, "en" สำหรับอังกฤษ, None สำหรับ auto-detect
        lang_code = None if language == "auto" else language
        
        logger.info(f"[OpenAI Whisper] 🎯 Transcribing: {audio_path}")
        logger.info(f"[OpenAI Whisper] 📦 Model: {model}")
        logger.info(f"[OpenAI Whisper] 🌍 Language: {lang_code or 'auto-detect'}")
        logger.info(f"[OpenAI Whisper] 🖥️  Device: {self.device}")
        logger.info(f"[OpenAI Whisper] 🔄 Thread-local models: {use_thread_local}")
        
        # Transcribe with optional lock (depends on model sharing strategy)
        # ⚠️ ถ้าใช้ thread-local models (use_thread_local=True) → ไม่ต้องใช้ lock
        # ⚠️ ถ้าใช้ shared model (use_thread_local=False) → ต้องใช้ lock
        cache_key = f"{model}_{self.device}"
        
        # ตรวจสอบว่าใช้ thread-local model หรือไม่
        is_thread_local = use_thread_local and hasattr(_thread_local_models, 'models') and cache_key in getattr(_thread_local_models, 'models', {})
        
        # Optimization parameters จาก environment variables
        # ⚡ Greedy decoding (beam_size=1) เพื่อความเร็ว
        beam_size = int(os.getenv('WHISPER_BEAM_SIZE', '1'))
        # ⚡ Temperature=0 เพื่อความเสถียรและเร็ว
        temperature = float(os.getenv('WHISPER_TEMPERATURE', '0'))
        # ⚡ Condition on previous text=False สำหรับ chunks (ไม่ต้องใช้ context จาก chunk ก่อนหน้า)
        condition_on_previous_text = os.getenv('WHISPER_CONDITION_ON_PREVIOUS_TEXT', 'false').lower() == 'true'
        # ⚡ Batch size สำหรับ GPU (8-32 สำหรับ RTX 4080S)
        batch_size = int(os.getenv('WHISPER_BATCH_SIZE', '16'))
        # ⚡ FP16 สำหรับ CUDA
        fp16 = self.device == 'cuda'
        
        start_time = time.time()
        try:
            if is_thread_local:
                # ใช้ thread-local model → ไม่ต้องใช้ lock (แต่ละ thread มี model instance ของตัวเอง)
                logger.debug(f"[OpenAI Whisper] Using thread-local model (no lock needed) for parallel processing")
                
                result = whisper_model.transcribe(
                    str(audio_path_obj),
                    language=lang_code,
                    task="transcribe",
                    verbose=False,  # ไม่แสดง progress bar
                    fp16=fp16,  # ใช้ fp16 บน CUDA เพื่อเพิ่มประสิทธิภาพ
                    beam_size=beam_size,  # Greedy decoding (beam_size=1) เพื่อความเร็ว
                    temperature=temperature,  # Temperature=0 เพื่อความเสถียร
                    condition_on_previous_text=condition_on_previous_text,  # ไม่ใช้ context จาก chunk ก่อนหน้า
                    initial_prompt=None,  # ไม่ใช้ initial prompt
                    word_timestamps=False,  # ไม่ใช้ word-level timestamps (ประหยัดเวลา)
                    no_speech_threshold=0.6,  # Default threshold
                    logprob_threshold=-1.0,  # Default threshold
                    compression_ratio_threshold=2.4,  # Default threshold
                    best_of=1,  # ไม่ใช้ best_of (ใช้ greedy decoding)
                    patience=1.0,  # Default patience
                    length_penalty=1.0,  # Default length penalty
                    suppress_tokens="-1",  # Suppress special tokens
                    without_timestamps=False,  # ยังคงใช้ timestamps (สำหรับ segments)
                    max_initial_timestamp=1.0,  # Default max initial timestamp
                    # batch_size ไม่ได้รองรับใน openai-whisper (ใช้ internal batching)
                )
            else:
                # ใช้ shared model → ต้องใช้ lock (ป้องกัน race condition)
                logger.debug(f"[OpenAI Whisper] Using shared model (lock required) for sequential processing")
                # สร้าง lock สำหรับ model นี้ (ถ้ายังไม่มี)
                with _usage_lock:
                    if cache_key not in _model_usage_locks:
                        _model_usage_locks[cache_key] = threading.Lock()
                    usage_lock = _model_usage_locks[cache_key]
                
                # ใช้ lock เมื่อใช้ model (ป้องกัน race condition)
                with usage_lock:
                    result = whisper_model.transcribe(
                        str(audio_path_obj),
                        language=lang_code,
                        task="transcribe",
                        verbose=False,  # ไม่แสดง progress bar
                        fp16=fp16,  # ใช้ fp16 บน CUDA เพื่อเพิ่มประสิทธิภาพ
                        beam_size=beam_size,  # Greedy decoding (beam_size=1) เพื่อความเร็ว
                        temperature=temperature,  # Temperature=0 เพื่อความเสถียร
                        condition_on_previous_text=condition_on_previous_text,  # ไม่ใช้ context จาก chunk ก่อนหน้า
                        initial_prompt=None,  # ไม่ใช้ initial prompt
                        word_timestamps=False,  # ไม่ใช้ word-level timestamps (ประหยัดเวลา)
                        no_speech_threshold=0.6,  # Default threshold
                        logprob_threshold=-1.0,  # Default threshold
                        compression_ratio_threshold=2.4,  # Default threshold
                        best_of=1,  # ไม่ใช้ best_of (ใช้ greedy decoding)
                        patience=1.0,  # Default patience
                        length_penalty=1.0,  # Default length penalty
                        suppress_tokens="-1",  # Suppress special tokens
                        without_timestamps=False,  # ยังคงใช้ timestamps (สำหรับ segments)
                        max_initial_timestamp=1.0,  # Default max initial timestamp
                    )
            processing_time = time.time() - start_time
            
            # Log optimization parameters
            if self.device == 'cuda':
                logger.debug(f"[OpenAI Whisper] 💡 Optimization: fp16={fp16}, beam_size={beam_size}, temperature={temperature}, condition_on_previous_text={condition_on_previous_text}")
            
            # Extract text and segments
            text = result.get("text", "").strip()
            segments_data = result.get("segments", [])
            
            # Convert segments to standard format
            segments = []
            for seg in segments_data:
                segments.append({
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                    "text": seg.get("text", "").strip()
                })
            
            # Get detected language
            detected_language = result.get("language", language)
            
            logger.info(f"[OpenAI Whisper] ✅ Transcription completed in {processing_time:.2f}s")
            logger.info(f"[OpenAI Whisper] 📝 Text length: {len(text)} characters")
            logger.info(f"[OpenAI Whisper] 📦 Segments: {len(segments)}")
            logger.info(f"[OpenAI Whisper] 🌍 Detected language: {detected_language}")
            
            return TranscriptionResult(
                text=text,
                segments=segments,
                language=detected_language,
                provider=self.provider_name,
                model=model,
                duration=None,  # openai-whisper ไม่ return duration โดยตรง
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"[OpenAI Whisper] ❌ Transcription failed: {e}", exc_info=True)
            raise
    
    def health_check(self) -> bool:
        """
        ตรวจสอบสถานะของ Provider
        
        Returns:
            bool: True ถ้า Provider พร้อมใช้งาน
        """
        try:
            if not WHISPER_AVAILABLE:
                return False
            
            # Try to load tiny model (smallest, fastest to load)
            try:
                test_model = whisper.load_model("tiny", device=self.device)
                del test_model  # Free memory
                torch.cuda.empty_cache() if torch.cuda.is_available() else None
                return True
            except Exception as e:
                logger.warning(f"[OpenAI Whisper] Health check failed: {e}")
                return False
        except Exception as e:
            logger.error(f"[OpenAI Whisper] Health check error: {e}")
            return False

