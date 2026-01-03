"""
Deprecation Helper - เพิ่ม deprecation warnings ให้กับ API responses
"""

from typing import Dict, Any, Optional
from datetime import datetime


def add_deprecation_warning(
    response_data: Dict[str, Any],
    old_endpoint: str,
    new_endpoint: str,
    removal_date: str = "2026-03-01",
    migration_guide_url: str = "https://docs.example.com/api-migration"
) -> Dict[str, Any]:
    """
    เพิ่ม deprecation warning ให้กับ response
    
    Args:
        response_data: Response data ที่จะเพิ่ม warning
        old_endpoint: Endpoint เก่าที่ deprecated
        new_endpoint: Endpoint ใหม่ที่แนะนำ
        removal_date: วันที่จะปิด endpoint เก่า
        migration_guide_url: URL ของ migration guide
    
    Returns:
        Response data พร้อม deprecation warning
    """
    response_data["_deprecated"] = {
        "message": f"This endpoint ({old_endpoint}) is deprecated. Please use {new_endpoint} instead",
        "old_endpoint": old_endpoint,
        "new_endpoint": new_endpoint,
        "removal_date": removal_date,
        "migration_guide": migration_guide_url,
        "announced_date": "2025-12-29"
    }
    
    return response_data


def create_deprecation_response(
    old_endpoint: str,
    new_endpoint: str,
    suggestion: Optional[str] = None
) -> Dict[str, Any]:
    """
    สร้าง response เฉพาะสำหรับ deprecated endpoint
    
    Args:
        old_endpoint: Endpoint เก่า
        new_endpoint: Endpoint ใหม่
        suggestion: คำแนะนำเพิ่มเติม
    
    Returns:
        Deprecation response
    """
    return {
        "deprecated": True,
        "message": f"⚠️ This endpoint is deprecated",
        "old_endpoint": old_endpoint,
        "new_endpoint": new_endpoint,
        "removal_date": "2026-03-01",
        "suggestion": suggestion or f"Please migrate to {new_endpoint}",
        "migration_guide": "https://docs.example.com/api-migration",
        "status": "deprecated"
    }


# Mapping ของ deprecated endpoints
DEPRECATED_ENDPOINTS = {
    # Task Status endpoints
    "/api/progress/transcription/{task_id}": {
        "new": "/api/v2/tasks/{task_id}?format=progress",
        "description": "Use unified tasks API with format=progress"
    },
    "/api/polling/task/{task_id}": {
        "new": "/api/v2/tasks/{task_id}?format=minimal",
        "description": "Use unified tasks API with format=minimal for polling"
    },
    "/api/transcribe-enhanced/status/{task_id}": {
        "new": "/api/v2/tasks/{task_id}?format=full&include_thai_processing=true",
        "description": "Use unified tasks API with Thai processing flag"
    },
    
    # Task List endpoints
    "/api/tasks/by-date": {
        "new": "/api/v2/tasks?date={date}",
        "description": "Use unified tasks API with date filter"
    },
    "/api/polling/tasks/active": {
        "new": "/api/v2/tasks?active=true",
        "description": "Use unified tasks API with active filter"
    },
    "/api/polling/tasks/recent": {
        "new": "/api/v2/tasks?limit=10&sort=updated_at&order=desc",
        "description": "Use unified tasks API with sort parameters"
    },
    
    # Upload endpoints
    "/api/video/upload": {
        "new": "/api/upload/",
        "description": "Use unified upload API"
    },
    "/api/video/info/{file_path}": {
        "new": "/api/upload/info/{file_path}",
        "description": "Use unified upload API for file info"
    },
    
    # Stats endpoints
    "/api/tasks/summary": {
        "new": "/api/v2/tasks/stats/summary",
        "description": "Use unified stats API"
    },
    "/api/history/stats": {
        "new": "/api/v2/tasks/stats/summary",
        "description": "Use unified stats API"
    },
    "/api/tasks/available-dates": {
        "new": "/api/v2/tasks/stats/available-dates",
        "description": "Use unified stats API"
    }
}


def get_deprecation_info(endpoint: str) -> Optional[Dict[str, str]]:
    """
    ดึงข้อมูล deprecation สำหรับ endpoint
    
    Args:
        endpoint: Endpoint path
    
    Returns:
        Deprecation info หรือ None ถ้าไม่ deprecated
    """
    return DEPRECATED_ENDPOINTS.get(endpoint)


def is_deprecated(endpoint: str) -> bool:
    """
    ตรวจสอบว่า endpoint deprecated หรือไม่
    
    Args:
        endpoint: Endpoint path
    
    Returns:
        True ถ้า deprecated
    """
    return endpoint in DEPRECATED_ENDPOINTS

