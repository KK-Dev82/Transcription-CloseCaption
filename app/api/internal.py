"""
Internal API Endpoint สำหรับ Worker
- dispatcher ส่ง chunk ไป worker
- worker ส่ง WebSocket events กลับผ่าน HTTP callback (แทน Redis)
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.whisper_service import WhisperService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/internal", tags=["internal"])


class InternalTranscribeRequest(BaseModel):
    audio_path: str
    model_size: str = "base"
    language: str = "th"
    use_thai_processor: bool = False


@router.post("/transcribe")
async def internal_transcribe(request: InternalTranscribeRequest):
    try:
        whisper_service = WhisperService()
        result = whisper_service.transcribe_file(
            audio_path=request.audio_path,
            model_size=request.model_size,
            language=request.language,
            use_thai_processor=request.use_thai_processor,
        )
        return {
            "success": True,
            "text": result.get("text", ""),
            "segments": result.get("segments", []),
        }
    except Exception as e:
        logger.error(f"❌ Error in internal transcribe: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ws-event")
async def ws_event(payload: Dict[str, Any]):
    """
    Worker -> Main API callback
    payload:
      - task_id OR meeting_id
      - message (optional)
    """
    try:
        from app.services.websocket_service import websocket_manager

        task_id = payload.get("task_id")
        meeting_id = payload.get("meeting_id")
        message = payload.get("message", payload)

        if task_id:
            await websocket_manager.broadcast_task_update(str(task_id), message)
            return {"ok": True, "type": "task_update", "task_id": str(task_id)}

        if meeting_id:
            await websocket_manager.broadcast_to_meeting(str(meeting_id), message)
            return {"ok": True, "type": "meeting_update", "meeting_id": str(meeting_id)}

        return {"ok": False, "error": "missing task_id or meeting_id"}

    except Exception as e:
        logger.error(f"❌ Error in ws-event: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}
