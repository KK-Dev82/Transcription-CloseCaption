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
import os

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
    file_path = task.get("file_path")
    response = {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "progress": task.get("progress", 0),
        "current_stage": task.get("current_stage"),
        "current_stage_description": task.get("current_stage_description"),
        "stage_progress": task.get("stage_progress"),
        "file_path": file_path,
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
    
    # Path สำหรับ play audio (FE ต่อกับ baseUrl)
    if file_path:
        response["audio_preview"] = {"file_path": file_path, "endpoint": "/api/upload/preview"}
    
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
    file_path = task.get("file_path")
    response = {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "progress": task.get("progress", 0),
        "filename": task.get("filename"),
        "file_path": file_path,
        "file_name": task.get("file_name") or task.get("filename"),  # Support both
        "language": task.get("language"),
        "model_size": task.get("model_size"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "completed_at": task.get("completed_at"),
        "total_duration": task.get("total_duration"),
        "duration": task.get("duration"),
        "_format": "full",
        "full_text": task.get("full_text", "") or task.get("text", "")
    }
    
    # Path สำหรับ play audio (FE ต่อกับ baseUrl ของตัวเอง)
    # ใช้: ${baseUrl}/api/upload/preview?file_path=${encodeURIComponent(audio_preview.file_path)}
    if file_path:
        response["audio_preview"] = {
            "file_path": file_path,
            "endpoint": "/api/upload/preview"
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
    item = {
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
    # Path สำหรับ play audio (FE ต่อกับ baseUrl)
    fp = task.get("file_path")
    if fp:
        item["audio_preview"] = {"file_path": fp, "endpoint": "/api/upload/preview"}
    return item


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
    
    **Response - audio_preview** (เมื่อมี file_path):
    - `audio_preview.file_path`: path ของไฟล์เสียง/วิดีโอ
    - `audio_preview.endpoint`: endpoint สำหรับ stream (เช่น /api/upload/preview)
    - FE ต่อ URL: ``${baseUrl}${audio_preview.endpoint}?file_path=${encodeURIComponent(audio_preview.file_path)}``
    
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


@router.post("/{task_id}/pause")
async def pause_task(task_id: str) -> Dict:
    """
    ⏸️ **Pause Task**
    
    หยุดชั่วคราว — ไม่ enqueue chunk ถัดไป (chunk ที่กำลังรันจะทำงานต่อจนเสร็จ)
    
    **Returns:**
    - `success`: True ถ้าสำเร็จ
    - `status`: "paused"
    """
    try:
        task_data = _get_task_from_storage(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        status = task_data.get("status", "")
        if status in ("completed", "failed", "cancelled"):
            return {"success": False, "message": f"Task อยู่ในสถานะ {status} แล้ว", "status": status}
        from redis import Redis
        from app.services.redis_queue_service import get_redis_queue_service
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        conn = Redis.from_url(redis_url, decode_responses=True)
        ttl = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))
        conn.setex(f"task:{task_id}:paused", ttl, "1")
        from datetime import datetime, timezone
        task_data["status"] = "paused"
        task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        task_data["current_stage"] = "paused"
        task_data["current_stage_description"] = "หยุดชั่วคราว (รอ Resume)"
        sqlite_storage, _ = _get_storage()
        sqlite_storage.save_transcription(task_id, task_data)
        return {"success": True, "message": "หยุดชั่วคราวแล้ว", "task_id": task_id, "status": "paused"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/resume")
async def resume_task(task_id: str) -> Dict:
    """
    ▶️ **Resume Task (จาก Paused)**
    
    ดำเนินการต่อ — enqueue chunk ถัดไป
    """
    try:
        task_data = _get_task_from_storage(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        status = task_data.get("status", "")
        if status not in ("paused", "on_hold"):
            return {"success": False, "message": f"Task อยู่ในสถานะ {status} — Resume ได้เฉพาะ paused/on_hold", "status": status}
        from redis import Redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        conn = Redis.from_url(redis_url, decode_responses=True)
        ttl = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))
        conn.delete(f"task:{task_id}:paused")
        conn.srem("tasks:on_hold", task_id)
        conn.delete(f"task:{task_id}:on_hold")
        chunks_metadata_key = f"task:{task_id}:chunks_metadata"
        inflight_key = f"task:{task_id}:inflight_chunks"
        enqueued_guard_prefix = f"task:{task_id}:enqueued"
        inflight_limit = int(os.getenv('CHUNK_INFLIGHT_LIMIT_PER_JOB', '2'))
        from app.workers.rq_worker import _do_claim_and_enqueue_next_chunk, _update_task_stage_sync
        enqueued = _do_claim_and_enqueue_next_chunk(
            conn, task_id, chunks_metadata_key, inflight_key,
            enqueued_guard_prefix, inflight_limit, ttl
        )
        if enqueued:
            from datetime import datetime, timezone
            task_data["status"] = "processing"
            task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            task_data["current_stage"] = "transcribing"
            task_data["current_stage_description"] = "กำลังแปลงเสียงเป็นข้อความ (ต่อจาก Resume)"
            sqlite_storage, _ = _get_storage()
            sqlite_storage.save_transcription(task_id, task_data)
            return {"success": True, "message": "ดำเนินการต่อแล้ว", "task_id": task_id, "status": "processing"}
        return {"success": True, "message": "ไม่มี chunk ถัดไป (อาจเสร็จหมดแล้ว)", "task_id": task_id, "status": status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str) -> Dict:
    """
    🛑 **Cancel Task**
    
    ยกเลิก transcription task และ jobs ที่เกี่ยวข้องใน Redis queue
    ใช้เมื่ออัปโหลดไฟล์ผิดและต้องการยกเลิก
    
    **Parameters:**
    - `task_id`: Task ID ที่ต้องการยกเลิก
    
    **Returns:**
    - `success`: True ถ้าสำเร็จ
    - `cancelled`: True ถ้า task ถูกยกเลิก
    - `cancelled_jobs`: จำนวน jobs ที่ยกเลิก
    - `redis_keys_deleted`: จำนวน Redis keys ที่ลบ
    
    **Examples:**
    ```
    POST /api/v2/tasks/dc534414-5fef-49b9-a5aa-4f597396d16d/cancel
    ```
    """
    try:
        task_data = _get_task_from_storage(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        status = task_data.get("status", "")
        if status in ("completed", "failed", "cancelled"):
            return {
                "success": True,
                "cancelled": False,
                "message": f"Task อยู่ในสถานะ {status} แล้ว ไม่สามารถยกเลิกได้",
                "status": status
            }
        
        # ใช้ logic จาก transcribe.py
        from datetime import datetime, timezone
        sqlite_storage, json_storage = _get_storage()
        storage = sqlite_storage
        
        # Cancel Redis jobs
        cancelled_jobs = 0
        redis_keys_deleted = 0
        try:
            from app.services.redis_queue_service import get_redis_queue_service
            queue_service = get_redis_queue_service()
            cancel_result = queue_service.cancel_task(task_id)
            cancelled_jobs = cancel_result.get("cancelled_jobs", 0)
            redis_keys_deleted = cancel_result.get("redis_keys_deleted", 0)
        except Exception as e:
            logger.warning(f"Error cancelling Redis jobs: {e}")
        
        # อัปเดต task status
        task_data["status"] = "cancelled"
        task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        task_data["current_stage"] = "cancelled"
        task_data["current_stage_description"] = "ยกเลิกโดยผู้ใช้"
        if "error_message" in task_data:
            del task_data["error_message"]
        storage.save_transcription(task_id, task_data)
        
        return {
            "success": True,
            "cancelled": True,
            "message": "ยกเลิก task สำเร็จ",
            "task_id": task_id,
            "status": "cancelled",
            "cancelled_jobs": cancelled_jobs,
            "redis_keys_deleted": redis_keys_deleted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/retry")
async def retry_task(task_id: str) -> Dict:
    """
    🔄 **Retry Task (Stuck หรือ Failed)**
    
    - **Failed tasks**: ใช้ task เดิม ล้าง Redis + re-enqueue preprocess
    - **Stuck tasks**: ใช้ StuckTaskMonitor แก้ไข
    
    **Parameters:**
    - `task_id`: Task ID ที่ต้องการ retry
    
    **Returns:**
    - `success`: True ถ้าสำเร็จ
    - `message`: ข้อความอธิบาย
    - `fixed` / `retried`: สถานะการดำเนินการ
    
    **Examples:**
    ```
    POST /api/v2/tasks/dc534414-5fef-49b9-a5aa-4f597396d16d/retry
    ```
    """
    try:
        task_data = _get_task_from_storage(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        status = task_data.get('status', '')
        
        # กรณี Failed: ใช้ task เดิม re-enqueue
        if status == "failed":
            file_path = task_data.get('file_path')
            if not file_path:
                raise HTTPException(status_code=400, detail="Task ไม่มี file_path ไม่สามารถ retry ได้")
            
            from pathlib import Path
            if not Path(file_path).exists():
                raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์: {file_path}")
            
            from datetime import datetime, timezone
            from app.api.transcribe import TranscriptionRequest
            from app.services.redis_queue_service import get_redis_queue_service
            from app.services.close_caption_config import get_transcription_model_display
            
            sqlite_storage, json_storage = _get_storage()
            storage = sqlite_storage
            
            # ล้าง Redis keys ของ task
            redis_url = os.getenv('REDIS_URL')
            if redis_url:
                try:
                    from redis import Redis
                    r = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=10)
                    prefix = f"task:{task_id}:"
                    keys = list(r.scan_iter(match=prefix + "*", count=500))
                    if keys:
                        r.delete(*keys)
                        logger.info(f"✅ ลบ Redis keys: {len(keys)} keys สำหรับ retry {task_id}")
                except Exception as e:
                    logger.warning(f"Could not clear Redis: {e}")
            
            # อัปเดต task เป็น queued
            task_data["status"] = "queued"
            task_data["progress"] = 0
            task_data["current_stage"] = None
            task_data["current_stage_description"] = None
            task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            if "error_message" in task_data:
                del task_data["error_message"]
            storage.save_transcription(task_id, task_data)
            
            # Enqueue preprocess
            queue_service = get_redis_queue_service()
            model_size = task_data.get('model_size') or get_transcription_model_display()
            chunk_duration = task_data.get('chunk_duration', 150)
            source = task_data.get('source') if task_data.get('source') == 'video_record' else None
            
            preprocess_job_id = queue_service.enqueue_preprocess(
                task_id=task_id,
                file_path=file_path,
                language=task_data.get('language', 'th'),
                model_size=model_size,
                chunk_duration=chunk_duration,
                source=source
            )
            
            logger.info(f"✅ Retried failed task {task_id} (re-enqueued preprocess)")
            return {
                "success": True,
                "message": f"Task {task_id} retry initiated (ใช้ task เดิม)",
                "retried": True,
                "status": "queued",
                "preprocess_job_id": preprocess_job_id
            }
        
        # กรณี Stuck: ใช้ StuckTaskMonitor
        from app.services.stuck_task_monitor import StuckTaskMonitor
        monitor = StuckTaskMonitor()
        
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
        
        fixed = monitor.fix_stuck_task(task_id, reason)
        
        if fixed:
            logger.info(f"✅ Successfully retried stuck task {task_id}: {reason}")
            return {
                "success": True,
                "message": f"Task {task_id} retry initiated (stuck fix)",
                "fixed": True,
                "reason": reason,
                "status": task_data.get('status'),
                "progress": task_data.get('progress', 0)
            }
        else:
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
        logger.error(f"Error retrying task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/resubmit")
async def resubmit_task(task_id: str) -> Dict:
    """
    🔄 **Resubmit Task (Send New Transcription)**
    
    ส่งการแปลงใหม่โดยใช้ไฟล์เดิม (สร้าง task ใหม่)
    
    **Parameters:**
    - `task_id`: Task ID ที่ต้องการ resubmit
    
    **Returns:**
    - `success`: True ถ้าสำเร็จ
    - `new_task_id`: Task ID ใหม่
    - `message`: ข้อความอธิบาย
    
    **Examples:**
    ```
    POST /api/v2/tasks/dc534414-5fef-49b9-a5aa-4f597396d16d/resubmit
    ```
    """
    try:
        # ดึง task เดิม
        task_data = _get_task_from_storage(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        # รองรับทั้ง file_path (ไฟล์เดียว) และ chunk_group (file_paths)
        file_path = task_data.get('file_path')
        file_paths = task_data.get('file_paths') or []
        chunk_group = task_data.get('chunk_group', False) and file_paths
        
        if chunk_group:
            # ตรวจสอบทุกไฟล์ใน file_paths
            from pathlib import Path
            missing = [p for p in file_paths if not Path(p).exists()]
            if missing:
                raise HTTPException(status_code=404, detail=f"Files not found: {missing[:3]}{'...' if len(missing) > 3 else ''}")
        else:
            if not file_path:
                raise HTTPException(status_code=400, detail="Original task has no file_path (required for resubmit)")
            from pathlib import Path
            if not Path(file_path).exists():
                raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        
        import uuid
        from datetime import datetime, timezone
        from app.services.redis_queue_service import get_redis_queue_service
        
        new_task_id = str(uuid.uuid4())
        
        # สร้าง request ใหม่ (model_size: ใช้จาก task หรือ default จาก WHISPER_MODEL)
        from app.services.close_caption_config import get_transcription_model_display
        model_size = task_data.get('model_size') or get_transcription_model_display()
        language = task_data.get('language', 'th')
        source = task_data.get("source") if task_data.get("source") == "video_record" else None
        
        # สร้าง task และบันทึกลง storage
        sqlite_storage, json_storage = _get_storage()
        storage = sqlite_storage  # ใช้ SQLite เป็นหลัก
        task_dict = {
            "task_id": new_task_id,
            "status": "queued",
            "progress": 0,
            "language": language,
            "model_size": model_size,
            "full_text": "",
            "chunks": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": task_data.get("source", "upload"),
        }
        if chunk_group:
            task_dict["file_path"] = file_paths[0]
            task_dict["file_paths"] = file_paths
            task_dict["chunk_group"] = True
        else:
            task_dict["file_path"] = file_path
            task_dict["chunk_duration"] = task_data.get('chunk_duration', 150)
            task_dict["use_chunking"] = task_data.get('use_chunking', True)
        storage.save_transcription(new_task_id, task_dict)
        
        # Enqueue preprocessing job
        queue_service = get_redis_queue_service()
        try:
            if chunk_group:
                preprocess_job_id = queue_service.enqueue_preprocess_chunk_group(
                    task_id=new_task_id,
                    file_paths=file_paths,
                    language=language,
                    model_size=model_size,
                    source=source
                )
            else:
                preprocess_job_id = queue_service.enqueue_preprocess(
                    task_id=new_task_id,
                    file_path=file_path,
                    language=language,
                    model_size=model_size,
                    chunk_duration=task_data.get('chunk_duration', 150),
                    source=source
                )
            
            logger.info(f"✅ Resubmitted task {task_id} as new task {new_task_id} (chunk_group={chunk_group})")
            
            return {
                "success": True,
                "message": "Task resubmitted successfully",
                "original_task_id": task_id,
                "new_task_id": new_task_id,
                "status": "queued",
                "file_path": file_paths[0] if chunk_group else file_path,
                "preprocess_job_id": preprocess_job_id,
                "chunk_group": chunk_group,
            }
        except Exception as e:
            logger.error(f"❌ Error enqueueing resubmit job: {e}", exc_info=True)
            # Update task status to failed
            task_dict["status"] = "failed"
            task_dict["error_message"] = str(e)
            storage.save_transcription(new_task_id, task_dict)
            raise HTTPException(status_code=500, detail=f"Failed to enqueue resubmit job: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resubmitting task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{task_id}/priority")
async def change_task_priority(task_id: str, priority: bool = True) -> Dict:
    """
    ⬆️ **Change Task Priority**

    เปลี่ยน priority ของ task ที่ยัง queued อยู่ โดยยกเลิก preprocess job เดิม
    แล้ว re-enqueue ใน queue ที่มี priority สูงขึ้น (preprocess_video_record)

    **Parameters:**
    - `task_id`: Task ID
    - `priority`: True = เพิ่ม priority (ใช้ video_record queue), False = ลด priority (ใช้ upload queue)

    **Returns:**
    - `success`: True ถ้าสำเร็จ
    - `new_job_id`: Job ID ใหม่หลัง re-enqueue
    """
    try:
        task_data = _get_task_from_storage(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        status = task_data.get("status", "")
        if status not in ("queued", "pending"):
            return {
                "success": False,
                "message": f"Task อยู่ในสถานะ {status} — เปลี่ยน priority ได้เฉพาะ queued/pending",
                "status": status
            }

        from app.services.redis_queue_service import get_redis_queue_service

        queue_service = get_redis_queue_service()

        # ยกเลิก preprocess job เดิม (ถ้ายังอยู่ใน queue)
        preprocess_job_id = f"{task_id}_preprocess"
        try:
            from rq.job import Job
            job = Job.fetch(preprocess_job_id, connection=queue_service.redis_conn)
            job_status = job.get_status()
            if job_status in ("queued", "deferred"):
                job.cancel()
                logger.info(f"✅ Cancelled preprocess job {preprocess_job_id} for priority change")
            elif job_status == "started":
                return {
                    "success": False,
                    "message": "Preprocess job กำลังทำงานอยู่ ไม่สามารถเปลี่ยน priority ได้",
                    "status": status
                }
        except Exception:
            pass  # Job อาจไม่มีแล้ว

        # Re-enqueue ด้วย source ที่เหมาะสม
        new_source = "video_record" if priority else None
        file_path = task_data.get("file_path", "")
        language = task_data.get("language", "th")
        model_size = task_data.get("model_size")
        chunk_duration = task_data.get("chunk_duration", 150)

        new_job_id = queue_service.enqueue_preprocess(
            task_id=task_id,
            file_path=file_path,
            language=language,
            model_size=model_size,
            chunk_duration=chunk_duration,
            source=new_source
        )

        # อัปเดต task data
        from datetime import datetime, timezone
        task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        sqlite_storage, _ = _get_storage()
        sqlite_storage.save_transcription(task_id, task_data)

        logger.info(f"✅ Changed priority for task {task_id} (priority={priority}, source={new_source})")
        return {
            "success": True,
            "message": f"เปลี่ยน priority สำเร็จ ({'สูงขึ้น' if priority else 'ปกติ'})",
            "task_id": task_id,
            "priority": priority,
            "new_job_id": new_job_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing priority for task {task_id}: {e}", exc_info=True)
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