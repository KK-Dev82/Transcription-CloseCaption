from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import logging
from typing import List

from ..models.caption import CaptionRequest, CaptionResponse
from ..services.caption_service import CaptionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/caption", tags=["caption"])

caption_service = CaptionService()

@router.post("/", response_model=CaptionResponse)
async def start_caption_generation(request: CaptionRequest):
    """เริ่มการสร้าง close caption"""
    
    try:
        # ตรวจสอบไฟล์
        from pathlib import Path
        if not Path(request.file_path).exists():
            raise HTTPException(
                status_code=404,
                detail=f"ไม่พบไฟล์: {request.file_path}"
            )
        
        # เริ่มการสร้าง caption
        task_id = await caption_service.start_caption_generation(
            file_path=request.file_path,
            language=request.language,
            model_size=request.model_size,
            subtitle_format=request.subtitle_format
        )
        
        # ดึง task status
        task = caption_service.get_task_status(task_id)
        
        logger.info(f"เริ่มการสร้าง caption: {task_id}")
        
        return task
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเริ่มการสร้าง caption: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการเริ่มการสร้าง caption: {str(e)}"
        )

@router.get("/{task_id}", response_model=CaptionResponse)
async def get_caption_status(task_id: str):
    """ดึงสถานะการสร้าง caption"""
    
    task = caption_service.get_task_status(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="ไม่พบ task"
        )
    
    return task

@router.get("/", response_model=List[CaptionResponse])
async def get_all_captions():
    """ดึงรายการ caption tasks ทั้งหมด"""
    
    return caption_service.get_all_tasks()

@router.delete("/{task_id}")
async def cancel_caption(task_id: str):
    """ยกเลิกการสร้าง caption"""
    
    success = await caption_service.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="ไม่สามารถยกเลิก task ได้"
        )
    
    return {"message": "ยกเลิก task สำเร็จ"}

@router.get("/{task_id}/subtitle")
async def get_caption_subtitle(task_id: str):
    """ดึงไฟล์ subtitle"""
    
    task = caption_service.get_task_status(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="ไม่พบ task"
        )
    
    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="การสร้าง caption ยังไม่เสร็จสิ้น"
        )
    
    return {
        "task_id": task_id,
        "subtitle_format": task.subtitle_format,
        "subtitle_content": task.subtitle_content,
        "total_segments": len(task.segments) if task.segments else 0
    }

@router.get("/{task_id}/segments")
async def get_caption_segments(task_id: str):
    """ดึง segments ของ caption"""
    
    task = caption_service.get_task_status(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="ไม่พบ task"
        )
    
    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="การสร้าง caption ยังไม่เสร็จสิ้น"
        )
    
    return {
        "task_id": task_id,
        "segments": task.segments,
        "total_segments": len(task.segments) if task.segments else 0
    }

@router.post("/cleanup")
async def cleanup_old_caption_tasks(background_tasks: BackgroundTasks):
    """ลบ caption tasks เก่า"""
    
    background_tasks.add_task(caption_service.cleanup_completed_tasks)
    
    return {"message": "เริ่มการลบ caption tasks เก่า"} 