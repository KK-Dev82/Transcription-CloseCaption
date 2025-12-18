"""
File Service - จัดการไฟล์และตรวจสอบประเภทไฟล์
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FileService:
    """Service สำหรับจัดการไฟล์และตรวจสอบประเภทไฟล์"""
    
    # Video extensions
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.3gp'}
    
    # Audio extensions
    AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.aac', '.ogg', '.flac', '.wma', '.opus'}
    
    def __init__(self):
        logger.info("FileService initialized")
    
    def is_video_file(self, file_path: str) -> bool:
        """
        ตรวจสอบว่าไฟล์เป็นวิดีโอหรือไม่
        
        Args:
            file_path: Path ไปยังไฟล์
            
        Returns:
            bool: True ถ้าเป็นวิดีโอ
        """
        if not file_path:
            return False
        
        path = Path(file_path)
        extension = path.suffix.lower()
        return extension in self.VIDEO_EXTENSIONS
    
    def is_audio_file(self, file_path: str) -> bool:
        """
        ตรวจสอบว่าไฟล์เป็นเสียงหรือไม่
        
        Args:
            file_path: Path ไปยังไฟล์
            
        Returns:
            bool: True ถ้าเป็นเสียง
        """
        if not file_path:
            return False
        
        path = Path(file_path)
        extension = path.suffix.lower()
        return extension in self.AUDIO_EXTENSIONS
    
    def get_file_type(self, file_path: str) -> Optional[str]:
        """
        ตรวจสอบประเภทไฟล์
        
        Args:
            file_path: Path ไปยังไฟล์
            
        Returns:
            str: 'video', 'audio', หรือ None
        """
        if self.is_video_file(file_path):
            return 'video'
        elif self.is_audio_file(file_path):
            return 'audio'
        else:
            return None
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """
        ดึงขนาดไฟล์
        
        Args:
            file_path: Path ไปยังไฟล์
            
        Returns:
            int: ขนาดไฟล์เป็น bytes หรือ None ถ้าไม่พบ
        """
        try:
            path = Path(file_path)
            if path.exists():
                return path.stat().st_size
            return None
        except Exception as e:
            logger.error(f"Error getting file size: {e}")
            return None
    
    def file_exists(self, file_path: str) -> bool:
        """
        ตรวจสอบว่าไฟล์มีอยู่หรือไม่
        
        Args:
            file_path: Path ไปยังไฟล์
            
        Returns:
            bool: True ถ้าไฟล์มีอยู่
        """
        try:
            return Path(file_path).exists()
        except Exception:
            return False
    
    async def save_uploaded_file(self, file_content: bytes, filename: str) -> str:
        """
        บันทึกไฟล์ที่อัปโหลด
        
        Args:
            file_content: เนื้อหาไฟล์ (bytes)
            filename: ชื่อไฟล์
            
        Returns:
            str: Path ไปยังไฟล์ที่บันทึก
        """
        try:
            import uuid
            upload_dir = Path("uploads")
            upload_dir.mkdir(exist_ok=True)
            
            # สร้าง unique filename
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = upload_dir / unique_filename
            
            # บันทึกไฟล์
            file_path.write_bytes(file_content)
            
            logger.info(f"✅ Saved uploaded file: {file_path}")
            return str(file_path)
        except Exception as e:
            logger.error(f"❌ Error saving uploaded file: {e}", exc_info=True)
            raise
    
    def get_filename_from_url(self, url: str) -> Optional[str]:
        """
        ดึงชื่อไฟล์จาก URL
        
        Args:
            url: URL ของไฟล์
            
        Returns:
            str: ชื่อไฟล์หรือ None
        """
        try:
            from urllib.parse import urlparse
            import os
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            return filename if filename else None
        except Exception:
            return None
    
    def get_file_info(self, file_path: str) -> dict:
        """
        ดึงข้อมูลไฟล์
        
        Args:
            file_path: Path ไปยังไฟล์
            
        Returns:
            dict: ข้อมูลไฟล์ (file_size, file_type, duration, etc.)
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return {
                    "file_size": 0,
                    "file_type": "unknown",
                    "duration": None
                }
            
            file_size = path.stat().st_size
            file_type = self.get_file_type(file_path)
            
            # ดึง duration ถ้าเป็นวิดีโอหรือเสียง
            duration = None
            if file_type in ['video', 'audio']:
                try:
                    import ffmpeg
                    probe = ffmpeg.probe(str(file_path))
                    duration = float(probe['format'].get('duration', 0))
                except Exception:
                    pass
            
            return {
                "file_size": file_size,
                "file_type": file_type or "unknown",
                "duration": duration
            }
        except Exception as e:
            logger.error(f"❌ Error getting file info: {e}", exc_info=True)
            return {
                "file_size": 0,
                "file_type": "unknown",
                "duration": None
            }

