from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
import logging
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from ..models.transcription import TranscriptionRequest, TranscriptionResponse
from ..services.transcription_service import TranscriptionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcribe", tags=["transcription"])

transcription_service = TranscriptionService()


class CleanupRequest(BaseModel):
    max_age_hours: int = Field(default=24, ge=0, description="ลบรายการที่เก่ากว่า (ชั่วโมง)")
    statuses: Optional[List[str]] = Field(
        default=None,
        description="ระบุสถานะที่ต้องการลบ (ค่าเริ่มต้น: completed, failed, cancelled)"
    )

@router.post("/", response_model=TranscriptionResponse)
async def start_transcription(request: TranscriptionRequest):
    """เริ่มการแปลงเสียงเป็นข้อความ"""
    
    try:
        # เริ่มการแปลงเสียง
        task_id = await transcription_service.start_transcription(
            file_path=request.file_path,
            file_url=str(request.file_url) if request.file_url else None,
            file_name=request.file_name,
            language=request.language,
            model_size=request.model_size,
            chunk_duration=request.chunk_duration,
            callback_url=request.callback_url,
            job_id=request.job_id,
            user_id=request.user_id
        )
        
        # ดึง task status
        task = transcription_service.get_task_status(task_id)
        
        logger.info(f"เริ่มการแปลงเสียง: {task_id}")
        
        return task
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเริ่มการแปลงเสียง: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการเริ่มการแปลงเสียง: {str(e)}"
        )

@router.get("/{task_id}", response_model=TranscriptionResponse)
async def get_transcription_status(task_id: str):
    """ดึงสถานะการแปลงเสียง"""
    
    task = transcription_service.get_task_status(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="ไม่พบ task"
        )
    
    return task

@router.get("/", response_model=List[TranscriptionResponse])
async def get_all_transcriptions():
    """ดึงรายการ transcription tasks ทั้งหมด"""
    
    return transcription_service.get_all_tasks()

@router.post("/cleanup")
async def cleanup_transcription_tasks(request: CleanupRequest):
    """ลบ transcription tasks ออกจาก storage/cache ตามเงื่อนไขที่กำหนด"""
    try:
        removed = transcription_service.cleanup_tasks(
            statuses=request.statuses,
            max_age_hours=request.max_age_hours
        )
        return {"removed": removed, "statuses": request.statuses or ["completed", "failed", "cancelled"]}
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการ cleanup transcription tasks: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการ cleanup transcription tasks: {str(e)}"
        )

@router.delete("/{task_id}")
async def cancel_transcription(task_id: str):
    """ยกเลิกการแปลงเสียง"""
    
    success = await transcription_service.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="ไม่สามารถยกเลิก task ได้"
        )
    
    return {"message": "ยกเลิก task สำเร็จ"}

@router.get("/{task_id}/text")
async def get_transcription_text(task_id: str):
    """ดึงข้อความที่แปลงแล้ว"""
    
    task = transcription_service.get_task_status(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="ไม่พบ task"
        )
    
    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="การแปลงเสียงยังไม่เสร็จสิ้น"
        )
    
    return {
        "task_id": task_id,
        "full_text": task.full_text,
        "language": task.language,
        "total_duration": task.total_duration
    }

@router.get("/{task_id}/chunks")
async def get_transcription_chunks(task_id: str):
    """ดึง chunks ที่แปลงแล้ว"""
    
    task = transcription_service.get_task_status(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="ไม่พบ task"
        )
    
    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="การแปลงเสียงยังไม่เสร็จสิ้น"
        )
    
    return {
        "task_id": task_id,
        "chunks": task.chunks,
        "total_chunks": len(task.chunks) if task.chunks else 0
    }

# ฟังก์ชันใหม่สำหรับการค้นหา
@router.get("/{task_id}/search")
async def search_transcription(
    task_id: str,
    query: str = Query(..., description="คำค้นหา"),
    case_sensitive: bool = Query(False, description="ค้นหาแบบ case sensitive")
):
    """ค้นหาข้อความใน transcription"""
    
    if not query.strip():
        raise HTTPException(
            status_code=400,
            detail="กรุณาระบุคำค้นหา"
        )
    
    try:
        results = transcription_service.search_transcription(
            task_id, query, case_sensitive
        )
        
        return {
            "task_id": task_id,
            "query": query,
            "case_sensitive": case_sensitive,
            "total_results": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการค้นหา: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการค้นหา: {str(e)}"
        )

@router.get("/search/global")
async def search_all_transcriptions(
    query: str = Query(..., description="คำค้นหา"),
    case_sensitive: bool = Query(False, description="ค้นหาแบบ case sensitive")
):
    """ค้นหาข้อความใน transcription ทั้งหมด"""
    
    if not query.strip():
        raise HTTPException(
            status_code=400,
            detail="กรุณาระบุคำค้นหา"
        )
    
    try:
        results = transcription_service.search_all_transcriptions(
            query, case_sensitive
        )
        
        return {
            "query": query,
            "case_sensitive": case_sensitive,
            "total_results": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการค้นหา: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการค้นหา: {str(e)}"
        )

@router.get("/{task_id}/stats")
async def get_transcription_stats(task_id: str):
    """ดึงสถิติของ transcription"""
    
    try:
        stats = transcription_service.get_transcription_stats(task_id)
        
        if not stats:
            raise HTTPException(
                status_code=404,
                detail="ไม่พบข้อมูล transcription"
            )
        
        return stats
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงสถิติ: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงสถิติ: {str(e)}"
        )

@router.get("/list/stored")
async def list_stored_transcriptions():
    """ดึงรายการ transcription ที่เก็บใน JSON storage"""
    
    try:
        transcriptions = transcription_service.list_all_transcriptions()
        
        return {
            "total_transcriptions": len(transcriptions),
            "transcriptions": transcriptions
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงรายการ: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงรายการ: {str(e)}"
        )

@router.delete("/{task_id}/permanent")
async def delete_transcription_permanent(task_id: str):
    """ลบ transcription ถาวร"""
    
    try:
        success = transcription_service.delete_transcription(task_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="ไม่พบ transcription ที่จะลบ"
            )
        
        # Send WebSocket notification about task deletion
        try:
            from ..services.websocket_service import websocket_manager
            logger.info(f"🔍 Attempting to send WebSocket notification for task deletion: {task_id}")
            await websocket_manager.broadcast_to_all({
                "type": "task.deleted",
                "task_id": task_id,
                "timestamp": datetime.now().isoformat()
            })
            logger.info(f"📡 WebSocket notification sent for task deletion: {task_id}")
        except Exception as ws_error:
            logger.error(f"❌ Failed to send WebSocket notification: {ws_error}")
            logger.error(f"❌ WebSocket error details: {type(ws_error).__name__}: {str(ws_error)}")
        
        return {"message": "ลบ transcription สำเร็จ"}
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการลบ transcription: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการลบ transcription: {str(e)}"
        )
