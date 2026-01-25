"""
API endpoints สำหรับ Stuck Task Monitor
"""

from fastapi import APIRouter, HTTPException
from typing import Dict
import logging

from app.services.stuck_task_monitor import StuckTaskMonitor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


@router.post("/stuck-tasks/check")
async def check_stuck_tasks() -> Dict:
    """
    ตรวจสอบและแก้ไข stuck tasks
    """
    try:
        monitor = StuckTaskMonitor()
        result = monitor.check_and_fix_stuck_tasks()
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error checking stuck tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stuck-tasks/status")
async def get_stuck_tasks_status() -> Dict:
    """
    ดูสถานะ stuck tasks (ไม่แก้ไข)
    """
    try:
        monitor = StuckTaskMonitor()
        
        # ดึง tasks ทั้งหมด
        if hasattr(monitor.storage, 'list_all_transcriptions'):
            all_tasks_list = monitor.storage.list_all_transcriptions()
            all_tasks = []
            for task in all_tasks_list:
                task_id = task.get('task_id')
                if task_id:
                    task_data = monitor.storage.load_transcription(task_id, skip_migration=True)
                    if task_data:
                        all_tasks.append((task_id, task_data))
        else:
            from pathlib import Path
            storage_dir = Path("storage/transcriptions")
            all_tasks = []
            if storage_dir.exists():
                for task_file in storage_dir.glob("*.json"):
                    task_id = task_file.stem
                    task_data = monitor.storage.load_transcription(task_id)
                    if task_data:
                        all_tasks.append((task_id, task_data))
        
        stuck_tasks = []
        for task_id, task_data in all_tasks:
            is_stuck, reason = monitor.is_task_really_stuck(task_id, task_data)
            if is_stuck:
                stuck_tasks.append({
                    'task_id': task_id,
                    'reason': reason,
                    'status': task_data.get('status'),
                    'progress': task_data.get('progress', 0),
                    'current_stage': task_data.get('current_stage', 'N/A')
                })
        
        return {
            "success": True,
            "total_checked": len(all_tasks),
            "stuck_count": len(stuck_tasks),
            "stuck_tasks": stuck_tasks
        }
    except Exception as e:
        logger.error(f"Error getting stuck tasks status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stuck-tasks/{task_id}/retry")
async def retry_stuck_task(task_id: str) -> Dict:
    """
    Retry task ที่ stuck โดยเฉพาะ
    
    **Parameters:**
    - `task_id`: Task ID ที่ต้องการ retry
    
    **Returns:**
    - `success`: True ถ้าสำเร็จ
    - `message`: ข้อความอธิบาย
    - `fixed`: True ถ้า task ถูก fix แล้ว
    - `reason`: เหตุผลที่ task stuck (ถ้ามี)
    
    **Examples:**
    ```
    POST /api/monitoring/stuck-tasks/dc534414-5fef-49b9-a5aa-4f597396d16d/retry
    ```
    """
    try:
        monitor = StuckTaskMonitor()
        
        # ตรวจสอบว่า task นี้ stuck หรือไม่
        task_data = monitor.storage.load_transcription(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        is_stuck, reason = monitor.is_task_really_stuck(task_id, task_data)
        
        if not is_stuck:
            return {
                "success": True,
                "message": f"Task {task_id} is not stuck",
                "fixed": False,
                "reason": None,
                "status": task_data.get('status'),
                "progress": task_data.get('progress', 0)
            }
        
        # Fix stuck task
        fixed = monitor.fix_stuck_task(task_id, reason)
        
        if fixed:
            logger.info(f"✅ Successfully retried stuck task {task_id}: {reason}")
            return {
                "success": True,
                "message": f"Task {task_id} retry initiated",
                "fixed": True,
                "reason": reason,
                "status": task_data.get('status'),
                "progress": task_data.get('progress', 0)
            }
        else:
            logger.warning(f"⚠️  Could not fix stuck task {task_id}: {reason}")
            return {
                "success": False,
                "message": f"Could not fix task {task_id}",
                "fixed": False,
                "reason": reason,
                "status": task_data.get('status'),
                "progress": task_data.get('progress', 0)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying stuck task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
