"""
Cleanup and deletion API routes
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Support both relative and absolute imports
try:
    from ..config import SERVERS
    from ..services import cleanup_service
except ImportError:
    import sys
    from pathlib import Path
    dashboard_dir = Path(__file__).parent.parent
    if str(dashboard_dir) not in sys.path:
        sys.path.insert(0, str(dashboard_dir))
    from config import SERVERS
    from services import cleanup_service

cleanup_progress_store = cleanup_service.cleanup_progress_store

logger = logging.getLogger(__name__)
router = APIRouter()


class DeleteOldTasksRequest(BaseModel):
    days: Optional[int] = Field(None, ge=0, description="Delete tasks older than N days. If None, delete all.")
    statuses: Optional[List[str]] = Field(
        default=["completed", "failed", "cancelled", "stopped"],
        description="List of statuses to delete (e.g., ['completed', 'failed', 'cancelled', 'stopped'])"
    )


@router.post("/api/server/{server_name}/tasks/delete-old")
async def delete_old_tasks(server_name: str, request: DeleteOldTasksRequest):
    """Delete old tasks from remote server with progress tracking"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    cleanup_id = str(uuid.uuid4())
    
    cleanup_progress_store[cleanup_id] = {
        "server_name": server_name,
        "status": "starting",
        "total": 0,
        "deleted": 0,
        "failed": 0,
        "current_file": "",
        "started_at": datetime.now().isoformat(),
        "days": request.days,
        "statuses": request.statuses
    }
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # First, get all tasks to count
            async with session.get(
                f"{api_url}/transcribe/",
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    all_tasks = await response.json()
                    if not isinstance(all_tasks, list):
                        cleanup_progress_store[cleanup_id]["status"] = "error"
                        cleanup_progress_store[cleanup_id]["error"] = "Invalid response format"
                        return {"cleanup_id": cleanup_id, "error": "Invalid response format"}
                    
                    # Filter tasks by status and age
                    now = datetime.now()
                    days_threshold = request.days if request.days is not None else 0
                    threshold_date = now - timedelta(days=days_threshold)
                    
                    # Normalize status list to lowercase for comparison
                    statuses_lower = [s.lower() for s in (request.statuses or [])]
                    
                    old_tasks = []
                    for task in all_tasks:
                        task_status = (task.get("status", "") or "").lower()
                        # Check if task status matches any of the requested statuses
                        if request.statuses and task_status not in statuses_lower:
                            continue
                        
                        # If days is None (delete all), skip age check
                        if request.days is not None:
                            updated_at = task.get("updated_at") or task.get("completed_at") or task.get("created_at")
                            if not updated_at:
                                continue
                            
                            try:
                                task_date = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                                if task_date.replace(tzinfo=None) >= threshold_date.replace(tzinfo=None):
                                    continue  # Skip tasks that are not old enough
                            except:
                                pass  # If date parsing fails, include the task
                        
                        old_tasks.append(task)
                    
                    cleanup_progress_store[cleanup_id]["total"] = len(old_tasks)
                    cleanup_progress_store[cleanup_id]["status"] = "processing"
                    
                    logger.info(f"Found {len(old_tasks)} tasks to delete on {server_name} (statuses: {request.statuses}, days: {request.days})")
                    
                    # Use bulk cleanup endpoint for better reliability and actual deletion
                    # This is more efficient than deleting one by one and ensures permanent deletion
                    try:
                        # Prepare cleanup request
                        # Convert days to hours for max_age_hours
                        max_age_hours = 0 if request.days is None else (request.days * 24)
                        
                        cleanup_request = {
                            "statuses": request.statuses or ["completed", "failed", "cancelled", "stopped"],
                            "max_age_hours": max_age_hours
                        }
                        
                        logger.info(f"Calling bulk cleanup on {server_name}: {cleanup_request}")
                        cleanup_progress_store[cleanup_id]["current_file"] = "Bulk cleanup in progress..."
                        
                        async with session.post(
                            f"{api_url}/transcribe/cleanup",
                            json=cleanup_request,
                            timeout=aiohttp.ClientTimeout(total=120)  # Longer timeout for bulk operation
                        ) as cleanup_response:
                            if cleanup_response.status == 200:
                                result = await cleanup_response.json()
                                removed_count = result.get("removed_count", 0)
                                failed_count = result.get("failed_count", 0)
                                removed_ids = result.get("removed_task_ids", []) or result.get("removed_ids", [])
                                
                                # Update progress
                                cleanup_progress_store[cleanup_id]["deleted"] = removed_count
                                cleanup_progress_store[cleanup_id]["failed"] = failed_count
                                cleanup_progress_store[cleanup_id]["status"] = "completed"
                                cleanup_progress_store[cleanup_id]["completed_at"] = datetime.now().isoformat()
                                
                                logger.info(f"✅ Bulk cleanup completed on {server_name}: {removed_count} deleted, {failed_count} failed")
                                
                                return {
                                    "cleanup_id": cleanup_id,
                                    "success": True,
                                    "total": len(old_tasks),
                                    "deleted": removed_count,
                                    "failed": failed_count,
                                    "removed_task_ids": removed_ids[:10] if removed_ids else []  # Return first 10 IDs for reference
                                }
                            else:
                                error_text = await cleanup_response.text()
                                logger.error(f"Bulk cleanup failed: HTTP {cleanup_response.status}: {error_text}")
                                # Fallback to individual deletion
                                logger.info("Falling back to individual deletion...")
                    except Exception as bulk_error:
                        logger.warning(f"Bulk cleanup failed, falling back to individual deletion: {bulk_error}", exc_info=True)
                    
                    # Fallback: Delete tasks one by one with progress updates
                    deleted_count = 0
                    failed_count = 0
                    
                    for task in old_tasks:
                        task_id = task.get("task_id") or task.get("id")
                        if not task_id:
                            continue
                        
                        cleanup_progress_store[cleanup_id]["current_file"] = task_id
                        
                        try:
                            # Method 1: Try permanent delete endpoint (actually deletes from storage)
                            deleted = False
                            
                            try:
                                async with session.delete(
                                    f"{api_url}/transcribe/{task_id}/permanent",
                                    timeout=aiohttp.ClientTimeout(total=10)
                                ) as delete_response:
                                    if delete_response.status in [200, 204]:
                                        deleted_count += 1
                                        deleted = True
                                        logger.info(f"✅ Permanently deleted task {task_id} via /permanent")
                            except Exception as e1:
                                logger.debug(f"Permanent delete failed for {task_id}: {e1}")
                            
                            # Method 2: Fallback to regular delete (cancels, may not delete from storage)
                            if not deleted:
                                try:
                                    async with session.delete(
                                        f"{api_url}/transcribe/{task_id}",
                                        timeout=aiohttp.ClientTimeout(total=10)
                                    ) as delete_response:
                                        if delete_response.status in [200, 204]:
                                            deleted_count += 1
                                            deleted = True
                                            logger.warning(f"⚠️ Deleted task {task_id} via /transcribe/{task_id} (may only be cancelled, not permanently deleted)")
                                except Exception as e2:
                                    logger.debug(f"Regular delete failed for {task_id}: {e2}")
                            
                            if not deleted:
                                failed_count += 1
                                logger.warning(f"⚠️ Failed to delete task {task_id} using both methods")
                                
                        except Exception as e:
                            logger.error(f"Error deleting task {task_id}: {e}", exc_info=True)
                            failed_count += 1
                        
                        cleanup_progress_store[cleanup_id]["deleted"] = deleted_count
                        cleanup_progress_store[cleanup_id]["failed"] = failed_count
                    
                    cleanup_progress_store[cleanup_id]["status"] = "completed"
                    cleanup_progress_store[cleanup_id]["completed_at"] = datetime.now().isoformat()
                    
                    return {
                        "cleanup_id": cleanup_id,
                        "success": True,
                        "total": len(old_tasks),
                        "deleted": deleted_count,
                        "failed": failed_count
                    }
                else:
                    cleanup_progress_store[cleanup_id]["status"] = "error"
                    error_text = await response.text()
                    cleanup_progress_store[cleanup_id]["error"] = error_text
                    return {"cleanup_id": cleanup_id, "error": f"Server returned status {response.status}"}
    except Exception as e:
        logger.error(f"Error deleting old tasks on {server_name}: {e}", exc_info=True)
        cleanup_progress_store[cleanup_id]["status"] = "error"
        cleanup_progress_store[cleanup_id]["error"] = str(e)
        return {"cleanup_id": cleanup_id, "error": str(e)}


@router.get("/api/cleanup/{cleanup_id}/progress")
async def get_cleanup_progress(cleanup_id: str):
    """Get cleanup progress by ID"""
    if cleanup_id not in cleanup_progress_store:
        raise HTTPException(status_code=404, detail="Cleanup ID not found")
    
    return cleanup_progress_store[cleanup_id]
