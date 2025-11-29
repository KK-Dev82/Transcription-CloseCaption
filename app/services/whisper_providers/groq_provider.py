"""
Groq Whisper API Provider
ใช้ Groq Cloud API สำหรับ transcription ด้วย whisper-large-v3-turbo

Features:
- ความเร็วสูงมาก (วิดีโอ 1 ชม → ~3-5 นาที)
- ความแม่นยำสูง (large-v3-turbo)
- รองรับภาษาไทย + อังกฤษ
"""

import os
import asyncio
import aiohttp
import logging
import time
from pathlib import Path
from typing import Dict, Optional

from .base_provider import WhisperProvider, TranscriptionResult

logger = logging.getLogger(__name__)


class GroqProvider(WhisperProvider):
    """
    Groq Whisper API Provider
    
    Environment Variables:
    - GROQ_API_KEY: API Key จาก Groq Console
    - GROQ_MODEL: Model ที่ใช้ (default: whisper-large-v3-turbo)
    - GROQ_TIMEOUT: Timeout สำหรับ request (default: 300)
    """
    
    # Model mapping - Groq รองรับ large-v3 series
    MODEL_MAPPING = {
        "large-v3": "whisper-large-v3",
        "large-v3-turbo": "whisper-large-v3-turbo",
        "large": "whisper-large-v3",
        # Map smaller models to large-v3-turbo (ใน Groq)
        "base": "whisper-large-v3-turbo",
        "small": "whisper-large-v3-turbo", 
        "medium": "whisper-large-v3-turbo",
    }
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.provider_name = "groq"
        
        # Config
        self.api_key = (config or {}).get('api_key') or os.getenv('GROQ_API_KEY')
        self.api_url = "https://api.groq.com/openai/v1/audio/transcriptions"
        self.default_model = (config or {}).get('model') or os.getenv('GROQ_MODEL', 'whisper-large-v3-turbo')
        self.timeout = int((config or {}).get('timeout') or os.getenv('GROQ_TIMEOUT', '300'))
        
        # Supported formats
        self.supported_formats = ['.wav', '.mp3', '.m4a', '.webm', '.mp4', '.mpeg', '.mpga', '.ogg', '.flac']
        
        if not self.api_key:
            logger.warning("⚠️ GROQ_API_KEY not configured - Groq provider will not work")
    
    async def transcribe(
        self, 
        audio_path: str, 
        language: str = "th",
        model_size: str = None
    ) -> TranscriptionResult:
        """
        Transcribe audio using Groq API
        
        Args:
            audio_path: Path ไปยังไฟล์ audio
            language: ภาษา ("th", "en", "auto")
            model_size: จะถูก map เป็น Groq model
            
        Returns:
            TranscriptionResult
        """
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not configured")
        
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Map model
        groq_model = self.MODEL_MAPPING.get(model_size or self.default_model, self.default_model)
        
        logger.info(f"[Groq] 🎯 Transcribing: {audio_path}")
        logger.info(f"[Groq] 📦 Model: {groq_model}, Language: {language}")
        
        start_time = time.time()
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Prepare multipart form data
                with open(audio_path, 'rb') as f:
                    file_content = f.read()
                
                data = aiohttp.FormData()
                data.add_field(
                    'file',
                    file_content,
                    filename=audio_file.name,
                    content_type=self._get_content_type(audio_file.suffix)
                )
                data.add_field('model', groq_model)
                data.add_field('language', language if language != "auto" else "")
                data.add_field('response_format', 'verbose_json')
                data.add_field('temperature', '0')  # More deterministic
                
                headers = {
                    'Authorization': f'Bearer {self.api_key}'
                }
                
                logger.info(f"[Groq] 📡 Sending request to API...")
                
                async with session.post(
                    self.api_url,
                    data=data,
                    headers=headers
                ) as response:
                    processing_time = time.time() - start_time
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        # Parse segments
                        segments = []
                        for seg in result.get('segments', []):
                            segments.append({
                                'start': seg.get('start', 0),
                                'end': seg.get('end', 0),
                                'text': seg.get('text', '').strip()
                            })
                        
                        # Normalize segments
                        normalized_segments = self.normalize_segments(segments)
                        
                        logger.info(f"[Groq] ✅ Transcription complete!")
                        logger.info(f"[Groq] 📊 Text length: {len(result.get('text', ''))} chars")
                        logger.info(f"[Groq] 📊 Segments: {len(normalized_segments)}")
                        logger.info(f"[Groq] ⏱️ Processing time: {processing_time:.2f}s")
                        
                        return TranscriptionResult(
                            text=result.get('text', ''),
                            segments=normalized_segments,
                            language=result.get('language', language),
                            provider='groq',
                            model=groq_model,
                            duration=result.get('duration'),
                            processing_time=processing_time
                        )
                    else:
                        error_text = await response.text()
                        logger.error(f"[Groq] ❌ API error {response.status}: {error_text}")
                        raise Exception(f"Groq API error {response.status}: {error_text}")
                        
        except asyncio.TimeoutError:
            logger.error(f"[Groq] ⏰ Timeout after {self.timeout}s")
            raise Exception(f"Groq API timeout after {self.timeout}s")
        except aiohttp.ClientError as e:
            logger.error(f"[Groq] 🔌 Connection error: {e}")
            raise Exception(f"Groq API connection error: {e}")
        except Exception as e:
            logger.error(f"[Groq] ❌ Transcription error: {e}")
            raise
    
    def _get_content_type(self, suffix: str) -> str:
        """Get content type for audio file"""
        content_types = {
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.m4a': 'audio/mp4',
            '.webm': 'audio/webm',
            '.mp4': 'audio/mp4',
            '.mpeg': 'audio/mpeg',
            '.mpga': 'audio/mpeg',
            '.ogg': 'audio/ogg',
            '.flac': 'audio/flac'
        }
        return content_types.get(suffix.lower(), 'audio/wav')
    
    def health_check(self) -> bool:
        """Check Groq API health by listing models"""
        if not self.api_key:
            return False
        
        try:
            import requests
            response = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={'Authorization': f'Bearer {self.api_key}'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("[Groq] ✅ Health check passed")
                return True
            else:
                logger.warning(f"[Groq] ⚠️ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"[Groq] ⚠️ Health check error: {e}")
            return False
    
    def get_provider_info(self) -> Dict:
        """Return provider information"""
        base_info = super().get_provider_info()
        base_info.update({
            "api_url": self.api_url,
            "default_model": self.default_model,
            "timeout": self.timeout,
            "api_key_configured": bool(self.api_key),
            "supported_formats": self.supported_formats,
            "model_mapping": self.MODEL_MAPPING
        })
        return base_info


