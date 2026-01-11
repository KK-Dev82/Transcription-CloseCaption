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
    file_path: str
    language: str = "th"
    model_size: str = "base"  # เร็วกว่า large-v3 มาก
    chunk_duration: int = 30
    enable_thai_processing: bool = True

@router.post("/start")
async def start_enhanced_transcription(request: EnhancedTranscriptionRequest):
    """เริ่ม transcription แบบ enhanced (เร็ว + แม่นยำ)
    
    หมายเหตุ: Endpoint นี้ใช้ logic เดียวกับ /api/transcribe/ 
    แต่เพิ่ม Thai processing ในภายหลัง
    """
    try:
        # ใช้ logic เดียวกับ /api/transcribe/ โดยตรง
        from ..api.transcribe import TranscriptionRequest
        from ..utils.json_storage import JSONStorage
        from ..services.redis_queue_service import get_redis_queue_service
        import uuid
        from datetime import datetime, timezone
        from pathlib import Path
        
        # ตรวจสอบไฟล์
        file_path = request.file_path
        if not Path(file_path).exists():
            raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์: {file_path}")
        
        # สร้าง task_id
        task_id = str(uuid.uuid4())
        
        # สร้าง task และบันทึกลง storage
        json_storage = JSONStorage()
        task_dict = {
            "task_id": task_id,
            "status": "queued",
            "progress": 0,
            "file_path": file_path,
            "language": request.language,
            "model_size": request.model_size,
            "chunk_duration": request.chunk_duration,
            "full_text": "",
            "chunks": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "enable_thai_processing": request.enable_thai_processing,
        }
        json_storage.save_transcription(task_id, task_dict)
        
        # Enqueue preprocessing job
        queue_service = get_redis_queue_service()
        try:
            preprocess_job_id = queue_service.enqueue_preprocess(
                task_id=task_id,
                file_path=file_path,
                language=request.language,
                model_size=request.model_size,
                chunk_duration=request.chunk_duration
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
            "enable_thai_processing": request.enable_thai_processing
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
