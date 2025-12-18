"""
API endpoints สำหรับดึง tasks ตามวันที่และ filter ต่างๆ
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from ..services.transcription_service import TranscriptionService
from ..utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["Tasks"])

json_storage = JSONStorage()

def parse_date(date_str: str) -> datetime.date:
    """Parse date string to date object"""
    try:
        if len(date_str) == 10:  # YYYY-MM-DD format
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            # Try ISO format
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD format.")

def parse_datetime_str(dt_str: str) -> datetime:
    """Parse datetime string to datetime object"""
    if isinstance(dt_str, str):
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except:
            try:
                return datetime.strptime(dt_str.split('T')[0], "%Y-%m-%d")
            except:
                return None
    return None

def get_date_from_task(task: Dict) -> Optional[datetime.date]:
    """Extract date from task's created_at"""
    created_at = task.get("created_at")
    if not created_at:
        return None
    
    try:
        if isinstance(created_at, str):
            dt = parse_datetime_str(created_at)
            return dt.date() if dt else None
        elif isinstance(created_at, datetime):
            return created_at.date()
        else:
            return None
    except:
        return None

@router.get("/by-date")
async def get_tasks_by_date(
    date: str = Query(..., description="วันที่ในรูปแบบ YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="Filter by status: completed, failed, processing, pending"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    ดึง tasks ตามวันที่
    """
    try:
        target_date = parse_date(date)
        
        # Get all transcriptions
        # ใช้ run_in_executor เพื่อไม่ให้ blocking event loop
        import asyncio
        loop = asyncio.get_event_loop()
        all_transcriptions = await loop.run_in_executor(None, json_storage.list_all_transcriptions)
        
        # Filter by date
        filtered_tasks = []
        for task in all_transcriptions:
            task_date = get_date_from_task(task)
            if not task_date or task_date != target_date:
                continue
            
            # Filter by status if provided
            if status and task.get("status") != status:
                continue
            
            filtered_tasks.append(task)
        
        # Sort by created_at desc
        filtered_tasks.sort(
            key=lambda x: x.get("created_at") or "1970-01-01T00:00:00",
            reverse=True
        )
        
        # Pagination
        total_count = len(filtered_tasks)
        paginated_tasks = filtered_tasks[offset:offset + limit]
        
        # Format response
        formatted_tasks = []
        for task in paginated_tasks:
            created_at = task.get("created_at")
            completed_at = task.get("completed_at")
            start_time = task.get("start_time") or created_at
            end_time = task.get("end_time") or completed_at
            
            # Calculate time used
            time_used = task.get("processing_time") or task.get("result_time")
            if not time_used and start_time and end_time:
                try:
                    start = parse_datetime_str(start_time) if isinstance(start_time, str) else start_time
                    end = parse_datetime_str(end_time) if isinstance(end_time, str) else end_time
                    if start and end:
                        time_used = (end - start).total_seconds()
                except:
                    pass
            
            # Handle chunks and full_text safely
            chunks = task.get("chunks") or []
            if not isinstance(chunks, list):
                chunks = []
            full_text = task.get("full_text") or ""
            if not isinstance(full_text, str):
                full_text = ""
            
            formatted_tasks.append({
                "task_id": task.get("task_id"),
                "video_file": task.get("file_name") or task.get("filename") or (task.get("file_path", "").split("/")[-1] if task.get("file_path") else ""),
                "status": task.get("status", "unknown"),
                "start_time": start_time,
                "end_time": end_time,
                "time_used": time_used,
                "progress": task.get("progress", 0),
                "full_text": full_text,
                "file_path": task.get("file_path"),
                "language": task.get("language", "th"),
                "model_size": task.get("model_size", "base"),
                "error_message": task.get("error_message"),
                "chunks_count": len(chunks),
                "text_length": len(full_text)
            })
        
        return {
            "tasks": formatted_tasks,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            },
            "date": date,
            "status_filter": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tasks by date: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary")
async def get_tasks_summary(
    date: Optional[str] = Query(None, description="วันที่ในรูปแบบ YYYY-MM-DD (ถ้าไม่ระบุจะใช้วันนี้)")
):
    """
    ดึง summary ของ tasks ตามวันที่
    """
    try:
        if date:
            target_date = parse_date(date)
        else:
            target_date = datetime.now().date()
        
        # Get all transcriptions
        # ใช้ run_in_executor เพื่อไม่ให้ blocking event loop
        import asyncio
        loop = asyncio.get_event_loop()
        all_transcriptions = await loop.run_in_executor(None, json_storage.list_all_transcriptions)
        
        # Filter by date
        tasks_by_date = []
        for task in all_transcriptions:
            task_date = get_date_from_task(task)
            if task_date == target_date:
                tasks_by_date.append(task)
        
        # Calculate summary
        all_count = len(tasks_by_date)
        completed_count = sum(1 for t in tasks_by_date if t.get("status") == "completed")
        processing_count = sum(1 for t in tasks_by_date if t.get("status") in ["processing", "transcribing"])
        waiting_count = sum(1 for t in tasks_by_date if t.get("status") in ["pending", "queued"])
        failed_count = sum(1 for t in tasks_by_date if t.get("status") == "failed")
        
        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "summary": {
                "all_tasks": all_count,
                "completed": completed_count,
                "processing": processing_count,
                "waiting": waiting_count,
                "failed": failed_count
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tasks summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/available-dates")
async def get_available_dates():
    """
    ดึงรายการวันที่ที่มี tasks
    """
    try:
        # ใช้ run_in_executor เพื่อไม่ให้ blocking event loop
        import asyncio
        loop = asyncio.get_event_loop()
        all_transcriptions = await loop.run_in_executor(None, json_storage.list_all_transcriptions)
        
        dates = set()
        for task in all_transcriptions:
            task_date = get_date_from_task(task)
            if task_date:
                dates.add(task_date.strftime("%Y-%m-%d"))
        
        sorted_dates = sorted(dates, reverse=True)
        
        return {
            "dates": sorted_dates,
            "count": len(sorted_dates),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting available dates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{task_id}")
async def get_task_by_id(task_id: str):
    """
    ดึงข้อมูล task ตาม task_id
    """
    try:
        # ดึงข้อมูลจาก storage
        task_data = json_storage.get_transcription(task_id)
        
        if not task_data:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        # Handle chunks safely - ensure it's a list
        chunks = task_data.get("chunks") or []
        if not isinstance(chunks, list):
            chunks = []
        
        return {
            "task_id": task_id,
            "status": task_data.get("status", "unknown"),
            "progress": task_data.get("progress", 0),
            "file_path": task_data.get("file_path"),
            "file_name": task_data.get("file_name") or task_data.get("filename"),
            "language": task_data.get("language", "th"),
            "model_size": task_data.get("model_size", "base"),
            "created_at": task_data.get("created_at"),
            "updated_at": task_data.get("updated_at"),
            "completed_at": task_data.get("completed_at"),
            "full_text": task_data.get("full_text") or "",
            "chunks": chunks,
            "chunks_count": len(chunks),
            "error_message": task_data.get("error_message"),
            "current_stage": task_data.get("current_stage"),
            "current_stage_description": task_data.get("current_stage_description"),
            "total_duration": task_data.get("total_duration")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
