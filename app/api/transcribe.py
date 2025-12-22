"""
Transcription API Endpoint
รองรับ /api/transcribe/ สำหรับ job-based architecture
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcribe", tags=["transcription"])

class TranscriptionRequest(BaseModel):
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    language: str = "th"
    model_size: str = "base"
    chunk_duration: Optional[int] = None
    use_chunking: bool = False
    callback_url: Optional[str] = None

@router.post("/")
async def start_transcription(request: TranscriptionRequest):
    """
    เริ่ม transcription job
    รองรับทั้ง file_path และ file_url
    
    วิธีใช้:
    1. ใช้ file_path (ไฟล์ที่อัปโหลดแล้ว):
       {
         "file_path": "uploads/video.mp4",
         "language": "th",
         "model_size": "base"
       }
    
    2. ใช้ file_url (ดาวน์โหลดและ transcribe):
       {
         "file_url": "https://example.com/video.mp4",
         "language": "th",
         "model_size": "base"
       }
    """
    try:
        # ตรวจสอบว่ามี file_path หรือ file_url
        if not request.file_path and not request.file_url:
            raise HTTPException(
                status_code=400,
                detail="ต้องระบุ file_path หรือ file_url อย่างใดอย่างหนึ่ง"
            )
        
        if request.file_path and request.file_url:
            raise HTTPException(
                status_code=400,
                detail="ระบุได้แค่ file_path หรือ file_url อย่างใดอย่างหนึ่งเท่านั้น"
            )
        
        import uuid
        from datetime import datetime, timezone
        from app.services.transcription_service import TranscriptionService
        from app.models.transcription import TranscriptionResponse
        from app.services.file_service import FileService
        from pathlib import Path
        
        transcription_service = TranscriptionService()
        file_service = FileService()
        
        # กรณีใช้ file_url - ดาวน์โหลดไฟล์ก่อน
        file_path = request.file_path
        if request.file_url:
            logger.info(f"📥 Downloading file from URL: {request.file_url}")
            try:
                import aiohttp
                import os
                from urllib.parse import urlparse
                
                # ดาวน์โหลดไฟล์จาก URL
                async with aiohttp.ClientSession() as session:
                    async with session.get(request.file_url) as response:
                        if response.status != 200:
                            raise HTTPException(
                                status_code=400,
                                detail=f"ไม่สามารถดาวน์โหลดไฟล์จาก URL ได้ (Status: {response.status})"
                            )
                        
                        # ดึงชื่อไฟล์จาก URL
                        parsed_url = urlparse(request.file_url)
                        filename = os.path.basename(parsed_url.path) or "downloaded_file.mp4"
                        
                        # อ่านเนื้อหาไฟล์
                        file_content = await response.read()
                        
                        # บันทึกไฟล์
                        file_path = await file_service.save_uploaded_file(file_content, filename)
                        logger.info(f"✅ File downloaded and saved: {file_path}")
                        
            except aiohttp.ClientError as e:
                logger.error(f"❌ Error downloading file from URL: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"ไม่สามารถดาวน์โหลดไฟล์จาก URL ได้: {str(e)}"
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ Unexpected error downloading file: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"เกิดข้อผิดพลาดในการดาวน์โหลดไฟล์: {str(e)}"
                )
        
        # ตรวจสอบว่าไฟล์มีอยู่จริง
        if not Path(file_path).exists():
            raise HTTPException(
                status_code=404,
                detail=f"ไม่พบไฟล์: {file_path}"
            )
        
        # Log request for debugging
        logger.info(f"📥 Received transcription request: file_path={file_path}, language={request.language}, model_size={request.model_size}")
        
        # สร้าง task_id
        task_id = str(uuid.uuid4())
        
        # สร้าง task object
        task = TranscriptionResponse(
            task_id=task_id,
            status="queued",
            file_path=file_path,
            language=request.language,
            model_size=request.model_size,
            created_at=datetime.now(timezone.utc),
            callback_url=request.callback_url
        )
        
        # เพิ่ม task เข้าไปใน service
        transcription_service.tasks[task_id] = task
        
        # บันทึก task
        transcription_service._save_task(task)
        
        # ใช้ Redis Queue แทน async task (แก้ปัญหา timeout)
        try:
            from app.services.redis_queue_service import get_redis_queue_service
            
            queue_service = get_redis_queue_service()
            
            # Enqueue job เข้า Redis Queue
            job_id = queue_service.enqueue_transcription(
                task_id=task_id,
                file_path=file_path,
                language=request.language,
                model_size=request.model_size,
                chunk_duration=request.chunk_duration or 90,  # default 90s
                priority=False,  # TODO: เพิ่ม priority สำหรับ live streaming
                worker_gpu=None  # None = round-robin
            )
            
            logger.info(f"✅ Job {task_id} enqueued to Redis Queue (Job ID: {job_id})")
            
            return {
                "task_id": task_id,
                "status": "queued",
                "message": "Transcription job queued successfully",
                "file_path": file_path,
                "queue": "redis"
            }
        except ImportError:
            # Fallback: ใช้ async task ถ้า Redis Queue ไม่พร้อม
            logger.warning("⚠️ Redis Queue not available, falling back to async task")
            import asyncio
            asyncio.create_task(
                transcription_service._process_transcription(
                    task_id=task_id,
                    file_path=file_path,
                    language=request.language,
                    model_size=request.model_size,
                    chunk_duration=request.chunk_duration or 90,
                    use_chunking=request.use_chunking
                )
            )
            
            return {
                "task_id": task_id,
                "status": "queued",
                "message": "Transcription started (async mode)",
                "file_path": file_path,
                "queue": "async"
            }
        except Exception as e:
            logger.error(f"❌ Error enqueueing job: {e}", exc_info=True)
            # Fallback: ใช้ async task
            import asyncio
            asyncio.create_task(
                transcription_service._process_transcription(
                    task_id=task_id,
                    file_path=file_path,
                    language=request.language,
                    model_size=request.model_size,
                    chunk_duration=request.chunk_duration or 90,
                    use_chunking=request.use_chunking
                )
            )
            
            return {
                "task_id": task_id,
                "status": "queued",
                "message": f"Transcription started (fallback mode: {str(e)})",
                "file_path": file_path,
                "queue": "async"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting transcription: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

