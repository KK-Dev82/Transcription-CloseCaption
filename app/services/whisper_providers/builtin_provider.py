"""
Builtin Whisper Provider (whisper.cpp via Docker)
ใช้ whisper.cpp ที่รันใน Docker container

Features:
- รองรับ model: base, small, medium, large, large-v3, large-v3-turbo
- On-Premise - ข้อมูลไม่ออกจากองค์กร
- ต้องการ GPU สำหรับ performance ที่ดี
"""

import os
import time
import logging
import requests
from pathlib import Path
from typing import Dict, Optional

from .base_provider import WhisperProvider, TranscriptionResult

logger = logging.getLogger(__name__)


class BuiltinProvider(WhisperProvider):
    """
    Built-in Whisper Provider using whisper.cpp (via Docker)
    
    Environment Variables:
    - WHISPER_API_URL: URL ของ Whisper service (default: http://whisper:8002)
    - WHISPER_MODEL: Default model (default: base)
    - WHISPER_TIMEOUT: Timeout (default: 600)
    
    Model Support:
    - tiny: เร็วสุด, ความแม่นยำต่ำ
    - base: เร็ว, ความแม่นยำปานกลาง (default)
    - small: ปานกลาง, ความแม่นยำดี
    - medium: ช้า, ความแม่นยำดีมาก
    - large: ช้าสุด, ความแม่นยำสูงสุด
    - large-v3: OpenAI Whisper large v3
    - large-v3-turbo: Optimized large v3 (ต้องมี GPU)
    """
    
    # Supported models
    SUPPORTED_MODELS = [
        "tiny", "base", "small", "medium", "large", 
        "large-v2", "large-v3", "large-v3-turbo"
    ]
    
    # Model to file mapping
    MODEL_FILES = {
        "tiny": "ggml-tiny.bin",
        "base": "ggml-base.bin",
        "small": "ggml-small.bin",
        "medium": "ggml-medium.bin",
        "large": "ggml-large.bin",
        "large-v2": "ggml-large-v2.bin",
        "large-v3": "ggml-large-v3.bin",
        "large-v3-turbo": "ggml-large-v3-turbo.bin"
    }
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.provider_name = "builtin"
        
        # Config
        self.whisper_api_url = (config or {}).get('api_url') or os.getenv('WHISPER_API_URL', 'http://whisper:8002')
        self.default_model = (config or {}).get('model') or os.getenv('WHISPER_MODEL', 'base')
        self.timeout = int((config or {}).get('timeout') or os.getenv('WHISPER_TIMEOUT', '600'))
        
        logger.info(f"[Builtin] Initialized with API URL: {self.whisper_api_url}")
        logger.info(f"[Builtin] Default model: {self.default_model}")
    
    async def transcribe(
        self, 
        audio_path: str, 
        language: str = "th",
        model_size: str = None
    ) -> TranscriptionResult:
        """
        Transcribe audio using built-in whisper.cpp
        
        Args:
            audio_path: Path ไปยังไฟล์ audio
            language: ภาษา ("th", "en")
            model_size: ขนาด model (tiny, base, small, medium, large, large-v3-turbo)
            
        Returns:
            TranscriptionResult
        """
        audio_path_obj = Path(audio_path)
        
        if not audio_path_obj.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Use default model if not specified
        model = model_size or self.default_model
        if model not in self.SUPPORTED_MODELS:
            logger.warning(f"[Builtin] Unknown model '{model}', using 'base'")
            model = "base"
        
        # Convert path for Docker container
        whisper_audio_path = self._convert_path_for_docker(audio_path)
        
        # Get model file path
        model_file = self.MODEL_FILES.get(model, "ggml-base.bin")
        model_path = f"/app/models/{model_file}"
        
        logger.info(f"[Builtin] 🎯 Transcribing: {audio_path}")
        logger.info(f"[Builtin] 📦 Model: {model} ({model_file})")
        logger.info(f"[Builtin] 🌍 Language: {language}")
        logger.info(f"[Builtin] 📂 Whisper path: {whisper_audio_path}")
        
        start_time = time.time()
        
        # Prepare request
        request_data = {
            "audio_path": whisper_audio_path,
            "language": language,
            "model_path": model_path
        }
        
        # Retry mechanism for connection errors
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                logger.info(f"[Builtin] 📡 Sending request to {self.whisper_api_url}/transcribe (attempt {attempt + 1}/{max_retries})")
                
                # Check if service is available before making request
                try:
                    health_response = requests.get(
                        f"{self.whisper_api_url}/health",
                        timeout=5
                    )
                    if health_response.status_code != 200:
                        logger.warning(f"[Builtin] ⚠️  Whisper API health check failed: {health_response.status_code}")
                        if attempt < max_retries - 1:
                            logger.info(f"[Builtin] ⏳ Retrying in {retry_delay}s...")
                            time.sleep(retry_delay)
                            continue
                except requests.RequestException as health_e:
                    logger.warning(f"[Builtin] ⚠️  Whisper API health check failed: {health_e}")
                    if attempt < max_retries - 1:
                        logger.info(f"[Builtin] ⏳ Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        continue
                
                response = requests.post(
                    f"{self.whisper_api_url}/transcribe",
                    json=request_data,
                    timeout=self.timeout
                )
                
                processing_time = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result.get("success"):
                        # Normalize segments
                        segments = result.get("segments", [])
                        normalized_segments = self.normalize_segments(segments)
                        
                        logger.info(f"[Builtin] ✅ Transcription complete!")
                        logger.info(f"[Builtin] 📊 Text length: {len(result.get('text', ''))} chars")
                        logger.info(f"[Builtin] 📊 Segments: {len(normalized_segments)}")
                        logger.info(f"[Builtin] ⏱️ Processing time: {processing_time:.2f}s")
                        
                        return TranscriptionResult(
                            text=result.get('text', ''),
                            segments=normalized_segments,
                            language=result.get('language', language),
                            provider='builtin',
                            model=model,
                            duration=None,  # whisper.cpp doesn't return this
                            processing_time=processing_time
                        )
                    else:
                        error = result.get('error', 'Unknown error')
                        logger.error(f"[Builtin] ❌ Whisper API error: {error}")
                        # Don't retry on API errors (not connection issues)
                        raise Exception(f"Whisper API error: {error}")
                else:
                    logger.error(f"[Builtin] ❌ HTTP error: {response.status_code}")
                    if attempt < max_retries - 1 and response.status_code >= 500:
                        # Retry on server errors
                        logger.info(f"[Builtin] ⏳ Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        continue
                    raise Exception(f"Whisper API HTTP error: {response.status_code}")
                    
            except requests.Timeout:
                logger.error(f"[Builtin] ⏰ Timeout after {self.timeout}s (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    logger.info(f"[Builtin] ⏳ Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                raise Exception(f"Whisper API timeout after {self.timeout}s")
            except requests.ConnectionError as e:
                logger.error(f"[Builtin] 🔌 Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"[Builtin] ⏳ Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                raise Exception(f"Cannot connect to Whisper service after {max_retries} attempts: {e}")
            except Exception as e:
                # Don't retry on other exceptions
                logger.error(f"[Builtin] ❌ Transcription error: {e}")
                raise
        
        # Should not reach here, but just in case
        raise Exception(f"Failed to transcribe after {max_retries} attempts")
    
    def _convert_path_for_docker(self, audio_path: str) -> str:
        """
        Convert local path to Docker container path
        
        API container: temp/task_xxx/chunk_X_xxx.wav  
        Whisper container: /app/temp/task_xxx/chunk_X_xxx.wav
        """
        audio_path_obj = Path(audio_path)
        
        if audio_path_obj.is_absolute():
            try:
                relative_path = audio_path_obj.relative_to(Path.cwd())
                return f"/app/{relative_path}"
            except ValueError:
                return str(audio_path_obj)
        else:
            return f"/app/{audio_path}"
    
    def health_check(self) -> bool:
        """Check whisper.cpp service health"""
        try:
            response = requests.get(
                f"{self.whisper_api_url}/health",
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info("[Builtin] ✅ Health check passed")
                return True
            else:
                logger.warning(f"[Builtin] ⚠️ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"[Builtin] ⚠️ Health check error: {e}")
            return False
    
    def get_available_models(self) -> list:
        """Get list of available models from Whisper service"""
        try:
            response = requests.get(
                f"{self.whisper_api_url}/models",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                models = [m.get('name', '').replace('ggml-', '').replace('.bin', '') 
                         for m in result.get('models', [])]
                return models
            return []
        except Exception as e:
            logger.warning(f"[Builtin] Cannot get models list: {e}")
            return []
    
    def get_provider_info(self) -> Dict:
        """Return provider information"""
        base_info = super().get_provider_info()
        base_info.update({
            "api_url": self.whisper_api_url,
            "default_model": self.default_model,
            "timeout": self.timeout,
            "supported_models": self.SUPPORTED_MODELS,
            "available_models": self.get_available_models() if self.health_check() else []
        })
        return base_info


