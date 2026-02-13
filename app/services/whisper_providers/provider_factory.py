"""
Whisper Provider Factory
สำหรับ switch ระหว่าง providers (Groq, Builtin, etc.)

Usage:
    # Get default provider (from env WHISPER_PROVIDER)
    provider = WhisperProviderFactory.get_provider()
    
    # Get specific provider
    provider = WhisperProviderFactory.get_provider("groq")
    
    # Get provider with automatic fallback
    provider = WhisperProviderFactory.get_with_fallback()
"""

import os
import logging
from typing import Dict, Optional
from enum import Enum

from .base_provider import WhisperProvider
from .builtin_provider import BuiltinProvider
from .groq_provider import GroqProvider
from .openai_whisper_provider import OpenAIWhisperProvider
from .faster_whisper_provider import FasterWhisperProvider
from .whisper_cpp_provider import WhisperCppProvider

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported provider types"""
    BUILTIN = "builtin"
    GROQ = "groq"
    OPENAI_WHISPER = "openai-whisper"
    FASTER_WHISPER = "faster-whisper"
    NEMO_TYPHOON = "nemo-typhoon"
    WHISPER_CPP = "whisper-cpp"


class WhisperProviderFactory:
    """
    Factory สำหรับสร้างและจัดการ Whisper Providers
    
    Features:
    - Singleton pattern สำหรับ provider instances
    - Automatic fallback เมื่อ primary provider ไม่พร้อม
    - Configuration จาก environment variables
    
    Environment Variables:
    - WHISPER_PROVIDER: Provider ที่ใช้ (builtin, groq, openai-whisper) - default: builtin
    - WHISPER_FALLBACK_ENABLED: เปิด fallback (true/false) - default: true
    """
    
    # Cache providers (singleton)
    _providers: Dict[str, WhisperProvider] = {}
    
    # Fallback order (primary -> fallback)
    # Note:
    # - faster-whisper / nemo-typhoon: GPU (Runpod) — สลับได้ via WHISPER_PROVIDER
    # - whisper-cpp: Local Test (Mac Mini M4)
    _fallback_order = [
        ProviderType.FASTER_WHISPER,   # GPU (Runpod) — fallback เมื่อ nemo-typhoon ล้มเหลว
        ProviderType.NEMO_TYPHOON,     # NeMo Typhoon ASR — fallback เมื่อ faster-whisper ล้มเหลว
        ProviderType.WHISPER_CPP,      # Local Test (Mac Mini M4)
        ProviderType.OPENAI_WHISPER,   # Fallback
        ProviderType.GROQ,             # Cloud API
        ProviderType.BUILTIN           # Docker API (last resort)
    ]
    
    @classmethod
    def get_provider(cls, provider_type: str = None) -> WhisperProvider:
        """
        Get or create a Whisper provider
        
        Args:
            provider_type: Provider type ("builtin", "groq") หรือ None เพื่อใช้ค่าจาก env
            
        Returns:
            WhisperProvider instance
        """
        # Get provider type from env if not specified
        if provider_type is None:
            provider_type = os.getenv('WHISPER_PROVIDER', 'builtin')
        
        # Normalize
        provider_type = provider_type.lower().strip()
        
        # Return cached provider if exists
        if provider_type in cls._providers:
            logger.debug(f"[Factory] Returning cached provider: {provider_type}")
            return cls._providers[provider_type]
        
        # Create new provider
        logger.info(f"[Factory] 🏭 Creating provider: {provider_type}")
        provider = cls._create_provider(provider_type)
        cls._providers[provider_type] = provider
        
        return provider
    
    @classmethod
    def _create_provider(cls, provider_type: str) -> WhisperProvider:
        """Create a new provider instance"""
        
        config = cls._get_provider_config(provider_type)
        
        if provider_type == ProviderType.BUILTIN.value:
            return BuiltinProvider(config)
        elif provider_type == ProviderType.GROQ.value:
            return GroqProvider(config)
        elif provider_type == ProviderType.OPENAI_WHISPER.value:
            return OpenAIWhisperProvider(config)
        elif provider_type == ProviderType.FASTER_WHISPER.value:
            return FasterWhisperProvider(config)
        elif provider_type == ProviderType.WHISPER_CPP.value:
            return WhisperCppProvider(config)
        elif provider_type == ProviderType.NEMO_TYPHOON.value:
            from .nemo_typhoon_provider import NeMoTyphoonProvider
            return NeMoTyphoonProvider(config)
        else:
            logger.warning(f"[Factory] ⚠️ Unknown provider '{provider_type}', using builtin")
            return BuiltinProvider(config)
    
    @classmethod
    def _get_provider_config(cls, provider_type: str) -> Dict:
        """Get configuration for provider from environment"""
        
        if provider_type == ProviderType.GROQ.value:
            return {
                'api_key': os.getenv('GROQ_API_KEY'),
                'model': os.getenv('GROQ_MODEL', 'whisper-large-v3-turbo'),
                'timeout': int(os.getenv('GROQ_TIMEOUT', '300'))
            }
        elif provider_type == ProviderType.BUILTIN.value:
            return {
                'api_url': os.getenv('WHISPER_API_URL', 'http://whisper:8002'),
                'model': os.getenv('WHISPER_MODEL', 'base'),
                'timeout': int(os.getenv('WHISPER_TIMEOUT', '600'))
            }
        elif provider_type == ProviderType.OPENAI_WHISPER.value:
            return {
                'model': os.getenv('WHISPER_MODEL', 'base'),
                'device': os.getenv('WHISPER_DEVICE', 'auto'),
                'download_root': os.getenv('WHISPER_DOWNLOAD_ROOT', None)
            }
        elif provider_type == ProviderType.FASTER_WHISPER.value:
            return {
                'model': os.getenv('WHISPER_MODEL', 'medium'),
                'device': os.getenv('WHISPER_DEVICE', 'auto'),
                'compute_type': os.getenv('WHISPER_COMPUTE_TYPE', None),
                'batch_size': int(os.getenv('WHISPER_BATCH_SIZE', '16')),
                'download_root': os.getenv('WHISPER_DOWNLOAD_ROOT', None)
            }
        elif provider_type == ProviderType.WHISPER_CPP.value:
            return {
                'whisper_cpp_path': os.getenv('WHISPER_CPP_PATH', None),
                'model_dir': os.getenv('WHISPER_MODEL_DIR', 'models'),
                'model': os.getenv('WHISPER_MODEL', 'base'),
                'use_metal': os.getenv('WHISPER_USE_METAL', None)
            }
        elif provider_type == ProviderType.NEMO_TYPHOON.value:
            return {
                'model': os.getenv('TRANSCRIPTION_TYPHOON_MODEL') or os.getenv('FE_CC_TYPHOON_MODEL', 'typhoon-ai/typhoon-asr-realtime'),
                'device': os.getenv('TRANSCRIPTION_TYPHOON_DEVICE') or os.getenv('FE_CC_TYPHOON_DEVICE', 'auto'),
            }
        return {}
    
    @classmethod
    def get_with_fallback(cls) -> WhisperProvider:
        """
        Get provider with automatic fallback
        
        ลำดับ fallback:
        1. Primary provider (จาก WHISPER_PROVIDER)
        2. Groq (ถ้ามี API key)
        3. Builtin (always available)
        
        Returns:
            WhisperProvider ที่พร้อมใช้งาน
        """
        fallback_enabled = os.getenv('WHISPER_FALLBACK_ENABLED', 'true').lower() == 'true'
        primary_type = os.getenv('WHISPER_PROVIDER', 'builtin').lower()
        
        # Try primary provider first
        try:
            provider = cls.get_provider(primary_type)
            if provider.health_check():
                logger.info(f"[Factory] ✅ Using primary provider: {primary_type}")
                return provider
            else:
                logger.warning(f"[Factory] ⚠️ Primary provider '{primary_type}' health check failed")
        except Exception as e:
            logger.warning(f"[Factory] ⚠️ Primary provider '{primary_type}' error: {e}")
        
        # Try fallback providers
        if fallback_enabled:
            for provider_type in cls._fallback_order:
                if provider_type.value == primary_type:
                    continue  # Skip primary (already tried)
                
                try:
                    provider = cls.get_provider(provider_type.value)
                    if provider.health_check():
                        logger.info(f"[Factory] ✅ Using fallback provider: {provider_type.value}")
                        return provider
                except Exception as e:
                    logger.warning(f"[Factory] ⚠️ Fallback provider '{provider_type.value}' error: {e}")
        
        # Last resort: return builtin anyway (may still work)
        logger.warning("[Factory] ⚠️ All providers failed, returning builtin as last resort")
        return cls.get_provider(ProviderType.BUILTIN.value)
    
    @classmethod
    def get_all_providers_status(cls) -> Dict:
        """
        Get health status of all providers
        สำหรับ monitoring dashboard
        """
        status = {}
        active_provider = os.getenv('WHISPER_PROVIDER', 'builtin')
        
        for provider_type in ProviderType:
            try:
                provider = cls.get_provider(provider_type.value)
                is_healthy = provider.health_check()
                status[provider_type.value] = {
                    'healthy': is_healthy,
                    'active': provider_type.value == active_provider,
                    'info': provider.get_provider_info() if is_healthy else {}
                }
            except Exception as e:
                status[provider_type.value] = {
                    'healthy': False,
                    'active': provider_type.value == active_provider,
                    'error': str(e)
                }
        
        return status
    
    @classmethod
    def switch_provider(cls, provider_type: str) -> WhisperProvider:
        """
        Switch to a different provider at runtime
        (Note: ควรใช้ env var แทนสำหรับ permanent change)
        
        Args:
            provider_type: Provider to switch to
            
        Returns:
            New provider instance
        """
        logger.info(f"[Factory] 🔄 Switching provider to: {provider_type}")
        
        # Validate provider type
        valid_types = [pt.value for pt in ProviderType]
        if provider_type.lower() not in valid_types:
            raise ValueError(f"Invalid provider type: {provider_type}. Valid: {valid_types}")
        
        # Create and return new provider
        provider = cls.get_provider(provider_type.lower())
        
        # Health check
        if not provider.health_check():
            raise Exception(f"Provider '{provider_type}' is not healthy")
        
        return provider
    
    @classmethod
    def clear_cache(cls):
        """Clear provider cache (useful for testing)"""
        cls._providers.clear()
        logger.info("[Factory] 🗑️ Provider cache cleared")


