"""
Server-related API routes
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from pathlib import Path

# Support both relative and absolute imports
try:
    from ..server_constants import SERVERS
except ImportError:
    try:
        from ..config import SERVERS
    except ImportError:
        import sys
        from pathlib import Path
        dashboard_dir = Path(__file__).parent.parent
        if str(dashboard_dir) not in sys.path:
            sys.path.insert(0, str(dashboard_dir))
        try:
            from server_constants import SERVERS
        except ImportError:
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
    
    task_timeout = 60  # เพิ่ม timeout เป็น 60s สำหรับ server ที่มี tasks เยอะ
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            params = {"limit": limit * 2}  # เรียก limit มากกว่าเล็กน้อยเพื่อให้มี buffer
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
                    
                    # ใช้ total จาก response
                    total_tasks = len(tasks)
                    
                    # เพิ่ม updated_at ถ้าไม่มี
                    for task in tasks:
                        if "updated_at" not in task and "created_at" in task:
                            task["updated_at"] = task["created_at"]
                    
                    # Sort และ limit - ถ้ามี tasks เยอะมาก ให้ limit ก่อนแล้วค่อย sort เพื่อประหยัดเวลา
                    if len(tasks) > limit * 2:
                        # Limit ก่อนแล้วค่อย sort (เร็วกว่า)
                        tasks_to_sort = tasks[:limit * 2]
                        tasks_sorted = sorted(
                            tasks_to_sort,
                            key=lambda x: x.get("updated_at", "") or "",
                            reverse=True
                        )
                        limited_tasks = tasks_sorted[:limit]
                    else:
                        # ถ้ามี tasks น้อย ให้ sort ทั้งหมดก่อนแล้วค่อย limit
                        tasks_sorted = sorted(
                            tasks,
                            key=lambda x: x.get("updated_at", "") or "",
                            reverse=True
                        )
                        limited_tasks = tasks_sorted[:limit]
                    
                    # For completed tasks, ensure full_text is available
                    # Try to construct from chunks if not present
                    for task in limited_tasks:
                        if task.get("status", "").lower() == "completed":
                            # If no full_text or corrected_text, try to construct from chunks
                            if not task.get("full_text") and not task.get("corrected_text") and not task.get("original_text"):
                                chunks = task.get("chunks", [])
                                if chunks:
                                    # Combine chunks text
                                    chunk_texts = [chunk.get("text", "") for chunk in chunks if chunk.get("text")]
                                    if chunk_texts:
                                        task["full_text"] = " ".join(chunk_texts).strip()
                    
                    # นับ status จาก tasks ที่มี (ไม่ต้องนับทั้งหมดเพื่อประหยัดเวลา)
                    status_count = {}
                    for task in tasks[:limit * 2]:  # นับจาก tasks ที่ fetch มา
                        task_status = task.get("status", "unknown").lower()
                        status_count[task_status] = status_count.get(task_status, 0) + 1
                    
                    return {
                        "tasks": limited_tasks,
                        "total": total_tasks,  # ใช้ total จาก response
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
    except aiohttp.ClientConnectorError as e:
        logger.error(f"Connection error to {server_name} ({api_url}): {e}")
        return {
            "tasks": [],
            "total": 0,
            "error": f"Cannot connect to host {api_url}",
            "error_details": str(e),
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
            # Try /api/control/videos first, fallback to /videos/list or /videos
            video_endpoints = [
                f"{api_url}/api/control/videos",
                f"{api_url}/videos/list",
                f"{api_url}/videos"
            ]
            
            videos = []
            response_status = None
            
            for endpoint in video_endpoints:
                try:
                    async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=30)) as response:  # เพิ่ม timeout เป็น 30s
                        response_status = response.status
                        if response.status == 200:
                            data = await response.json()
                            if isinstance(data, list):
                                videos = data
                            elif isinstance(data, dict):
                                if "videos" in data:
                                    videos = data["videos"]
                                elif "files" in data:
                                    videos = data["files"]
                            break
                except Exception as e:
                    logger.debug(f"Failed to get videos from {endpoint}: {e}")
                    continue
            
            if not videos:
                # If all endpoints failed, return error
                return {"error": f"Could not fetch videos from server (last status: {response_status})", "videos": []}
            
            # Process videos - ensure each video has duration and file_name info
            try:
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
            except Exception as e:
                logger.error(f"Error processing videos: {e}", exc_info=True)
                return {"error": f"Error processing videos: {str(e)}", "videos": []}
    except Exception as e:
        logger.error(f"Error getting videos from {server_name}: {e}", exc_info=True)(f"Error getting videos from {server_name}: {e}")
        return {"error": str(e), "videos": []}


@router.get("/api/server/{server_name}/task/{task_id}")
async def get_task_status(server_name: str, task_id: str):
    """Get single task status from remote server (proxy to avoid CORS)"""
    if server_name not in SERVERS:
        return {
            "error": f"Server {server_name} not found",
            "task_id": task_id,
            "status": "error"
        }
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Try /transcribe/{task_id} endpoint
            endpoint = f"{api_url}/transcribe/{task_id}"
            async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Server {server_name} returned status {response.status} for task {task_id}: {error_text[:500]}")
                    # Return error response instead of raising exception
                    return {
                        "error": f"Server returned status {response.status}",
                        "error_details": error_text[:200],
                        "task_id": task_id,
                        "status": "error",
                        "server": server_name,
                        "api_url": api_url
                    }
    except aiohttp.ClientConnectorError as e:
        logger.error(f"Connection error getting task {task_id} from {server_name}: {e}")
        return {
            "error": f"Cannot connect to host {api_url}",
            "error_details": str(e),
            "task_id": task_id,
            "status": "error",
            "server": server_name,
            "api_url": api_url
        }
    except aiohttp.ClientError as e:
        logger.error(f"Client error getting task {task_id} from {server_name}: {e}")
        return {
            "error": f"Connection error: {str(e)}",
            "error_details": str(e),
            "task_id": task_id,
            "status": "error",
            "server": server_name,
            "api_url": api_url
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error getting task {task_id} from {server_name}: {error_details}")
        return {
            "error": f"Error: {str(e)}",
            "error_details": str(e),
            "task_id": task_id,
            "status": "error",
            "server": server_name,
            "api_url": api_url
        }


@router.get("/api/server/{server_name}/queue/check-task/{task_id}")
async def check_task_in_queue(server_name: str, task_id: str):
    """ตรวจสอบ task ที่ค้างใน queue (proxy to remote server)"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{api_url}/queue/check-task/{task_id}",
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Server {server_name} returned status {response.status} for task {task_id}: {error_text}")
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Server returned status {response.status}: {error_text[:200]}"
                    )
    except aiohttp.ClientError as e:
        logger.error(f"Error checking task {task_id} from {server_name}: {e}")
        raise HTTPException(status_code=503, detail=f"Connection error: {str(e)}")
    except Exception as e:
        logger.error(f"Error checking task {task_id} from {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/server/{server_name}/tasks/{task_id}/stop")
async def stop_task(server_name: str, task_id: str):
    """Stop a single task by calling remote server's DELETE endpoint"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Try /transcribe/{task_id} first, then /api/transcribe/{task_id}
            endpoints = [
                f"{api_url}/transcribe/{task_id}",
                f"{api_url}/api/transcribe/{task_id}"
            ]
            
            last_error = None
            for endpoint in endpoints:
                try:
                    async with session.delete(
                        endpoint,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info(f"✅ Stopped task {task_id} on {server_name} via {endpoint}")
                            return {
                                "success": True,
                                "message": result.get("message", "Task stopped successfully"),
                                "task_id": task_id
                            }
                        elif response.status == 404:
                            # Task not found - might already be deleted or completed
                            logger.info(f"ℹ️ Task {task_id} not found on {server_name} (may already be deleted/completed)")
                            return {
                                "success": True,
                                "message": f"Task {task_id} not found (may already be deleted or completed)",
                                "task_id": task_id,
                                "server": server_name
                            }
                        elif response.status == 500:
                            # Server error - try next endpoint
                            error_text = await response.text()
                            last_error = f"HTTP {response.status}: {error_text[:200]}"
                            logger.warning(f"⚠️ Server error stopping task {task_id} on {server_name} via {endpoint}: {last_error}")
                            continue
                        else:
                            error_text = await response.text()
                            last_error = f"HTTP {response.status}: {error_text[:200]}"
                            logger.warning(f"⚠️ Failed to stop task {task_id} on {server_name} via {endpoint}: {last_error}")
                            continue
                except aiohttp.ClientError as e:
                    last_error = f"Connection error: {str(e)}"
                    logger.warning(f"⚠️ Connection error stopping task {task_id} on {server_name} via {endpoint}: {last_error}")
                    continue
                except Exception as e:
                    last_error = f"Unexpected error: {str(e)}"
                    logger.warning(f"⚠️ Unexpected error stopping task {task_id} on {server_name} via {endpoint}: {last_error}")
                    continue
            
            # All endpoints failed - return graceful error
            logger.warning(f"⚠️ Could not stop task {task_id} on {server_name}: All endpoints failed. Last error: {last_error}")
            return {
                "success": False,
                "message": f"Could not stop task: {last_error or 'Unknown error'}",
                "error": last_error or "Unknown error",  # For backward compatibility
                "task_id": task_id,
                "server": server_name,
                "note": "Task may already be completed or the server may not support stopping tasks"
            }
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ Timeout stopping task {task_id} on {server_name}")
        return {
            "success": False,
            "message": "Connection timeout",
            "error": "Connection timeout",  # For backward compatibility
            "task_id": task_id,
            "server": server_name,
            "note": "The server may be busy or unreachable. Task may already be completed."
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error stopping task {task_id} on {server_name}: {error_details}")
        return {
            "success": False,
            "error": f"Error: {str(e)}",
            "task_id": task_id
        }


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


@router.get("/api/server/{server_name}/chunk-audio/{task_id}/{chunk_index}")
async def get_chunk_audio(server_name: str, task_id: str, chunk_index: int):
    """Proxy audio chunk file from transcription service"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    try:
        import aiohttp
        # Proxy file from transcription service
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{api_url}/transcribe/{task_id}/chunk/{chunk_index}/audio",
                timeout=aiohttp.ClientTimeout(total=60)
            ) as audio_response:
                if audio_response.status != 200:
                    error_text = await audio_response.text()
                    raise HTTPException(
                        status_code=audio_response.status,
                        detail=f"Failed to get audio: {error_text}"
                    )
                
                # Stream the audio file
                return StreamingResponse(
                    audio_response.content.iter_chunked(8192),
                    media_type=audio_response.headers.get('Content-Type', 'audio/wav'),
                    headers={
                        'Content-Disposition': audio_response.headers.get('Content-Disposition', f'inline; filename="chunk_{chunk_index}.wav"')
                    }
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chunk audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

