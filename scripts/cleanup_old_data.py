#!/usr/bin/env python3
"""
Cleanup Script: ลบข้อมูลเก่าและไฟล์ชั่วคราว
- ลบ JSON storage เก่า (ถ้าไม่ต้องการเก็บ)
- ลบ wav files ใน uploads/tmp
- ลบ temp folders
"""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def cleanup_json_storage(storage_dir: str, dry_run: bool = False) -> dict:
    """ลบ JSON storage เก่า"""
    stats = {
        'folders_deleted': 0,
        'files_deleted': 0,
        'size_freed_mb': 0
    }
    
    storage_path = Path(storage_dir)
    transcriptions_dir = storage_path / "transcriptions"
    
    if not transcriptions_dir.exists():
        logger.info("📁 No transcriptions directory found")
        return stats
    
    logger.info(f"🧹 Cleaning up JSON storage: {transcriptions_dir}")
    
    # ลบทุกโฟลเดอร์ใน transcriptions
    for task_folder in transcriptions_dir.iterdir():
        if task_folder.is_dir():
            try:
                # คำนวณขนาดก่อนลบ
                size = sum(f.stat().st_size for f in task_folder.rglob('*') if f.is_file())
                size_mb = size / (1024 * 1024)
                
                if dry_run:
                    logger.info(f"  [DRY RUN] Would delete: {task_folder} ({size_mb:.2f} MB)")
                else:
                    shutil.rmtree(task_folder)
                    stats['folders_deleted'] += 1
                    stats['files_deleted'] += sum(1 for _ in task_folder.rglob('*') if _.is_file())
                    stats['size_freed_mb'] += size_mb
                    logger.info(f"  ✅ Deleted: {task_folder} ({size_mb:.2f} MB)")
            except Exception as e:
                logger.error(f"  ❌ Failed to delete {task_folder}: {e}")
    
    # ลบไฟล์ JSON เก่า (backward compatibility)
    for json_file in transcriptions_dir.glob("*.json"):
        try:
            size = json_file.stat().st_size
            size_mb = size / (1024 * 1024)
            
            if dry_run:
                logger.info(f"  [DRY RUN] Would delete: {json_file} ({size_mb:.2f} MB)")
            else:
                json_file.unlink()
                stats['files_deleted'] += 1
                stats['size_freed_mb'] += size_mb
                logger.info(f"  ✅ Deleted: {json_file} ({size_mb:.2f} MB)")
        except Exception as e:
            logger.error(f"  ❌ Failed to delete {json_file}: {e}")
    
    return stats

def cleanup_wav_files(uploads_dir: str, temp_dir: str = None, dry_run: bool = False) -> dict:
    """ลบ wav files ใน uploads/tmp และ temp folders"""
    stats = {
        'wav_files_deleted': 0,
        'temp_folders_deleted': 0,
        'size_freed_mb': 0
    }
    
    # ลบ wav files ใน uploads/tmp
    uploads_path = Path(uploads_dir)
    tmp_dir = uploads_path / "tmp"
    
    if tmp_dir.exists():
        logger.info(f"🧹 Cleaning up wav files in: {tmp_dir}")
        for wav_file in tmp_dir.rglob("*.wav"):
            try:
                size = wav_file.stat().st_size
                size_mb = size / (1024 * 1024)
                
                if dry_run:
                    logger.info(f"  [DRY RUN] Would delete: {wav_file} ({size_mb:.2f} MB)")
                else:
                    wav_file.unlink()
                    stats['wav_files_deleted'] += 1
                    stats['size_freed_mb'] += size_mb
                    logger.info(f"  ✅ Deleted: {wav_file} ({size_mb:.2f} MB)")
            except Exception as e:
                logger.error(f"  ❌ Failed to delete {wav_file}: {e}")
    
    # ลบ temp folders (uploads/temp หรือ temp_dir)
    temp_paths = []
    if temp_dir:
        temp_paths.append(Path(temp_dir))
    if (uploads_path / "temp").exists():
        temp_paths.append(uploads_path / "temp")
    
    for temp_path in temp_paths:
        if temp_path.exists():
            logger.info(f"🧹 Cleaning up temp folders in: {temp_path}")
            for temp_folder in temp_path.iterdir():
                if temp_folder.is_dir():
                    try:
                        # คำนวณขนาดก่อนลบ
                        size = sum(f.stat().st_size for f in temp_folder.rglob('*') if f.is_file())
                        size_mb = size / (1024 * 1024)
                        
                        if dry_run:
                            logger.info(f"  [DRY RUN] Would delete: {temp_folder} ({size_mb:.2f} MB)")
                        else:
                            shutil.rmtree(temp_folder)
                            stats['temp_folders_deleted'] += 1
                            stats['size_freed_mb'] += size_mb
                            logger.info(f"  ✅ Deleted: {temp_folder} ({size_mb:.2f} MB)")
                    except Exception as e:
                        logger.error(f"  ❌ Failed to delete {temp_folder}: {e}")
    
    return stats

def main():
    parser = argparse.ArgumentParser(description='Cleanup old data and temporary files')
    parser.add_argument('--storage-dir', default='storage', help='Storage directory')
    parser.add_argument('--uploads-dir', default='uploads', help='Uploads directory')
    parser.add_argument('--temp-dir', default='temp', help='Temp directory')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (no actual deletion)')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No files will be deleted")
    
    total_stats = {
        'folders_deleted': 0,
        'files_deleted': 0,
        'wav_files_deleted': 0,
        'temp_folders_deleted': 0,
        'size_freed_mb': 0
    }
    
    # Cleanup JSON storage
    logger.info("=" * 80)
    logger.info("📦 Cleaning up JSON storage...")
    logger.info("=" * 80)
    json_stats = cleanup_json_storage(args.storage_dir, args.dry_run)
    total_stats['folders_deleted'] += json_stats['folders_deleted']
    total_stats['files_deleted'] += json_stats['files_deleted']
    total_stats['size_freed_mb'] += json_stats['size_freed_mb']
    
    # Cleanup wav files and temp folders
    logger.info("=" * 80)
    logger.info("🎵 Cleaning up wav files and temp folders...")
    logger.info("=" * 80)
    wav_stats = cleanup_wav_files(args.uploads_dir, args.temp_dir, args.dry_run)
    total_stats['wav_files_deleted'] += wav_stats['wav_files_deleted']
    total_stats['temp_folders_deleted'] += wav_stats['temp_folders_deleted']
    total_stats['size_freed_mb'] += wav_stats['size_freed_mb']
    
    # Summary
    logger.info("=" * 80)
    logger.info("📊 Cleanup Summary")
    logger.info("=" * 80)
    logger.info(f"  Folders deleted: {total_stats['folders_deleted']}")
    logger.info(f"  Files deleted: {total_stats['files_deleted']}")
    logger.info(f"  WAV files deleted: {total_stats['wav_files_deleted']}")
    logger.info(f"  Temp folders deleted: {total_stats['temp_folders_deleted']}")
    logger.info(f"  Total size freed: {total_stats['size_freed_mb']:.2f} MB")
    
    if args.dry_run:
        logger.info("\n🔍 This was a DRY RUN - No files were actually deleted")
        logger.info("   Run without --dry-run to perform actual cleanup")

if __name__ == '__main__':
    main()

