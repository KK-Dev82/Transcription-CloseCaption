"""
Faster Whisper Provider
ใช้ faster-whisper library (CTranslate2 backend) สำหรับ GPU acceleration
"""
import os
import logging
import asyncio
from typing import Dict, Optional
from pathlib import Path

from .base_provider import WhisperProvider, TranscriptionResult

logger = logging.getLogger(__name__)

# Import faster-whisper
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning("faster-whisper not installed. Please install: pip install faster-whisper")


class FasterWhisperProvider(WhisperProvider):
    """
    Faster Whisper Provider
    ใช้ faster-whisper (CTranslate2) สำหรับ GPU acceleration
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.provider_name = "faster-whisper"
        
        if not FASTER_WHISPER_AVAILABLE:
            raise ImportError("faster-whisper not installed. Please install: pip install faster-whisper")
        
        # Configuration
        self.device = os.getenv('WHISPER_DEVICE', 'cuda')
        self.compute_type = os.getenv('WHISPER_COMPUTE_TYPE', None)
        
        # Auto-detect compute_type based on device
        if self.compute_type is None:
            if self.device == 'cuda':
                self.compute_type = 'float16'
            else:
                self.compute_type = 'float32'
        
        # Check for CUDNN_DISABLE
        self.cudnn_disable = os.getenv('CUDNN_DISABLE', '0') == '1'
        
        # Model cache (singleton pattern)
        self._model_cache = {}
        self._model_lock = asyncio.Lock()
        
        logger.info(f"✅ FasterWhisperProvider initialized (device: {self.device}, compute_type: {self.compute_type})")
    
    async def transcribe(
        self,
        audio_path: str,
        language: str = "th",
        model_size: str = None,
        initial_prompt: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio file using faster-whisper
        
        Args:
            audio_path: Path to audio file
            language: Language code (th, en, auto)
            model_size: Model size (tiny, base, small, medium, large)
            initial_prompt: Initial prompt for better accuracy
            
        Returns:
            TranscriptionResult
        """
        try:
            # Validate file
            if not Path(audio_path).exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            # Use default model if not specified
            if model_size is None:
                model_size = self.default_model
            
            # Get or load model
            model = await self._get_model(model_size)
            
            # Transcribe
            logger.info(f"[Faster Whisper] Transcribing: {audio_path}")
            logger.info(f"   Model: {model_size}, Language: {language}, Device: {self.device}")
            
            import time
            start_time = time.time()
            
            # Run transcription (faster-whisper is synchronous)
            segments, info = model.transcribe(
                audio_path,
                language=language if language != "auto" else None,
                vad_filter=True,
                initial_prompt=initial_prompt
            )
            
            # Convert segments to list (this is where it might crash if cuDNN is wrong)
            logger.info(f"[Faster Whisper] 🔍 Segments is generator, converting to list...")
            segments_list = list(segments)
            
            processing_time = time.time() - start_time
            
            logger.info(f"[Faster Whisper] ✅ Transcription completed: {len(segments_list)} segments in {processing_time:.2f}s")
            
            # Convert to TranscriptionResult format
            text = " ".join([seg.text for seg in segments_list])
            segments_data = [
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text
                }
                for seg in segments_list
            ]
            
            return TranscriptionResult(
                text=text,
                segments=segments_data,
                provider=self.provider_name,
                model=f"{model_size} (faster-whisper)",
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"[Faster Whisper] ❌ Error transcribing: {e}", exc_info=True)
            raise
    
    async def _get_model(self, model_size: str):
        """Get or load model (singleton pattern)"""
        cache_key = f"{model_size}_{self.device}_{self.compute_type}"
        
        if cache_key in self._model_cache:
            logger.debug(f"[Faster Whisper] Using cached model: {cache_key}")
            return self._model_cache[cache_key]
        
        # Load model
        logger.info(f"[Faster Whisper] Loading model: {model_size} (device: {self.device}, compute_type: {self.compute_type})")
        
        try:
            model = WhisperModel(
                model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            self._model_cache[cache_key] = model
            logger.info(f"[Faster Whisper] ✅ Model loaded: {cache_key}")
            return model
        except Exception as e:
            logger.error(f"[Faster Whisper] ❌ Error loading model: {e}", exc_info=True)
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
            
            # ตรวจสอบว่า CUDA พร้อมใช้งานหรือไม่ (ถ้าใช้ GPU)
            if self.device == 'cuda':
                import torch
                if not torch.cuda.is_available():
                    logger.warning("[Faster Whisper] CUDA not available")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"[Faster Whisper] Health check error: {e}")
            return False

