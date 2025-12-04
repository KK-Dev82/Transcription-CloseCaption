"""
Cleanup Service for Phase 5: Auto-cleanup temp files, monitor disk space, and periodic cleanup

Features:
- Periodic cleanup scheduler
- Disk space monitoring
- Auto-cleanup temp files
"""

import asyncio
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class CleanupService:
    """Service สำหรับ cleanup และ monitoring disk space"""
    
    def __init__(self):
        self.file_service = None  # Lazy load to avoid circular import
        self.cleanup_interval_seconds = int(os.getenv('CLEANUP_INTERVAL_SECONDS', '3600'))  # Default: 1 hour
        self.temp_folder_max_age_hours = int(os.getenv('TEMP_FOLDER_MAX_AGE_HOURS', '24'))
        self.disk_space_warning_threshold_gb = float(os.getenv('DISK_SPACE_WARNING_THRESHOLD_GB', '10.0'))
        self.disk_space_critical_threshold_gb = float(os.getenv('DISK_SPACE_CRITICAL_THRESHOLD_GB', '5.0'))
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
    def _get_file_service(self):
        """Lazy load FileService to avoid circular import"""
        if self.file_service is None:
            from .file_service import FileService
            self.file_service = FileService()
        return self.file_service
    
    def get_disk_usage(self, path: str = "/") -> Dict[str, float]:
        """
        ตรวจสอบ disk space usage
        
        Args:
            path: Path ที่ต้องการตรวจสอบ (default: root /)
            
        Returns:
            Dict with keys: total_gb, used_gb, free_gb, percent_used
        """
        try:
            stat = shutil.disk_usage(path)
            total_gb = stat.total / (1024 ** 3)
            used_gb = stat.used / (1024 ** 3)
            free_gb = stat.free / (1024 ** 3)
            percent_used = (stat.used / stat.total) * 100
            
            return {
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2),
                "free_gb": round(free_gb, 2),
                "percent_used": round(percent_used, 2),
                "path": path,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Error getting disk usage for {path}: {e}")
            return {
                "error": str(e),
                "path": path,
                "timestamp": datetime.now().isoformat()
            }
    
    def check_disk_space(self, path: str = "/") -> Tuple[bool, str, Dict[str, float]]:
        """
        ตรวจสอบ disk space และ return status
        
        Args:
            path: Path ที่ต้องการตรวจสอบ
            
        Returns:
            Tuple of (is_critical, warning_message, disk_usage_dict)
        """
        disk_usage = self.get_disk_usage(path)
        
        if "error" in disk_usage:
            return False, f"Error checking disk space: {disk_usage['error']}", disk_usage
        
        free_gb = disk_usage.get("free_gb", 0)
        percent_used = disk_usage.get("percent_used", 0)
        
        is_critical = False
        warning_msg = None
        
        if free_gb < self.disk_space_critical_threshold_gb:
            is_critical = True
            warning_msg = (
                f"⚠️ CRITICAL: Disk space is low! "
                f"Free: {free_gb:.2f} GB (Critical threshold: {self.disk_space_critical_threshold_gb} GB). "
                f"Used: {percent_used:.1f}%"
            )
        elif free_gb < self.disk_space_warning_threshold_gb:
            warning_msg = (
                f"⚠️ WARNING: Disk space is getting low. "
                f"Free: {free_gb:.2f} GB (Warning threshold: {self.disk_space_warning_threshold_gb} GB). "
                f"Used: {percent_used:.1f}%"
            )
        else:
            warning_msg = (
                f"✅ Disk space OK. Free: {free_gb:.2f} GB, Used: {percent_used:.1f}%"
            )
        
        return is_critical, warning_msg, disk_usage
    
    def cleanup_old_temp_folders(self, max_age_hours: Optional[int] = None) -> Dict[str, int]:
        """
        ลบ temp folders ที่เก่าเกิน max_age_hours
        
        Args:
            max_age_hours: อายุสูงสุดของ temp folder (ชั่วโมง)
                          ถ้า None จะใช้ค่า default จาก env
            
        Returns:
            Dict with cleanup statistics
        """
        if max_age_hours is None:
            max_age_hours = self.temp_folder_max_age_hours
        
        file_service = self._get_file_service()
        deleted_count = 0
        total_size_freed = 0
        errors = []
        
        try:
            temp_dir = Path("temp")
            if not temp_dir.exists():
                logger.debug(f"Temp directory does not exist: {temp_dir}")
                return {
                    "deleted_count": 0,
                    "total_size_freed_bytes": 0,
                    "total_size_freed_gb": 0.0,
                    "errors": []
                }
            
            current_time = time.time()
            
            for folder in temp_dir.iterdir():
                if not folder.is_dir():
                    continue
                
                try:
                    # ตรวจสอบอายุของ folder
                    # รองรับทั้งรูปแบบ "task_TIMESTAMP_NAME" และ mtime
                    folder_name = folder.name
                    folder_time = None
                    
                    # ลองแยก timestamp จากชื่อ folder (รูปแบบ: task_TIMESTAMP_NAME)
                    if folder_name.startswith("task_"):
                        try:
                            parts = folder_name.split("_")
                            if len(parts) >= 2:
                                timestamp_str = parts[1]
                                folder_time = float(timestamp_str)
                        except (ValueError, IndexError):
                            pass
                    
                    # ถ้าไม่ได้ timestamp จากชื่อ ให้ใช้ mtime
                    if folder_time is None:
                        folder_time = folder.stat().st_mtime
                    
                    # ตรวจสอบอายุ
                    age_hours = (current_time - folder_time) / 3600
                    
                    if age_hours > max_age_hours:
                        # คำนวณขนาดก่อนลบ
                        folder_size = self._get_folder_size(folder)
                        
                        # ลบ folder
                        shutil.rmtree(folder)
                        deleted_count += 1
                        total_size_freed += folder_size
                        
                        logger.info(
                            f"🧹 Deleted old temp folder: {folder_name} "
                            f"(age: {age_hours:.1f}h, size: {folder_size / (1024**2):.2f} MB)"
                        )
                        
                except Exception as e:
                    error_msg = f"Error deleting folder {folder.name}: {e}"
                    errors.append(error_msg)
                    logger.warning(f"⚠️ {error_msg}")
            
            total_size_freed_gb = total_size_freed / (1024 ** 3)
            
            if deleted_count > 0:
                logger.info(
                    f"✅ Cleanup completed: Deleted {deleted_count} temp folders, "
                    f"freed {total_size_freed_gb:.2f} GB"
                )
            
            return {
                "deleted_count": deleted_count,
                "total_size_freed_bytes": total_size_freed,
                "total_size_freed_gb": round(total_size_freed_gb, 2),
                "errors": errors,
                "max_age_hours": max_age_hours
            }
            
        except Exception as e:
            error_msg = f"Error during cleanup: {e}"
            logger.error(f"❌ {error_msg}")
            return {
                "deleted_count": 0,
                "total_size_freed_bytes": 0,
                "total_size_freed_gb": 0.0,
                "errors": [error_msg]
            }
    
    def _get_folder_size(self, folder_path: Path) -> int:
        """คำนวณขนาดของ folder (bytes)"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for filename in filenames:
                    filepath = Path(dirpath) / filename
                    try:
                        total_size += filepath.stat().st_size
                    except (OSError, FileNotFoundError):
                        pass
        except Exception as e:
            logger.warning(f"⚠️ Error calculating folder size for {folder_path}: {e}")
        
        return total_size
    
    async def periodic_cleanup_task(self):
        """
        Background task สำหรับ periodic cleanup
        
        Runs:
        - Cleanup old temp folders
        - Check disk space and log warnings
        """
        logger.info(f"🔄 Starting periodic cleanup task (interval: {self.cleanup_interval_seconds}s)")
        
        self._running = True
        
        while self._running:
            try:
                # 1. Check disk space
                is_critical, warning_msg, disk_usage = self.check_disk_space()
                logger.info(warning_msg)
                
                if is_critical:
                    logger.warning(f"🚨 CRITICAL disk space - triggering aggressive cleanup")
                    # ทำ cleanup แบบ aggressive (ลด max_age_hours)
                    self.cleanup_old_temp_folders(max_age_hours=1)  # ลบไฟล์เก่ากว่า 1 ชั่วโมง
                else:
                    # Cleanup ปกติ
                    cleanup_stats = self.cleanup_old_temp_folders()
                    if cleanup_stats.get("deleted_count", 0) > 0:
                        logger.info(
                            f"🧹 Periodic cleanup: {cleanup_stats['deleted_count']} folders deleted, "
                            f"{cleanup_stats['total_size_freed_gb']} GB freed"
                        )
                
                # 2. Wait for next interval
                await asyncio.sleep(self.cleanup_interval_seconds)
                
            except asyncio.CancelledError:
                logger.info("🛑 Periodic cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in periodic cleanup task: {e}", exc_info=True)
                # Continue running even if error occurs
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    def start_periodic_cleanup(self):
        """Start periodic cleanup background task"""
        if self._cleanup_task is not None and not self._cleanup_task.done():
            logger.warning("⚠️ Periodic cleanup task is already running")
            return
        
        self._cleanup_task = asyncio.create_task(self.periodic_cleanup_task())
        logger.info(f"✅ Started periodic cleanup task (interval: {self.cleanup_interval_seconds}s)")
    
    def stop_periodic_cleanup(self):
        """Stop periodic cleanup background task"""
        self._running = False
        if self._cleanup_task is not None and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("🛑 Stopped periodic cleanup task")
    
    async def cleanup_on_startup(self):
        """Cleanup ที่รันตอน startup (ก่อน periodic task)"""
        logger.info("🧹 Running startup cleanup...")
        
        # 1. Check disk space
        is_critical, warning_msg, disk_usage = self.check_disk_space()
        logger.info(warning_msg)
        
        # 2. Cleanup old temp folders
        cleanup_stats = self.cleanup_old_temp_folders()
        
        if cleanup_stats.get("deleted_count", 0) > 0:
            logger.info(
                f"✅ Startup cleanup: {cleanup_stats['deleted_count']} folders deleted, "
                f"{cleanup_stats['total_size_freed_gb']} GB freed"
            )
        
        return cleanup_stats


# Global instance
cleanup_service = CleanupService()

