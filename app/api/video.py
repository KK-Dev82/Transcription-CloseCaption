from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Body, BackgroundTasks
from fastapi.responses import FileResponse
from typing import List, Optional, Dict
import logging
from pathlib import Path
import uuid

from ..services.video_service import VideoService
from ..services.file_service import FileService
from ..utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["Video Processing"])
video_service = VideoService()
file_service = FileService()
json_storage = JSONStorage()

@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """อัปโหลดไฟล์วิดีโอ"""
    try:
        # ตรวจสอบประเภทไฟล์
        allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
        file_extension = Path(file.filename).suffix.lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"ไม่รองรับไฟล์ประเภท {file_extension}. รองรับ: {', '.join(allowed_extensions)}"
            )
        
        # อ่านไฟล์เป็น bytes
        file_content = await file.read()
        # บันทึกไฟล์
        file_path = await file_service.save_uploaded_file(file_content, file.filename)
        
        # ดึงข้อมูลวิดีโอ
        video_info = video_service.get_video_info(str(file_path))
        
        return {
            "message": "อัปโหลดไฟล์สำเร็จ",
            "file_path": str(file_path),
            "file_name": file.filename,
            "file_size": file.size,
            "video_info": video_info
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการอัปโหลด: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.post("/trim")
async def trim_video(
    input_file: str = Form(...),
    start_time: float = Form(...),
    end_time: float = Form(...),
    output_format: str = Form("mp4"),
    quality: str = Form("medium")
):
    """ตัดวิดีโอตามช่วงเวลา"""
    try:
        # ตรวจสอบไฟล์
        if not Path(input_file).exists():
            raise HTTPException(status_code=404, detail="ไม่พบไฟล์วิดีโอ")
        
        # ตรวจสอบเวลา
        if start_time >= end_time:
            raise HTTPException(status_code=400, detail="เวลาเริ่มต้นต้องน้อยกว่าเวลาสิ้นสุด")
        
        # เริ่มการประมวลผล
        task_id = await video_service.trim_video(
            input_file=input_file,
            start_time=start_time,
            end_time=end_time,
            output_format=output_format,
            quality=quality
        )
        
        return {
            "message": "เริ่มการตัดวิดีโอ",
            "task_id": task_id,
            "status": "pending"
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการตัดวิดีโอ: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.post("/merge")
async def merge_videos(
    input_files: List[str] = Form(...),
    output_format: str = Form("mp4"),
    quality: str = Form("medium")
):
    """รวมวิดีโอหลายไฟล์"""
    try:
        # ตรวจสอบไฟล์
        for input_file in input_files:
            if not Path(input_file).exists():
                raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์: {input_file}")
        
        if len(input_files) < 2:
            raise HTTPException(status_code=400, detail="ต้องมีไฟล์อย่างน้อย 2 ไฟล์")
        
        # เริ่มการประมวลผล
        task_id = await video_service.merge_videos(
            input_files=input_files,
            output_format=output_format,
            quality=quality
        )
        
        return {
            "message": "เริ่มการรวมวิดีโอ",
            "task_id": task_id,
            "status": "pending"
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการรวมวิดีโอ: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.post("/convert")
async def convert_format(
    input_file: str = Form(...),
    output_format: str = Form(...),
    quality: str = Form("medium")
):
    """แปลงรูปแบบไฟล์"""
    try:
        # ตรวจสอบไฟล์
        if not Path(input_file).exists():
            raise HTTPException(status_code=404, detail="ไม่พบไฟล์วิดีโอ")
        
        # ตรวจสอบ output format
        allowed_formats = {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm'}
        if output_format.lower() not in allowed_formats:
            raise HTTPException(
                status_code=400, 
                detail=f"ไม่รองรับรูปแบบ {output_format}. รองรับ: {', '.join(allowed_formats)}"
            )
        
        # เริ่มการประมวลผล
        task_id = await video_service.convert_format(
            input_file=input_file,
            output_format=output_format,
            quality=quality
        )
        
        return {
            "message": "เริ่มการแปลงรูปแบบ",
            "task_id": task_id,
            "status": "pending"
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการแปลงรูปแบบ: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.post("/resize")
async def resize_video(
    input_file: str = Form(...),
    width: int = Form(...),
    height: int = Form(...),
    output_format: str = Form("mp4"),
    quality: str = Form("medium")
):
    """ปรับขนาดวิดีโอ"""
    try:
        # ตรวจสอบไฟล์
        if not Path(input_file).exists():
            raise HTTPException(status_code=404, detail="ไม่พบไฟล์วิดีโอ")
        
        # ตรวจสอบขนาด
        if width <= 0 or height <= 0:
            raise HTTPException(status_code=400, detail="ขนาดต้องมากกว่า 0")
        
        # เริ่มการประมวลผล
        task_id = await video_service.resize_video(
            input_file=input_file,
            width=width,
            height=height,
            output_format=output_format,
            quality=quality
        )
        
        return {
            "message": "เริ่มการปรับขนาดวิดีโอ",
            "task_id": task_id,
            "status": "pending"
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการปรับขนาดวิดีโอ: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.post("/batch")
async def batch_process(operations: List[Dict]):
    """ประมวลผลหลายไฟล์พร้อมกัน"""
    try:
        if not operations:
            raise HTTPException(status_code=400, detail="ต้องมี operations อย่างน้อย 1 รายการ")
        
        # ตรวจสอบ operations
        for operation in operations:
            op_type = operation.get("type")
            if op_type not in ["trim", "convert", "resize"]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"ไม่รองรับ operation type: {op_type}"
                )
        
        # เริ่มการประมวลผล
        task_id = await video_service.batch_process(operations)
        
        return {
            "message": "เริ่มการประมวลผลแบบ batch",
            "task_id": task_id,
            "status": "pending"
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดใน batch processing: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """ดึงสถานะของ task"""
    try:
        # ดึงจาก memory
        task = video_service.get_task_status(task_id)
        
        if not task:
            # ดึงจาก storage
            task = json_storage.load_video_task(task_id)
            
        if not task:
            raise HTTPException(status_code=404, detail="ไม่พบ task")
        
        return {
            "task_id": task_id,
            "status": task.get("status"),
            "type": task.get("type"),
            "progress": task.get("progress", 0),
            "created_at": task.get("created_at"),
            "completed_at": task.get("completed_at"),
            "output_file": task.get("output_file"),
            "error_message": task.get("error_message")
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงสถานะ: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.get("/tasks")
async def get_all_tasks():
    """ดึงรายการ tasks ทั้งหมด"""
    try:
        # ดึงจาก memory
        memory_tasks = video_service.get_all_tasks()
        
        # ดึงจาก storage
        storage_tasks = json_storage.list_all_video_tasks()
        
        # รวมและจัดเรียงตามเวลา
        all_tasks = memory_tasks + storage_tasks
        all_tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return {
            "tasks": all_tasks,
            "total": len(all_tasks)
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงรายการ tasks: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.delete("/cancel/{task_id}")
async def cancel_task(task_id: str):
    """ยกเลิก task"""
    try:
        success = await video_service.cancel_task(task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="ไม่สามารถยกเลิก task ได้")
        
        return {
            "message": "ยกเลิก task สำเร็จ",
            "task_id": task_id
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการยกเลิก task: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.get("/download/{task_id}")
async def download_result(task_id: str):
    """ดาวน์โหลดผลลัพธ์"""
    try:
        # ดึงข้อมูล task
        task = video_service.get_task_status(task_id)
        if not task:
            task = json_storage.load_video_task(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="ไม่พบ task")
        
        if task.get("status") != "completed":
            raise HTTPException(status_code=400, detail="task ยังไม่เสร็จสิ้น")
        
        output_file = task.get("output_file")
        if not output_file or not Path(output_file).exists():
            raise HTTPException(status_code=404, detail="ไม่พบไฟล์ผลลัพธ์")
        
        # ส่งไฟล์
        return FileResponse(
            path=output_file,
            filename=Path(output_file).name,
            media_type='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดาวน์โหลด: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.get("/info/{file_path:path}")
async def get_video_info(file_path: str):
    """ดึงข้อมูลวิดีโอ"""
    try:
        full_path = Path(file_path)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="ไม่พบไฟล์")
        
        info = video_service.get_video_info(str(full_path))
        
        if "error" in info:
            raise HTTPException(status_code=500, detail=info["error"])
        
        return info
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลวิดีโอ: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.delete("/delete/{task_id}")
async def delete_task(task_id: str):
    """ลบ task และไฟล์ที่เกี่ยวข้อง"""
    try:
        # ลบจาก storage
        success = json_storage.delete_video_task(task_id)
        
        # ลบไฟล์ผลลัพธ์
        task = json_storage.load_video_task(task_id)
        if task and task.get("output_file"):
            output_path = Path(task["output_file"])
            if output_path.exists():
                output_path.unlink()
        
        if not success:
            raise HTTPException(status_code=404, detail="ไม่พบ task")
        
        return {
            "message": "ลบ task สำเร็จ",
            "task_id": task_id
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการลบ task: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.post("/cleanup")
async def cleanup_old_files(max_age_hours: int = Query(24, description="อายุไฟล์สูงสุด (ชั่วโมง)")):
    """ลบไฟล์เก่า"""
    try:
        json_storage.cleanup_old_files(max_age_hours)
        
        return {
            "message": "ลบไฟล์เก่าเสร็จสิ้น",
            "max_age_hours": max_age_hours
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการลบไฟล์เก่า: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.post("/segment")
async def segment_video(
    request: dict = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    แบ่งตอนวิดีโอและทำ transcription แบบ batch พร้อมกัน
    """
    try:
        file_path = request.get("file_path")
        segment_duration = request.get("segment_duration", 600)  # 10 นาที
        overlap = request.get("overlap", 5)  # 5 วินาที
        language = request.get("language", "th")
        model_size = request.get("model_size", "base")
        
        if not file_path:
            raise HTTPException(status_code=400, detail="ต้องระบุ file_path")
        
        # สร้าง task ID
        task_id = str(uuid.uuid4())
        
        # ส่งงานไปยัง background task แบบ async
        background_tasks.add_task(
            video_service.process_video_segmentation,
            task_id,
            file_path,
            segment_duration,
            overlap,
            language,
            model_size
        )
        
        return {
            "task_id": task_id,
            "message": "ส่งงานแบ่งตอนวิดีโอและ transcription พร้อมกันสำเร็จ",
            "status": "processing",
            "segments": {
                "duration": segment_duration,
                "overlap": overlap,
                "language": language,
                "model_size": model_size
            }
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการแบ่งตอนวิดีโอ: {str(e)}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.get("/segment/{task_id}")
async def get_segmentation_status(task_id: str):
    """
    ตรวจสอบสถานะการแบ่งตอนวิดีโอ
    """
    try:
        status = video_service.get_segmentation_status(task_id)
        return status
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบสถานะ: {str(e)}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}") 