"""
Cleanup API Endpoints for Phase 5: Cleanup & Monitoring

Features:
- Disk space monitoring
- Manual cleanup triggers
- Cleanup statistics
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict
from pydantic import BaseModel

from ..services.cleanup_service import cleanup_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cleanup", tags=["Cleanup & Monitoring"])


class DiskUsageResponse(BaseModel):
    """Response model for disk usage"""
    total_gb: float
    used_gb: float
    free_gb: float
    percent_used: float
    path: str
    timestamp: str
    status: str  # "ok", "warning", "critical"
    message: str


@router.get("/disk-space", response_model=DiskUsageResponse)
async def get_disk_space(path: str = Query("/", description="Path to check disk space")):
    """
    ตรวจสอบ disk space usage
    
    Args:
        path: Path ที่ต้องการตรวจสอบ (default: /)
    
    Returns:
        DiskUsageResponse with disk space information
    """
    try:
        is_critical, warning_msg, disk_usage = cleanup_service.check_disk_space(path)
        
        if "error" in disk_usage:
            raise HTTPException(status_code=500, detail=disk_usage.get("error"))
        
        # Determine status
        free_gb = disk_usage.get("free_gb", 0)
        critical_threshold = cleanup_service.disk_space_critical_threshold_gb
        warning_threshold = cleanup_service.disk_space_warning_threshold_gb
        
        if free_gb < critical_threshold:
            status = "critical"
        elif free_gb < warning_threshold:
            status = "warning"
        else:
            status = "ok"
        
        response = DiskUsageResponse(
            total_gb=disk_usage.get("total_gb", 0),
            used_gb=disk_usage.get("used_gb", 0),
            free_gb=disk_usage.get("free_gb", 0),
            percent_used=disk_usage.get("percent_used", 0),
            path=disk_usage.get("path", path),
            timestamp=disk_usage.get("timestamp", ""),
            status=status,
            message=warning_msg
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting disk space: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting disk space: {str(e)}")


@router.post("/temp-folders")
async def cleanup_temp_folders(max_age_hours: Optional[int] = Query(None, description="Maximum age in hours (default: from env)")):
    """
    ลบ temp folders ที่เก่าเกิน max_age_hours
    
    Args:
        max_age_hours: อายุสูงสุดของ temp folder (ชั่วโมง)
                      ถ้า None จะใช้ค่า default จาก env
    
    Returns:
        Cleanup statistics
    """
    try:
        stats = cleanup_service.cleanup_old_temp_folders(max_age_hours=max_age_hours)
        
        return {
            "message": f"Cleanup completed: {stats.get('deleted_count', 0)} folders deleted, {stats.get('total_size_freed_gb', 0)} GB freed",
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Error during cleanup: {str(e)}")


@router.get("/status")
async def get_cleanup_status():
    """
    ดูสถานะของ Cleanup Service
    
    Returns:
        Status information including disk space, cleanup settings, etc.
    """
    try:
        # Get disk space
        is_critical, warning_msg, disk_usage = cleanup_service.check_disk_space()
        
        return {
            "cleanup_service": {
                "running": cleanup_service._running,
                "cleanup_interval_seconds": cleanup_service.cleanup_interval_seconds,
                "temp_folder_max_age_hours": cleanup_service.temp_folder_max_age_hours,
                "disk_space_warning_threshold_gb": cleanup_service.disk_space_warning_threshold_gb,
                "disk_space_critical_threshold_gb": cleanup_service.disk_space_critical_threshold_gb
            },
            "disk_space": disk_usage,
            "disk_space_message": warning_msg,
            "disk_space_critical": is_critical
        }
        
    except Exception as e:
        logger.error(f"Error getting cleanup status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting cleanup status: {str(e)}")

