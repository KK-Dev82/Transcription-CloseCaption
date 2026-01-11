"""
Unified Tasks API v2
รวม endpoints ที่ซ้ำซ้อน:
- GET /api/tasks/{task_id} (tasks.py)
- GET /api/progress/transcription/{task_id} (progress.py)
- GET /api/polling/task/{task_id} (polling.py)
- GET /api/transcribe-enhanced/status/{task_id} (transcription_enhanced.py)
- GET /api/history/transcriptions (history.py)
- GET /api/tasks/by-date (tasks.py)
- GET /api/polling/tasks/active (polling.py)
- GET /api/polling/tasks/recent (polling.py)
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2/tasks", tags=["Tasks V2 (Unified)"])


# ==================== Helper Functions ====================

def _get_storage():
    """Get storage instance (SQLite primary, JSON fallback)"""
    from app.utils.sqlite_storage import SQLiteStorage
    from app.utils.json_storage import JSONStorage
    
    sqlite_storage = SQLiteStorage()
    json_storage = JSONStorage()
    
    return sqlite_storage, json_storage


def _get_task_from_storage(task_id: str) -> Optional[Dict]:
    """Get task from storage (try SQLite first, fallback to JSON)"""
    sqlite_storage, json_storage = _get_storage()
    
    # Try SQLite first
    task = sqlite_storage.load_transcription(task_id)
    if not task:
        task = json_storage.get_transcription(task_id)
    
    # ถ้าใช้ SQLite storage และ task มีอยู่แล้ว ให้ลองดึง segments จาก segments table
    if task:
        try:
            # Check if segments table exists and has data
            conn = sqlite_storage._get_connection()
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='segments'"
            )
            if cursor.fetchone():
                # ดึง segments จาก segments table
                cursor = conn.execute(
                    "SELECT idx, start_time, end_time, text, confidence FROM segments WHERE task_id = ? ORDER BY idx",
                    (task_id,)
                )
                segments_rows = cursor.fetchall()
                
                # ถ้าพบ segments ใน segments table ให้ใช้แทน chunks
                if segments_rows:
                    segments = []
                    for row in segments_rows:
                        # row format: (idx, start_time, end_time, text, confidence)
                        # Use dict-like access if Row factory, else index access
                        if hasattr(row, 'keys'):
                            # sqlite3.Row with row_factory
                            segments.append({
                                "start_time": float(row['start_time']) if row['start_time'] is not None else 0.0,
                                "end_time": float(row['end_time']) if row['end_time'] is not None else 0.0,
                                "text": str(row['text']) if row['text'] is not None else "",
                                "confidence": float(row['confidence']) if row['confidence'] is not None else None
                            })
                        else:
                            # Tuple access (fallback)
                            segments.append({
                                "start_time": float(row[1]) if len(row) > 1 and row[1] is not None else 0.0,
                                "end_time": float(row[2]) if len(row) > 2 and row[2] is not None else 0.0,
                                "text": str(row[3]) if len(row) > 3 and row[3] is not None else "",
                                "confidence": float(row[4]) if len(row) > 4 and row[4] is not None else None
                            })
                    # เพิ่ม segments เข้า task (ใช้แทน chunks หรือ segments เดิม)
                    if segments:
                        task["segments"] = segments
                        task["chunks"] = segments  # เก็บ chunks ด้วยเพื่อ backward compatibility
                        logger.debug(f"✅ Loaded {len(segments)} segments from segments table for {task_id}")
        except Exception as e:
            logger.debug(f"Could not load segments from segments table for {task_id}: {e}")
    
    return task


def _get_all_tasks() -> List[Dict]:
    """Get all tasks from storage"""
    sqlite_storage, json_storage = _get_storage()
    
    all_tasks = sqlite_storage.list_all_transcriptions()
    if not all_tasks:
        all_tasks = json_storage.list_all_transcriptions()
    
    return all_tasks or []


def _parse_datetime(dt_str: Any) -> Optional[datetime]:
    """Parse datetime string to datetime object"""
    if isinstance(dt_str, datetime):
        return dt_str
    
    if isinstance(dt_str, str):
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except:
            try:
                return datetime.strptime(dt_str.split('T')[0], "%Y-%m-%d")
            except:
                return None
    
    return None


def _get_task_date(task: Dict) -> Optional[datetime.date]:
    """Extract date from task's created_at"""
    created_at = task.get("created_at")
    if not created_at:
        return None
    
    dt = _parse_datetime(created_at)
    return dt.date() if dt else None


def _calculate_elapsed_time(task: Dict) -> Dict[str, Any]:
    """Calculate elapsed time and estimate remaining"""
    result = {}
    
    created_at = _parse_datetime(task.get("created_at"))
    updated_at = _parse_datetime(task.get("updated_at"))
    
    if created_at and updated_at:
        elapsed = (updated_at - created_at).total_seconds()
        result["elapsed_seconds"] = int(elapsed)
        result["elapsed_formatted"] = f"{int(elapsed//60)}:{int(elapsed%60):02d}"
        
        # Estimate remaining time
        progress = task.get("progress", 0)
        if 0 < progress < 100:
            estimated_total = elapsed / (progress / 100)
            remaining = estimated_total - elapsed
            result["estimated_remaining_seconds"] = max(0, int(remaining))
            result["estimated_remaining_formatted"] = f"{int(remaining//60)}:{int(remaining%60):02d}"
    
    return result


# ==================== Response Builders ====================

def _build_minimal_response(task: Dict) -> Dict:
    """
    Format: minimal (สำหรับ polling - เร็วที่สุด)
    แทน: /api/polling/task/{task_id}
    """
    return {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "progress": task.get("progress", 0),
        "updated_at": task.get("updated_at"),
        "_format": "minimal"
    }


def _build_progress_response(task: Dict) -> Dict:
    """
    Format: progress (สำหรับ progress tracking)
    แทน: /api/progress/transcription/{task_id}
    """
    response = {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "progress": task.get("progress", 0),
        "current_stage": task.get("current_stage"),
        "current_stage_description": task.get("current_stage_description"),
        "stage_progress": task.get("stage_progress"),
        "file_path": task.get("file_path"),
        "filename": task.get("filename"),
        "language": task.get("language"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "_format": "progress"
    }
    
    # Add elapsed time calculations
    timing = _calculate_elapsed_time(task)
    response.update(timing)
    
    # Add stage description based on status
    status = task.get("status", "")
    if status == "pending":
        response["stage_description"] = "รอการประมวลผล"
    elif status == "processing":
        response["stage_description"] = "กำลังประมวลผล"
    elif status == "completed":
        response["stage_description"] = "เสร็จสิ้น"
        response["completed_at"] = task.get("completed_at")
    elif status == "failed":
        response["stage_description"] = "เกิดข้อผิดพลาด"
        response["error"] = task.get("error")
    
    return response


def _build_full_response(
    task: Dict,
    include_chunks: bool = False,
    include_thai_processing: bool = False
) -> Dict:
    """
    Format: full (ข้อมูลแบบเต็ม)
    แทน: /api/tasks/{task_id}, /api/transcribe-enhanced/status/{task_id}
    """
    response = {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "progress": task.get("progress", 0),
        "filename": task.get("filename"),
        "file_path": task.get("file_path"),
        "file_name": task.get("file_name") or task.get("filename"),  # Support both
        "language": task.get("language"),
        "model_size": task.get("model_size"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "completed_at": task.get("completed_at"),
        "total_duration": task.get("total_duration"),
        "duration": task.get("duration"),
        "_format": "full"
    }
    
    # Add timing info
    timing = _calculate_elapsed_time(task)
    response.update(timing)
    
    # Include result if completed
    if task.get("status") == "completed":
        # ดึง full_text (ใช้ full_text แทน text)
        full_text = task.get("full_text", "") or task.get("text", "")
        
        # ดึง segments จาก chunks (ข้อมูลถูกเก็บเป็น chunks)
        chunks = task.get("chunks", []) or task.get("segments", [])
        segments = []
        
        # แปลง chunks format เป็น segments format
        for chunk in chunks:
            if isinstance(chunk, dict):
                # ถ้า chunk มี format ที่ถูกต้องแล้ว
                if "start_time" in chunk and "end_time" in chunk:
                    segments.append({
                        "start_time": chunk.get("start_time", 0),
                        "end_time": chunk.get("end_time", 0),
                        "text": chunk.get("text", ""),
                        "confidence": chunk.get("confidence")
                    })
                # ถ้า chunk เป็น format อื่น ให้ลองแปลง
                elif "start" in chunk and "end" in chunk:
                    segments.append({
                        "start_time": chunk.get("start", 0),
                        "end_time": chunk.get("end", 0),
                        "text": chunk.get("text", ""),
                        "confidence": chunk.get("confidence")
                    })
        
        # ดึง word_segments ถ้ามี (อาจไม่มีใน storage)
        word_segments = task.get("word_segments", [])
        
        response["result"] = {
            "text": full_text,
            "segments": segments,
            "word_segments": word_segments
        }
        
        # Include subtitle if available
        if task.get("subtitle_content"):
            response["subtitle"] = {
                "format": task.get("subtitle_format", "srt"),
                "content": task.get("subtitle_content")
            }
    
    # Include error if failed
    if task.get("status") == "failed":
        response["error"] = task.get("error")
        response["error_details"] = task.get("error_details")
    
    # Include chunks if requested
    if include_chunks:
        response["chunks"] = task.get("chunks", [])
        response["total_chunks"] = len(task.get("chunks", []))
    
    # Include Thai processing info if requested
    if include_thai_processing:
        response["thai_processed"] = task.get("thai_processed", False)
        
        if task.get("thai_processing_stats"):
            response["thai_processing_stats"] = task.get("thai_processing_stats")
        
        if task.get("original_text"):
            response["original_text"] = task.get("original_text")
            response["corrected_text"] = task.get("text", "")
    
    return response


def _build_list_item(task: Dict) -> Dict:
    """Build list item (summary view for list endpoints)"""
    return {
        "task_id": task.get("task_id"),
        "id": task.get("task_id"),  # Alias for compatibility
        "filename": task.get("filename") or task.get("file_name"),
        "file_name": task.get("file_name") or task.get("filename"),
        "status": task.get("status"),
        "progress": task.get("progress", 0),
        "language": task.get("language"),
        "model_size": task.get("model_size"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "completed_at": task.get("completed_at"),
        "duration": task.get("duration"),
        "total_duration": task.get("total_duration")
    }


# ==================== API Endpoints ====================

@router.get("/{task_id}")
async def get_task(
    task_id: str,
    format: Literal["full", "progress", "minimal"] = Query(
        "full",
        description="Response format: full (complete data), progress (tracking info), minimal (polling)"
    ),
    include_chunks: bool = Query(
        False,
        description="Include transcription chunks (only for format=full)"
    ),
    include_thai_processing: bool = Query(
        False,
        description="Include Thai processing information (only for format=full)"
    )
):
    """
    🎯 **Unified Task Status API**
    
    รวม endpoints:
    - `GET /api/tasks/{task_id}` (tasks.py)
    - `GET /api/progress/transcription/{task_id}` (progress.py)
    - `GET /api/polling/task/{task_id}` (polling.py)
    - `GET /api/transcribe-enhanced/status/{task_id}` (transcription_enhanced.py)
    
    **Parameters:**
    - `format`: full|progress|minimal (default: full)
        - `full`: ข้อมูลแบบเต็ม รวม result, segments, etc.
        - `progress`: สำหรับติดตาม progress, elapsed time, ETA
        - `minimal`: สำหรับ polling (เร็วที่สุด) - เฉพาะ status, progress
    - `include_chunks`: รวม chunks หรือไม่ (default: false)
    - `include_thai_processing`: รวมข้อมูล Thai processing (default: false)
    
    **Examples:**
    ```
    # Full data
    GET /api/v2/tasks/abc-123?format=full
    
    # Progress tracking
    GET /api/v2/tasks/abc-123?format=progress
    
    # Quick polling
    GET /api/v2/tasks/abc-123?format=minimal
    
    # With Thai processing info
    GET /api/v2/tasks/abc-123?format=full&include_thai_processing=true
    ```
    """
    try:
        task = _get_task_from_storage(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Build response based on format
        if format == "minimal":
            return _build_minimal_response(task)
        elif format == "progress":
            return _build_progress_response(task)
        else:  # full
            return _build_full_response(
                task,
                include_chunks=include_chunks,
                include_thai_processing=include_thai_processing
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_tasks(
    # Status filter
    status: Optional[str] = Query(
        None,
        description="Filter by status: completed, failed, processing, pending"
    ),
    
    # Date filters
    date: Optional[str] = Query(
        None,
        description="Filter by specific date (YYYY-MM-DD)"
    ),
    date_from: Optional[str] = Query(
        None,
        description="Filter from date (YYYY-MM-DD)"
    ),
    date_to: Optional[str] = Query(
        None,
        description="Filter to date (YYYY-MM-DD)"
    ),
    days_ago: Optional[int] = Query(
        None,
        ge=1,
        le=365,
        description="Show results from last N days"
    ),
    
    # Other filters
    active: Optional[bool] = Query(
        None,
        description="Show only active (processing) tasks"
    ),
    filename_contains: Optional[str] = Query(
        None,
        description="Search in filename"
    ),
    language: Optional[str] = Query(
        None,
        description="Filter by language (th, en, etc.)"
    ),
    
    # Pagination
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of results per page"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Offset for pagination"
    ),
    
    # Sorting
    sort: Literal["created_at", "updated_at", "filename"] = Query(
        "updated_at",
        description="Sort by field"
    ),
    order: Literal["asc", "desc"] = Query(
        "desc",
        description="Sort order"
    )
):
    """
    🎯 **Unified Task List API**
    
    รวม endpoints:
    - `GET /api/history/transcriptions` (history.py)
    - `GET /api/tasks/by-date` (tasks.py)
    - `GET /api/polling/tasks/active` (polling.py)
    - `GET /api/polling/tasks/recent` (polling.py)
    
    **Filters:**
    - `status`: completed|failed|processing|pending
    - `date`: YYYY-MM-DD (specific date)
    - `date_from`, `date_to`: date range
    - `days_ago`: last N days
    - `active`: active tasks only (shortcut for status=processing)
    - `filename_contains`: search in filename
    - `language`: filter by language
    
    **Examples:**
    ```
    # Get all tasks (latest first)
    GET /api/v2/tasks?limit=20
    
    # Get tasks by date
    GET /api/v2/tasks?date=2025-12-29
    
    # Get active tasks
    GET /api/v2/tasks?active=true
    # or
    GET /api/v2/tasks?status=processing
    
    # Get recent completed tasks
    GET /api/v2/tasks?status=completed&limit=10&sort=updated_at&order=desc
    
    # Get tasks from last 7 days
    GET /api/v2/tasks?days_ago=7
    
    # Search by filename
    GET /api/v2/tasks?filename_contains=meeting
    
    # Complex filter
    GET /api/v2/tasks?status=completed&days_ago=7&language=th&filename_contains=test
    ```
    """
    try:
        # Get all tasks
        all_tasks = _get_all_tasks()
        
        # Apply filters
        filtered_tasks = all_tasks
        
        # Status filter
        if status:
            filtered_tasks = [t for t in filtered_tasks if t.get("status") == status]
        
        # Active filter (shortcut for status=processing)
        if active:
            filtered_tasks = [t for t in filtered_tasks if t.get("status") == "processing"]
        
        # Language filter
        if language:
            filtered_tasks = [t for t in filtered_tasks if t.get("language") == language]
        
        # Date filters
        if date:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
            filtered_tasks = [
                t for t in filtered_tasks
                if _get_task_date(t) == target_date
            ]
        
        if date_from:
            from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
            filtered_tasks = [
                t for t in filtered_tasks
                if _get_task_date(t) and _get_task_date(t) >= from_date
            ]
        
        if date_to:
            to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
            filtered_tasks = [
                t for t in filtered_tasks
                if _get_task_date(t) and _get_task_date(t) <= to_date
            ]
        
        if days_ago:
            cutoff = datetime.now() - timedelta(days=days_ago)
            filtered_tasks = [
                t for t in filtered_tasks
                if _parse_datetime(t.get("created_at")) and _parse_datetime(t.get("created_at")) >= cutoff
            ]
        
        # Filename filter
        if filename_contains:
            filtered_tasks = [
                t for t in filtered_tasks
                if filename_contains.lower() in (t.get("filename") or t.get("file_name") or "").lower()
            ]
        
        # Sort
        reverse = (order == "desc")
        filtered_tasks.sort(
            key=lambda x: x.get(sort) or "1970-01-01T00:00:00",
            reverse=reverse
        )
        
        # Pagination
        total_count = len(filtered_tasks)
        paginated_tasks = filtered_tasks[offset:offset + limit]
        
        # Build response
        return {
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count,
            "filters_applied": {
                k: v for k, v in {
                    "status": status,
                    "date": date,
                    "date_from": date_from,
                    "date_to": date_to,
                    "days_ago": days_ago,
                    "active": active,
                    "filename_contains": filename_contains,
                    "language": language
                }.items() if v is not None
            },
            "sort": {
                "field": sort,
                "order": order
            },
            "tasks": [_build_list_item(t) for t in paginated_tasks]
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
async def get_tasks_summary():
    """
    📊 Get tasks summary statistics
    
    แทน: /api/tasks/summary, /api/history/stats
    """
    try:
        all_tasks = _get_all_tasks()
        
        # Count by status
        status_counts = {}
        for task in all_tasks:
            status = task.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Calculate success rate
        completed = status_counts.get("completed", 0)
        failed = status_counts.get("failed", 0)
        total_finished = completed + failed
        success_rate = (completed / total_finished * 100) if total_finished > 0 else 0
        
        # Count by language
        language_counts = {}
        for task in all_tasks:
            lang = task.get("language", "unknown")
            language_counts[lang] = language_counts.get(lang, 0) + 1
        
        # Recent activity (last 24 hours)
        cutoff_24h = datetime.now() - timedelta(hours=24)
        recent_tasks = [
            t for t in all_tasks
            if _parse_datetime(t.get("created_at")) and _parse_datetime(t.get("created_at")) >= cutoff_24h
        ]
        
        return {
            "total_tasks": len(all_tasks),
            "status_counts": status_counts,
            "success_rate": round(success_rate, 2),
            "language_counts": language_counts,
            "recent_24h": len(recent_tasks),
            "active_tasks": status_counts.get("processing", 0)
        }
    
    except Exception as e:
        logger.error(f"Error getting tasks summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/available-dates")
async def get_available_dates():
    """
    📅 Get available dates that have tasks
    
    แทน: /api/tasks/available-dates
    """
    try:
        all_tasks = _get_all_tasks()
        
        # Extract unique dates
        dates = set()
        for task in all_tasks:
            task_date = _get_task_date(task)
            if task_date:
                dates.add(task_date)
        
        # Sort dates (newest first)
        sorted_dates = sorted(dates, reverse=True)
        
        # Count tasks per date
        date_counts = {}
        for date in sorted_dates:
            count = sum(1 for t in all_tasks if _get_task_date(t) == date)
            date_counts[date.isoformat()] = count
        
        return {
            "total_dates": len(sorted_dates),
            "dates": [d.isoformat() for d in sorted_dates],
            "date_counts": date_counts
        }
    
    except Exception as e:
        logger.error(f"Error getting available dates: {e}")
        raise HTTPException(status_code=500, detail=str(e))