"""
Server-related API routes
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Support both relative and absolute imports
try:
    from ..config import SERVERS
except ImportError:
    import sys
    from pathlib import Path
    dashboard_dir = Path(__file__).parent.parent
    if str(dashboard_dir) not in sys.path:
        sys.path.insert(0, str(dashboard_dir))
    from config import SERVERS

logger = logging.getLogger(__name__)
router = APIRouter()


class ClearTasksRequest(BaseModel):
    statuses: Optional[List[str]] = None


@router.get("/api/server/{server_name}/summary")
async def get_server_summary(server_name: str):
    """Get task summary from remote server"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_url}/api/tasks/summary", timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Server returned status {response.status}"}
    except Exception as e:
        logger.error(f"Error getting summary from {server_name}: {e}")
        return {"error": str(e)}


@router.get("/api/server/{server_name}/status")
async def get_server_status(server_name: str):
    """Get health, worker, and queue status from remote server"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Get health
            health = "unknown"
            worker = {"error": "Unable to fetch"}
            queues = {"error": "Unable to fetch"}
            
            try:
                async with session.get(f"{api_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        health_data = await response.json()
                        health = health_data.get("status", "unknown")
            except:
                pass
            
            # Get worker status
            try:
                async with session.get(f"{api_url}/api/control/status", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        worker = await response.json()
            except:
                pass
            
            # Get queue status
            try:
                async with session.get(f"{api_url}/queue/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        queues = await response.json()
            except:
                pass
            
            return {
                "health": health,
                "worker": worker,
                "queues": queues
            }
    except Exception as e:
        logger.error(f"Error getting status from {server_name}: {e}")
        return {"error": str(e)}


@router.get("/api/server/{server_name}/tasks")
async def get_server_tasks(server_name: str, limit: int = 20, status: Optional[str] = None):
    """Get list of tasks from remote server with optional status filter"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    task_timeout = 30
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            params = {}
            if status:
                params["status"] = status
            
            async with session.get(
                f"{api_url}/transcribe/",
                params=params,
                timeout=aiohttp.ClientTimeout(total=task_timeout)
            ) as response:
                if response.status == 200:
                    tasks = await response.json()
                    if not isinstance(tasks, list):
                        return {"tasks": [], "total": 0, "error": "Invalid response format"}
                    
                    for task in tasks:
                        if "updated_at" not in task and "created_at" in task:
                            task["updated_at"] = task["created_at"]
                    
                    tasks_sorted = sorted(
                        tasks,
                        key=lambda x: x.get("updated_at", "") or "",
                        reverse=True
                    )
                    
                    limited_tasks = tasks_sorted[:limit]
                    
                    status_count = {}
                    for task in tasks:
                        task_status = task.get("status", "unknown").lower()
                        status_count[task_status] = status_count.get(task_status, 0) + 1
                    
                    return {
                        "tasks": limited_tasks,
                        "total": len(tasks),
                        "showing": len(limited_tasks),
                        "status_count": status_count
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Server {server_name} returned status {response.status}: {error_text}")
                    return {
                        "tasks": [],
                        "total": 0,
                        "error": f"Server returned status {response.status}",
                        "error_details": error_text[:500],
                        "server": server_name,
                        "api_url": api_url
                    }
    except asyncio.TimeoutError:
        logger.error(f"Timeout getting tasks from {server_name} ({api_url})")
        return {
            "tasks": [],
            "total": 0,
            "error": "Connection timeout",
            "error_details": f"Request to {api_url}/transcribe/ timed out after {task_timeout} seconds",
            "server": server_name,
            "api_url": api_url
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error getting tasks from {server_name}: {error_details}")
        return {
            "tasks": [],
            "total": 0,
            "error": f"Error: {str(e)}",
            "error_details": str(e),
            "server": server_name,
            "api_url": api_url
        }


@router.get("/api/server/{server_name}/videos")
async def get_server_videos(server_name: str):
    """Get list of videos from server's /uploads directory"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_url}/api/control/videos", timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    videos = []
                    if isinstance(data, list):
                        videos = data
                    elif isinstance(data, dict) and "videos" in data:
                        videos = data["videos"]
                    
                    # Ensure each video has duration and file_name info
                    for video in videos:
                        # Ensure file_name exists
                        if "file_name" not in video:
                            if "filename" in video:
                                video["file_name"] = video["filename"]
                            elif "file_path" in video:
                                video["file_name"] = video["file_path"].split("/")[-1]
                        
                        duration = 0
                        if "duration" in video:
                            duration = video["duration"]
                        elif "duration_seconds" in video:
                            duration = video["duration_seconds"]
                        elif "video_info" in video and isinstance(video["video_info"], dict):
                            duration = video["video_info"].get("duration", 0)
                        elif "video_info" in video and isinstance(video["video_info"], str):
                            try:
                                import json
                                video_info = json.loads(video["video_info"])
                                duration = video_info.get("duration", 0)
                            except:
                                pass
                        
                        video["duration"] = float(duration) if duration else 0
                        if video["duration"] > 0:
                            minutes = int(video["duration"] // 60)
                            seconds = int(video["duration"] % 60)
                            video["duration_formatted"] = f"{minutes}:{seconds:02d}"
                        else:
                            video["duration_formatted"] = "Unknown"
                    
                    return {"videos": videos}
                else:
                    return {"error": f"Server returned status {response.status}", "videos": []}
    except Exception as e:
        logger.error(f"Error getting videos from {server_name}: {e}")
        return {"error": str(e), "videos": []}


@router.post("/api/server/{server_name}/tasks/mark-stopped")
async def mark_tasks_stopped(server_name: str, request: ClearTasksRequest):
    """Mark stuck tasks as 'stopped' by calling remote server's DELETE endpoint"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    statuses = request.statuses if request.statuses is not None else ["pending", "processing"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Get all tasks first
            async with session.get(f"{api_url}/transcribe/", timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    all_tasks = await response.json()
                    if not isinstance(all_tasks, list):
                        return {"success": False, "message": "Invalid response format"}
                    
                    # Filter tasks by status
                    tasks_to_stop = [
                        task for task in all_tasks
                        if (task.get("status", "").lower() in [s.lower() for s in statuses])
                    ]
                    
                    stopped_count = 0
                    failed_count = 0
                    
                    for task in tasks_to_stop:
                        task_id = task.get("task_id") or task.get("id")
                        if not task_id:
                            continue
                        
                        try:
                            async with session.delete(
                                f"{api_url}/transcribe/{task_id}",
                                timeout=aiohttp.ClientTimeout(total=5)
                            ) as cancel_response:
                                if cancel_response.status in [200, 404]:
                                    stopped_count += 1
                                else:
                                    failed_count += 1
                        except:
                            failed_count += 1
                    
                    return {
                        "success": True,
                        "message": f"Marked {stopped_count} tasks as stopped",
                        "server": server_name,
                        "stopped_count": stopped_count,
                        "failed_count": failed_count,
                        "total_checked": len(tasks_to_stop),
                        "statuses": statuses
                    }
                else:
                    return {"success": False, "message": f"Server returned status {response.status}"}
    except asyncio.TimeoutError:
        return {"success": False, "message": "Connection timeout"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/server/{server_name}/tasks/clear")
async def clear_tasks(server_name: str, request: ClearTasksRequest):
    """Clear tasks by status from remote server"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    statuses = request.statuses if request.statuses is not None else ["pending", "processing"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            cleanup_request = {
                "statuses": statuses,
                "max_age_hours": 0
            }
            
            async with session.post(
                f"{api_url}/transcribe/cleanup",
                json=cleanup_request,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "message": f"Cleared tasks with statuses: {', '.join(statuses)}",
                        "server": server_name,
                        "result": result
                    }
                else:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "message": f"Server returned status {response.status}",
                        "error": error_text,
                        "server": server_name
                    }
    except asyncio.TimeoutError:
        return {"success": False, "message": "Connection timeout", "server": server_name}
    except Exception as e:
        return {"success": False, "message": str(e), "server": server_name}

