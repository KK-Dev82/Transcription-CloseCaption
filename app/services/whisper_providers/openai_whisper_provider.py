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

# Import openai-whisper
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("openai-whisper not installed. Please install: pip install openai-whisper")

# Global model cache with thread-safe loading
_model_cache = {}
_model_locks = {}
_cache_lock = threading.Lock()

# Lock สำหรับการใช้ model (ป้องกัน race condition เมื่อหลาย threads ใช้ model พร้อมกัน)
_model_usage_locks = {}
_usage_lock = threading.Lock()


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
            else:
                self.device = 'cpu'
                logger.info(f"[OpenAI Whisper] Using CPU device")
        
        # Load model (lazy loading - load when first transcribe)
        self._model = None
        self._model_name = None
        
        logger.info(f"[OpenAI Whisper] Initialized with device: {self.device}, default model: {self.default_model}")
    
    def _load_model(self, model_size: str = None):
        """Load Whisper model (lazy loading with thread-safe singleton pattern)"""
        model_name = model_size or self.default_model
        
        if model_name not in self.SUPPORTED_MODELS:
            logger.warning(f"[OpenAI Whisper] Unknown model '{model_name}', using 'base'")
            model_name = "base"
        
        # ถ้า model ถูก load อยู่แล้วและเป็น model เดียวกัน ไม่ต้อง load ใหม่
        if self._model is not None and self._model_name == model_name:
            return self._model
        
        # ใช้ global cache เพื่อให้ทุก threads ใช้ model เดียวกัน
        cache_key = f"{model_name}_{self.device}"
        
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
        whisper_model = self._load_model(model)
        
        # Prepare language code
        # openai-whisper ใช้ "th" สำหรับภาษาไทย, "en" สำหรับอังกฤษ, None สำหรับ auto-detect
        lang_code = None if language == "auto" else language
        
        logger.info(f"[OpenAI Whisper] 🎯 Transcribing: {audio_path}")
        logger.info(f"[OpenAI Whisper] 📦 Model: {model}")
        logger.info(f"[OpenAI Whisper] 🌍 Language: {lang_code or 'auto-detect'}")
        logger.info(f"[OpenAI Whisper] 🖥️  Device: {self.device}")
        
        # Transcribe with thread-safe lock
        # ⚠️ ต้องใช้ lock เพราะ model มี internal state (kv_cache) ที่ไม่ thread-safe
        cache_key = f"{model}_{self.device}"
        
        # สร้าง lock สำหรับ model นี้ (ถ้ายังไม่มี)
        with _usage_lock:
            if cache_key not in _model_usage_locks:
                _model_usage_locks[cache_key] = threading.Lock()
            usage_lock = _model_usage_locks[cache_key]
        
        start_time = time.time()
        try:
            # ใช้ lock เมื่อใช้ model (ป้องกัน race condition)
            with usage_lock:
                # ใช้ fp16 เพื่อเพิ่มประสิทธิภาพบน GPU (ถ้าใช้ CUDA)
                fp16 = self.device == 'cuda'
                
                result = whisper_model.transcribe(
                    str(audio_path_obj),
                    language=lang_code,
                    task="transcribe",
                    verbose=False,  # ไม่แสดง progress bar
                    fp16=fp16  # ใช้ fp16 บน CUDA เพื่อเพิ่มประสิทธิภาพ
                )
            processing_time = time.time() - start_time
            
            # Log GPU utilization hint
            if self.device == 'cuda':
                logger.debug(f"[OpenAI Whisper] 💡 Using fp16={fp16} for CUDA acceleration")
            
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

