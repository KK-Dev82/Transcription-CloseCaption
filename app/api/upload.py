from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
import uuid

from ..models.upload import UploadResponse
from ..services.file_service import FileService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["upload"])

file_service = FileService()

@router.post("/", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """อัปโหลดไฟล์วิดีโอหรือเสียง"""
    
    # ตรวจสอบประเภทไฟล์
    allowed_extensions = {
        # วิดีโอ
        '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm',
        # เสียง
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'
    }
    
    file_extension = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
    if f'.{file_extension}' not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"ประเภทไฟล์ไม่รองรับ กรุณาใช้: {', '.join(allowed_extensions)}"
        )
    
    # ตรวจสอบขนาดไฟล์ (สูงสุด 2GB)
    max_size = 2 * 1024 * 1024 * 1024  # 2GB
    if file.size and file.size > max_size:
        raise HTTPException(
            status_code=400,
            detail="ขนาดไฟล์ใหญ่เกินไป (สูงสุด 2GB)"
        )
    
    try:
        # อ่านไฟล์
        file_content = await file.read()
        
        # บันทึกไฟล์
        file_path = await file_service.save_uploaded_file(file_content, file.filename)
        
        # ดึงข้อมูลไฟล์
        file_info = file_service.get_file_info(file_path)
        
        # สร้าง response
        response = UploadResponse(
            file_id=str(uuid.uuid4()),
            filename=file.filename,
            file_path=file_path,
            file_size=file_info["file_size"],
            file_type=file_info["file_type"],
            duration=file_info.get("duration"),
            uploaded_at=datetime.now(),
            status="uploaded"
        )
        
        logger.info(f"อัปโหลดไฟล์สำเร็จ: {file.filename} -> {file_path}")
        
        return response
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการอัปโหลด: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการอัปโหลด: {str(e)}"
        )

@router.get("/{file_id}/info")
async def get_file_info(file_id: str):
    """ดึงข้อมูลไฟล์"""
    # ในที่นี้เราจะใช้ file_path แทน file_id เพื่อความง่าย
    # ในระบบจริงควรมี database เก็บ mapping ระหว่าง file_id และ file_path
    
    try:
        # หาไฟล์จาก uploads directory
        import glob
        from pathlib import Path
        
        upload_dir = Path("uploads")
        file_pattern = f"*_{file_id}*"
        matching_files = list(upload_dir.glob(file_pattern))
        
        if not matching_files:
            raise HTTPException(
                status_code=404,
                detail="ไม่พบไฟล์"
            )
        
        file_path = str(matching_files[0])
        file_info = file_service.get_file_info(file_path)
        
        return {
            "file_id": file_id,
            "file_path": file_path,
            "file_size": file_info["file_size"],
            "file_type": file_info["file_type"],
            "duration": file_info.get("duration"),
            "is_video": file_service.is_video_file(file_path),
            "is_audio": file_service.is_audio_file(file_path)
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลไฟล์: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงข้อมูลไฟล์: {str(e)}"
        ) 