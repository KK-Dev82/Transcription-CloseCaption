"""
Transcription API Endpoint
รองรับ /api/transcribe/ สำหรับ job-based architecture
"""
import os
import logging
import uuid
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcribe", tags=["transcription"])

@router.delete("/{task_id}", include_in_schema=True)
async def cancel_transcription(task_id: str):
    """
    ยกเลิก transcription task
    
    - หยุด jobs ที่เกี่ยวข้องใน Redis queue (preprocess, chunks, aggregator)
    - ลบ Redis keys ของ task
    - อัปเดต task status เป็น cancelled
    
    ใช้เมื่ออัปโหลดไฟล์ผิดและต้องการยกเลิก
    """
    try:
        import os
        from datetime import datetime, timezone
        
        storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
        if storage_type == 'sqlite':
            from app.utils.sqlite_storage import SQLiteStorage
            storage = SQLiteStorage()
        else:
            from app.utils.json_storage import JSONStorage
            storage = JSONStorage()
        
        task = storage.load_transcription(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"ไม่พบ task: {task_id}")
        
        status = task.get("status", "")
        if status in ("completed", "failed", "cancelled"):
            return {
                "task_id": task_id,
                "status": status,
                "message": f"Task อยู่ในสถานะ {status} แล้ว ไม่สามารถยกเลิกได้",
                "cancelled": False
            }
        
        # Cancel Redis jobs
        try:
            from app.services.redis_queue_service import get_redis_queue_service
            queue_service = get_redis_queue_service()
            cancel_result = queue_service.cancel_task(task_id)
            
            cancelled_jobs = cancel_result.get("cancelled_jobs", 0)
            redis_keys_deleted = cancel_result.get("redis_keys_deleted", 0)
            
            logger.info(f"✅ Cancelled {cancelled_jobs} jobs, deleted {redis_keys_deleted} Redis keys for {task_id}")
        except ImportError as e:
            logger.warning(f"Redis Queue not available: {e}")
            cancelled_jobs = 0
            redis_keys_deleted = 0
        except Exception as e:
            logger.warning(f"Error cancelling Redis jobs (continuing): {e}")
            cancelled_jobs = 0
            redis_keys_deleted = 0
        
        # อัปเดต task status เป็น cancelled
        task["status"] = "cancelled"
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        task["current_stage"] = "cancelled"
        task["current_stage_description"] = "ยกเลิกโดยผู้ใช้"
        if "error_message" in task:
            del task["error_message"]
        storage.save_transcription(task_id, task)
        
        # ส่ง WebSocket notification (broadcast ให้ users ที่ subscribe task_id หรือ "all")
        try:
            from app.services.websocket_service import websocket_manager
            msg = {
                "type": "task.cancelled",
                "task_id": task_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await websocket_manager.broadcast_task_update(task_id, msg)
            await websocket_manager.broadcast_task_update("all", msg)
        except Exception as ws_e:
            logger.warning(f"WebSocket notification failed: {ws_e}")
        
        return {
            "task_id": task_id,
            "status": "cancelled",
            "message": "ยกเลิก task สำเร็จ",
            "cancelled": True,
            "cancelled_jobs": cancelled_jobs,
            "redis_keys_deleted": redis_keys_deleted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling transcription {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
                'preprocess_video_record': queue_service.preprocess_video_record_queue,
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
    model_size: Optional[str] = None
    chunk_duration: Optional[int] = None
    use_chunking: bool = False
    callback_url: Optional[str] = None
    enable_diarization: Optional[bool] = None  # None = ใช้ ENABLE_DIARIZATION_DEFAULT
    source: Optional[str] = None  # "video_record" = ลัดคิว (slot พิเศษ +1)
    # Chunk Group: หลายไฟล์ pre-chunked
    file_paths: Optional[List[str]] = None
    chunk_group: bool = False

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
        # Chunk Group: ตรวจสอบ file_paths + chunk_group (ไม่กระทบ flow เดิม)
        if request.chunk_group:
            if not request.file_paths:
                raise HTTPException(
                    status_code=400,
                    detail="ต้องระบุ file_paths เมื่อใช้ chunk_group"
                )
            if request.file_path or request.file_url:
                raise HTTPException(
                    status_code=400,
                    detail="เมื่อใช้ chunk_group ให้ระบุเฉพาะ file_paths"
                )
        elif request.file_paths:
            raise HTTPException(
                status_code=400,
                detail="ต้องระบุ chunk_group=true เมื่อใช้ file_paths"
            )

        # ตรวจสอบว่ามี file_path หรือ file_url (flow ปกติ)
        if not request.chunk_group and not request.file_path and not request.file_url:
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
        
        # ========== Chunk Group Flow ==========
        if request.chunk_group and request.file_paths:
            from app.services.chunk_group_validator import validate_chunk_group_request
            validate_chunk_group_request(request.file_paths)
            
            storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
            if storage_type == 'sqlite':
                from app.utils.sqlite_storage import SQLiteStorage
                storage = SQLiteStorage()
            else:
                from app.utils.json_storage import JSONStorage
                storage = JSONStorage()
            
            from app.services.close_caption_config import get_transcription_model_display
            _raw = (request.model_size or "").strip().lower()
            if _raw in ("", "default", "base"):
                model_size = get_transcription_model_display()
            else:
                model_size = request.model_size
            
            task_id = str(uuid.uuid4())
            enable_diarization = request.enable_diarization
            if enable_diarization is None:
                enable_diarization = os.getenv("ENABLE_DIARIZATION_DEFAULT", "0").lower() in ("1", "true", "yes")
            
            # file_name สำหรับ history: ใช้ชื่อโฟลเดอร์ + จำนวน chunks (ไม่ใช้ chunk_0000.wav เพื่อไม่สับสน)
            first_path = Path(request.file_paths[0])
            display_name = f"{first_path.parent.name} ({len(request.file_paths)} chunks)"
            task_dict = {
                "task_id": task_id,
                "status": "queued",
                "progress": 0,
                "file_path": request.file_paths[0],
                "file_name": display_name,
                "file_paths": request.file_paths,
                "chunk_group": True,
                "language": request.language,
                "model_size": model_size,
                "full_text": "",
                "chunks": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "callback_url": request.callback_url,
                "enable_diarization": enable_diarization,
            }
            storage.save_transcription(task_id, task_dict)
            
            from app.services.redis_queue_service import get_redis_queue_service, QueueFullError
            queue_service = get_redis_queue_service()
            source = request.source if request.source == 'video_record' else None
            try:
                preprocess_job_id = queue_service.enqueue_preprocess_chunk_group(
                    task_id=task_id,
                    file_paths=request.file_paths,
                    language=request.language,
                    model_size=model_size,
                    source=source
                )
                logger.info(f"✅ Chunk group preprocess job enqueued: {preprocess_job_id}")
            except QueueFullError as e:
                raise HTTPException(status_code=429, detail=e.message)
            
            return {
                "task_id": task_id,
                "status": "queued",
                "message": "Chunk group transcription job queued (preprocessing in background)",
                "file_paths": request.file_paths,
                "chunk_group": True,
                "queue": "redis",
                "chunks": len(request.file_paths),
            }
        
        # ========== Flow ปกติ (file_path / file_url) ==========
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
        
        # model_size: ไม่ส่ง / ว่าง / "default" / "base" = ใช้ WHISPER_MODEL (turbo) จาก .env
        from app.services.close_caption_config import get_transcription_model_display
        _raw = (request.model_size or "").strip().lower()
        if _raw in ("", "default", "base"):
            model_size = get_transcription_model_display()
            logger.info(f"📥 model_size not sent/empty/base → using WHISPER_MODEL: {model_size}")
        else:
            model_size = request.model_size
        
        # Log request for debugging
        logger.info(f"📥 Received transcription request: file_path={file_path}, language={request.language}, model_size={model_size}")
        
        # สร้าง task_id
        task_id = str(uuid.uuid4())
        
        # สร้าง task object และบันทึกลง storage โดยตรง
        task = TranscriptionResponse(
            task_id=task_id,
            status="queued",
            file_path=file_path,
            language=request.language,
            model_size=model_size,
            created_at=datetime.now(timezone.utc),
            callback_url=request.callback_url
        )
        
        # enable_diarization: None = ใช้ ENABLE_DIARIZATION_DEFAULT จาก env
        enable_diarization = request.enable_diarization
        if enable_diarization is None:
            enable_diarization = os.getenv("ENABLE_DIARIZATION_DEFAULT", "0").lower() in ("1", "true", "yes")

        # บันทึก task ลง storage โดยตรง (ไม่ใช้ in-memory tasks dict)
        task_dict = {
            "task_id": task_id,
            "status": "queued",
            "progress": 0,
            "file_path": file_path,
            "language": request.language,
            "model_size": model_size,
            "full_text": "",
            "chunks": [],
            "created_at": task.created_at.isoformat(),
            "callback_url": request.callback_url,
            "enable_diarization": enable_diarization,
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
            source = request.source if request.source == 'video_record' else None
            try:
                preprocess_job_id = queue_service.enqueue_preprocess(
                    task_id=task_id,
                    file_path=file_path,
                    language=request.language,
                    model_size=model_size,
                    chunk_duration=chunk_duration,
                    source=source
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
                    model_size=model_size,
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
                    model_size=model_size,
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

