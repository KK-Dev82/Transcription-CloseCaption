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
from fastapi import APIRouter, HTTPException, Request, Header, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import aiofiles
import json
from io import BytesIO

from ..services.whisper_service import WhisperService
from ..services.websocket_service import websocket_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcription/realtime", tags=["realtime-transcription"])

# Initialize services
whisper_service = WhisperService()

# Store active audio stream sessions
active_stream_sessions: dict[str, dict] = {}

# Chunk size for processing (5 seconds of audio at 16kHz mono PCM16)
# PCM16: 16kHz * 2 bytes * 5 seconds = 160,000 bytes (raw audio data)
# WAV header: 44 bytes
# สำหรับ WAV streaming: ต้องคำนวณเฉพาะ audio data (ไม่รวม header)
CHUNK_SIZE_AUDIO_DATA = 160000  # ~5 seconds of raw PCM16 audio data (ไม่รวม WAV header)


class AudioStreamResponse(BaseModel):
    """Response model สำหรับ audio stream"""
    session_id: str
    status: str
    message: str
    created_at: str


@router.post("/stream")
async def receive_audio_stream(
    request: Request,
    x_meeting_id: Optional[str] = Header(None, alias="X-Meeting-Id"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """
    รับ continuous audio stream จาก Audio Tap และทำ transcription แบบ real-time
    รองรับ streaming (chunked encoding) โดยอ่าน chunk by chunk
    
    ✅ ใช้ StreamingResponse (NDJSON) เพื่อให้ connection ยังเปิดอยู่
    และสามารถอ่าน request body ได้ตลอดเวลา
    
    Args:
        request: FastAPI Request object (สำหรับอ่าน stream)
        x_meeting_id: Meeting ID (optional, from header)
        x_session_id: Session ID (optional, from header)
        
    Returns:
        StreamingResponse: NDJSON stream with status updates
    """
    # Generate session ID
    session_id = x_session_id or str(uuid.uuid4())
    meeting_id = x_meeting_id or "unknown"
    
    logger.info(
        f"📥 Received audio stream request: SessionId={session_id}, MeetingId={meeting_id}, "
        f"ContentType={request.headers.get('content-type', 'unknown')}"
    )
    
    # Store session info
    active_stream_sessions[session_id] = {
        "session_id": session_id,
        "meeting_id": meeting_id,
        "status": "streaming",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "audio_size": 0,
        "chunks_processed": 0
    }
    
    async def stream_generator():
        """Generator สำหรับ StreamingResponse"""
        try:
            # Yield initial status (NDJSON format)
            initial_response = {
                "session_id": session_id,
                "status": "streaming",
                "message": "Audio stream started, processing chunks in background",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            yield json.dumps(initial_response) + "\n"
            
            # Process streaming audio (consume request body)
            # ⚠️ สำคัญ: อ่าน stream ใน generator เพื่อให้ connection ยังเปิดอยู่
            await process_streaming_audio(
                session_id=session_id,
                meeting_id=meeting_id,
                request_body=request.stream()
            )
            
            # Yield final status
            final_status = active_stream_sessions.get(session_id, {})
            final_response = {
                "session_id": session_id,
                "status": final_status.get("status", "completed"),
                "message": "Audio stream processing completed",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "audio_size": final_status.get("audio_size", 0),
                "chunks_processed": final_status.get("chunks_processed", 0)
            }
            yield json.dumps(final_response) + "\n"
            
        except asyncio.CancelledError:
            logger.warning(f"⚠️ Stream generator cancelled: SessionId={session_id}")
            # Update session status
            if session_id in active_stream_sessions:
                active_stream_sessions[session_id]["status"] = "cancelled"
            # Yield cancellation status
            cancel_response = {
                "session_id": session_id,
                "status": "cancelled",
                "message": "Audio stream processing cancelled (client disconnected)",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            yield json.dumps(cancel_response) + "\n"
            raise
        except Exception as e:
            logger.error(f"❌ Error in stream generator: SessionId={session_id}, Error={e}", exc_info=True)
            # Update session status
            if session_id in active_stream_sessions:
                active_stream_sessions[session_id]["status"] = "failed"
                active_stream_sessions[session_id]["error"] = str(e)
            # Yield error status
            error_response = {
                "session_id": session_id,
                "status": "failed",
                "message": f"Error processing audio stream: {str(e)}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }
            yield json.dumps(error_response) + "\n"
    
    # Return StreamingResponse with NDJSON format
    return StreamingResponse(
        stream_generator(),
        media_type="application/x-ndjson",  # NDJSON format
        headers={
            "X-Session-Id": session_id,
            "X-Meeting-Id": meeting_id
        }
    )


async def process_streaming_audio(
    session_id: str,
    meeting_id: str,
    request_body
):
    """
    อ่าน audio stream chunk by chunk และประมวลผล transcription ทีละ chunk
    
    ✅ ฟังก์ชันนี้ถูกเรียกจาก stream_generator() ใน StreamingResponse
    เพื่อให้แน่ใจว่า connection ยังเปิดอยู่และสามารถอ่าน stream ได้
    
    Args:
        session_id: Session ID
        meeting_id: Meeting ID
        request_body: Request stream iterator
    """
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)
    
    chunk_index = 0
    audio_buffer = BytesIO()  # Buffer สำหรับ audio data เท่านั้น (ไม่รวม header)
    total_bytes = 0
    wav_header = None
    header_received = False
    
    try:
        logger.info(
            f"🔄 Starting streaming audio processing: SessionId={session_id}, "
            f"MeetingId={meeting_id}"
        )
        
        # อ่าน stream chunk by chunk
        async for chunk in request_body:
            if not chunk:
                break
            
            # ตรวจสอบ WAV header (44 bytes) ใน chunk แรก
            if not header_received:
                if len(chunk) >= 44:
                    # ตรวจสอบว่าเป็น WAV file หรือไม่
                    if chunk[:4] == b'RIFF' and chunk[8:12] == b'WAVE':
                        wav_header = bytes(chunk[:44])
                        header_received = True
                        logger.info(f"📋 Detected WAV header: SessionId={session_id}")
                        
                        # เขียน audio data ที่เหลือ (ถ้ามี) ลง buffer
                        if len(chunk) > 44:
                            audio_data = chunk[44:]
                            audio_buffer.write(audio_data)
                            total_bytes += len(audio_data)
                    else:
                        # ไม่ใช่ WAV - สร้าง header ใหม่ (assume PCM16 16kHz mono)
                        header_received = True
                        logger.info(f"📋 No WAV header detected, will create new header: SessionId={session_id}")
                        audio_buffer.write(chunk)
                        total_bytes += len(chunk)
                else:
                    # Chunk แรกยังไม่ครบ 44 bytes - เก็บไว้รอ chunk ถัดไป
                    continue
            else:
                # Header รับแล้ว - เขียน audio data ลง buffer
                audio_buffer.write(chunk)
                total_bytes += len(chunk)
            
            # เมื่อ buffer มี audio data ครบ 5 วินาที (~160KB) ให้ประมวลผล transcription
            audio_data_size = audio_buffer.tell()
            
            if audio_data_size >= CHUNK_SIZE_AUDIO_DATA:
                # สร้าง temporary WAV file สำหรับ chunk นี้
                temp_file = tempfile.NamedTemporaryFile(
                    suffix=".wav",
                    delete=False,
                    dir=str(temp_dir)
                )
                temp_path = temp_file.name
                
                # เขียน WAV header
                if wav_header:
                    # ใช้ header เดิม แต่ update file size
                    file_size = 44 + audio_data_size
                    updated_header = bytearray(wav_header)
                    updated_header[4:8] = (file_size - 8).to_bytes(4, 'little')
                    updated_header[40:44] = audio_data_size.to_bytes(4, 'little')
                    temp_file.write(updated_header)
                else:
                    # สร้าง WAV header ใหม่สำหรับ PCM16 16kHz mono
                    new_header = create_wav_header(audio_data_size)
                    temp_file.write(new_header)
                
                # เขียน audio data
                audio_buffer.seek(0)
                audio_data = audio_buffer.read()
                temp_file.write(audio_data)
                temp_file.close()
                
                logger.info(
                    f"💾 Saved audio chunk {chunk_index}: {temp_path} "
                    f"({audio_data_size} bytes audio data)"
                )
                
                # ประมวลผล transcription สำหรับ chunk นี้ (ใน background)
                asyncio.create_task(
                    process_audio_chunk_transcription(
                        session_id=session_id,
                        meeting_id=meeting_id,
                        audio_path=temp_path,
                        chunk_index=chunk_index,
                        audio_size=audio_data_size
                    )
                )
                
                # Reset buffer สำหรับ chunk ถัดไป
                audio_buffer = BytesIO()
                chunk_index += 1
                
                # Update session info
                if session_id in active_stream_sessions:
                    active_stream_sessions[session_id]["chunks_processed"] = chunk_index
                    active_stream_sessions[session_id]["audio_size"] = total_bytes
        
        # ประมวลผล buffer ที่เหลือ (ถ้ามี)
        audio_data_size = audio_buffer.tell()
        if audio_data_size > 0:
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
                dir=str(temp_dir)
            )
            temp_path = temp_file.name
            
            # เขียน WAV header
            if wav_header:
                file_size = 44 + audio_data_size
                updated_header = bytearray(wav_header)
                updated_header[4:8] = (file_size - 8).to_bytes(4, 'little')
                updated_header[40:44] = audio_data_size.to_bytes(4, 'little')
                temp_file.write(updated_header)
            else:
                new_header = create_wav_header(audio_data_size)
                temp_file.write(new_header)
            
            # เขียน audio data
            audio_buffer.seek(0)
            audio_data = audio_buffer.read()
            temp_file.write(audio_data)
            temp_file.close()
            
            logger.info(
                f"💾 Saved final audio chunk {chunk_index}: {temp_path} "
                f"({audio_data_size} bytes audio data)"
            )
            
            # ประมวลผล transcription สำหรับ chunk สุดท้าย
            await process_audio_chunk_transcription(
                session_id=session_id,
                meeting_id=meeting_id,
                audio_path=temp_path,
                chunk_index=chunk_index,
                audio_size=audio_data_size
            )
            
            chunk_index += 1
        
        # Update session status
        if session_id in active_stream_sessions:
            active_stream_sessions[session_id]["status"] = "completed"
            active_stream_sessions[session_id]["chunks_processed"] = chunk_index
        
        logger.info(
            f"✅ Streaming audio processing completed: SessionId={session_id}, "
            f"TotalChunks={chunk_index}, TotalBytes={total_bytes}"
        )
        
        # Log final status for debugging
        if total_bytes == 0:
            logger.warning(
                f"⚠️ Warning: No audio data received for SessionId={session_id}"
            )
        else:
            logger.info(
                f"📊 Final stats: SessionId={session_id}, "
                f"TotalBytes={total_bytes}, ChunksProcessed={chunk_index}"
            )
        
    except asyncio.CancelledError:
        logger.warning(
            f"⚠️ Streaming audio processing cancelled (client disconnected): "
            f"SessionId={session_id}, TotalBytes={total_bytes}, ChunksProcessed={chunk_index}"
        )
        if session_id in active_stream_sessions:
            active_stream_sessions[session_id]["status"] = "cancelled"
        raise
    except Exception as e:
        logger.error(
            f"❌ Error processing streaming audio: SessionId={session_id}, "
            f"TotalBytes={total_bytes}, ChunksProcessed={chunk_index}, Error={e}",
            exc_info=True
        )
        if session_id in active_stream_sessions:
            active_stream_sessions[session_id]["status"] = "failed"
            active_stream_sessions[session_id]["error"] = str(e)
        raise
    finally:
        # Cleanup: Log final state
        final_state = active_stream_sessions.get(session_id, {})
        logger.info(
            f"🏁 Real-time stream ended: SessionId={session_id}, "
            f"Status={final_state.get('status', 'unknown')}, "
            f"TotalBytes={total_bytes}, ChunksProcessed={chunk_index}"
        )


def create_wav_header(data_size: int) -> bytes:
    """
    สร้าง WAV header สำหรับ 16kHz mono PCM
    """
    sample_rate = 16000
    channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    
    # WAV header structure
    header = b'RIFF'
    header += (36 + data_size).to_bytes(4, 'little')  # File size - 8
    header += b'WAVE'
    header += b'fmt '
    header += (16).to_bytes(4, 'little')  # fmt chunk size
    header += (1).to_bytes(2, 'little')  # Audio format (PCM)
    header += channels.to_bytes(2, 'little')
    header += sample_rate.to_bytes(4, 'little')
    header += byte_rate.to_bytes(4, 'little')
    header += block_align.to_bytes(2, 'little')
    header += bits_per_sample.to_bytes(2, 'little')
    header += b'data'
    header += data_size.to_bytes(4, 'little')
    
    return header


async def process_audio_chunk_transcription(
    session_id: str,
    meeting_id: str,
    audio_path: str,
    chunk_index: int,
    audio_size: int
):
    """
    ประมวลผล transcription สำหรับ audio chunk หนึ่ง
    """
    temp_path = audio_path
    try:
        logger.info(
            f"🔄 Processing audio chunk transcription: SessionId={session_id}, "
            f"ChunkIndex={chunk_index}, AudioPath={audio_path}"
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
            f"✅ Transcription completed for chunk {chunk_index}: SessionId={session_id}, "
            f"TextLength={len(text)}, SegmentsCount={len(segments)}"
        )
        
        # Send caption events via WebSocket
        if meeting_id and meeting_id != "unknown":
            user_id = f"user-{meeting_id}"
        else:
            user_id = f"stream-{session_id}"
        
        # Calculate timing (use chunk index as base time)
        base_time = chunk_index * 5.0  # 5 seconds per chunk
        
        # Send each segment as a caption chunk
        for idx, segment in enumerate(segments):
            chunk_data = {
                "seq": chunk_index * 100 + idx,  # Unique sequence number
                "t0": base_time + segment.get("start", 0.0),
                "t1": base_time + segment.get("end", segment.get("start", 0.0) + 5.0),
                "text": segment.get("text", ""),
                "isFinal": True
            }
            
            message = {
                "type": "caption.chunk",
                "session_id": session_id,
                "chunk_index": chunk_index,
                "segment_index": idx,
                "chunk_data": chunk_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Send via WebSocket
            await websocket_manager.send_to_user(user_id, message)
            
            logger.debug(
                f"📡 Sent caption chunk: SessionId={session_id}, "
                f"ChunkIndex={chunk_index}, SegmentIndex={idx}, Text={chunk_data['text'][:50]}..."
            )
        
    except Exception as e:
        logger.error(
            f"❌ Error processing audio chunk transcription: SessionId={session_id}, "
            f"ChunkIndex={chunk_index}, Error={e}"
        )
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

