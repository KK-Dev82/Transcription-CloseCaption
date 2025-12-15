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
        # Temporary files management: default ไม่เก็บไฟล์ชั่วคราว
        self.save_temp_files = os.getenv('SAVE_TEMP_FILES', 'not_save').lower() == 'save'
        self._ensure_directories()
    
    def _ensure_directories(self):
        """สร้างโฟลเดอร์ที่จำเป็น"""
        self.upload_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
        # สร้าง uploads/tmp สำหรับ wav files
        (self.upload_dir / "tmp").mkdir(exist_ok=True)
    
    async def save_uploaded_file(self, file_content: bytes, filename: str) -> str:
        """บันทึกไฟล์ที่อัปโหลด"""
        file_id = str(uuid.uuid4())
        file_path = self.upload_dir / f"{file_id}_{filename}"
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        # ตั้งค่า permission ให้ไฟล์สามารถอ่านได้
        try:
            os.chmod(file_path, 0o644)  # rw-r--r--
            logger.info(f"Set file permission for: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to set file permission: {e}")
        
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
    
    def create_chunks(self, file_path: str, chunk_duration: int = 30) -> List[Dict[str, any]]:
        """แบ่งไฟล์เป็น chunks พร้อม metadata (start_time, end_time)"""
        chunks = []
        file_info = self.get_file_info(file_path)
        duration = file_info.get("duration")
        
        if not duration:
            # ถ้าไม่สามารถดึง duration ได้ ให้ใช้ไฟล์เดียว
            return [{"path": file_path, "start_time": 0.0, "end_time": duration or 0.0, "chunk_index": 0, "duration": duration or 0.0}]
        
        num_chunks = int(duration // chunk_duration) + 1
        
        # สร้าง temp directory แยกตาม timestamp
        import time
        task_folder = f"task_{int(time.time())}_{Path(file_path).stem}"
        temp_task_dir = self.temp_dir / task_folder
        temp_task_dir.mkdir(parents=True, exist_ok=True)
        
        for i in range(num_chunks):
            start_time = i * chunk_duration
            end_time = min((i + 1) * chunk_duration, duration)
            
            chunk_path = temp_task_dir / f"chunk_{i}_{Path(file_path).name}"
            
            try:
                # ใช้ FFmpeg ตัดไฟล์
                stream = ffmpeg.input(file_path, ss=start_time, t=end_time-start_time)
                # ใช้ 48kHz แทน 16kHz เพื่อให้คุณภาพดีขึ้น (Whisper จะ downsample เอง)
                stream = ffmpeg.output(stream, str(chunk_path), acodec='pcm_s16le', ar=48000)
                ffmpeg.run(stream, overwrite_output=True, quiet=True)
                
                # ตรวจสอบ duration จริงของไฟล์ chunk
                actual_duration = end_time - start_time
                if chunk_path.exists():
                    try:
                        chunk_probe = ffmpeg.probe(str(chunk_path))
                        actual_duration = float(chunk_probe['format'].get('duration', actual_duration))
                    except Exception:
                        pass  # ใช้ calculated duration ถ้า probe ไม่ได้
                
                chunks.append({
                    "path": str(chunk_path),
                    "start_time": start_time,
                    "end_time": start_time + actual_duration,  # ใช้ actual_duration เพื่อความแม่นยำ
                    "chunk_index": i,
                    "duration": actual_duration
                })
                
                logger.debug(f"สร้าง chunk {i+1}: {start_time}s - {start_time + actual_duration:.2f}s (duration: {actual_duration:.2f}s)")
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการสร้าง chunk {i}: {e}")
                continue
        
        return chunks
    
    def extract_audio(self, video_path: str) -> str:
        """แยกเสียงจากวิดีโอ"""
        # สร้าง temp directory แยกตาม timestamp
        import time
        task_folder = f"task_{int(time.time())}_{Path(video_path).stem}"
        temp_task_dir = self.temp_dir / task_folder
        temp_task_dir.mkdir(parents=True, exist_ok=True)
        
        audio_path = temp_task_dir / f"{Path(video_path).stem}_audio.wav"
        
        try:
            stream = ffmpeg.input(video_path)
            # ใช้ 48kHz แทน 16kHz เพื่อให้คุณภาพดีขึ้น (Whisper จะ downsample เอง)
            stream = ffmpeg.output(stream, str(audio_path), acodec='pcm_s16le', ar=48000)
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            return str(audio_path)
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแยกเสียง: {e}")
            raise
    
    def cleanup_temp_files(self, file_paths: List[str]):
        """ลบไฟล์ชั่วคราว (ถ้า SAVE_TEMP_FILES=not_save)"""
        if self.save_temp_files:
            logger.debug(f"💾 Keeping temp files (SAVE_TEMP_FILES=save): {len(file_paths)} files")
            return
        
        for file_path in file_paths:
            try:
                Path(file_path).unlink(missing_ok=True)
                logger.info(f"🧹 ลบไฟล์ temp: {file_path}")
            except Exception as e:
                logger.warning(f"⚠️ ไม่สามารถลบไฟล์ {file_path}: {e}")
    
    def cleanup_temp_folder(self, folder_path: str):
        """ลบ temp folder ทั้งหมด (ถ้า SAVE_TEMP_FILES=not_save)"""
        if self.save_temp_files:
            logger.debug(f"💾 Keeping temp folder (SAVE_TEMP_FILES=save): {folder_path}")
            return
        
        try:
            folder = Path(folder_path)
            if folder.exists() and folder.is_dir():
                import shutil
                shutil.rmtree(folder)
                logger.info(f"🧹 ลบ temp folder: {folder_path}")
        except Exception as e:
            logger.warning(f"⚠️ ไม่สามารถลบ temp folder {folder_path}: {e}")
    
    def cleanup_wav_files_in_uploads_tmp(self):
        """ลบ wav files ใน uploads/tmp (ถ้า SAVE_TEMP_FILES=not_save)"""
        if self.save_temp_files:
            logger.debug("💾 Keeping wav files in uploads/tmp (SAVE_TEMP_FILES=save)")
            return
        
        tmp_dir = self.upload_dir / "tmp"
        if not tmp_dir.exists():
            return
        
        wav_files = list(tmp_dir.rglob("*.wav"))
        deleted_count = 0
        for wav_file in wav_files:
            try:
                wav_file.unlink()
                deleted_count += 1
                logger.debug(f"🧹 ลบ wav file: {wav_file}")
            except Exception as e:
                logger.warning(f"⚠️ ไม่สามารถลบ wav file {wav_file}: {e}")
        
        if deleted_count > 0:
            logger.info(f"🧹 ลบ wav files ใน uploads/tmp: {deleted_count} files")
    
    def cleanup_old_temp_folders(self, max_age_hours: int = 24):
        """ลบ temp folders ที่เก่าเกิน max_age_hours"""
        try:
            temp_dir = Path("temp")
            if not temp_dir.exists():
                return
            
            import time
            current_time = time.time()
            
            for folder in temp_dir.iterdir():
                if folder.is_dir() and folder.name.startswith("task_"):
                    try:
                        # แยก timestamp จากชื่อ folder
                        timestamp_str = folder.name.split("_")[1]
                        folder_time = float(timestamp_str)
                        
                        # ตรวจสอบอายุ
                        age_hours = (current_time - folder_time) / 3600
                        
                        if age_hours > max_age_hours:
                            import shutil
                            shutil.rmtree(folder)
                            logger.info(f"ลบ temp folder เก่า: {folder} (อายุ: {age_hours:.1f} ชั่วโมง)")
                    except (ValueError, IndexError) as e:
                        logger.warning(f"ไม่สามารถแยก timestamp จาก folder {folder.name}: {e}")
                        
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการลบ temp folders เก่า: {e}")
    
    def is_video_file(self, file_path: str) -> bool:
        """ตรวจสอบว่าเป็นไฟล์วิดีโอหรือไม่"""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
        return Path(file_path).suffix.lower() in video_extensions
    
    def is_audio_file(self, file_path: str) -> bool:
        """ตรวจสอบว่าเป็นไฟล์เสียงหรือไม่"""
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
        return Path(file_path).suffix.lower() in audio_extensions 