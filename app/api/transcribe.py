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

@router.get("/debug/queue", include_in_schema=True)
async def debug_queue():
    """
    Debug endpoint เพื่อตรวจสอบ Redis connection และ queue status
    ใช้เพื่อ debug ปัญหา "enqueue ไปผิด Redis"
    """
    import os
    from app.services.redis_queue_service import get_redis_queue_service
    
    try:
        redis_url = os.getenv('REDIS_URL')
        if redis_url and '@' in redis_url:
            # Mask password
            parts = redis_url.split('@')
            if len(parts) == 2:
                auth_part = parts[0]
                if ':' in auth_part:
                    user_pass = auth_part.split('://', 1)[1] if '://' in auth_part else auth_part
                    if ':' in user_pass:
                        redis_url_log = redis_url.replace(f':{user_pass.split(":")[1]}', ':****')
                    else:
                        redis_url_log = redis_url
                else:
                    redis_url_log = redis_url
            else:
                redis_url_log = redis_url
        else:
            redis_url_log = redis_url or "NOT SET"
        
        queue_service = get_redis_queue_service()
        
        # Get queue stats
        queue_stats = {}
        try:
            from rq import Queue
            from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry
            
            queues = {
                'preprocess': queue_service.preprocess_queue,
                'cpu': queue_service.cpu_queue,
                'priority': queue_service.priority_queue,
            }
            
            for name, queue in queues.items():
                queue_length = len(queue)
                started = len(StartedJobRegistry(queue=queue))
                finished = len(FinishedJobRegistry(queue=queue))
                failed = len(FailedJobRegistry(queue=queue))
                
                queue_stats[name] = {
                    'queue_name': queue.name,
                    'length': queue_length,
                    'started': started,
                    'finished': finished,
                    'failed': failed
                }
            
            # GPU queues
            for gpu_key, queue in queue_service.queues.items():
                queue_length = len(queue)
                started = len(StartedJobRegistry(queue=queue))
                finished = len(FinishedJobRegistry(queue=queue))
                failed = len(FailedJobRegistry(queue=queue))
                
                queue_stats[gpu_key] = {
                    'queue_name': queue.name,
                    'length': queue_length,
                    'started': started,
                    'finished': finished,
                    'failed': failed
                }
        except Exception as e:
            queue_stats = {'error': str(e)}
        
        return {
            "REDIS_URL": redis_url_log,
            "redis_connected": True,
            "queues": queue_stats
        }
    except Exception as e:
        return {
            "REDIS_URL": os.getenv('REDIS_URL', 'NOT SET'),
            "redis_connected": False,
            "error": str(e)
        }

class TranscriptionRequest(BaseModel):
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    language: str = "th"
    model_size: str = "Vinxscribe/biodatlab-whisper-th-medium-faster"
    chunk_duration: Optional[int] = None
    use_chunking: bool = False
    callback_url: Optional[str] = None

@router.post("/")
async def start_transcription(request: TranscriptionRequest):
    """
    เริ่ม transcription job
    รองรับทั้ง file_path และ file_url
    จำกัดจำนวน concurrent requests ไม่เกิน 25 requests
    
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
    
    Rate Limiting:
    - จำกัดจำนวน concurrent requests ไม่เกิน 25 requests
    - ถ้าเกิน limit จะ return HTTP 429 (Too Many Requests)
    """
    # Rate Limiting: ตรวจสอบจำนวน concurrent requests
    try:
        from app.services.rate_limiter import get_rate_limiter, RateLimitExceeded
        
        rate_limiter = get_rate_limiter()
        
        # ใช้ context manager เพื่อ acquire/release request slot
        with rate_limiter.acquire():
            # ผ่าน rate limit check แล้ว - process request
            pass
    except RateLimitExceeded as e:
        # เกิน rate limit
        logger.warning(f"⚠️ Rate limit exceeded: {e.message}")
        raise HTTPException(
            status_code=429,
            detail=e.message
        )
    except Exception as e:
        # ถ้า rate limiter มีปัญหา ให้ log warning แต่ยัง process request ต่อ
        logger.warning(f"⚠️ Rate limiter error (continuing anyway): {e}")
    
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
        import os
        from datetime import datetime, timezone
        from app.models.transcription import TranscriptionResponse
        from app.services.file_service import FileService
        from pathlib import Path
        
        # ใช้ storage ตาม STORAGE_TYPE (SQLite หรือ JSON)
        storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
        if storage_type == 'sqlite':
            from app.utils.sqlite_storage import SQLiteStorage
            storage = SQLiteStorage()
        else:
            from app.utils.json_storage import JSONStorage
            storage = JSONStorage()
        
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
        
        # สร้าง task object และบันทึกลง storage โดยตรง
        task = TranscriptionResponse(
            task_id=task_id,
            status="queued",
            file_path=file_path,
            language=request.language,
            model_size=request.model_size,
            created_at=datetime.now(timezone.utc),
            callback_url=request.callback_url
        )
        
        # บันทึก task ลง storage โดยตรง (ไม่ใช้ in-memory tasks dict)
        task_dict = {
            "task_id": task_id,
            "status": "queued",
            "progress": 0,
            "file_path": file_path,
            "language": request.language,
            "model_size": request.model_size,
            "full_text": "",
            "chunks": [],
            "created_at": task.created_at.isoformat(),
            "callback_url": request.callback_url,  # บันทึก callback_url เพื่อใช้ส่ง callback เมื่อเสร็จ
        }
        storage.save_transcription(task_id, task_dict)
        
        # ใช้ Fan-out/Fan-in Pattern: enqueue preprocessing job แล้ว return ทันที
        # Preprocessing (extract + chunking) จะทำงานใน background
        try:
            from app.services.redis_queue_service import get_redis_queue_service
            import os
            
            # FIX: Log REDIS_URL เพื่อ debug (ตรวจสอบว่า API ใช้ Redis ตัวเดียวกับ Worker หรือไม่)
            redis_url = os.getenv('REDIS_URL')
            if redis_url:
                # Mask password in log
                redis_url_log = redis_url
                if '@' in redis_url:
                    parts = redis_url.split('@')
                    if len(parts) == 2:
                        auth_part = parts[0]
                        if ':' in auth_part:
                            user_pass = auth_part.split('://', 1)[1] if '://' in auth_part else auth_part
                            if ':' in user_pass:
                                redis_url_log = redis_url.replace(f':{user_pass.split(":")[1]}', ':****')
                logger.info(f"🔍 API ENV REDIS_URL={redis_url_log}")
            else:
                logger.error("❌ API ENV REDIS_URL is NOT SET! This will cause jobs to be enqueued to wrong Redis!")
            
            queue_service = get_redis_queue_service()
            chunk_duration = request.chunk_duration or 150
            
            # Enqueue preprocessing job (จะทำ extract + chunking แล้ว enqueue chunk jobs)
            try:
                preprocess_job_id = queue_service.enqueue_preprocess(
                    task_id=task_id,
                    file_path=file_path,
                    language=request.language,
                    model_size=request.model_size,
                    chunk_duration=chunk_duration
                )
                
                logger.info(f"✅ Preprocess job enqueued: {preprocess_job_id}")
            except Exception as e:
                # ตรวจสอบว่าเป็น QueueFullError หรือไม่
                from app.services.redis_queue_service import QueueFullError
                if isinstance(e, QueueFullError):
                    logger.warning(f"⚠️ Queue full: {e.message}")
                    raise HTTPException(
                        status_code=429,
                        detail=e.message
                    )
                # ถ้าไม่ใช่ QueueFullError ให้ raise ใหม่
                raise
            
            return {
                "task_id": task_id,
                "status": "queued",
                "message": "Transcription job queued successfully (preprocessing in background)",
                "file_path": file_path,
                "queue": "redis",
                "chunks": 0  # ยังไม่รู้จำนวน chunks (จะรู้หลัง preprocessing เสร็จ)
            }
        except ImportError:
            # Fallback: ใช้ async task ถ้า Redis Queue ไม่พร้อม
            logger.warning("⚠️ Redis Queue not available, falling back to async task")
            from app.services.transcription_service import TranscriptionService
            import asyncio
            transcription_service = TranscriptionService()
            asyncio.create_task(
                transcription_service._process_transcription(
                    task_id=task_id,
                    file_path=file_path,
                    language=request.language,
                    model_size=request.model_size,
                    chunk_duration=request.chunk_duration or 150,
                    use_chunking=request.use_chunking
                )
            )
            
            return {
                "task_id": task_id,
                "status": "queued",
                "message": "Transcription started (async mode)",
                "file_path": file_path,
                "queue": "async",
                "chunks": 0
            }
        except Exception as e:
            logger.error(f"❌ Error enqueueing job: {e}", exc_info=True)
            # Fallback: ใช้ async task
            from app.services.transcription_service import TranscriptionService
            import asyncio
            transcription_service = TranscriptionService()
            asyncio.create_task(
                transcription_service._process_transcription(
                    task_id=task_id,
                    file_path=file_path,
                    language=request.language,
                    model_size=request.model_size,
                    chunk_duration=request.chunk_duration or 150,
                    use_chunking=request.use_chunking
                )
            )
            
            return {
                "task_id": task_id,
                "status": "queued",
                "message": f"Transcription started (fallback mode: {str(e)})",
                "file_path": file_path,
                "queue": "async",
                "chunks": 0,
                "error": str(e)
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting transcription: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

