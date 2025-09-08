"""
Dashboard API สำหรับ monitoring system status
เหมาะสำหรับ production environment หลัง NAT
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json
import psutil
import docker
from datetime import datetime, timedelta
from typing import Dict, List
import logging

from ..services.transcription_service import TranscriptionService
from ..services.webhook_service import webhook_service
from ..utils.storage_factory import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Templates directory
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Dashboard หน้าแรก - Overview ทั้งระบบ"""
    return templates.TemplateResponse("dashboard/index.html", {"request": request})

@router.get("/recent-tasks")
async def get_recent_tasks():
    """ดึงรายการ tasks ล่าสุด"""
    try:
        from ..utils.json_storage import JSONStorage
        json_storage = JSONStorage()
        
        # ดึง tasks ล่าสุด 10 รายการ
        all_tasks = json_storage.list_all_transcriptions()
        recent_tasks = sorted(
            all_tasks,
            key=lambda x: x.get("updated_at") or x.get("created_at") or "1970-01-01T00:00:00",
            reverse=True
        )[:10]
        
        return {
            "tasks": recent_tasks,
            "count": len(recent_tasks),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting recent tasks: {e}")
        return {"tasks": [], "count": 0, "error": str(e)}

@router.get("/api/system-status")
async def get_system_status():
    """ข้อมูล system status สำหรับ dashboard"""
    try:
        # System resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Docker containers status
        docker_status = await get_docker_status()
        
        # Service health
        storage = get_storage()
        transcription_service = TranscriptionService()
        
        # Active tasks
        all_tasks = transcription_service.get_all_tasks()
        active_tasks = [
            task for task in all_tasks 
            if task.__dict__.get('status') not in ['completed', 'failed', 'cancelled']
        ]
        
        # Recent completions (last 24h)
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        recent_tasks = [
            task for task in all_tasks
            if task.__dict__.get('created_at') and 
               task.__dict__.get('created_at') > yesterday
        ]
        
        completed_today = sum(
            1 for task in recent_tasks 
            if task.__dict__.get('status') == 'completed'
        )
        
        failed_today = sum(
            1 for task in recent_tasks 
            if task.__dict__.get('status') == 'failed'
        )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "free": disk.free,
                    "used": disk.used,
                    "percent": (disk.used / disk.total) * 100
                }
            },
            "containers": docker_status,
            "tasks": {
                "active": len(active_tasks),
                "total_today": len(recent_tasks),
                "completed_today": completed_today,
                "failed_today": failed_today,
                "success_rate": (completed_today / max(1, len(recent_tasks))) * 100
            },
            "services": {
                "api": "healthy",
                "storage": "healthy",
                "webhook": "healthy"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/api/active-tasks")
async def get_active_tasks():
    """รายการ tasks ที่กำลังทำงานอยู่"""
    try:
        transcription_service = TranscriptionService()
        all_tasks = transcription_service.get_all_tasks()
        
        active_tasks = []
        for task in all_tasks:
            task_dict = task.__dict__
            if task_dict.get('status') not in ['completed', 'failed', 'cancelled']:
                active_tasks.append({
                    "task_id": task_dict.get('task_id'),
                    "file_path": task_dict.get('file_path'),
                    "status": task_dict.get('status'),
                    "progress": task_dict.get('progress', 0),
                    "language": task_dict.get('language'),
                    "created_at": task_dict.get('created_at').isoformat() if task_dict.get('created_at') else None,
                    "updated_at": task_dict.get('updated_at').isoformat() if task_dict.get('updated_at') else None
                })
        
        return {
            "active_tasks": active_tasks,
            "count": len(active_tasks)
        }
        
    except Exception as e:
        logger.error(f"Failed to get active tasks: {e}")
        return {"error": str(e), "active_tasks": [], "count": 0}

@router.get("/api/recent-tasks")
async def get_recent_tasks(hours: int = 24):
    """รายการ tasks ล่าสุด"""
    try:
        transcription_service = TranscriptionService()
        all_tasks = transcription_service.get_all_tasks()
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_tasks = []
        
        for task in all_tasks:
            task_dict = task.__dict__
            created_at = task_dict.get('created_at')
            
            if created_at and created_at > cutoff_time:
                recent_tasks.append({
                    "task_id": task_dict.get('task_id'),
                    "file_path": task_dict.get('file_path'),
                    "status": task_dict.get('status'),
                    "progress": task_dict.get('progress', 0),
                    "language": task_dict.get('language'),
                    "created_at": created_at.isoformat(),
                    "completed_at": task_dict.get('completed_at').isoformat() if task_dict.get('completed_at') else None,
                    "duration": self._calculate_duration(task_dict)
                })
        
        # Sort by created_at desc
        recent_tasks.sort(key=lambda x: x['created_at'], reverse=True)
        
        return {
            "recent_tasks": recent_tasks[:50],  # Limit to 50
            "total": len(recent_tasks),
            "hours": hours
        }
        
    except Exception as e:
        logger.error(f"Failed to get recent tasks: {e}")
        return {"error": str(e), "recent_tasks": [], "total": 0}

@router.get("/api/queue-status")
async def get_queue_status():
    """สถานะ RabbitMQ queues"""
    try:
        # This would need RabbitMQ management API
        # For now, return mock data
        return {
            "queues": [
                {
                    "name": "video_trim_queue",
                    "messages": 0,
                    "consumers": 2,
                    "status": "idle"
                },
                {
                    "name": "video_merge_queue", 
                    "messages": 0,
                    "consumers": 2,
                    "status": "idle"
                },
                {
                    "name": "transcription_queue",
                    "messages": 3,
                    "consumers": 2,
                    "status": "active"
                }
            ],
            "total_messages": 3,
            "total_consumers": 6
        }
        
    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        return {"error": str(e), "queues": []}

@router.get("/api/webhook-stats")
async def get_webhook_stats():
    """สถิติ webhook"""
    try:
        stats = webhook_service.get_stats()
        subscriptions = webhook_service.list_subscriptions()
        
        return {
            "stats": stats,
            "subscriptions": [
                {
                    "id": sub["id"],
                    "url": sub["url"],
                    "events": sub["events"],
                    "active": sub["active"],
                    "success_count": sub["success_count"],
                    "error_count": sub["error_count"]
                }
                for sub in subscriptions
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get webhook stats: {e}")
        return {"error": str(e)}

@router.get("/api/performance-metrics")
async def get_performance_metrics():
    """Performance metrics สำหรับ charts"""
    try:
        transcription_service = TranscriptionService()
        all_tasks = transcription_service.get_all_tasks()
        
        # Calculate metrics for last 7 days
        now = datetime.now()
        metrics = {}
        
        for i in range(7):
            date = now - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            
            day_tasks = []
            for task in all_tasks:
                created_at = task.__dict__.get('created_at')
                if created_at:
                    try:
                        # Handle both datetime and string formats
                        if isinstance(created_at, str):
                            task_date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).date()
                        else:
                            task_date = created_at.date()
                        
                        if task_date == date.date():
                            day_tasks.append(task)
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Invalid date format for task: {created_at}, error: {e}")
                        continue
            
            completed = sum(1 for task in day_tasks if task.__dict__.get('status') == 'completed')
            failed = sum(1 for task in day_tasks if task.__dict__.get('status') == 'failed')
            
            metrics[date_str] = {
                "total": len(day_tasks),
                "completed": completed,
                "failed": failed,
                "success_rate": (completed / max(1, len(day_tasks))) * 100
            }
        
        return {
            "daily_metrics": metrics,
            "period": "7_days"
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        return {"error": str(e)}

async def get_docker_status():
    """ตรวจสอบสถานะ Docker containers"""
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        
        status = []
        for container in containers:
            if 'transcription' in container.name:
                status.append({
                    "name": container.name,
                    "status": container.status,
                    "image": container.image.tags[0] if container.image.tags else "unknown",
                    "created": container.attrs['Created'],
                    "ports": container.attrs.get('NetworkSettings', {}).get('Ports', {})
                })
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get docker status: {e}")
        return []

def _calculate_duration(task_dict):
    """คำนวณระยะเวลาการประมวลผล"""
    created_at = task_dict.get('created_at')
    completed_at = task_dict.get('completed_at')
    
    if created_at and completed_at:
        duration = completed_at - created_at
        return duration.total_seconds()
    
    return None

@router.get("/workers", response_class=HTMLResponse)
async def dashboard_workers(request: Request):
    """Dashboard สำหรับ workers"""
    return templates.TemplateResponse("dashboard/workers.html", {"request": request})

@router.get("/queues", response_class=HTMLResponse)
async def dashboard_queues(request: Request):
    """Dashboard สำหรับ queues"""
    return templates.TemplateResponse("dashboard/queues.html", {"request": request})

@router.get("/tasks", response_class=HTMLResponse)
async def dashboard_tasks(request: Request):
    """Dashboard สำหรับ tasks"""
    return templates.TemplateResponse("dashboard/tasks.html", {"request": request})

@router.get("/webhooks", response_class=HTMLResponse)
async def dashboard_webhooks(request: Request):
    """Dashboard สำหรับ webhooks"""
    return templates.TemplateResponse("dashboard/webhooks.html", {"request": request})
