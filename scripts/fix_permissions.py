#!/usr/bin/env python3
"""
Script สำหรับแก้ไข permission ของไฟล์ใน staging server
"""

import os
import stat
from pathlib import Path
import logging

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_file_permissions(directory: str = "uploads"):
    """แก้ไข permission ของไฟล์ใน directory"""
    uploads_dir = Path(directory)
    
    if not uploads_dir.exists():
        logger.error(f"Directory {directory} does not exist")
        return
    
    # ตั้งค่า permission ของ directory
    try:
        os.chmod(uploads_dir, 0o755)  # rwxr-xr-x
        logger.info(f"Set directory permission for: {uploads_dir}")
    except Exception as e:
        logger.warning(f"Failed to set directory permission: {e}")
    
    # แก้ไข permission ของไฟล์ทั้งหมด
    fixed_count = 0
    error_count = 0
    
    for file_path in uploads_dir.iterdir():
        if file_path.is_file():
            try:
                # ตั้งค่า permission เป็น 644 (rw-r--r--)
                os.chmod(file_path, 0o644)
                logger.info(f"Fixed permission for: {file_path.name}")
                fixed_count += 1
            except Exception as e:
                logger.error(f"Failed to fix permission for {file_path.name}: {e}")
                error_count += 1
    
    logger.info(f"Permission fix completed: {fixed_count} files fixed, {error_count} errors")

def fix_storage_permissions():
    """แก้ไข permission ของ storage directory"""
    storage_dirs = ["storage", "storage/transcriptions", "storage/captions", "storage/videos", "storage/metadata"]
    
    for dir_path in storage_dirs:
        path = Path(dir_path)
        if path.exists():
            try:
                # ตั้งค่า permission ของ directory
                os.chmod(path, 0o755)  # rwxr-xr-x
                logger.info(f"Set directory permission for: {path}")
                
                # แก้ไข permission ของไฟล์ทั้งหมดใน directory
                if path.is_dir():
                    for file_path in path.rglob("*"):
                        if file_path.is_file():
                            try:
                                os.chmod(file_path, 0o644)  # rw-r--r--
                                logger.info(f"Fixed permission for: {file_path}")
                            except Exception as e:
                                logger.warning(f"Failed to fix permission for {file_path}: {e}")
            except Exception as e:
                logger.warning(f"Failed to set directory permission for {path}: {e}")

def main():
    """Main function"""
    logger.info("Starting permission fix...")
    
    # แก้ไข permission ของ uploads directory
    fix_file_permissions("uploads")
    
    # แก้ไข permission ของ temp directory
    fix_file_permissions("temp")
    
    # แก้ไข permission ของ storage directories
    fix_storage_permissions()
    
    logger.info("Permission fix completed!")

if __name__ == "__main__":
    main()
