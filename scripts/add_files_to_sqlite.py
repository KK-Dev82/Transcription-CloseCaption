#!/usr/bin/env python3
"""
Script สำหรับเพิ่มไฟล์ที่เหลืออยู่ใน uploads directory ลงใน SQLite database
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from app.utils.storage_factory import get_storage
from app.services.file_service import FileService
from app.services.video_service import VideoService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ไฟล์ที่ต้องการเพิ่ม
FILES_TO_ADD = [
    "f8f3d293-ba60-41c5-9054-09725a3a22fb_v30-1.wav",
    "fd08afc7-0060-43ac-a95a-7c697b8aca04_v30-1.mp4"
]

def add_files_to_sqlite():
    """เพิ่มไฟล์ลงใน SQLite database"""
    upload_dir = Path("uploads")
    
    if not upload_dir.exists():
        logger.error("ไม่พบโฟลเดอร์ uploads")
        return
    
    # ตรวจสอบว่า storage รองรับ SQLite หรือไม่
    storage = get_storage()
    if not hasattr(storage, 'save_uploaded_file'):
        logger.error("Storage backend ไม่รองรับ save_uploaded_file method")
        logger.info(f"Storage type: {type(storage).__name__}")
        return
    
    file_service = FileService()
    video_service = VideoService()
    
    added_count = 0
    errors = []
    
    for filename in FILES_TO_ADD:
        file_path = upload_dir / filename
        
        if not file_path.exists():
            logger.warning(f"⚠️  ไม่พบไฟล์: {filename}")
            errors.append(f"File not found: {filename}")
            continue
        
        try:
            logger.info(f"📝 กำลังเพิ่มไฟล์: {filename}")
            
            # ดึงข้อมูลไฟล์
            stat = file_path.stat()
            is_video = file_service.is_video_file(str(file_path))
            is_audio = file_service.is_audio_file(str(file_path))
            
            if not (is_video or is_audio):
                logger.warning(f"⚠️  ไฟล์ไม่ใช่ video หรือ audio: {filename}")
                errors.append(f"Not a video/audio file: {filename}")
                continue
            
            file_type = "video" if is_video else "audio"
            duration_seconds = 0
            duration_minutes = 0
            duration_formatted = "0:00"
            video_info = None
            audio_info = None
            
            # ดึงข้อมูลวิดีโอหรือ audio
            if is_video:
                logger.info(f"  📹 ดึงข้อมูลวิดีโอ...")
                video_info = video_service.get_video_info(str(file_path))
                duration_seconds = video_info.get("duration", 0)
                logger.info(f"  ✅ Duration: {duration_seconds:.2f} วินาที")
            elif is_audio:
                logger.info(f"  🎵 ดึงข้อมูล audio...")
                file_info = file_service.get_file_info(str(file_path))
                duration_seconds = file_info.get("duration", 0) or 0
                
                # ดึงข้อมูล audio เพิ่มเติมด้วย ffmpeg
                try:
                    import ffmpeg
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
                        logger.info(f"  ✅ Audio codec: {audio_info['audio_codec']}, Sample rate: {audio_info['sample_rate']} Hz")
                except Exception as e:
                    logger.warning(f"  ⚠️  ไม่สามารถดึงข้อมูล audio stream: {e}")
            
            # คำนวณ duration
            duration_minutes = round(duration_seconds / 60, 2) if duration_seconds > 0 else 0
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            duration_formatted = f"{minutes}:{seconds:02d}"
            
            # บันทึกลง database
            file_id = storage.save_uploaded_file(
                filename=filename,
                file_path=str(file_path),
                file_type=file_type,
                file_size=stat.st_size,
                duration=duration_seconds,
                duration_minutes=duration_minutes,
                duration_formatted=duration_formatted,
                video_info=video_info,
                audio_info=audio_info
            )
            
            logger.info(f"  ✅ เพิ่มไฟล์สำเร็จ: {filename} (ID: {file_id}, Duration: {duration_formatted}, Size: {stat.st_size / (1024*1024):.2f} MB)")
            added_count += 1
            
        except Exception as e:
            error_msg = f"❌ ไม่สามารถเพิ่มไฟล์ {filename}: {e}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
    
    logger.info(f"\n✅ เพิ่มไฟล์เสร็จสิ้น: {added_count} ไฟล์")
    
    if errors:
        logger.warning(f"⚠️  มีข้อผิดพลาด {len(errors)} รายการ:")
        for error in errors:
            logger.warning(f"  {error}")
    
    # ตรวจสอบข้อมูลใน database
    if hasattr(storage, 'list_uploaded_files'):
        logger.info("\n📊 ตรวจสอบข้อมูลใน database...")
        all_files = storage.list_uploaded_files(limit=100)
        logger.info(f"  พบไฟล์ใน database: {len(all_files)} ไฟล์")
        for f in all_files:
            logger.info(f"  - {f.get('filename')} ({f.get('file_type')}, {f.get('duration_formatted')})")

if __name__ == "__main__":
    add_files_to_sqlite()
