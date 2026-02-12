"""
Real-time Transcription API Endpoint
สำหรับการประมวลผล audio chunks แบบ real-time (ทุก 5 วินาที)
รองรับการส่ง audio_url และ callback_url สำหรับ webhook
รองรับ CloseCaption Profile: TH-CC-RT v1 (Small + Overlap + Dedupe + Postprocess)
"""

import logging
import uuid
import asyncio
import tempfile
import os
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Header, Query
from pydantic import BaseModel
import aiohttp
import aiofiles

# 🧪 Mock mode: ตรวจสอบ environment variable เพื่อ skip transcription
MOCK_MODE = os.getenv("TRANSCRIPTION_MOCK_MODE", "false").lower() == "true"

# CloseCaption Configuration
from ..services.close_caption_config import CloseCaptionConfig, get_default_whisper_model_display
from ..utils.overlap_buffer import OverlapBuffer
from ..utils.dedupe_text import dedupe_text, dedupe_segments
from ..utils.thai_postprocess import postprocess_thai_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcription/realtime", tags=["realtime-transcription"])

# Initialize services
if not MOCK_MODE:
    from ..services.whisper_service import WhisperService
    from ..services.file_service import FileService
    whisper_service = WhisperService()
    file_service = FileService()
else:
    logger.info("🧪 MOCK MODE: Transcription disabled - only testing chunk connectivity")
    whisper_service = None
    file_service = None

# Overlap buffers per meeting (เก็บ tail audio สำหรับ overlap)
_overlap_buffers: Dict[str, OverlapBuffer] = {}

# Last emitted text per meeting (สำหรับ dedupe)
_last_emitted_text: Dict[str, str] = {}


@router.get("/config")
async def get_transcription_config():
    """
    คืนค่า config การแปลง (โมเดลที่ backend ใช้จริงจาก env)
    ให้ frontend เรียกเพื่อแสดงและบันทึกชื่อโมเดลได้ถูกต้อง
    """
    return {"whisper_model": get_default_whisper_model_display()}


class RealtimeChunkRequest(BaseModel):
    """Request model สำหรับ real-time transcription chunk (audio_url-based)"""
    audio_url: str  # Public URL ของ audio file
    callback_url: str  # Webhook callback URL
    chunk_index: Optional[int] = 0
    start_time: Optional[float] = 0.0
    duration: Optional[float] = 5.0
    language: str = "th"
    model_size: str = "Vinxscribe/biodatlab-whisper-th-medium-faster"


class LiveChunkRequest(BaseModel):
    """Request model สำหรับ live audio chunk (raw PCM/WAV จาก body)"""
    chunk_index: Optional[int] = 0
    start_time: Optional[float] = 0.0
    duration: Optional[float] = 3.0
    language: str = "th"
    model_size: str = "Vinxscribe/biodatlab-whisper-th-medium-faster"
    session_id: Optional[str] = None
    meeting_id: Optional[str] = None


class RealtimeChunkResponse(BaseModel):
    """Response model สำหรับ real-time transcription chunk"""
    task_id: str
    status: str
    chunk_index: int
    created_at: str


async def download_audio_file(audio_url: str) -> str:
    """
    Download audio file จาก URL และบันทึกเป็น temporary file
    
    Args:
        audio_url: URL ของ audio file
        
    Returns:
        str: Path ไปยังไฟล์ที่ download แล้ว
    """
    try:
        logger.info(f"📥 Downloading audio from URL: {audio_url}")
        
        # Create temporary file
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
            dir=str(temp_dir)
        )
        temp_path = temp_file.name
        temp_file.close()
        
        # Download file
        async with aiohttp.ClientSession() as session:
            async with session.get(audio_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"ไม่สามารถดาวน์โหลดไฟล์จาก URL ได้ (Status: {response.status})"
                    )
                
                # Read content and save
                content = await response.read()
                async with aiofiles.open(temp_path, 'wb') as f:
                    await f.write(content)
        
        logger.info(f"✅ Audio downloaded: {temp_path} ({len(content)} bytes)")
        return temp_path
        
    except aiohttp.ClientError as e:
        logger.error(f"❌ Error downloading audio: {e}")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(
            status_code=500,
            detail=f"ไม่สามารถดาวน์โหลดไฟล์จาก URL ได้: {str(e)}"
        )
    except Exception as e:
        logger.error(f"❌ Unexpected error downloading audio: {e}")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดาวน์โหลดไฟล์: {str(e)}"
        )


async def send_webhook_callback(
    callback_url: str,
    task_id: str,
    chunk_index: int,
    start_time: float,
    duration: float,
    transcription_result: dict,
    language: str,
    model_size: str
):
    """
    ส่ง webhook callback ไปยัง callback_url
    
    Args:
        callback_url: URL สำหรับ webhook callback
        task_id: Task ID
        chunk_index: Index ของ chunk
        start_time: เวลาเริ่มต้น (วินาที)
        duration: ระยะเวลา (วินาที)
        transcription_result: ผลลัพธ์ transcription
        language: ภาษา
        model_size: ขนาด model
    """
    try:
        payload = {
            "task_id": task_id,
            "chunk_index": chunk_index,
            "start_time": start_time,
            "duration": duration,
            "text": transcription_result.get("text", ""),
            "segments": transcription_result.get("segments", []),
            "language": language,
            "model_size": model_size,
            "confidence": transcription_result.get("confidence", 0.0)
        }
        
        logger.info(f"📤 Sending webhook callback to: {callback_url}")
        logger.info(f"   Task ID: {task_id}, Chunk: {chunk_index}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                callback_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ Webhook callback sent successfully")
                else:
                    logger.warning(f"⚠️ Webhook callback returned status {response.status}")
                    
    except Exception as e:
        logger.error(f"❌ Error sending webhook callback: {e}")
        # Don't raise exception - just log error (webhook failure shouldn't fail the request)


async def process_realtime_chunk(
    task_id: str,
    audio_url: str,
    callback_url: str,
    chunk_index: int,
    start_time: float,
    duration: float,
    language: str,
    model_size: str
):
    """
    ประมวลผล real-time transcription chunk (background task)
    
    Args:
        task_id: Task ID
        audio_url: URL ของ audio file
        callback_url: Webhook callback URL
        chunk_index: Index ของ chunk
        start_time: เวลาเริ่มต้น
        duration: ระยะเวลา
        language: ภาษา
        model_size: ขนาด model
    """
    temp_path = None
    try:
        logger.info(f"🔄 Processing real-time chunk: task_id={task_id}, chunk_index={chunk_index}")
        
        # Download audio file
        temp_path = await download_audio_file(audio_url)
        
        # Transcribe audio
        logger.info(f"📝 Transcribing audio: {temp_path}")
        transcription_result = whisper_service.transcribe_file(
            audio_path=temp_path,
            model_size=model_size,
            language=language,
            use_thai_processor=(language == "th")
        )
        
        logger.info(f"✅ Transcription completed: {len(transcription_result.get('text', ''))} characters")
        
        # Send webhook callback
        await send_webhook_callback(
            callback_url=callback_url,
            task_id=task_id,
            chunk_index=chunk_index,
            start_time=start_time,
            duration=duration,
            transcription_result=transcription_result,
            language=language,
            model_size=model_size
        )
        
    except Exception as e:
        logger.error(f"❌ Error processing real-time chunk {task_id}: {e}", exc_info=True)
        # Send error webhook callback
        try:
            error_payload = {
                "task_id": task_id,
                "chunk_index": chunk_index,
                "status": "error",
                "error": str(e)
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    callback_url,
                    json=error_payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    logger.info(f"Error webhook sent: {response.status}")
        except Exception as webhook_error:
            logger.error(f"Failed to send error webhook: {webhook_error}")
    finally:
        # Cleanup temporary file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                logger.info(f"🧹 Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to cleanup temporary file: {e}")


@router.post("/chunk", response_model=RealtimeChunkResponse)
async def process_realtime_chunk_endpoint(
    request: RealtimeChunkRequest,
    background_tasks: BackgroundTasks
):
    """
    ประมวลผล real-time transcription chunk
    
    รับ audio_url (Public URL) และ callback_url
    ดาวน์โหลด audio → transcription → ส่งผลลัพธ์กลับผ่าน webhook
    
    Args:
        request: ข้อมูล request
        background_tasks: Background tasks
        
    Returns:
        RealtimeChunkResponse: Task ID และสถานะ
    """
    try:
        # Validate request
        if not request.audio_url:
            raise HTTPException(status_code=400, detail="audio_url is required")
        if not request.callback_url:
            raise HTTPException(status_code=400, detail="callback_url is required")
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        logger.info(f"📥 Received real-time chunk request:")
        logger.info(f"   Task ID: {task_id}")
        logger.info(f"   Audio URL: {request.audio_url}")
        logger.info(f"   Callback URL: {request.callback_url}")
        model_size = request.model_size or get_default_whisper_model_display()
        logger.info(f"   Chunk Index: {request.chunk_index}")
        logger.info(f"   Language: {request.language}, Model: {model_size}")
        
        # Add background task
        background_tasks.add_task(
            process_realtime_chunk,
            task_id=task_id,
            audio_url=request.audio_url,
            callback_url=request.callback_url,
            chunk_index=request.chunk_index,
            start_time=request.start_time,
            duration=request.duration,
            language=request.language,
            model_size=model_size
        )
        
        return RealtimeChunkResponse(
            task_id=task_id,
            status="processing",
            chunk_index=request.chunk_index,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in real-time chunk endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)}"
        )


@router.post("/live-chunk")
async def process_live_chunk(
    request: Request,
    x_meeting_id: Optional[str] = Header(None, alias="X-Meeting-Id"),
    x_chunk_index: Optional[str] = Header(None, alias="X-Chunk-Index"),
    x_start_time: Optional[str] = Header(None, alias="X-Start-Time"),
    x_duration: Optional[str] = Header(None, alias="X-Duration"),
    x_audio_format: Optional[str] = Header(None, alias="X-Audio-Format"),
    x_sample_rate: Optional[str] = Header(None, alias="X-Sample-Rate"),
    x_channels: Optional[str] = Header(None, alias="X-Channels"),
    x_model_size: Optional[str] = Header(None, alias="X-Model-Size"),
    background_tasks: BackgroundTasks = None
):
    """
    ✅ Chunk-based: ประมวลผล live audio chunk จาก Request.Body (raw PCM/WAV)
    
    รับ raw PCM/WAV data จาก Request.Body
    บันทึกเป็น temp file → transcription → ส่งผลลัพธ์ผ่าน WebSocket
    
    Args:
        request: HTTP Request (body = raw PCM/WAV data)
        x_meeting_id: Meeting ID (header)
        x_chunk_index: Chunk index (header)
        x_start_time: Start time in seconds (header)
        x_duration: Duration in seconds (header)
        x_model_size: Model size (optional header, ไม่ส่ง = ใช้จาก env)
        background_tasks: Background tasks
    
    Returns:
        202 Accepted (process in background)
    
    Note:
        - model_size ไม่จำเป็นต้องส่ง (ใช้ default อัตโนมัติ)
        - สามารถ override ได้ผ่าน X-Model-Size header
    """
    try:
        # Parse headers
        meeting_id = x_meeting_id or "unknown"
        chunk_index = int(x_chunk_index) if x_chunk_index and x_chunk_index.isdigit() else 0
        start_time = float(x_start_time) if x_start_time else 0.0
        duration = float(x_duration) if x_duration else 3.0
        audio_format = x_audio_format or "s16le"
        sample_rate = int(x_sample_rate) if x_sample_rate and x_sample_rate.isdigit() else 16000
        channels = int(x_channels) if x_channels and x_channels.isdigit() else 1
        model_size = x_model_size or get_default_whisper_model_display()
        
        # Generate session ID
        session_id = f"live-{meeting_id}-{chunk_index}"
        
        logger.info(f"📥 Received live chunk: MeetingId={meeting_id}, ChunkIndex={chunk_index}, StartTime={start_time}s, Duration={duration}s")
        
        # Read raw audio data from Request.Body
        audio_data = await request.body()
        if not audio_data or len(audio_data) == 0:
            raise HTTPException(status_code=400, detail="Audio data is required in request body")
        
        logger.info(f"✅ Received audio data: {len(audio_data)} bytes")
        
        temp_path = None
        # Create temporary file (only if not MOCK_MODE)
        if not MOCK_MODE:
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".wav" if audio_format.lower() != "s16le" else ".raw",
                delete=False,
                dir=str(temp_dir)
            )
            temp_path = temp_file.name
            temp_file.close()
            
            # Save audio data to temp file
            async with aiofiles.open(temp_path, 'wb') as f:
                await f.write(audio_data)
            
            logger.info(f"✅ Saved audio data to: {temp_path}")
        else:
            logger.info(f"🧪 MOCK MODE: Skipping file save (audio data received: {len(audio_data)} bytes)")
        
        # If raw PCM (s16le), convert to WAV format (only if not MOCK_MODE)
        if audio_format.lower() == "s16le" and not MOCK_MODE:
            # ✅ CloseCaption: ใช้ overlap buffer ถ้าเปิดใช้งาน
            if CloseCaptionConfig.is_enabled():
                # สร้าง overlap buffer สำหรับ meeting นี้ (ถ้ายังไม่มี)
                if meeting_id not in _overlap_buffers:
                    overlap_seconds = CloseCaptionConfig.CHUNK_OVERLAP_SECONDS
                    _overlap_buffers[meeting_id] = OverlapBuffer(
                        overlap_seconds=overlap_seconds,
                        sample_rate=sample_rate
                    )
                    logger.info(f"🔗 Created overlap buffer for meeting {meeting_id}: {overlap_seconds}s overlap")
                
                # เพิ่ม chunk พร้อม prepend tail
                overlap_buffer = _overlap_buffers[meeting_id]
                audio_data = overlap_buffer.add_chunk(audio_data)
                logger.info(f"🔗 Applied overlap: {len(audio_data)} bytes (with tail)")
            
            # Convert raw PCM to WAV
            import wave
            import struct
            
            wav_path = temp_path.replace(".raw", ".wav")
            with wave.open(wav_path, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)  # 16-bit = 2 bytes
                wav_file.setframerate(sample_rate)
                
                # Write raw PCM data (อาจมี overlap แล้ว)
                wav_file.writeframes(audio_data)
            
            # Remove raw file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            temp_path = wav_path
        
        # ✅ ใช้ RQ + Priority Queue แทน background_tasks
        try:
            from ..services.redis_queue_service import get_redis_queue_service
            
            queue_service = get_redis_queue_service()
            job_id = queue_service.enqueue_live_chunk(
                session_id=session_id,
                meeting_id=meeting_id,
                chunk_index=chunk_index,
                start_time=start_time,
                duration=duration,
                audio_path=temp_path if not MOCK_MODE else None,  # Skip saving file in MOCK_MODE
                model_size=model_size  # ส่ง model_size ไป worker
            )
            logger.info(f"📌 Live chunk enqueued to PRIORITY queue (Job ID: {job_id})")
            
            return {
                "status": "accepted",
                "session_id": session_id,
                "meeting_id": meeting_id,
                "chunk_index": chunk_index,
                "start_time": start_time,
                "duration": duration,
                "job_id": job_id,
                "queue": "priority",
                "message": "Audio chunk received. Processing in priority queue. Caption events will be sent via WebSocket."
            }
        except Exception as e:
            logger.error(f"❌ Failed to enqueue live chunk to RQ: {e}", exc_info=True)
            # Fallback: ใช้ background_tasks ถ้า RQ ไม่พร้อม
            logger.warning("⚠️ Falling back to background_tasks (RQ not available)")
            if background_tasks:
                background_tasks.add_task(
                    process_live_chunk_background,
                    session_id=session_id,
                    meeting_id=meeting_id,
                    chunk_index=chunk_index,
                    start_time=start_time,
                    duration=duration,
                    audio_path=temp_path if not MOCK_MODE else None,  # Skip saving file in MOCK_MODE
                    model_size=model_size  # ส่ง model_size ไป background task
                )
            
            return {
                "status": "accepted",
                "session_id": session_id,
                "meeting_id": meeting_id,
                "chunk_index": chunk_index,
                "start_time": start_time,
                "duration": duration,
                "queue": "background_tasks",
                "message": "Audio chunk received. Processing in background (fallback). Caption events will be sent via WebSocket."
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in live chunk endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)}"
        )


async def process_live_chunk_background(
    session_id: str,
    meeting_id: str,
    chunk_index: int,
    start_time: float,
    duration: float,
    audio_path: Optional[str] = None,
    model_size: Optional[str] = None
):
    """
    ประมวลผล live chunk ใน background (transcription + WebSocket)
    ใน MOCK_MODE: ส่ง mock caption events แทน transcription
    """
    temp_path = audio_path
    processed_at = datetime.now(timezone.utc).isoformat()
    try:
        logger.info(f"🔄 Processing live chunk: SessionId={session_id}, ChunkIndex={chunk_index}, StartTime={start_time}s, MockMode={MOCK_MODE}")
        
        # ✅ Track chunk metadata (เก็บไว้ใน memory เพื่อแสดงใน UI)
        chunk_metadata = {
            "session_id": session_id,
            "meeting_id": meeting_id,
            "chunk_index": chunk_index,
            "start_time": start_time,
            "duration": duration,
            "processed_at": processed_at,
            "status": "processing",
            "mock_mode": MOCK_MODE
        }
        
        # Add to metadata store
        if meeting_id not in _chunk_metadata_store:
            _chunk_metadata_store[meeting_id] = []
        _chunk_metadata_store[meeting_id].append(chunk_metadata)
        
        # Keep only last 100 chunks per meeting (prevent memory leak)
        if len(_chunk_metadata_store[meeting_id]) > 100:
            _chunk_metadata_store[meeting_id] = _chunk_metadata_store[meeting_id][-100:]
        
        if MOCK_MODE:
            # 🧪 MOCK MODE: ส่ง mock caption events แทน transcription
            logger.info(f"🧪 MOCK MODE: Generating mock caption events for chunk {chunk_index}")
            
            # ✅ V3 Compliant: Calculate chunk timing in milliseconds
            chunk_start_ms = int(start_time * 1000)  # Convert seconds to milliseconds
            chunk_duration_ms = int(duration * 1000)
            
            # Mock text (แสดงว่า chunk ถูกส่งสำเร็จ)
            mock_text = f"[MOCK] Audio chunk {chunk_index} received ({duration}s, start={start_time:.1f}s)"
            
            # ✅ V3 Compliant: Create "final" event with V3 schema
            # ใช้ default model สำหรับ mock mode
            default_model = "Vinxscribe/biodatlab-whisper-th-medium-faster"
            final_event = {
                "type": "final",
                "meeting_id": meeting_id,
                "session_id": session_id,
                "seq": chunk_index * 100,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "chunk_index": chunk_index,
                "chunk_start_ms": chunk_start_ms,
                "chunk_duration_ms": chunk_duration_ms,
                "language": "th",
                "model": default_model,  # Mock mode ใช้ default model
                "provider": "mock",
                "text": mock_text,
                "segments": [
                    {
                        "id": f"seg-{chunk_index}-0",
                        "t0_ms": chunk_start_ms,
                        "t1_ms": chunk_start_ms + chunk_duration_ms,
                        "text": mock_text,
                        "confidence": 0.95,
                        "is_final": True,
                        "speaker": None
                    }
                ]
            }
            
            # Send via HTTP callback (Worker → Main API)
            try:
                from app.workers.rq_worker import send_ws_event_via_http
                await send_ws_event_via_http(
                    meeting_id=meeting_id,
                    message=final_event
                )
                logger.info(f"📤 Sent V3 MOCK final event via HTTP: ChunkIndex={chunk_index}, Text={mock_text}")
            except Exception as e:
                logger.warning(f"⚠️  Failed to send MOCK event via HTTP: {e}")
            
            # ✅ Update chunk metadata status
            chunk_metadata["status"] = "completed"
            chunk_metadata["text_length"] = len(mock_text)
            chunk_metadata["completed_at"] = datetime.now(timezone.utc).isoformat()
        else:
            # Normal mode: Transcribe audio
            if not whisper_service:
                logger.error("❌ whisper_service not available")
                return
            
            if not temp_path or not os.path.exists(temp_path):
                logger.error(f"❌ Audio file not found: {temp_path}")
                return
            
            # ✅ CloseCaption: ใช้ config จาก CloseCaptionConfig ถ้าเปิดใช้งาน
            if CloseCaptionConfig.is_enabled():
                cc_config = CloseCaptionConfig.get_whisper_params()
                model_size = model_size or cc_config["model_size"]
                language = cc_config["language"]
                logger.info(f"🎯 Using CloseCaption Profile (TH-CC-RT v1): model={model_size}, language={language}")
                logger.info(CloseCaptionConfig.get_summary())
            else:
                # ใช้ default config (ถ้าไม่ได้ส่งมา)
                model_size = model_size or get_default_whisper_model_display()
                language = "th"
            
            # ✅ Detailed logging: เริ่ม transcription
            transcribe_start_time = datetime.now(timezone.utc)
            logger.info(f"🎤 Starting transcription: audio_path={temp_path}, model={model_size}, language={language}")
            logger.info(f"   Chunk: {chunk_index}, StartTime: {start_time}s, Duration: {duration}s")
            
            transcription_result = whisper_service.transcribe_file(
                audio_path=temp_path,
                model_size=model_size,
                language=language,
                use_thai_processor=True
            )
            
            transcribe_end_time = datetime.now(timezone.utc)
            transcribe_duration = (transcribe_end_time - transcribe_start_time).total_seconds()
            
            transcription_text = (transcription_result.get('text', '') or '').strip()
            segments = transcription_result.get('segments', [])
            
            # ✅ Detailed logging: ผลลัพธ์ transcription
            logger.info(f"✅ Transcription completed: {len(transcription_text)} characters, {len(segments)} segments")
            logger.info(f"   Duration: {transcribe_duration:.2f}s, Text: {transcription_text[:100]}..." if len(transcription_text) > 100 else f"   Duration: {transcribe_duration:.2f}s, Text: {transcription_text}")
            if segments:
                logger.info(f"   Segments: {len(segments)} segments (first: {segments[0].get('text', '')[:50]}...)")
            
            # ✅ CloseCaption: Dedupe ข้อความ (ตัดส่วนซ้ำจาก overlap)
            if CloseCaptionConfig.is_enabled() and CloseCaptionConfig.DEDUPE_ENABLED:
                last_text = _last_emitted_text.get(meeting_id, "")
                original_length = len(transcription_text)
                
                logger.info(f"🔍 Dedupe: original_text_length={original_length}, last_emitted_length={len(last_text)}")
                
                deduped_text = dedupe_text(
                    transcription_text,
                    last_text,
                    max_match_length=CloseCaptionConfig.DEDUPE_MAX_MATCH_LENGTH
                )
                
                if deduped_text != transcription_text:
                    removed_chars = original_length - len(deduped_text)
                    logger.info(f"🔍 Dedupe: removed {removed_chars} chars overlap (before: {original_length}, after: {len(deduped_text)})")
                    logger.info(f"   Original: {transcription_text[:100]}..." if len(transcription_text) > 100 else f"   Original: {transcription_text}")
                    logger.info(f"   Deduped: {deduped_text[:100]}..." if len(deduped_text) > 100 else f"   Deduped: {deduped_text}")
                    transcription_text = deduped_text
                else:
                    logger.info(f"🔍 Dedupe: no overlap found, keeping original text")
                
                # เก็บข้อความที่ emit แล้ว
                _last_emitted_text[meeting_id] = transcription_text
            
            # ✅ CloseCaption: Postprocess ข้อความภาษาไทย
            if CloseCaptionConfig.is_enabled() and CloseCaptionConfig.POSTPROCESS_ENABLED:
                preprocess_text = transcription_text
                postprocess_start_time = datetime.now(timezone.utc)
                
                logger.info(f"🔧 Postprocessing: normalize={CloseCaptionConfig.POSTPROCESS_NORMALIZE}, word_seg={CloseCaptionConfig.POSTPROCESS_WORD_SEGMENTATION}, fuzzy_match={CloseCaptionConfig.FUZZY_MATCH_ENABLED}")
                
                transcription_text = postprocess_thai_text(
                    transcription_text,
                    normalize=CloseCaptionConfig.POSTPROCESS_NORMALIZE,
                    fix_words=True,
                    word_segmentation=CloseCaptionConfig.POSTPROCESS_WORD_SEGMENTATION,
                    fuzzy_match=CloseCaptionConfig.FUZZY_MATCH_ENABLED,  # ✅ เปิด/ปิดได้
                )
                
                postprocess_end_time = datetime.now(timezone.utc)
                postprocess_duration = (postprocess_end_time - postprocess_start_time).total_seconds()
                
                logger.info(f"🔧 Postprocessed: {len(transcription_text)} characters (took {postprocess_duration:.3f}s)")
                if preprocess_text != transcription_text:
                    logger.info(f"   Before: {preprocess_text[:100]}..." if len(preprocess_text) > 100 else f"   Before: {preprocess_text}")
                    logger.info(f"   After: {transcription_text[:100]}..." if len(transcription_text) > 100 else f"   After: {transcription_text}")
            
            # ✅ Update chunk metadata status
            chunk_metadata["status"] = "completed"
            chunk_metadata["text_length"] = len(transcription_text)
            chunk_metadata["completed_at"] = datetime.now(timezone.utc).isoformat()
            chunk_metadata["segments_count"] = len(transcription_result.get("segments", []))
            
            # Send caption events via WebSocket
            # segments already extracted above
            
            # ✅ V3 Compliant: Calculate chunk timing in milliseconds
            chunk_start_ms = int(start_time * 1000)  # Convert seconds to milliseconds
            chunk_duration_ms = int(duration * 1000)
            chunk_end_ms = chunk_start_ms + chunk_duration_ms
            
            # ✅ V3 Compliant: Send single "final" event with all segments (not per-segment)
            # Build segments array with V3 format
            v3_segments = []
            for idx, segment in enumerate(segments):
                segment_start_s = segment.get("start", 0.0)
                segment_end_s = segment.get("end", segment.get("start", 0.0) + duration)
                
                # Convert to milliseconds (relative to chunk start)
                segment_start_ms = int(segment_start_s * 1000)
                segment_end_ms = int(segment_end_s * 1000)
                
                # Calculate absolute time (for search/seek)
                segment_t0_ms = chunk_start_ms + segment_start_ms
                segment_t1_ms = chunk_start_ms + segment_end_ms
                
                v3_segments.append({
                    "id": f"seg-{chunk_index}-{idx}",
                    "t0_ms": segment_t0_ms,  # Absolute time (meeting timeline)
                    "t1_ms": segment_t1_ms,
                    "text": (segment.get("text", "") or "").strip(),
                    "confidence": segment.get("confidence", 0.0) if isinstance(segment.get("confidence"), (int, float)) else 0.0,
                    "is_final": True,
                    "speaker": None
                })
            
            # ✅ V3 Compliant: Create "final" event with V3 schema
            # Get provider info
            provider_name = "faster-whisper"  # Default
            try:
                if whisper_service and hasattr(whisper_service, 'provider'):
                    provider_name = getattr(whisper_service.provider, '__class__', {}).__name__ or "faster-whisper"
                    if "whisper_cpp" in provider_name.lower():
                        provider_name = "whisper-cpp"
            except:
                pass
            
            # Create V3 compliant final event
            # ✅ Strip whitespace จาก text ก่อนส่ง
            final_text = transcription_text.strip() if transcription_text else ""
            
            final_event = {
                "type": "final",
                "meeting_id": meeting_id,
                "session_id": session_id,
                "seq": chunk_index * 100 + len(segments),  # Use last segment index
                "created_at": datetime.now(timezone.utc).isoformat(),
                "chunk_index": chunk_index,
                "chunk_start_ms": chunk_start_ms,
                "chunk_duration_ms": chunk_duration_ms,
                "language": language,
                "model": model_size,  # ใช้ค่าจากการประมวลผลจริง (ไม่ hardcode)
                "provider": provider_name,
                "text": final_text,  # Full text (stripped)
                "segments": v3_segments,
                "meta": {
                    "transcribe_duration_seconds": round(transcribe_duration, 3),
                    "text_length": len(final_text),
                    "segments_count": len(v3_segments),
                },
            }
            
            # ✅ Detailed logging: ส่ง WebSocket event
            # Log final_text ที่ strip แล้ว (ไม่ใช่ transcription_text)
            logger.info(f"📤 Preparing to send V3 final caption event:")
            logger.info(f"   MeetingId: {meeting_id}, ChunkIndex: {chunk_index}")
            logger.info(f"   Segments: {len(v3_segments)}, TextLength: {len(final_text)} (original: {len(transcription_text)})")
            logger.info(f"   Text (stripped): {final_text[:100]}..." if len(final_text) > 100 else f"   Text (stripped): {final_text}")
            if final_text != transcription_text:
                logger.debug(f"   ⚠️  Text was stripped: original_length={len(transcription_text)}, stripped_length={len(final_text)}")
            
            # Send via HTTP callback (Worker → Main API)
            try:
                from app.workers.rq_worker import send_ws_event_via_http
                http_start_time = datetime.now(timezone.utc)
                
                await send_ws_event_via_http(
                    meeting_id=meeting_id,
                    message=final_event
                )
                
                http_end_time = datetime.now(timezone.utc)
                http_duration = (http_end_time - http_start_time).total_seconds()
                
                logger.info(f"📤 ✅ Sent V3 final caption event via HTTP: ChunkIndex={chunk_index}, Duration={http_duration:.3f}s")
                logger.info(f"   MeetingId: {meeting_id}, Segments: {len(v3_segments)}, TextLength: {len(transcription_text)}")
            except Exception as e:
                logger.error(f"❌ Failed to send final event via HTTP: {e}", exc_info=True)
            
            # ✅ Backward compatibility: Also send legacy events (for existing clients)
            # Send each segment as a legacy caption event (for backward compatibility)
            base_epoch_ms = int(datetime.now(timezone.utc).timestamp() * 1000) - int(start_time * 1000)
            for idx, segment in enumerate(segments):
                segment_start_s = start_time + segment.get("start", 0.0)
                segment_end_s = start_time + segment.get("end", segment.get("start", 0.0) + duration)
                
                # Convert to epoch_ms
                start_epoch_ms = base_epoch_ms + int(segment_start_s * 1000)
                end_epoch_ms = base_epoch_ms + int(segment_end_s * 1000)
                
                # Create legacy caption event (for backward compatibility)
                # ✅ Strip whitespace จาก segment text ก่อนส่ง
                segment_text = (segment.get("text", "") or "").strip()
                
                legacy_event = {
                    "type": "caption",
                    "session_id": session_id,
                    "stream_id": meeting_id,
                    "seq": chunk_index * 100 + idx,
                    "timing": {
                        "kind": "epoch_ms",
                        "start": start_epoch_ms,
                        "end": end_epoch_ms
                    },
                    "text": segment_text,  # Stripped text
                    "lang": "th",
                    "is_final": True,
                    "tokens": [],
                    "meta": {
                        "speaker": None,
                        "confidence": segment.get("confidence", 0.0) if isinstance(segment.get("confidence"), (int, float)) else 0.0,
                        "model": "faster-whisper",
                        "chunk_id": f"c_{chunk_index:04d}_{idx:02d}"
                    },
                    "ts": datetime.now(timezone.utc).isoformat()
                }
                
                # Send legacy event via HTTP callback (for backward compatibility)
                try:
                    from app.workers.rq_worker import send_ws_event_via_http
                    await send_ws_event_via_http(
                        meeting_id=meeting_id,
                        message=legacy_event
                    )
                    logger.debug(f"📤 Sent legacy caption event via HTTP: ChunkIndex={chunk_index}, Segment={idx}, Text (stripped): {segment_text[:50]}...")
                except Exception as e:
                    logger.debug(f"⚠️  Failed to send legacy event via HTTP: {e}")
        
    except Exception as e:
        logger.error(f"❌ Error processing live chunk: {e}", exc_info=True)
        # ✅ Update chunk metadata status on error
        if 'chunk_metadata' in locals():
            chunk_metadata["status"] = "error"
            chunk_metadata["error"] = str(e)
            chunk_metadata["error_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        # Cleanup temporary file (only if not MOCK_MODE)
        if temp_path and os.path.exists(temp_path) and not MOCK_MODE:
            try:
                os.unlink(temp_path)
                logger.info(f"🧹 Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to cleanup temporary file: {e}")


# ✅ In-memory chunk metadata tracking (แทนการแสดง files ที่ถูก cleanup แล้ว)
_chunk_metadata_store: dict[str, list[dict]] = {}  # meeting_id -> list of chunk metadata


@router.get("/chunk-metrics")
async def get_chunk_metrics(meeting_id: Optional[str] = Query(None, description="Filter by meeting ID")):
    """
    ✅ ดูเวลาแปลง Chunk ถึงส่งคำกลับ (และสรุป) สำหรับ Live Caption
    
    ข้อมูลมาจาก final event ที่ Worker ส่งกลับผ่าน ws-event
    ใช้ transcribe_duration_seconds = เวลาใน Worker ตั้งแต่เริ่ม transcription จนส่งผลกลับ
    
    Args:
        meeting_id: Optional meeting ID (เช่น 3a1f78df-8336-4b98-b2d4-0a746c8773e6)
    
    Returns:
        chunks: รายการ chunk พร้อม transcribe_duration_seconds, received_at
        summary: ค่าเฉลี่ย/ min/ max ของเวลาแปลง (วินาที)
    """
    try:
        from ..utils.live_chunk_metrics import get_metrics
        return get_metrics(meeting_id=meeting_id)
    except Exception as e:
        logger.error(f"❌ Error getting chunk metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึง chunk metrics: {str(e)}"
        )


@router.get("/chunk-metadata")
async def list_chunk_metadata(meeting_id: Optional[str] = None):
    """
    ✅ List chunk metadata ที่ถูก process แล้ว (ไม่ใช่ files เพราะ files ถูก cleanup ทันที)
    
    Args:
        meeting_id: Optional meeting ID เพื่อ filter chunks
    
    Returns:
        List of chunk metadata (chunk_index, start_time, duration, processed_at, etc.)
    """
    try:
        if not meeting_id:
            # Return all meetings' chunks
            all_chunks = []
            for mid, chunks in _chunk_metadata_store.items():
                all_chunks.extend(chunks)
            all_chunks.sort(key=lambda x: x.get("processed_at", ""), reverse=True)
            return {
                "status": "success",
                "total_chunks": len(all_chunks),
                "chunks": all_chunks[:100]  # Limit to 100 most recent chunks
            }
        else:
            # Return chunks for specific meeting
            chunks = _chunk_metadata_store.get(meeting_id, [])
            chunks.sort(key=lambda x: x.get("chunk_index", 0))
            return {
                "status": "success",
                "meeting_id": meeting_id,
                "total_chunks": len(chunks),
                "chunks": chunks
            }
        
    except Exception as e:
        logger.error(f"❌ Error listing chunk metadata: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงรายการ chunk metadata: {str(e)}"
        )


@router.get("/chunk-files")
async def list_chunk_files(meeting_id: Optional[str] = None):
    """
    ⚠️ DEPRECATED: Chunk files ถูก cleanup ทันทีหลัง transcription
    ใช้ /chunk-metadata แทน
    
    Returns:
        Empty list (files are cleaned up immediately after processing)
    """
    return {
        "status": "deprecated",
        "message": "Chunk files are cleaned up immediately after transcription. Use /chunk-metadata instead.",
        "files": []
    }


@router.get("/active-chunks")
async def list_active_chunks(meeting_id: Optional[str] = Query(None, description="Filter by meeting ID")):
    """
    ✅ List active chunk processing jobs (chunks ที่ยังอยู่ใน memory)
    
    Args:
        meeting_id: Optional meeting ID เพื่อ filter chunks
    
    Returns:
        List of active chunk processing jobs (แสดง chunks ทั้งหมดที่ยังอยู่ใน memory)
    """
    try:
        # ✅ Debug logging
        logger.info(f"📋 list_active_chunks called: meeting_id={meeting_id}, store_keys={list(_chunk_metadata_store.keys())}")
        
        active_chunks = []
        
        if meeting_id:
            # Filter chunks for specific meeting
            chunks = _chunk_metadata_store.get(meeting_id, [])
            logger.info(f"📋 Found {len(chunks)} chunks for meeting_id={meeting_id}")
            # ✅ Return all chunks for the meeting (ไม่ใช้ time-based filter)
            active_chunks = list(chunks)
        else:
            # Get active chunks from all meetings
            for mid, chunks in _chunk_metadata_store.items():
                logger.info(f"📋 Meeting {mid}: {len(chunks)} chunks")
                # ✅ Return all chunks from all meetings (ไม่ใช้ time-based filter)
                active_chunks.extend(list(chunks))
        
        # Sort by processed_at (newest first)
        active_chunks.sort(key=lambda x: x.get("processed_at", ""), reverse=True)
        
        logger.info(f"📋 Returning {len(active_chunks)} active chunks")
        
        return {
            "status": "success",
            "meeting_id": meeting_id,
            "total_active": len(active_chunks),
            "active_chunks": active_chunks
        }
        
    except Exception as e:
        logger.error(f"❌ Error listing active chunks: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงรายการ active chunks: {str(e)}"
        )


@router.post("/stop-chunks")
async def stop_chunks(
    meeting_id: Optional[str] = None,
    chunk_index: Optional[int] = None
):
    """
    ✅ Stop/cancel chunk processing jobs
    
    ⚠️ หมายเหตุสำคัญ:
    - การหยุด chunks จะหยุดเฉพาะ chunks ที่กำลัง process อยู่ (status = "processing")
    - Chunks ที่เสร็จแล้ว (status = "completed") ไม่สามารถหยุดได้
    - การหยุด chunks ไม่ได้หยุดการส่ง chunks ใหม่จาก Audio Tap
    - ต้องการหยุดการส่ง chunks ใหม่? กรุณาหยุด Audio Tap แทน (POST /api/audio-tap/stop/{meetingId})
    
    Args:
        meeting_id: Meeting ID เพื่อ stop chunks (ถ้าไม่ระบุจะ stop ทุก meeting)
        chunk_index: Optional chunk index เพื่อ stop chunk เฉพาะ (ถ้าไม่ระบุจะ stop ทุก chunk ของ meeting)
    
    Returns:
        Result of stop operation
    """
    try:
        stopped_count = 0
        not_found_count = 0
        
        if meeting_id:
            # Stop chunks for specific meeting
            if meeting_id in _chunk_metadata_store:
                chunks = _chunk_metadata_store[meeting_id]
                
                if chunk_index is not None:
                    # Stop specific chunk
                    found = False
                    for chunk in chunks:
                        if chunk.get("chunk_index") == chunk_index:
                            found = True
                            if chunk.get("status") == "processing":
                                chunk["status"] = "cancelled"
                                chunk["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                                stopped_count += 1
                                logger.info(f"⏹️ Cancelled chunk: MeetingId={meeting_id}, ChunkIndex={chunk_index}")
                            else:
                                logger.info(f"⚠️ Chunk already {chunk.get('status')}: MeetingId={meeting_id}, ChunkIndex={chunk_index}")
                                not_found_count += 1
                    if not found:
                        logger.warning(f"⚠️ Chunk not found: MeetingId={meeting_id}, ChunkIndex={chunk_index}")
                        not_found_count += 1
                else:
                    # Stop all processing chunks for this meeting
                    for chunk in chunks:
                        if chunk.get("status") == "processing":
                            chunk["status"] = "cancelled"
                            chunk["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                            stopped_count += 1
                            logger.info(f"⏹️ Cancelled chunk: MeetingId={meeting_id}, ChunkIndex={chunk.get('chunk_index')}")
        else:
            # Stop all processing chunks from all meetings
            for mid, chunks in _chunk_metadata_store.items():
                for chunk in chunks:
                    if chunk.get("status") == "processing":
                        chunk["status"] = "cancelled"
                        chunk["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                        stopped_count += 1
                        logger.info(f"⏹️ Cancelled chunk: MeetingId={mid}, ChunkIndex={chunk.get('chunk_index')}")
        
        logger.info(f"⏹️ Stopped {stopped_count} chunk processing job(s), {not_found_count} not found/already completed")
        
        message = f"Stopped {stopped_count} chunk processing job(s)"
        if not_found_count > 0:
            message += f" ({not_found_count} chunk(s) not found or already completed)"
        if stopped_count == 0 and not_found_count == 0:
            message = "No processing chunks found to stop"
        
        return {
            "status": "success",
            "meeting_id": meeting_id,
            "chunk_index": chunk_index,
            "stopped_count": stopped_count,
            "not_found_count": not_found_count,
            "message": message,
            "note": "⚠️ การหยุด chunks ไม่ได้หยุดการส่ง chunks ใหม่จาก Audio Tap. ต้องการหยุดการส่ง chunks ใหม่? กรุณาหยุด Audio Tap (POST /api/audio-tap/stop/{meetingId})"
        }
        
    except Exception as e:
        logger.error(f"❌ Error stopping chunks: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการหยุด chunks: {str(e)}"
        )

