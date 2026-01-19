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

# 🧪 Mock mode: ตรวจสอบ environment variable เพื่อ skip transcription
MOCK_MODE = os.getenv("TRANSCRIPTION_MOCK_MODE", "false").lower() == "true"

logger = logging.getLogger(__name__)

if not MOCK_MODE:
    from ..services.whisper_service import WhisperService
    from ..services.websocket_service import websocket_manager
    whisper_service = WhisperService()
else:
    logger.info("🧪 MOCK MODE: Transcription disabled - only testing stream connectivity")
    whisper_service = None
    websocket_manager = None
router = APIRouter(prefix="/transcription/realtime", tags=["realtime-transcription"])

# Store active audio stream sessions
active_stream_sessions: dict[str, dict] = {}

# Store caption event queues per session (สำหรับ yield events กลับไป NDJSON stream)
caption_event_queues: dict[str, asyncio.Queue] = {}

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
    x_audio_format: Optional[str] = Header(None, alias="X-Audio-Format"),
    x_sample_rate: Optional[str] = Header(None, alias="X-Sample-Rate"),
    x_channels: Optional[str] = Header(None, alias="X-Channels"),
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
        x_audio_format: Audio format (s16le, wav, etc.) - optional
        x_sample_rate: Sample rate (16000, etc.) - optional
        x_channels: Number of channels (1, 2, etc.) - optional
        
    Returns:
        StreamingResponse: NDJSON stream with status updates
    """
    # Generate session ID
    session_id = x_session_id or str(uuid.uuid4())
    meeting_id = x_meeting_id or "unknown"
    
    # Log audio format metadata
    audio_format = x_audio_format or "unknown"
    sample_rate = x_sample_rate or "unknown"
    channels = x_channels or "unknown"
    
    # ✅ เพิ่ม log ทันทีเพื่อตรวจสอบว่า request เข้ามาหรือไม่ (ก่อนอ่าน body)
    logger.info(
        f"📥 INGEST: request accepted - SessionId={session_id}, MeetingId={meeting_id}, "
        f"ContentType={request.headers.get('content-type', 'unknown')}, "
        f"AudioFormat={audio_format}, SampleRate={sample_rate}, Channels={channels}"
    )
    
    # Store session info (เก็บ datetime object เพื่อใช้คำนวณ epoch_ms)
    session_start_time = datetime.now(timezone.utc)
    active_stream_sessions[session_id] = {
        "session_id": session_id,
        "meeting_id": meeting_id,
        "status": "streaming",
        "created_at": session_start_time,  # ✅ เก็บ datetime object แทน ISO string
        "created_at_iso": session_start_time.isoformat(),  # สำหรับ JSON serialization
        "audio_size": 0,
        "chunks_processed": 0,
        "audio_format": audio_format,
        "sample_rate": sample_rate,
        "channels": channels
    }
    
    async def stream_generator():
        """Generator สำหรับ StreamingResponse"""
        try:
            # ✅ Send sync event first (สำหรับ sync กับวิดีโอ)
            session_start_time = datetime.now(timezone.utc)
            anchor_epoch_ms = int(session_start_time.timestamp() * 1000)
            
            sync_event = {
                "type": "sync",
                "session_id": session_id,
                "stream_id": meeting_id if meeting_id != "unknown" else session_id,
                "clock": {
                    "kind": "program_date_time",
                    "anchor_epoch_ms": anchor_epoch_ms,
                    "anchor_video_time_s": 0.0
                },
                "hls": {
                    "playlist_url": None,  # จะต้อง set จาก frontend
                    "target_latency_ms": 3500
                },
                "seq": 1,
                "ts": session_start_time.isoformat()
            }
            yield json.dumps(sync_event, ensure_ascii=False) + "\n"
            
            # Yield initial status (NDJSON format)
            initial_response = {
                "type": "status",
                "session_id": session_id,
                "status": "streaming",
                "message": f"Audio stream started, processing chunks in background (MOCK_MODE={MOCK_MODE})",
                "created_at": session_start_time.isoformat(),
                "audio_format": audio_format,
                "sample_rate": sample_rate,
                "channels": channels
            }
            yield json.dumps(initial_response, ensure_ascii=False) + "\n"
            
            # ✅ สร้าง queue สำหรับ caption events (เพื่อ yield กลับไป NDJSON stream)
            event_queue = asyncio.Queue()
            caption_event_queues[session_id] = event_queue
            
            # ✅ เริ่ม background task เพื่อ process streaming audio
            processing_task = asyncio.create_task(
                process_streaming_audio(
                    session_id=session_id,
                    meeting_id=meeting_id,
                    request_body=request.stream(),
                    event_queue=event_queue  # ✅ ส่ง queue ไปให้ process_streaming_audio
                )
            )
            
            try:
                # ✅ อ่าน caption events จาก queue และ yield กลับไป (พร้อม heartbeat)
                while True:
                    try:
                        # รอ event จาก queue (timeout 1 วินาที)
                        event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                        if event is None:  # Sentinel value = stop
                            break
                        yield json.dumps(event, ensure_ascii=False) + "\n"
                    except asyncio.TimeoutError:
                        # Timeout = ไม่มี event ใหม่ - yield heartbeat เพื่อ keep connection alive
                        heartbeat = {
                            "type": "heartbeat",
                            "session_id": session_id,
                            "status": "streaming",
                            "ts": datetime.now(timezone.utc).isoformat()
                        }
                        yield json.dumps(heartbeat, ensure_ascii=False) + "\n"
                        
                        # ตรวจสอบว่า processing task ยังทำงานอยู่หรือไม่
                        if processing_task.done():
                            break
            finally:
                # ✅ Signal stop และรอ processing task จบ
                await event_queue.put(None)  # Sentinel value
                try:
                    await asyncio.wait_for(processing_task, timeout=2.0)
                except asyncio.TimeoutError:
                    processing_task.cancel()
                finally:
                    # Cleanup
                    if session_id in caption_event_queues:
                        del caption_event_queues[session_id]
            
            # Yield final status
            final_status = active_stream_sessions.get(session_id, {})
            final_response = {
                "type": "status",
                "session_id": session_id,
                "status": final_status.get("status", "completed"),
                "message": "Audio stream processing completed",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "audio_size": final_status.get("audio_size", 0),
                "chunks_processed": final_status.get("chunks_processed", 0)
            }
            yield json.dumps(final_response, ensure_ascii=False) + "\n"
            
        except asyncio.CancelledError:
            logger.warning(f"⚠️ Stream generator cancelled: SessionId={session_id}")
            # Update session status
            if session_id in active_stream_sessions:
                active_stream_sessions[session_id]["status"] = "cancelled"
            # Yield cancellation status
            cancel_response = {
                "type": "status",
                "session_id": session_id,
                "status": "cancelled",
                "message": "Audio stream processing cancelled (client disconnected)",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            yield json.dumps(cancel_response, ensure_ascii=False) + "\n"
            raise
        except Exception as e:
            logger.error(f"❌ Error in stream generator: SessionId={session_id}, Error={e}", exc_info=True)
            # Update session status
            if session_id in active_stream_sessions:
                active_stream_sessions[session_id]["status"] = "failed"
                active_stream_sessions[session_id]["error"] = str(e)
            # Yield error status
            error_response = {
                "type": "status",
                "session_id": session_id,
                "status": "failed",
                "message": f"Error processing audio stream: {str(e)}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }
            yield json.dumps(error_response, ensure_ascii=False) + "\n"
    
    # ✅ เพิ่ม headers เพื่อปิด proxy buffering (ลดเวลารอ headers จาก 95s → < 3s)
    # Return StreamingResponse with NDJSON format
    return StreamingResponse(
        stream_generator(),
        media_type="application/x-ndjson",  # NDJSON format
        headers={
            "X-Session-Id": session_id,
            "X-Meeting-Id": meeting_id,
            "Cache-Control": "no-cache",              # ✅ ปิด cache
            "X-Accel-Buffering": "no",               # ✅ ปิด Nginx buffering (สำคัญ!)
            "Connection": "keep-alive"                # ✅ Keep connection alive
        }
    )


async def process_streaming_audio(
    session_id: str,
    meeting_id: str,
    request_body,
    event_queue: Optional[asyncio.Queue] = None  # ✅ Queue สำหรับ caption events
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
            f"MeetingId={meeting_id}, MOCK_MODE={MOCK_MODE}"
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
                        audio_size=audio_data_size,
                        event_queue=event_queue  # ✅ ส่ง queue ไปให้ process_audio_chunk_transcription
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
                audio_size=audio_data_size,
                event_queue=event_queue  # ✅ ส่ง queue ไปให้ process_audio_chunk_transcription
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
        # ✅ Cleanup: Log final state และลบ session จาก active_stream_sessions
        final_state = active_stream_sessions.get(session_id, {})
        duration = datetime.now(timezone.utc) - final_state.get("created_at", datetime.now(timezone.utc))
        logger.info(
            f"🏁 Real-time stream ended: SessionId={session_id}, "
            f"Status={final_state.get('status', 'unknown')}, "
            f"TotalBytes={total_bytes}, ChunksProcessed={chunk_index}, "
            f"Duration={duration}"
        )
        
        # ✅ ลบ session จาก active_stream_sessions เพื่อป้องกัน memory leak
        if session_id in active_stream_sessions:
            del active_stream_sessions[session_id]
        
        # ✅ ลบ queue จาก caption_event_queues (ถ้ายังมีอยู่)
        if session_id in caption_event_queues:
            del caption_event_queues[session_id]


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
    audio_size: int,
    event_queue: Optional[asyncio.Queue] = None  # ✅ Queue สำหรับ caption events
):
    """
    ประมวลผล transcription สำหรับ audio chunk หนึ่ง
    🧪 ใน MOCK_MODE: จะ skip transcription และส่ง mock caption events
    """
    temp_path = audio_path
    try:
        logger.info(
            f"🔄 Processing audio chunk transcription: SessionId={session_id}, "
            f"ChunkIndex={chunk_index}, AudioPath={audio_path}, MOCK_MODE={MOCK_MODE}"
        )
        
        if MOCK_MODE:
            # 🧪 Mock mode: ส่ง mock caption events โดยไม่ทำ transcription
            logger.info(
                f"🧪 MOCK MODE: Skipping transcription, sending mock caption events"
            )
            
            # Mock transcription result
            text = f"[Mock transcription for chunk {chunk_index}]"
            segments = [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": text,
                    "confidence": 0.95
                }
            ]
        else:
            # Real transcription
            if whisper_service is None:
                raise RuntimeError("WhisperService not initialized")
            
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
        
        # Send caption events via WebSocket (ถ้าไม่ใช่ MOCK_MODE)
        # ✅ IMPORTANT: /api/ws/captions ใช้ meeting_id เป็น user_id โดยตรง
        # ห้าม prefix เป็น user-{meeting_id} ไม่งั้นผู้ชมจะไม่รับ event
        if not MOCK_MODE and websocket_manager is not None:
            if meeting_id and meeting_id != "unknown":
                user_id = meeting_id
            else:
                user_id = session_id
            
            # ✅ Calculate timing using epoch_ms (milliseconds since epoch)
            # ใช้ session start time + chunk offset
            session_info = active_stream_sessions.get(session_id, {})
            session_start_time = session_info.get("created_at")
            if session_start_time:
                # ใช้ datetime object โดยตรง (ไม่ต้อง parse)
                try:
                    if isinstance(session_start_time, datetime):
                        base_epoch_ms = int(session_start_time.timestamp() * 1000)
                    elif isinstance(session_start_time, str):
                        session_dt = datetime.fromisoformat(session_start_time.replace('Z', '+00:00'))
                        base_epoch_ms = int(session_dt.timestamp() * 1000)
                    else:
                        raise ValueError(f"Unexpected type for created_at: {type(session_start_time)}")
                except Exception as e:
                    logger.warning(f"Failed to parse session start time: {e}, using current time")
                    base_epoch_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            else:
                base_epoch_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Calculate chunk start time in seconds (from session start)
            chunk_start_seconds = chunk_index * 5.0  # 5 seconds per chunk
            
            # Send each segment as a caption event (ตาม format ที่แนะนำ)
            for idx, segment in enumerate(segments):
                segment_start_s = chunk_start_seconds + segment.get("start", 0.0)
                segment_end_s = chunk_start_seconds + segment.get("end", segment.get("start", 0.0) + 5.0)
                
                # Convert to epoch_ms
                start_epoch_ms = base_epoch_ms + int(segment_start_s * 1000)
                end_epoch_ms = base_epoch_ms + int(segment_end_s * 1000)
                
                # ✅ Create caption event ตาม format ที่แนะนำ
                caption_event = {
                    "type": "caption",
                    "session_id": session_id,
                    "stream_id": meeting_id if meeting_id != "unknown" else session_id,
                    "seq": chunk_index * 100 + idx,  # Unique sequence number
                    "timing": {
                        "kind": "epoch_ms",
                        "start": start_epoch_ms,
                        "end": end_epoch_ms
                    },
                    "text": segment.get("text", ""),
                    "lang": "th",
                    "is_final": True,
                    "tokens": [],  # Optional: จะเพิ่ม tokens ถ้าต้องการ
                    "meta": {
                        "speaker": None,
                        "confidence": segment.get("confidence", 0.0) if isinstance(segment.get("confidence"), (int, float)) else 0.0,
                        "model": "faster-whisper" if not MOCK_MODE else "mock",
                        "chunk_id": f"c_{chunk_index:04d}_{idx:02d}"
                    },
                    "ts": datetime.now(timezone.utc).isoformat()
                }
                
                # ✅ Send via WebSocket (ถ้าไม่ใช่ MOCK_MODE)
                if not MOCK_MODE and websocket_manager is not None:
                    await websocket_manager.send_to_user(user_id, caption_event)
                
                # ✅ Put caption event ลง queue เพื่อ yield กลับไป NDJSON stream
                if event_queue is not None:
                    try:
                        await event_queue.put(caption_event)
                        logger.debug(
                            f"📡 Queued caption event: SessionId={session_id}, "
                            f"ChunkIndex={chunk_index}, SegmentIndex={idx}, "
                            f"Start={start_epoch_ms}ms, End={end_epoch_ms}ms, "
                            f"Text={caption_event['text'][:50]}..."
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to queue caption event: {e}")
                else:
                    logger.debug(
                        f"📡 Caption event (no queue): SessionId={session_id}, "
                        f"ChunkIndex={chunk_index}, SegmentIndex={idx}, "
                        f"Start={start_epoch_ms}ms, End={end_epoch_ms}ms, "
                        f"Text={caption_event['text'][:50]}..."
                    )
        else:
            # MOCK_MODE: ส่ง mock caption event ผ่าน queue
            if event_queue is not None:
                # ✅ สร้าง mock caption event
                chunk_start_seconds = chunk_index * 5.0
                base_epoch_ms = int(active_stream_sessions.get(session_id, {}).get("created_at", datetime.now(timezone.utc)).timestamp() * 1000)
                start_epoch_ms = base_epoch_ms + int(chunk_start_seconds * 1000)
                end_epoch_ms = base_epoch_ms + int((chunk_start_seconds + 5.0) * 1000)
                
                mock_caption_event = {
                    "type": "caption",
                    "session_id": session_id,
                    "stream_id": meeting_id if meeting_id != "unknown" else session_id,
                    "seq": chunk_index * 100,
                    "timing": {
                        "kind": "epoch_ms",
                        "start": start_epoch_ms,
                        "end": end_epoch_ms
                    },
                    "text": text,
                    "lang": "th",
                    "is_final": True,
                    "tokens": [],
                    "meta": {
                        "speaker": None,
                        "confidence": 0.95,
                        "model": "mock",
                        "chunk_id": f"c_{chunk_index:04d}_00"
                    },
                    "ts": datetime.now(timezone.utc).isoformat()
                }
                
                try:
                    await event_queue.put(mock_caption_event)
                    logger.info(
                        f"🧪 MOCK MODE: Queued mock caption event: SessionId={session_id}, "
                        f"ChunkIndex={chunk_index}, Text={text[:50]}..."
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Failed to queue mock caption event: {e}")
            else:
                logger.info(
                    f"🧪 MOCK MODE: Would send caption event: SessionId={session_id}, "
                    f"ChunkIndex={chunk_index}, Text={text[:50]}..."
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
