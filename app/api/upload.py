from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional
import logging
from datetime import datetime
import uuid

from ..models.upload import UploadResponse
from ..utils.storage_factory import get_storage

# 🧪 MOCK MODE: Skip FileService import
import os
MOCK_MODE = os.getenv("TRANSCRIPTION_MOCK_MODE", "false").lower() == "true"

if not MOCK_MODE:
    from ..services.file_service import FileService
    from ..services.video_service import VideoService
    file_service = FileService()
    video_service = VideoService()
else:
    # MOCK MODE: Create dummy FileService
    class FileService:
        pass
    file_service = FileService()
    video_service = None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["upload"])

class UploadFromURLRequest(BaseModel):
    """Request model สำหรับอัปโหลดจาก URL"""
    url: str
    filename: Optional[str] = None

@router.post("/", response_model=UploadResponse)
async def upload_file(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None)
):
    """
    อัปโหลดไฟล์วิดีโอหรือเสียง
    รองรับทั้งการอัปโหลดไฟล์โดยตรงและ URL
    
    วิธีใช้:
    1. อัปโหลดไฟล์: POST /api/upload/ (form-data: file=@file.mp4)
    2. อัปโหลดจาก URL: POST /api/upload/ (form-data: url=https://example.com/video.mp4)
    """
    
    # ตรวจสอบว่ามี file หรือ url
    if not file and not url:
        raise HTTPException(
            status_code=400,
            detail="ต้องระบุ file หรือ url อย่างใดอย่างหนึ่ง"
        )
    
    if file and url:
        raise HTTPException(
            status_code=400,
            detail="ระบุได้แค่ file หรือ url อย่างใดอย่างหนึ่งเท่านั้น"
        )
    
    # ตรวจสอบประเภทไฟล์
    allowed_extensions = {
        # วิดีโอ
        '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm',
        # เสียง
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'
    }
    
    # กรณีอัปโหลดจาก URL
    if url:
        try:
            import aiohttp
            import os
            from urllib.parse import urlparse
            
            logger.info(f"กำลังดาวน์โหลดไฟล์จาก URL: {url}")
            
            # ดาวน์โหลดไฟล์จาก URL
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=400,
                            detail=f"ไม่สามารถดาวน์โหลดไฟล์จาก URL ได้ (Status: {response.status})"
                        )
                    
                    # ดึงชื่อไฟล์จาก URL
                    parsed_url = urlparse(url)
                    filename = os.path.basename(parsed_url.path) or "downloaded_file.mp4"
                    
                    # ตรวจสอบประเภทไฟล์
                    file_extension = filename.lower().split('.')[-1] if '.' in filename else ''
                    if f'.{file_extension}' not in allowed_extensions:
                        raise HTTPException(
                            status_code=400,
                            detail=f"ประเภทไฟล์ไม่รองรับ กรุณาใช้: {', '.join(allowed_extensions)}"
                        )
                    
                    # อ่านเนื้อหาไฟล์
                    file_content = await response.read()
                    
                    # ตรวจสอบขนาดไฟล์ (สูงสุด 2GB)
                    max_size = 2 * 1024 * 1024 * 1024  # 2GB
                    if len(file_content) > max_size:
                        raise HTTPException(
                            status_code=400,
                            detail="ขนาดไฟล์ใหญ่เกินไป (สูงสุด 2GB)"
                        )
                    
                    # บันทึกไฟล์
                    file_path = await file_service.save_uploaded_file(file_content, filename)
                    
                    # ดึงข้อมูลไฟล์
                    file_info = file_service.get_file_info(file_path)
                    
                    # บันทึกข้อมูลลง database
                    file_id = None
                    if not MOCK_MODE:
                        try:
                            storage = get_storage()
                            if hasattr(storage, 'save_uploaded_file'):
                                duration_seconds = file_info.get("duration", 0) or 0
                                duration_minutes = round(duration_seconds / 60, 2) if duration_seconds > 0 else 0
                                minutes = int(duration_seconds // 60)
                                seconds = int(duration_seconds % 60)
                                duration_formatted = f"{minutes}:{seconds:02d}"
                                
                                video_info = None
                                audio_info = None
                                if file_service.is_video_file(file_path):
                                    video_info = video_service.get_video_info(file_path)
                                elif file_service.is_audio_file(file_path):
                                    try:
                                        import ffmpeg
                                        probe = ffmpeg.probe(file_path)
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
                                    except Exception:
                                        pass
                                
                                file_id = storage.save_uploaded_file(
                                    filename=filename,
                                    file_path=file_path,
                                    file_type=file_info["file_type"],
                                    file_size=file_info["file_size"],
                                    duration=duration_seconds,
                                    duration_minutes=duration_minutes,
                                    duration_formatted=duration_formatted,
                                    video_info=video_info,
                                    audio_info=audio_info
                                )
                        except Exception as e:
                            logger.warning(f"Failed to save file to database: {e}")
                    
                    # สร้าง response
                    response_obj = UploadResponse(
                        file_id=str(file_id) if file_id else str(uuid.uuid4()),
                        filename=filename,
                        file_path=file_path,
                        file_size=file_info["file_size"],
                        file_type=file_info["file_type"],
                        duration=file_info.get("duration"),
                        uploaded_at=datetime.now(),
                        status="uploaded"
                    )
                    
                    logger.info(f"ดาวน์โหลดไฟล์จาก URL สำเร็จ: {url} -> {file_path} (DB ID: {file_id})")
                    
                    return response_obj
                    
        except aiohttp.ClientError as e:
            logger.error(f"เกิดข้อผิดพลาดในการดาวน์โหลดไฟล์จาก URL: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"ไม่สามารถดาวน์โหลดไฟล์จาก URL ได้: {str(e)}"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดาวน์โหลดไฟล์จาก URL: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"เกิดข้อผิดพลาดในการดาวน์โหลดไฟล์: {str(e)}"
            )
    
    # กรณีอัปโหลดไฟล์โดยตรง (โค้ดเดิม)
    if not file:
        raise HTTPException(
            status_code=400,
            detail="ต้องระบุ file"
        )
    
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
        
        # บันทึกข้อมูลลง database
        file_id = None
        if not MOCK_MODE:
            try:
                storage = get_storage()
                if hasattr(storage, 'save_uploaded_file'):
                    duration_seconds = file_info.get("duration", 0) or 0
                    duration_minutes = round(duration_seconds / 60, 2) if duration_seconds > 0 else 0
                    minutes = int(duration_seconds // 60)
                    seconds = int(duration_seconds % 60)
                    duration_formatted = f"{minutes}:{seconds:02d}"
                    
                    video_info = None
                    audio_info = None
                    if file_service.is_video_file(file_path):
                        video_info = video_service.get_video_info(file_path)
                    elif file_service.is_audio_file(file_path):
                        try:
                            import ffmpeg
                            probe = ffmpeg.probe(file_path)
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
                        except Exception:
                            pass
                    
                    file_id = storage.save_uploaded_file(
                        filename=file.filename,
                        file_path=file_path,
                        file_type=file_info["file_type"],
                        file_size=file_info["file_size"],
                        duration=duration_seconds,
                        duration_minutes=duration_minutes,
                        duration_formatted=duration_formatted,
                        video_info=video_info,
                        audio_info=audio_info
                    )
            except Exception as e:
                logger.warning(f"Failed to save file to database: {e}")
        
        # สร้าง response
        response = UploadResponse(
            file_id=str(file_id) if file_id else str(uuid.uuid4()),
            filename=file.filename,
            file_path=file_path,
            file_size=file_info["file_size"],
            file_type=file_info["file_type"],
            duration=file_info.get("duration"),
            uploaded_at=datetime.now(),
            status="uploaded"
        )
        
        logger.info(f"อัปโหลดไฟล์สำเร็จ: {file.filename} -> {file_path} (DB ID: {file_id})")
        
        return response
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการอัปโหลด: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการอัปโหลด: {str(e)}"
        )

@router.get("/list")
async def list_uploaded_files():
    """ดึงรายการไฟล์ที่อัปโหลดแล้ว"""
    try:
        from pathlib import Path
        import os
        from datetime import datetime
        
        upload_dir = Path("uploads")
        if not upload_dir.exists():
            return {"files": [], "total": 0}
        
        files = []
        for file_path in upload_dir.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "filename": file_path.name,
                    "file_path": str(file_path),
                    "file_size": stat.st_size,
                    "file_type": file_path.suffix.lower(),
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "is_video": file_service.is_video_file(str(file_path)),
                    "is_audio": file_service.is_audio_file(str(file_path))
                })
        
        # เรียงตามวันที่แก้ไขล่าสุด
        files.sort(key=lambda x: x["modified_at"], reverse=True)
        
        return {
            "files": files,
            "total": len(files),
            "upload_directory": str(upload_dir)
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงรายการไฟล์: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงรายการไฟล์: {str(e)}"
        )

@router.get("/{file_id}/info")
async def get_file_info(file_id: str):
    """
    ดึงข้อมูลไฟล์
    
    รวม: /api/video/info/{file_path} (video.py)
    """
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
        
        # Get video info if it's a video file
        video_info = None
        if file_service.is_video_file(file_path):
            try:
                from ..services.video_service import VideoService
                video_service = VideoService()
                video_info = video_service.get_video_info(file_path)
            except Exception as e:
                logger.warning(f"ไม่สามารถดึงข้อมูลวิดีโอ: {e}")
        
        response = {
            "file_id": file_id,
            "file_path": file_path,
            "file_size": file_info["file_size"],
            "file_type": file_info["file_type"],
            "duration": file_info.get("duration"),
            "is_video": file_service.is_video_file(file_path),
            "is_audio": file_service.is_audio_file(file_path)
        }
        
        # Add video info if available
        if video_info:
            response["video_info"] = video_info
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลไฟล์: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงข้อมูลไฟล์: {str(e)}"
        )


@router.get("/info/{file_path:path}")
async def get_file_info_by_path(file_path: str):
    """
    ดึงข้อมูลไฟล์โดยใช้ path โดยตรง
    
    รวม: /api/video/info/{file_path} (video.py)
    
    Example: GET /api/upload/info/uploads/video.mp4
    """
    try:
        from pathlib import Path
        
        # ตรวจสอบว่าไฟล์มีอยู่จริง
        if not Path(file_path).exists():
            raise HTTPException(
                status_code=404,
                detail="ไม่พบไฟล์"
            )
        
        file_info = file_service.get_file_info(file_path)
        
        # Get video info if it's a video file
        video_info = None
        if file_service.is_video_file(file_path):
            try:
                from ..services.video_service import VideoService
                video_service = VideoService()
                video_info = video_service.get_video_info(file_path)
            except Exception as e:
                logger.warning(f"ไม่สามารถดึงข้อมูลวิดีโอ: {e}")
        
        response = {
            "file_path": file_path,
            "filename": Path(file_path).name,
            "file_size": file_info["file_size"],
            "file_type": file_info["file_type"],
            "duration": file_info.get("duration"),
            "is_video": file_service.is_video_file(file_path),
            "is_audio": file_service.is_audio_file(file_path)
        }
        
        # Add video info if available
        if video_info:
            response["video_info"] = video_info
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลไฟล์: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงข้อมูลไฟล์: {str(e)}"
        ) 