"""
Real-time Audio Stream API Endpoint
สำหรับรับ continuous audio stream จาก Audio Tap และทำ transcription แบบ real-time
"""

import logging
import uuid
import asyncio
import tempfile
import os
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, UploadFile, File, Header, BackgroundTasks
from pydantic import BaseModel
import aiofiles
from io import BytesIO

from ..services.whisper_service import WhisperService
from ..services.websocket_service import websocket_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcription/realtime", tags=["realtime-transcription"])

# Initialize services
whisper_service = WhisperService()

# Store active audio stream sessions
active_stream_sessions: dict[str, dict] = {}


class AudioStreamResponse(BaseModel):
    """Response model สำหรับ audio stream"""
    session_id: str
    status: str
    message: str
    created_at: str


@router.post("/stream", response_model=AudioStreamResponse)
async def receive_audio_stream(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    x_meeting_id: Optional[str] = Header(None, alias="X-Meeting-Id"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """
    รับ continuous audio stream จาก Audio Tap และทำ transcription แบบ real-time
    
    Args:
        audio: Audio stream (WAV format)
        x_meeting_id: Meeting ID (optional, from header)
        x_session_id: Session ID (optional, from header)
        
    Returns:
        AudioStreamResponse: Session ID และสถานะ
    """
    try:
        # Generate session ID
        session_id = x_session_id or str(uuid.uuid4())
        meeting_id = x_meeting_id or "unknown"
        
        logger.info(
            f"📥 Received audio stream: SessionId={session_id}, MeetingId={meeting_id}, "
            f"ContentType={audio.content_type}, Size={audio.size if hasattr(audio, 'size') else 'unknown'}"
        )
        
        # Read audio data
        audio_data = await audio.read()
        
        if len(audio_data) == 0:
            raise HTTPException(status_code=400, detail="Empty audio stream")
        
        # Save to temporary file
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
            dir=str(temp_dir)
        )
        temp_path = temp_file.name
        temp_file.write(audio_data)
        temp_file.close()
        
        logger.info(f"💾 Saved audio stream to: {temp_path} ({len(audio_data)} bytes)")
        
        # Process transcription in background
        background_tasks.add_task(
            process_audio_stream_transcription,
            session_id=session_id,
            meeting_id=meeting_id,
            audio_path=temp_path,
            audio_size=len(audio_data)
        )
        
        # Store session info
        active_stream_sessions[session_id] = {
            "session_id": session_id,
            "meeting_id": meeting_id,
            "status": "processing",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "audio_size": len(audio_data)
        }
        
        return AudioStreamResponse(
            session_id=session_id,
            status="received",
            message="Audio stream received and processing",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"❌ Error receiving audio stream: {e}")
        raise HTTPException(status_code=500, detail=f"Error receiving audio stream: {str(e)}")


async def process_audio_stream_transcription(
    session_id: str,
    meeting_id: str,
    audio_path: str,
    audio_size: int
):
    """
    ประมวลผล audio stream transcription (background task)
    """
    temp_path = audio_path
    try:
        logger.info(
            f"🔄 Processing audio stream transcription: SessionId={session_id}, "
            f"MeetingId={meeting_id}, AudioPath={audio_path}"
        )
        
        # Transcribe audio
        transcription_result = whisper_service.transcribe_file(
            audio_path=temp_path,
            model_size="base",
            language="th",
            use_thai_processor=True
        )
        
        text = transcription_result.get("text", "")
        segments = transcription_result.get("segments", [])
        
        logger.info(
            f"✅ Transcription completed: SessionId={session_id}, "
            f"TextLength={len(text)}, SegmentsCount={len(segments)}"
        )
        
        # Send caption events via WebSocket
        # Use session_id as user_id for WebSocket
        user_id = f"stream-{session_id}"
        
        # Calculate timing (use current time as reference)
        current_time = datetime.now(timezone.utc).timestamp()
        
        # Send each segment as a caption chunk
        for idx, segment in enumerate(segments):
            chunk_data = {
                "seq": idx,
                "t0": segment.get("start", 0.0),
                "t1": segment.get("end", segment.get("start", 0.0) + 5.0),
                "text": segment.get("text", ""),
                "isFinal": True
            }
            
            message = {
                "type": "caption.chunk",
                "session_id": session_id,
                "chunk_index": idx,
                "chunk_data": chunk_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Send via WebSocket
            await websocket_manager.send_to_user(user_id, message)
            
            logger.debug(
                f"📡 Sent caption chunk: SessionId={session_id}, "
                f"ChunkIndex={idx}, Text={chunk_data['text'][:50]}..."
            )
        
        # Update session status
        if session_id in active_stream_sessions:
            active_stream_sessions[session_id]["status"] = "completed"
            active_stream_sessions[session_id]["transcription_text"] = text
            active_stream_sessions[session_id]["segments_count"] = len(segments)
        
    except Exception as e:
        logger.error(
            f"❌ Error processing audio stream transcription: SessionId={session_id}, Error={e}"
        )
        if session_id in active_stream_sessions:
            active_stream_sessions[session_id]["status"] = "failed"
            active_stream_sessions[session_id]["error"] = str(e)
    finally:
        # Cleanup temporary file
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.debug(f"🗑️ Cleaned up temporary file: {temp_path}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to cleanup temporary file: {e}")


@router.get("/stream/{session_id}/status")
async def get_stream_status(session_id: str):
    """
    ตรวจสอบสถานะ audio stream session
    """
    if session_id not in active_stream_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return active_stream_sessions[session_id]


@router.get("/streams")
async def list_active_streams():
    """
    ดูรายการ active audio stream sessions
    """
    return {
        "sessions": list(active_stream_sessions.values()),
        "count": len(active_stream_sessions)
    }

