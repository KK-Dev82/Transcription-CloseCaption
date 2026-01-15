"""
Internal API Endpoint สำหรับ Worker
- dispatcher ส่ง chunk ไป worker
- worker ส่ง WebSocket events กลับผ่าน HTTP callback (แทน Redis)
"""

import logging
import json
from typing import Dict, Any
from datetime import datetime, timezone

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
        
        message_type = message.get("type", "unknown") if isinstance(message, dict) else "unknown"

        logger.info(f"📥 Received ws-event callback: task_id={task_id}, meeting_id={meeting_id}, type={message_type}")
        logger.debug(f"   Message: {json.dumps(message, ensure_ascii=False)[:200]}..." if isinstance(message, dict) else f"   Message: {str(message)[:200]}...")

        if task_id:
            await websocket_manager.broadcast_task_update(str(task_id), message)
            logger.info(f"✅ Broadcasted task update: {task_id}, type={message_type}")
            return {"ok": True, "type": "task_update", "task_id": str(task_id)}

        if meeting_id:
            broadcast_start_time = datetime.now(timezone.utc)
            await websocket_manager.broadcast_to_meeting(str(meeting_id), message)
            broadcast_end_time = datetime.now(timezone.utc)
            broadcast_duration = (broadcast_end_time - broadcast_start_time).total_seconds()
            
            logger.info(f"✅ Broadcasted meeting update: {meeting_id}, type={message_type}, duration={broadcast_duration:.3f}s")
            if isinstance(message, dict) and message.get("type") == "final":
                chunk_index = message.get("chunk_index", -1)
                text_length = len(message.get("text", ""))
                segments_count = len(message.get("segments", []))
                logger.info(f"   ChunkIndex: {chunk_index}, TextLength: {text_length}, Segments: {segments_count}")
            
            return {"ok": True, "type": "meeting_update", "meeting_id": str(meeting_id)}

        logger.warning(f"⚠️  ws-event: missing task_id or meeting_id")
        return {"ok": False, "error": "missing task_id or meeting_id"}

    except Exception as e:
        logger.error(f"❌ Error in ws-event: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}
