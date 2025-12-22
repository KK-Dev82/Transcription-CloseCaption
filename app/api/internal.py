"""
Internal API Endpoint สำหรับ Worker
ใช้สำหรับ dispatcher ส่ง chunk ไป worker
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
from app.services.whisper_service import WhisperService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal", tags=["internal"])

class InternalTranscribeRequest(BaseModel):
    """Request สำหรับ internal transcribe endpoint"""
    audio_path: str
    model_size: str = "base"
    language: str = "th"
    use_thai_processor: bool = False  # ปิดไว้เพราะจะทำ post-process แยก

@router.post("/transcribe")
async def internal_transcribe(request: InternalTranscribeRequest):
    """
    Internal endpoint สำหรับ transcribe chunk
    ใช้โดย dispatcher ส่ง chunk ไป worker
    """
    try:
        whisper_service = WhisperService()
        result = whisper_service.transcribe_file(
            audio_path=request.audio_path,
            model_size=request.model_size,
            language=request.language,
            use_thai_processor=request.use_thai_processor
        )
        
        return {
            "success": True,
            "text": result.get("text", ""),
            "segments": result.get("segments", [])
        }
    except Exception as e:
        logger.error(f"❌ Error in internal transcribe: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
