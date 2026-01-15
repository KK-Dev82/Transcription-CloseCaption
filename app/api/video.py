from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Body, BackgroundTasks
from fastapi.responses import FileResponse
from typing import List, Optional, Dict
import logging
from pathlib import Path
import uuid

from ..services.video_service import VideoService
from ..services.file_service import FileService
from ..utils.json_storage import JSONStorage
from ..utils.storage_factory import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["Video Processing"])
video_service = VideoService()
file_service = FileService()
json_storage = JSONStorage()

@router.get("/")
@router.get("/list")
async def list_video_files(
    use_database: bool = Query(True, description="ใช้ database (True) หรือ scan filesystem (False)")
):
    """
    ดึงรายการไฟล์วิดีโอและไฟล์ audio (.wav) ทั้งหมดพร้อมข้อมูล duration (นาที)
    
    Args:
        use_database: ใช้ database (True) หรือ scan filesystem (False)
    
    Returns:
        List ของไฟล์วิดีโอและ audio พร้อมข้อมูล:
        - id: ID ใน database (ถ้าใช้ database)
        - filename: ชื่อไฟล์
        - file_path: path ไปยังไฟล์
        - file_size: ขนาดไฟล์ (bytes)
        - file_type: ประเภทไฟล์ (video/audio)
        - duration: ความยาวไฟล์ (วินาที)
        - duration_minutes: ความยาวไฟล์ (นาที)
        - duration_formatted: ความยาวไฟล์ (รูปแบบ MM:SS)
        - video_info: ข้อมูลวิดีโอเพิ่มเติม (width, height, codec, etc.) - สำหรับไฟล์วิดีโอเท่านั้น
        - audio_info: ข้อมูล audio เพิ่มเติม - สำหรับไฟล์ audio เท่านั้น
    """
    try:
        # ใช้ database ถ้ามีและ use_database=True
        storage = get_storage()
        use_db = use_database and hasattr(storage, 'list_uploaded_files')
        
        if use_db:
            # อ่านจาก database
            try:
                all_files = storage.list_uploaded_files(limit=1000, order_by="created_at", order_desc=True)
                
                videos = []
                audios = []
                
                for file_data in all_files:
                    file_data_copy = file_data.copy()
                    # แปลง modified_at จาก created_at ถ้าไม่มี
                    if "modified_at" not in file_data_copy:
                        file_data_copy["modified_at"] = file_data_copy.get("created_at", "")
                    
                    if file_data["file_type"] == "video":
                        videos.append(file_data_copy)
                    elif file_data["file_type"] == "audio":
                        audios.append(file_data_copy)
                
                return {
                    "videos": videos,
                    "audios": audios,
                    "total": len(videos) + len(audios),
                    "total_videos": len(videos),
                    "total_audios": len(audios),
                    "source": "database"
                }
            except Exception as e:
                logger.warning(f"Failed to read from database, falling back to filesystem: {e}")
                use_db = False
        
        # Fallback: scan filesystem
        from datetime import datetime
        import ffmpeg
        
        upload_dir = Path("uploads")
        if not upload_dir.exists():
            return {
                "videos": [],
                "audios": [],
                "total": 0,
                "message": "ไม่พบโฟลเดอร์ uploads",
                "source": "filesystem"
            }
        
        videos = []
        audios = []
        
        for file_path in upload_dir.iterdir():
            if not file_path.is_file():
                continue
                
            is_video = file_service.is_video_file(str(file_path))
            is_audio = file_service.is_audio_file(str(file_path))
            
            if not (is_video or is_audio):
                continue
            
            try:
                stat = file_path.stat()
                duration_seconds = 0
                video_info = None
                audio_info = None
                
                if is_video:
                    # ดึงข้อมูลวิดีโอ
                    video_info = video_service.get_video_info(str(file_path))
                    duration_seconds = video_info.get("duration", 0)
                elif is_audio:
                    # ดึงข้อมูล audio
                    try:
                        file_info = file_service.get_file_info(str(file_path))
                        duration_seconds = file_info.get("duration", 0) or 0
                        
                        # ดึงข้อมูล audio เพิ่มเติมด้วย ffmpeg
                        try:
                            probe = ffmpeg.probe(str(file_path))
                            audio_stream = next(
                                (stream for stream in probe['streams'] if stream['codec_type'] == 'audio'),
                                None
                            )
                            if audio_stream:
                                audio_info = {
                                    "audio_codec": audio_stream.get('codec_name', 'unknown'),
                                    "sample_rate": int(audio_stream.get('sample_rate', 0)),
                                    "channels": int(audio_stream.get('channels', 0)),
                                    "bitrate": int(audio_stream.get('bit_rate', 0)) if audio_stream.get('bit_rate') else None
                                }
                        except Exception as e:
                            logger.debug(f"ไม่สามารถดึงข้อมูล audio stream สำหรับ {file_path.name}: {e}")
                    except Exception as e:
                        logger.warning(f"ไม่สามารถดึงข้อมูล audio สำหรับ {file_path.name}: {e}")
                
                # คำนวณ duration เป็นนาที
                duration_minutes = round(duration_seconds / 60, 2) if duration_seconds > 0 else 0
                
                # Format duration เป็น MM:SS
                minutes = int(duration_seconds // 60)
                seconds = int(duration_seconds % 60)
                duration_formatted = f"{minutes}:{seconds:02d}"
                
                file_data = {
                    "filename": file_path.name,
                    "file_path": str(file_path),
                    "file_size": stat.st_size,
                    "file_type": "video" if is_video else "audio",
                    "duration": duration_seconds,
                    "duration_minutes": duration_minutes,
                    "duration_formatted": duration_formatted,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
                
                if is_video:
                    file_data["video_info"] = video_info
                    videos.append(file_data)
                elif is_audio:
                    if audio_info:
                        file_data["audio_info"] = audio_info
                    audios.append(file_data)
                    
            except Exception as e:
                logger.warning(f"ไม่สามารถดึงข้อมูลสำหรับ {file_path.name}: {e}")
                # เพิ่มไฟล์แม้จะดึงข้อมูลไม่ได้ แต่ duration จะเป็น 0
                stat = file_path.stat()
                file_data = {
                    "filename": file_path.name,
                    "file_path": str(file_path),
                    "file_size": stat.st_size,
                    "file_type": "video" if is_video else "audio",
                    "duration": 0,
                    "duration_minutes": 0,
                    "duration_formatted": "0:00",
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "error": str(e)
                }
                
                if is_video:
                    file_data["video_info"] = None
                    videos.append(file_data)
                elif is_audio:
                    audios.append(file_data)
        
        # เรียงตามวันที่แก้ไขล่าสุด
        videos.sort(key=lambda x: x["modified_at"], reverse=True)
        audios.sort(key=lambda x: x["modified_at"], reverse=True)
        
        return {
            "videos": videos,
            "audios": audios,
            "total": len(videos) + len(audios),
            "total_videos": len(videos),
            "total_audios": len(audios),
            "upload_directory": str(upload_dir),
            "source": "filesystem"
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงรายการไฟล์: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงรายการไฟล์: {str(e)}"
        )

@router.post("/sync")
async def sync_uploaded_files():
    """
    Sync ข้อมูลใน database กับ filesystem
    - เพิ่มไฟล์ใหม่ที่ยังไม่มีใน database
    - ลบไฟล์ที่ไม่มีใน filesystem แล้ว (soft delete)
    """
    try:
        storage = get_storage()
        if not hasattr(storage, 'sync_uploaded_files'):
            raise HTTPException(
                status_code=501,
                detail="Storage backend ไม่รองรับ sync function"
            )
        
        result = storage.sync_uploaded_files()
        
        return {
            "message": "Sync สำเร็จ",
            "added": result["added"],
            "marked_deleted": result["marked_deleted"],
            "errors": result.get("errors", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการ sync: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการ sync: {str(e)}"
        )

@router.post("/cleanup-deleted")
async def cleanup_deleted_files(
    max_age_hours: int = Query(24, description="อายุไฟล์ที่ถูก soft delete (ชั่วโมง)")
):
    """
    ลบไฟล์ที่ถูก soft delete แล้วและเก่ากว่า max_age_hours
    (ลบทั้งจาก database และ filesystem)
    """
    try:
        storage = get_storage()
        if not hasattr(storage, 'cleanup_deleted_files'):
            raise HTTPException(
                status_code=501,
                detail="Storage backend ไม่รองรับ cleanup function"
            )
        
        result = storage.cleanup_deleted_files(max_age_hours=max_age_hours)
        
        return {
            "message": "Cleanup สำเร็จ",
            "deleted_count": result["deleted_count"],
            "errors": result.get("errors", []),
            "max_age_hours": max_age_hours
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการ cleanup: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการ cleanup: {str(e)}"
        )

@router.delete("/{file_id}")
async def delete_file(file_id: int, soft_delete: bool = Query(True, description="Soft delete (True) หรือ hard delete (False)")):
    """
    ลบไฟล์ (soft delete หรือ hard delete)
    """
    try:
        storage = get_storage()
        if not hasattr(storage, 'delete_uploaded_file'):
            raise HTTPException(
                status_code=501,
                detail="Storage backend ไม่รองรับ delete function"
            )
        
        success = storage.delete_uploaded_file(file_id, soft_delete=soft_delete)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="ไม่พบไฟล์"
            )
        
        return {
            "message": "ลบไฟล์สำเร็จ" if soft_delete else "ลบไฟล์ถาวรสำเร็จ",
            "file_id": file_id,
            "soft_delete": soft_delete
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการลบไฟล์: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการลบไฟล์: {str(e)}"
        )

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