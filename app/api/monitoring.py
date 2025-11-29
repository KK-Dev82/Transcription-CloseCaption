"""
Monitoring API สำหรับตรวจสอบสถานะ Whisper Providers
"""

import os
import logging
from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Dict, Any

from ..services.whisper_providers import WhisperProviderFactory, ProviderType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/providers/status")
async def get_providers_status() -> Dict[str, Any]:
    """
    📊 ตรวจสอบสถานะของทุก Whisper providers
    
    Returns:
        Dict: สถานะของแต่ละ provider
    """
    try:
        active_provider = os.getenv('WHISPER_PROVIDER', 'builtin')
        status = WhisperProviderFactory.get_all_providers_status()
        
        return {
            "active_provider": active_provider,
            "fallback_enabled": os.getenv('WHISPER_FALLBACK_ENABLED', 'true').lower() == 'true',
            "providers": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting providers status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers/active")
async def get_active_provider() -> Dict[str, Any]:
    """
    🎯 ดูข้อมูล provider ที่ใช้งานอยู่
    
    Returns:
        Dict: ข้อมูลของ active provider
    """
    try:
        provider = WhisperProviderFactory.get_with_fallback()
        
        return {
            "provider": provider.provider_name,
            "healthy": provider.health_check(),
            "info": provider.get_provider_info(),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting active provider: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers/{provider_name}")
async def get_provider_info(provider_name: str) -> Dict[str, Any]:
    """
    📋 ดูข้อมูลของ provider เฉพาะ
    
    Args:
        provider_name: ชื่อ provider (builtin, groq)
        
    Returns:
        Dict: ข้อมูลของ provider
    """
    try:
        # Validate provider name
        valid_providers = [pt.value for pt in ProviderType]
        if provider_name.lower() not in valid_providers:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid provider: {provider_name}. Valid: {valid_providers}"
            )
        
        provider = WhisperProviderFactory.get_provider(provider_name.lower())
        is_healthy = provider.health_check()
        
        return {
            "provider": provider.provider_name,
            "healthy": is_healthy,
            "info": provider.get_provider_info(),
            "is_active": os.getenv('WHISPER_PROVIDER', 'builtin').lower() == provider_name.lower(),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting provider info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/providers/switch/{provider_name}")
async def switch_provider(provider_name: str) -> Dict[str, Any]:
    """
    🔄 สลับไปใช้ provider อื่น (runtime only, ไม่ persistent)
    
    Args:
        provider_name: ชื่อ provider ที่ต้องการสลับไป
        
    Returns:
        Dict: ผลลัพธ์การสลับ
        
    Note:
        การสลับนี้ใช้ได้ชั่วคราว จะถูก reset เมื่อ restart service
        ควรใช้ environment variable WHISPER_PROVIDER สำหรับ permanent change
    """
    try:
        # Validate provider name
        valid_providers = [pt.value for pt in ProviderType]
        if provider_name.lower() not in valid_providers:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid provider: {provider_name}. Valid: {valid_providers}"
            )
        
        # Try to switch
        new_provider = WhisperProviderFactory.switch_provider(provider_name.lower())
        
        return {
            "success": True,
            "previous_provider": os.getenv('WHISPER_PROVIDER', 'builtin'),
            "new_provider": new_provider.provider_name,
            "healthy": new_provider.health_check(),
            "warning": "This change is temporary and will reset on service restart. "
                      "Set WHISPER_PROVIDER environment variable for permanent change.",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error switching provider: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_config() -> Dict[str, Any]:
    """
    ⚙️ ดู configuration ปัจจุบัน
    
    Returns:
        Dict: Configuration values (ไม่รวม secrets)
    """
    return {
        "whisper_provider": os.getenv('WHISPER_PROVIDER', 'builtin'),
        "whisper_model": os.getenv('WHISPER_MODEL', 'base'),
        "whisper_api_url": os.getenv('WHISPER_API_URL', 'http://whisper:8002'),
        "whisper_timeout": int(os.getenv('WHISPER_TIMEOUT', '600')),
        "groq_model": os.getenv('GROQ_MODEL', 'whisper-large-v3-turbo'),
        "groq_timeout": int(os.getenv('GROQ_TIMEOUT', '300')),
        "groq_api_key_configured": bool(os.getenv('GROQ_API_KEY')),
        "fallback_enabled": os.getenv('WHISPER_FALLBACK_ENABLED', 'true').lower() == 'true',
        "timestamp": datetime.now().isoformat()
    }


