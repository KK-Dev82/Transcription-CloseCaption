#!/usr/bin/env python3
"""
Script สำหรับ cleanup ไฟล์ใน uploads directory
ให้เหลือแค่ไฟล์ที่ระบุ
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from app.utils.storage_factory import get_storage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ไฟล์ที่ต้องการเก็บ
KEEP_FILES = [
    "f8f3d293-ba60-41c5-9054-09725a3a22fb_v30-1.wav",
    "fd08afc7-0060-43ac-a95a-7c697b8aca04_v30-1.mp4"
]

def cleanup_uploads():
    """ลบไฟล์ทั้งหมดยกเว้นไฟล์ที่ระบุ"""
    upload_dir = Path("uploads")
    
    if not upload_dir.exists():
        logger.error("ไม่พบโฟลเดอร์ uploads")
        return
    
    # หาไฟล์ทั้งหมด
    all_files = list(upload_dir.iterdir())
    files_to_delete = []
    files_to_keep = []
    
    for file_path in all_files:
        if not file_path.is_file():
            continue
        
        if file_path.name in KEEP_FILES:
            files_to_keep.append(file_path)
        else:
            files_to_delete.append(file_path)
    
    logger.info(f"พบไฟล์ทั้งหมด: {len(all_files)}")
    logger.info(f"ไฟล์ที่จะเก็บ: {len(files_to_keep)}")
    logger.info(f"ไฟล์ที่จะลบ: {len(files_to_delete)}")
    
    # แสดงไฟล์ที่จะเก็บ
    logger.info("\nไฟล์ที่จะเก็บ:")
    for f in files_to_keep:
        logger.info(f"  ✅ {f.name} ({f.stat().st_size / (1024*1024):.2f} MB)")
    
    # ถามยืนยัน
    print(f"\n⚠️  จะลบไฟล์ {len(files_to_delete)} ไฟล์")
    print("ไฟล์ที่จะเก็บ:")
    for f in files_to_keep:
        print(f"  - {f.name}")
    
    confirm = input("\nยืนยันการลบ? (yes/no): ").strip().lower()
    if confirm != "yes":
        logger.info("ยกเลิกการลบ")
        return
    
    # ลบไฟล์
    deleted_count = 0
    deleted_size = 0
    errors = []
    
    for file_path in files_to_delete:
        try:
            file_size = file_path.stat().st_size
            file_path.unlink()
            deleted_count += 1
            deleted_size += file_size
            logger.info(f"✅ ลบ: {file_path.name} ({file_size / (1024*1024):.2f} MB)")
        except Exception as e:
            error_msg = f"❌ ไม่สามารถลบ {file_path.name}: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
    
    logger.info(f"\n✅ ลบไฟล์เสร็จสิ้น: {deleted_count} ไฟล์ ({deleted_size / (1024*1024*1024):.2f} GB)")
    
    if errors:
        logger.warning(f"⚠️  มีข้อผิดพลาด {len(errors)} รายการ")
        for error in errors[:10]:  # แสดงแค่ 10 รายการแรก
            logger.warning(f"  {error}")
    
    # อัปเดต database (soft delete ไฟล์ที่ถูกลบ)
    try:
        storage = get_storage()
        if hasattr(storage, 'list_uploaded_files'):
            logger.info("\n🔄 อัปเดต database...")
            
            # หาไฟล์ใน database ที่ถูกลบไปแล้ว
            all_db_files = storage.list_uploaded_files(limit=10000)
            db_deleted = 0
            
            for db_file in all_db_files:
                file_path = db_file.get("file_path")
                if not file_path:
                    continue
                
                file_name = Path(file_path).name
                if file_name not in KEEP_FILES:
                    # Soft delete ใน database
                    file_id = db_file.get("id")
                    if file_id:
                        try:
                            storage.delete_uploaded_file(file_id, soft_delete=True)
                            db_deleted += 1
                        except Exception as e:
                            logger.warning(f"⚠️  ไม่สามารถ soft delete {file_name} ใน database: {e}")
            
            logger.info(f"✅ อัปเดต database: soft delete {db_deleted} records")
    except Exception as e:
        logger.warning(f"⚠️  ไม่สามารถอัปเดต database: {e}")
    
    logger.info("\n✅ Cleanup เสร็จสิ้น!")

if __name__ == "__main__":
    cleanup_uploads()
