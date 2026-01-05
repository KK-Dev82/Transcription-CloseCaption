"""
Real-time Transcription API Endpoint
สำหรับการประมวลผล audio chunks แบบ real-time (ทุก 5 วินาที)
รองรับการส่ง audio_url และ callback_url สำหรับ webhook
"""

import logging
import uuid
import asyncio
import tempfile
import os
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import aiohttp
import aiofiles

from ..services.whisper_service import WhisperService
from ..services.file_service import FileService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcription/realtime", tags=["realtime-transcription"])

# Initialize services
whisper_service = WhisperService()
file_service = FileService()


class RealtimeChunkRequest(BaseModel):
    """Request model สำหรับ real-time transcription chunk"""
    audio_url: str  # Public URL ของ audio file
    callback_url: str  # Webhook callback URL
    chunk_index: Optional[int] = 0
    start_time: Optional[float] = 0.0
    duration: Optional[float] = 5.0
    language: str = "th"
    model_size: str = "base"


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
        logger.info(f"   Chunk Index: {request.chunk_index}")
        logger.info(f"   Language: {request.language}, Model: {request.model_size}")
        
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
            model_size=request.model_size
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

