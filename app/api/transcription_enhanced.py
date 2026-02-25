"""
Enhanced Transcription API with Thai Processing
แก้ปัญหาความเร็วโดยใช้ base model + post-processing
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
import logging

from ..services.transcription_service import TranscriptionService
from ..services.thai_text_processor import create_thai_processor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcribe-enhanced", tags=["enhanced-transcription"])

transcription_service = TranscriptionService()

class EnhancedTranscriptionRequest(BaseModel):
    file_path: Optional[str] = None  # ใช้เมื่อไม่ใช้ chunk_group
    language: str = "th"
    model_size: Optional[str] = None  # ไม่ส่ง = ใช้จาก .env (WHISPER_MODEL)
    chunk_duration: Optional[int] = None  # ไม่ส่ง = ใช้จาก .env (TRANSCRIPTION_CHUNK_DURATION)
    use_chunking: Optional[bool] = None  # None = ใช้ TRANSCRIPTION_USE_CHUNKING จาก .env
    enable_thai_processing: bool = True
    enable_diarization: Optional[bool] = None  # None = ใช้ ENABLE_DIARIZATION_DEFAULT จาก .env (.env.runpod / .env.runpod-1GPU)
    source: Optional[str] = None  # "video_record" = ลัดคิว (slot พิเศษ +1)
    # Chunk Group
    file_paths: Optional[List[str]] = None
    chunk_group: bool = False

@router.post("/start")
async def start_enhanced_transcription(request: EnhancedTranscriptionRequest):
    """เริ่ม transcription แบบ enhanced (เร็ว + แม่นยำ)
    
    หมายเหตุ: Endpoint นี้ใช้ logic เดียวกับ /api/transcribe/ 
    แต่เพิ่ม Thai processing ในภายหลัง
    """
    try:
        import os
        from ..services.redis_queue_service import get_redis_queue_service
        import uuid
        from datetime import datetime, timezone
        from pathlib import Path
        
        # Chunk Group validation
        if request.chunk_group:
            if not request.file_paths:
                raise HTTPException(status_code=400, detail="ต้องระบุ file_paths เมื่อใช้ chunk_group")
            if request.file_path:
                raise HTTPException(status_code=400, detail="เมื่อใช้ chunk_group ให้ระบุเฉพาะ file_paths")
        elif request.file_paths:
            raise HTTPException(status_code=400, detail="ต้องระบุ chunk_group=true เมื่อใช้ file_paths")
        
        # Flow ปกติ: ต้องมี file_path
        if not request.chunk_group and not request.file_path:
            raise HTTPException(status_code=400, detail="ต้องระบุ file_path หรือ file_paths+chunk_group")
        
        # ========== Chunk Group Flow ==========
        if request.chunk_group and request.file_paths:
            from app.services.chunk_group_validator import validate_chunk_group_request
            validate_chunk_group_request(request.file_paths)
            
            storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
            if storage_type == 'sqlite':
                from ..utils.sqlite_storage import SQLiteStorage
                storage = SQLiteStorage()
            else:
                from ..utils.json_storage import JSONStorage
                storage = JSONStorage()
            
            from ..services.close_caption_config import get_transcription_model_display
            _raw = (request.model_size or "").strip().lower()
            if _raw in ("", "default", "base"):
                model_size = get_transcription_model_display()
            else:
                model_size = request.model_size
            
            task_id = str(uuid.uuid4())
            enable_diarization = request.enable_diarization
            if enable_diarization is None:
                enable_diarization = os.getenv("ENABLE_DIARIZATION_DEFAULT", "0").lower() in ("1", "true", "yes")
            
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
                "chunk_duration": int(os.getenv("TRANSCRIPTION_CHUNK_DURATION", "150")),
                "use_chunking": True,
                "full_text": "",
                "chunks": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "enable_thai_processing": request.enable_thai_processing,
                "enable_diarization": enable_diarization,
                "source": "video_record" if request.source == "video_record" else "upload",
            }
            storage.save_transcription(task_id, task_dict)
            
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
                logger.info(f"✅ Chunk group enhanced transcription job enqueued: {preprocess_job_id}")
            except Exception as e:
                from app.services.redis_queue_service import QueueFullError
                if isinstance(e, QueueFullError):
                    raise HTTPException(status_code=429, detail=e.message)
                raise
            
            return {
                "task_id": task_id,
                "status": "queued",
                "message": "Chunk group Enhanced Transcription เริ่มแล้ว",
                "chunk_group": True,
                "file_paths": request.file_paths,
                "queue": "redis",
                "chunks": len(request.file_paths),
            }
        
        # ========== Flow ปกติ (file_path) ==========
        file_path = request.file_path
        if not Path(file_path).exists():
            raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์: {file_path}")

        # model_size: ไม่ส่ง / ว่าง / "default" / "base" = ใช้ WHISPER_MODEL (turbo) จาก .env
        from ..services.close_caption_config import get_transcription_model_display
        _raw = (request.model_size or "").strip().lower()
        if _raw in ("", "default", "base"):
            model_size = get_transcription_model_display()
            logger.info(f"📥 model_size not sent/empty/base → using WHISPER_MODEL: {model_size}")
        else:
            model_size = request.model_size

        # chunk_duration: ไม่ส่ง = ใช้ TRANSCRIPTION_CHUNK_DURATION จาก .env
        chunk_duration = request.chunk_duration
        if chunk_duration is None:
            chunk_duration = int(os.getenv("TRANSCRIPTION_CHUNK_DURATION", "150"))

        # use_chunking: None = ใช้ TRANSCRIPTION_USE_CHUNKING จาก .env
        use_chunking = request.use_chunking
        if use_chunking is None:
            use_chunking = os.getenv("TRANSCRIPTION_USE_CHUNKING", "true").lower() in ("1", "true", "yes")

        # enable_diarization: None = ใช้ ENABLE_DIARIZATION_DEFAULT จาก .env (.env.runpod / .env.runpod-1GPU)
        enable_diarization = request.enable_diarization
        if enable_diarization is None:
            enable_diarization = os.getenv("ENABLE_DIARIZATION_DEFAULT", "0").lower() in ("1", "true", "yes")

        # สร้าง task_id
        task_id = str(uuid.uuid4())
        
        # สร้าง task และบันทึกลง storage (ใช้ storage ตาม STORAGE_TYPE เหมือน transcribe.py)
        storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
        if storage_type == 'sqlite':
            from ..utils.sqlite_storage import SQLiteStorage
            storage = SQLiteStorage()
        else:
            from ..utils.json_storage import JSONStorage
            storage = JSONStorage()
        task_dict = {
            "task_id": task_id,
            "status": "queued",
            "progress": 0,
            "file_path": file_path,
            "language": request.language,
            "model_size": model_size,
            "chunk_duration": chunk_duration,
            "use_chunking": use_chunking,
            "full_text": "",
            "chunks": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "enable_thai_processing": request.enable_thai_processing,
            "enable_diarization": enable_diarization,
            "source": "video_record" if request.source == "video_record" else "upload",
        }
        storage.save_transcription(task_id, task_dict)
        
        # Enqueue preprocessing job
        queue_service = get_redis_queue_service()
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
            
            logger.info(f"✅ Enhanced transcription job enqueued: {preprocess_job_id}")
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
            "message": "เริ่ม Enhanced Transcription สำเร็จ (base model + Thai processing)",
            "strategy": "fast_model_with_post_processing",
            "estimated_time": "3-5 นาทีสำหรับวิดีโอ 10 นาที",
            "queue": "redis",
            "enable_thai_processing": request.enable_thai_processing,
            "enable_diarization": enable_diarization
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enhanced transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{task_id}")
async def get_enhanced_status(task_id: str):
    """
    ⚠️ **DEPRECATED**: Endpoint นี้จะถูก deprecate ในอนาคต
    
    **แนะนำให้ใช้**: `GET /api/v2/tasks/{task_id}?format=full&include_thai_processing=true`
    
    ดูสถานะและใช้ Thai processing ถ้าเสร็จแล้ว
    """
    try:
        # ใช้ polling function แทนการเรียก HTTP
        from ..api.polling import poll_task_status
        
        task_data = await poll_task_status(task_id)
        
        # ถ้าเสร็จแล้ว และยังไม่ได้ Thai processing
        # ชั่วคราว skip Thai processing เพื่อทดสอบ
        # if task_data.get("status") == "completed" and not task_data.get("thai_processed"):
        #     logger.info(f"Applying Thai processing to completed task: {task_id}")
        #     task_data = await _apply_thai_processing_to_task(task_id, task_data)
        
        return task_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get enhanced status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/apply-thai-processing/{task_id}")
async def apply_thai_processing_manually(task_id: str):
    """ใช้ Thai processing กับ task ที่เสร็จแล้ว"""
    try:
        import requests
        
        response = requests.get(f"http://localhost:8001/transcribe/status/{task_id}")
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="ไม่พบ task")
        
        task_data = response.json()
            
        if task_data.get("status") != "completed":
            raise HTTPException(status_code=400, detail="Task ยังไม่เสร็จ")
        
        enhanced_task = await _apply_thai_processing_to_task(task_id, task_data)
        
        return {
            "message": "ใช้ Thai processing สำเร็จ",
            "task_id": task_id,
            "improvements": enhanced_task.get("thai_processing_stats", {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Apply Thai processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _apply_thai_processing_to_task(task_id: str, task: Dict) -> Dict:
    """ใช้ Thai processing กับ task"""
    try:
        processor = create_thai_processor()
        
        # ดึงข้อมูล chunks
        chunks = task.get("chunks", [])
        if not chunks:
            logger.warning(f"No chunks found for task {task_id}")
            return task
        
        # ประมวลผล chunks
        logger.info(f"Processing {len(chunks)} chunks with Thai processor")
        processed_chunks = processor.process_transcription_chunks(chunks)
        
        # อัปเดตข้อมูล
        enhanced_task = task.copy()
        enhanced_task["chunks"] = processed_chunks
        enhanced_task["thai_processed"] = True
        enhanced_task["thai_processing_stats"] = processor.get_statistics(processed_chunks)
        
        # รวมข้อความที่แก้ไขแล้ว
        corrected_text = " ".join([
            chunk.get("text", "") for chunk in processed_chunks 
            if chunk.get("text")
        ])
        enhanced_task["text"] = corrected_text
        enhanced_task["original_text"] = task.get("text", "")
        
        # บันทึกกลับ (อัปเดต JSON storage)
        transcription_service.json_storage.save_transcription(task_id, enhanced_task)
        
        logger.info(f"Thai processing completed for task {task_id}: {enhanced_task['thai_processing_stats']}")
        return enhanced_task
        
    except Exception as e:
        logger.error(f"Thai processing failed for task {task_id}: {e}")
        return task

@router.get("/compare/{task_id}")
async def compare_before_after(task_id: str):
    """เปรียบเทียบผลลัพธ์ก่อนและหลัง Thai processing"""
    try:
        import requests
        
        response = requests.get(f"http://localhost:8001/transcribe/status/{task_id}")
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="ไม่พบ task")
        
        task_data = response.json()
        
        if not task_data.get("thai_processed"):
            raise HTTPException(status_code=400, detail="Task ยังไม่ได้ Thai processing")
        
        original_chunks = []
        processed_chunks = []
        
        for chunk in task_data.get("chunks", []):
            if chunk.get("original_text") and chunk.get("text"):
                original_chunks.append({
                    "start_time": chunk.get("start_time"),
                    "end_time": chunk.get("end_time"), 
                    "text": chunk.get("original_text")
                })
                processed_chunks.append({
                    "start_time": chunk.get("start_time"),
                    "end_time": chunk.get("end_time"),
                    "text": chunk.get("text"),
                    "was_corrected": chunk.get("was_corrected", False),
                    "confidence": chunk.get("correction_confidence", 1.0)
                })
        
        return {
            "task_id": task_id,
            "comparison": {
                "original": {
                    "text": task_data.get("original_text", ""),
                    "chunks": original_chunks
                },
                "processed": {
                    "text": task_data.get("text", ""),
                    "chunks": processed_chunks
                }
            },
            "statistics": task_data.get("thai_processing_stats", {}),
            "improvements": {
                "total_corrections": sum(1 for chunk in task_data.get("chunks", []) if chunk.get("was_corrected")),
                "average_confidence": task_data.get("thai_processing_stats", {}).get("average_confidence", 0)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Compare before/after error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
