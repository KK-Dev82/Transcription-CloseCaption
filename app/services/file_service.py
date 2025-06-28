import os
import uuid
import aiofiles
import ffmpeg
from typing import List, Tuple, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FileService:
    def __init__(self, upload_dir: str = "uploads", temp_dir: str = "temp"):
        self.upload_dir = Path(upload_dir)
        self.temp_dir = Path(temp_dir)
        self._ensure_directories()
    
    def _ensure_directories(self):
        """สร้างโฟลเดอร์ที่จำเป็น"""
        self.upload_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
    
    async def save_uploaded_file(self, file_content: bytes, filename: str) -> str:
        """บันทึกไฟล์ที่อัปโหลด"""
        file_id = str(uuid.uuid4())
        file_path = self.upload_dir / f"{file_id}_{filename}"
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        return str(file_path)
    
    def get_file_info(self, file_path: str) -> dict:
        """ดึงข้อมูลไฟล์"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"ไฟล์ไม่พบ: {file_path}")
        
        info = {
            "file_size": path.stat().st_size,
            "file_type": path.suffix.lower(),
            "duration": None
        }
        
        # ดึงความยาวของวิดีโอ/เสียง
        try:
            probe = ffmpeg.probe(file_path)
            if 'duration' in probe['format']:
                info["duration"] = float(probe['format']['duration'])
        except Exception as e:
            logger.warning(f"ไม่สามารถดึงข้อมูลไฟล์ได้: {e}")
        
        return info
    
    def create_chunks(self, file_path: str, chunk_duration: int = 30) -> List[str]:
        """แบ่งไฟล์เป็น chunks"""
        chunks = []
        file_info = self.get_file_info(file_path)
        duration = file_info.get("duration")
        
        if not duration:
            # ถ้าไม่สามารถดึง duration ได้ ให้ใช้ไฟล์เดียว
            return [file_path]
        
        num_chunks = int(duration // chunk_duration) + 1
        
        for i in range(num_chunks):
            start_time = i * chunk_duration
            end_time = min((i + 1) * chunk_duration, duration)
            
            chunk_path = self.temp_dir / f"chunk_{i}_{Path(file_path).name}"
            
            try:
                # ใช้ FFmpeg ตัดไฟล์
                stream = ffmpeg.input(file_path, ss=start_time, t=end_time-start_time)
                stream = ffmpeg.output(stream, str(chunk_path), acodec='pcm_s16le', ar=16000)
                ffmpeg.run(stream, overwrite_output=True, quiet=True)
                
                chunks.append(str(chunk_path))
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการสร้าง chunk {i}: {e}")
                continue
        
        return chunks
    
    def extract_audio(self, video_path: str) -> str:
        """แยกเสียงจากวิดีโอ"""
        audio_path = self.temp_dir / f"{Path(video_path).stem}_audio.wav"
        
        try:
            stream = ffmpeg.input(video_path)
            stream = ffmpeg.output(stream, str(audio_path), acodec='pcm_s16le', ar=16000)
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            return str(audio_path)
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแยกเสียง: {e}")
            raise
    
    def cleanup_temp_files(self, file_paths: List[str]):
        """ลบไฟล์ชั่วคราว"""
        for file_path in file_paths:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"ไม่สามารถลบไฟล์ {file_path}: {e}")
    
    def is_video_file(self, file_path: str) -> bool:
        """ตรวจสอบว่าเป็นไฟล์วิดีโอหรือไม่"""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
        return Path(file_path).suffix.lower() in video_extensions
    
    def is_audio_file(self, file_path: str) -> bool:
        """ตรวจสอบว่าเป็นไฟล์เสียงหรือไม่"""
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
        return Path(file_path).suffix.lower() in audio_extensions 