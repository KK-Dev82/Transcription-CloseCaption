"""
Faster Whisper Provider
ใช้ faster-whisper library (CTranslate2 backend) สำหรับ GPU acceleration
"""
import os
import logging
import asyncio
from typing import Dict, Optional, Union
from pathlib import Path

from .base_provider import WhisperProvider, TranscriptionResult

logger = logging.getLogger(__name__)

# Import faster-whisper
try:
    from faster_whisper import WhisperModel, BatchedInferencePipeline
    import numpy as np
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning("faster-whisper not installed. Please install: pip install faster-whisper")
    np = None


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
        
        # Configuration - Model
        self.default_model = (config or {}).get('model') or os.getenv('WHISPER_MODEL', 'medium')
        
        # Configuration - Device (รองรับ multi-GPU)
        # ใช้ 'cuda' เป็น default สำหรับ GPU acceleration
        # ⚠️ device จะถูกอ่านใหม่ทุกครั้งใน _get_device() เพื่อรองรับ multi-GPU
        self.base_device = os.getenv('WHISPER_DEVICE', 'cuda')
        
        self.compute_type = os.getenv('WHISPER_COMPUTE_TYPE', None)
        
        # Configuration - Model download root (สำหรับ persistent model storage)
        self.download_root = os.getenv('WHISPER_DOWNLOAD_ROOT', '/workspace/transcription-service/models')
        
        # Auto-detect compute_type based on device
        if self.compute_type is None:
            if self.base_device.startswith('cuda'):
                self.compute_type = 'float16'
            else:
                self.compute_type = 'float32'
        
        # Check for CUDNN_DISABLE
        self.cudnn_disable = os.getenv('CUDNN_DISABLE', '0') == '1'
        
        # Model cache (singleton pattern) - รองรับ multi-GPU
        # Key format: "{model_size}_{device}_{compute_type}"
        self._model_cache = {}
        self._model_lock = asyncio.Lock()
        
        logger.info(f"✅ FasterWhisperProvider initialized (base_device: {self.base_device}, compute_type: {self.compute_type})")
    
    def _get_device(self) -> str:
        """
        อ่าน device จาก environment variable
        
        ⚠️  faster-whisper ไม่รองรับ "cuda:0" หรือ "cuda:1"
        ใช้ CUDA_VISIBLE_DEVICES ที่ตั้งไว้ตอนเริ่ม process แทน
        """
        device_str = self.base_device
        
        # ใช้ device_str ตามปกติ (cuda หรือ cpu)
        # CUDA_VISIBLE_DEVICES ถูกตั้งไว้ตอนเริ่ม process แล้ว (ใน start script)
        logger.debug(f"[Faster Whisper] Using device: {device_str} (CUDA_VISIBLE_DEVICES={os.getenv('CUDA_VISIBLE_DEVICES', 'not set')})")
        return device_str
    
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
            audio_path: Path to audio file (.wav, .mp3, etc.) หรือ .npy file (numpy array)
                       หรือถ้าเป็น numpy array ใน RAM ใช้ path เป็น memory identifier
            language: Language code (th, en, auto)
            model_size: Model size (tiny, base, small, medium, large)
            initial_prompt: Initial prompt for better accuracy
            
        Returns:
            TranscriptionResult
        """
        try:
            # OPTIMIZATION: ถ้า path เป็น .npy file (pre-decoded audio) ให้โหลดเป็น numpy array
            # เพื่อลด I/O และ CPU overhead (GPU จะทำงานต่อเนื่องขึ้น)
            audio_input: Union[str, np.ndarray] = audio_path
            
            if audio_path.endswith('.npy'):
                # โหลด pre-decoded numpy array (เร็วกว่า decode WAV file)
                if not Path(audio_path).exists():
                    raise FileNotFoundError(f"Audio array file not found: {audio_path}")
                logger.info(f"[Faster Whisper] 📦 Loading pre-decoded audio array: {audio_path}")
                audio_input = np.load(audio_path, mmap_mode='r')  # mmap_mode='r' เพื่อลด memory
                logger.info(f"[Faster Whisper] ✅ Loaded audio array: shape={audio_input.shape}, dtype={audio_input.dtype}")
            else:
                # Validate file สำหรับ audio files ปกติ
                if not Path(audio_path).exists():
                    raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            # Use default model if not specified
            if model_size is None:
                model_size = self.default_model
            
            # Get or load model
            model = await self._get_model(model_size)
            
            # อ่าน device ปัจจุบัน (อาจเปลี่ยนตาม WHISPER_DEVICE_ID)
            current_device = self._get_device()
            
            # Transcribe
            if isinstance(audio_input, np.ndarray):
                logger.info(f"[Faster Whisper] Transcribing: numpy array (shape={audio_input.shape})")
            else:
                logger.info(f"[Faster Whisper] Transcribing: {audio_path}")
            logger.info(f"   Model: {model_size}, Language: {language}, Device: {current_device}")
            
            import time
            start_time = time.time()
            
            # Run transcription (faster-whisper is synchronous)
            # ✅ CloseCaption: ใช้ CC_* env variables ถ้าเปิดใช้งาน CloseCaption
            # ถ้าไม่มี CC_* → fallback ไปใช้ WHISPER_* (backward compatible)
            cc_enabled = os.getenv('CC_ENABLED', 'false').lower() == 'true'
            
            if cc_enabled:
                # ใช้ CloseCaption config
                vad_filter = os.getenv('CC_VAD_FILTER', 'true').lower() == 'true'
                beam_size = int(os.getenv('CC_BEAM_SIZE', '3'))  # 3 สำหรับความแม่น (Profile TH-CC-RT v1)
                best_of = int(os.getenv('CC_BEST_OF', '1'))
                word_timestamps = os.getenv('CC_WORD_TIMESTAMPS', 'false').lower() == 'true'
                condition_on_previous_text = os.getenv('CC_CONDITION_ON_PREVIOUS_TEXT', 'false').lower() == 'true'
                temperature = float(os.getenv('CC_TEMPERATURE', '0.0'))
                no_speech_threshold = float(os.getenv('CC_NO_SPEECH_THRESHOLD', '0.6'))
                log_prob_threshold = float(os.getenv('CC_LOG_PROB_THRESHOLD', '-1.0'))
                logger.info(f"[Faster Whisper] 🎯 Using CloseCaption config: beam_size={beam_size}, temp={temperature}, vad={vad_filter}")
            else:
                # ใช้ default config (backward compatible)
                vad_filter = os.getenv('WHISPER_VAD_FILTER', 'true').lower() == 'true'
                beam_size = int(os.getenv('WHISPER_BEAM_SIZE', '1'))  # greedy (เร็วสุด)
                best_of = int(os.getenv('WHISPER_BEST_OF', '1'))
                word_timestamps = os.getenv('WHISPER_WORD_TIMESTAMPS', 'false').lower() == 'true'
                condition_on_previous_text = os.getenv('WHISPER_CONDITION_ON_PREVIOUS_TEXT', 'false').lower() == 'true'
                temperature = float(os.getenv('WHISPER_TEMPERATURE', '0.0'))
                no_speech_threshold = float(os.getenv('WHISPER_NO_SPEECH_THRESHOLD', '0.6'))
                log_prob_threshold = float(os.getenv('WHISPER_LOG_PROB_THRESHOLD', '-1.0'))
            
            # ใช้ BatchedInferencePipeline ถ้าเปิดใช้งาน
            use_batched = os.getenv('WHISPER_USE_BATCHED', 'false').lower() == 'true'
            # FIX: ลด batch_size default จาก 16 → 16 (ไม่เปลี่ยน) แต่แนะนำให้ set เป็น 16 ใน env
            # เพื่อลด peak RAM โดยเฉพาะเมื่อมีหลาย jobs พร้อมกัน
            batch_size = int(os.getenv('WHISPER_BATCH_SIZE', '16'))
            
            if use_batched:
                logger.info(f"[Faster Whisper] 🚀 Using BatchedInferencePipeline (batch_size={batch_size})")
                batched_model = BatchedInferencePipeline(model=model)
                segments, info = batched_model.transcribe(
                    audio_input,  # รองรับทั้ง str และ np.ndarray
                    language=language if language != "auto" else None,
                    vad_filter=vad_filter,
                    initial_prompt=initial_prompt,
                    beam_size=beam_size,
                    best_of=best_of,
                    word_timestamps=word_timestamps,
                    condition_on_previous_text=condition_on_previous_text,
                    temperature=temperature,
                    no_speech_threshold=no_speech_threshold,
                    log_prob_threshold=log_prob_threshold,
                    batch_size=batch_size
                )
            else:
                logger.info(f"[Faster Whisper] Using standard WhisperModel.transcribe()")
                segments, info = model.transcribe(
                    audio_input,  # รองรับทั้ง str และ np.ndarray
                    language=language if language != "auto" else None,
                    vad_filter=vad_filter,
                    initial_prompt=initial_prompt,
                    beam_size=beam_size,
                    best_of=best_of,
                    word_timestamps=word_timestamps,
                    condition_on_previous_text=condition_on_previous_text,
                    temperature=temperature,
                    no_speech_threshold=no_speech_threshold,
                    log_prob_threshold=log_prob_threshold
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
        """Get or load model (singleton pattern) - รองรับ multi-GPU"""
        # อ่าน device ปัจจุบัน (อาจเปลี่ยนตาม WHISPER_DEVICE_ID)
        current_device = self._get_device()
        cache_key = f"{model_size}_{current_device}_{self.compute_type}"
        
        if cache_key in self._model_cache:
            logger.info(f"[Faster Whisper] ✅ Using cached model: {cache_key}")
            return self._model_cache[cache_key]
        
        # Load model
        # FIX: เพิ่ม log เพื่อตรวจสอบ device จริง
        logger.info(f"[Faster Whisper] 🔄 Loading model: {model_size} (device: {current_device}, compute_type: {self.compute_type})")
        logger.info(f"[Faster Whisper]    Cache key: {cache_key}")
        logger.info(f"[Faster Whisper]    ENV WHISPER_DEVICE={os.getenv('WHISPER_DEVICE', 'not set')}")
        logger.info(f"[Faster Whisper]    ENV CUDA_VISIBLE_DEVICES={os.getenv('CUDA_VISIBLE_DEVICES', 'not set')}")
        
        try:
            model = WhisperModel(
                model_size,
                device=current_device,
                compute_type=self.compute_type,
                download_root=self.download_root
            )
            self._model_cache[cache_key] = model
            
            # FIX: ตรวจสอบ device จริงที่ model ใช้
            # faster-whisper (CTranslate2) model มี device attribute
            if hasattr(model, 'model') and hasattr(model.model, 'device'):
                actual_device = model.model.device
                logger.info(f"[Faster Whisper] ✅ Model loaded: {cache_key}")
                logger.info(f"[Faster Whisper]    ACTUAL model.device={actual_device} (ตรวจสอบว่าใช้ GPU จริงหรือไม่)")
            else:
                logger.info(f"[Faster Whisper] ✅ Model loaded: {cache_key}")
                logger.warning(f"[Faster Whisper]    ⚠️  Cannot detect actual device from model (may fallback to CPU)")
            
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
            current_device = self._get_device()
            if current_device.startswith('cuda'):
                import torch
                if not torch.cuda.is_available():
                    logger.warning("[Faster Whisper] CUDA not available")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"[Faster Whisper] Health check error: {e}")
            return False

