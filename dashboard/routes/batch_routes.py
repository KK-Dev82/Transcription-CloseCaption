"""
Batch transcription API routes
"""
import asyncio
import logging
import uuid
import random
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, Field

# Support both relative and absolute imports
try:
    from ..server_constants import SERVERS
    from ..services import batch_service
except ImportError:
    try:
        from ..config import SERVERS
        from ..services import batch_service
    except ImportError:
        import sys
        from pathlib import Path
        dashboard_dir = Path(__file__).parent.parent
        if str(dashboard_dir) not in sys.path:
            sys.path.insert(0, str(dashboard_dir))
        try:
            from server_constants import SERVERS
            from services import batch_service
        except ImportError:
            from config import SERVERS
            from services import batch_service

batch_tasks_store = batch_service.batch_tasks_store

logger = logging.getLogger(__name__)
router = APIRouter()


class BatchTranscriptionRequest(BaseModel):
    server_name: str
    video_files: List[str]
    concurrency: int = Field(1, ge=1, le=50)
    model_size: str = "medium"
    language: str = "th"


class BatchTaskStatus(BaseModel):
    batch_id: str
    server_name: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    processing_tasks: int
    pending_tasks: int
    task_ids: List[str]
    created_at: str
    status: str

    total_duration: Optional[float] = None


async def send_transcription_task(server_name: str, video_file: str, model_size: str, language: str, batch_id: str, callback_url: str = None, max_retries: int = 3):
    """Send a single transcription task to remote server with retry logic for rate limiting"""
    if server_name not in SERVERS:
        logger.error(f"❌ Server {server_name} not found in SERVERS config")
        return None
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    # Log which server we're sending to
    logger.info(f"📤 Sending transcription task to server: {server_name} ({api_url})")
    logger.info(f"   File: {video_file}, Model: {model_size}, Language: {language}")
    
    import aiohttp
    import json
    
    request_payload = {
        "file_path": video_file,
        "language": language,
        "model_size": model_size,
        "use_chunking": False
    }
    
    # Add callback_url if provided
    if callback_url:
        request_payload["callback_url"] = callback_url
        logger.debug(f"   Callback URL: {callback_url}")
    
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{api_url}/transcribe",
                    json=request_payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        task_id = result.get("task_id")
                        
                        logger.info(f"✅ Successfully sent task to {server_name}: task_id={task_id}")
                        
                        # Update batch status
                        if batch_id in batch_tasks_store:
                            batch_tasks_store[batch_id].pending_tasks -= 1
                            batch_tasks_store[batch_id].processing_tasks += 1
                        
                        return task_id
                    elif response.status == 429:
                        # Rate limit exceeded - retry after delay with exponential backoff + jitter
                        retry_after = int(response.headers.get("Retry-After", "60"))
                        error_data = await response.text()
                        try:
                            error_json = json.loads(error_data)
                            error_detail = error_json.get("detail", "Rate limit exceeded")
                        except:
                            error_detail = error_data
                        
                        if attempt < max_retries - 1:
                            # Exponential backoff: base * 2^attempt + jitter (±20%)
                            base_delay = retry_after if retry_after > 0 else 3
                            exponential_delay = base_delay * (2 ** attempt)
                            jitter = exponential_delay * 0.2 * (2 * random.random() - 1)  # ±20% jitter
                            delay = max(1, int(exponential_delay + jitter))
                            
                            logger.warning(f"⚠️  Rate limit exceeded (HTTP 429) for {server_name}, attempt {attempt + 1}/{max_retries}. Retrying after {delay} seconds (exponential backoff + jitter)...")
                            logger.warning(f"   Error: {error_detail}")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            logger.error(f"❌ Error sending task to {server_name} (HTTP 429 after {max_retries} attempts): {error_detail}")
                            if batch_id in batch_tasks_store:
                                batch_tasks_store[batch_id].pending_tasks -= 1
                                batch_tasks_store[batch_id].failed_tasks += 1
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Error sending task to {server_name} (HTTP {response.status}): {error_text}")
                        
                        if batch_id in batch_tasks_store:
                            batch_tasks_store[batch_id].pending_tasks -= 1
                            batch_tasks_store[batch_id].failed_tasks += 1
                        
                        return None
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                # Exponential backoff + jitter for timeout errors
                base_delay = 3
                exponential_delay = base_delay * (2 ** attempt)
                jitter = exponential_delay * 0.2 * (2 * random.random() - 1)  # ±20% jitter
                delay = max(1, int(exponential_delay + jitter))
                
                logger.warning(f"⚠️  Timeout sending task to {server_name}, attempt {attempt + 1}/{max_retries}. Retrying after {delay} seconds (exponential backoff + jitter)...")
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(f"❌ Timeout sending task to {server_name} after {max_retries} attempts")
                if batch_id in batch_tasks_store:
                    batch_tasks_store[batch_id].pending_tasks -= 1
                    batch_tasks_store[batch_id].failed_tasks += 1
                return None
        except Exception as e:
            if attempt < max_retries - 1:
                # Exponential backoff + jitter for general exceptions
                base_delay = 3
                exponential_delay = base_delay * (2 ** attempt)
                jitter = exponential_delay * 0.2 * (2 * random.random() - 1)  # ±20% jitter
                delay = max(1, int(exponential_delay + jitter))
                
                logger.warning(f"⚠️  Exception sending task to {server_name}, attempt {attempt + 1}/{max_retries}: {e}. Retrying after {delay} seconds (exponential backoff + jitter)...")
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(f"❌ Exception sending task to {server_name} ({api_url}) after {max_retries} attempts: {e}", exc_info=True)
                if batch_id in batch_tasks_store:
                    batch_tasks_store[batch_id].pending_tasks -= 1
                    batch_tasks_store[batch_id].failed_tasks += 1
                return None
    
    return None


async def send_all_tasks(
    server_name: str,
    video_files: List[str],
    model_size: str,
    language: str,
    concurrency: int,
    batch_id: str,
    callback_url: str = None
):
    """Send all tasks concurrently"""
    from datetime import datetime, timezone
    import os
    
    logger.info(f"🚀 Starting batch transcription: server={server_name}, files={len(video_files)}, concurrency={concurrency}")
    
    # Verify server config
    if server_name not in SERVERS:
        logger.error(f"❌ Server {server_name} not found in SERVERS config!")
        if batch_id in batch_tasks_store:
            batch_tasks_store[batch_id].status = "failed"
            batch_tasks_store[batch_id].failed_tasks = len(video_files)
        return
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    logger.info(f"📍 Target server: {server_name} -> {api_url}")
    
    # Get webhook URL if not provided
    if not callback_url:
        dashboard_base_url = os.getenv("DASHBOARD_BASE_URL", "http://localhost:8020")
        callback_url = f"{dashboard_base_url}/api/webhook/transcription"
        logger.info(f"📞 Using webhook callback URL: {callback_url}")
    
    # Limit concurrency to avoid rate limiting (API limit is 60 requests/minute)
    # Use lower concurrency to stay under rate limit
    effective_concurrency = min(concurrency, 50)  # Cap at 50 to leave buffer for rate limit
    semaphore = asyncio.Semaphore(effective_concurrency)
    task_ids = []
    
    async def send_with_semaphore(video_file: str, index: int):
        async with semaphore:
            # Add small delay between requests to avoid hitting rate limit
            if index > 0 and index % 10 == 0:
                await asyncio.sleep(1)  # Small delay every 10 requests
            return await send_transcription_task(server_name, video_file, model_size, language, batch_id, callback_url)
    
    tasks = [send_with_semaphore(video_file, idx) for idx, video_file in enumerate(video_files)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    failed_tasks = []
    for idx, (video_file, result) in enumerate(zip(video_files, results)):
        if result and not isinstance(result, Exception):
            task_ids.append(result)
            logger.debug(f"✅ Task {idx + 1}/{len(video_files)}: {video_file} -> task_id={result}")
        elif isinstance(result, Exception):
            logger.error(f"❌ Task {idx + 1}/{len(video_files)} failed with exception: {result}")
            failed_tasks.append((idx + 1, video_file, str(result)))
        else:
            # result is None - task failed to send
            logger.error(f"❌ Task {idx + 1}/{len(video_files)} failed: {video_file} -> No task_id returned")
            failed_tasks.append((idx + 1, video_file, "No task_id returned from server"))
    
    logger.info(f"✅ Batch complete: {len(task_ids)}/{len(video_files)} tasks sent successfully to {server_name}")
    if failed_tasks:
        logger.warning(f"⚠️  Failed tasks ({len(failed_tasks)}):")
        for task_num, video_file, error in failed_tasks:
            logger.warning(f"   - Task {task_num}: {video_file} - {error}")
    
    # Update batch status
    if batch_id in batch_tasks_store:
        batch_tasks_store[batch_id].task_ids = task_ids
        batch_tasks_store[batch_id].pending_tasks = len(video_files) - len(task_ids)
        if len(task_ids) == len(video_files):
            batch_tasks_store[batch_id].status = "sent"
        elif len(task_ids) > 0:
            batch_tasks_store[batch_id].status = "partial"
        else:
            batch_tasks_store[batch_id].status = "failed"


@router.post("/api/batch/transcription")
async def start_batch_transcription(request: BatchTranscriptionRequest, background_tasks: BackgroundTasks):
    """Start batch transcription tasks"""
    if request.server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {request.server_name} not found")
    
    batch_id = str(uuid.uuid4())
    from datetime import datetime, timezone
    
    batch_status = BatchTaskStatus(
        batch_id=batch_id,
        server_name=request.server_name,
        total_tasks=len(request.video_files),
        completed_tasks=0,
        failed_tasks=0,
        processing_tasks=0,
        pending_tasks=len(request.video_files),
        task_ids=[],
        created_at=datetime.now(timezone.utc).isoformat(),
        status="starting"
    )
    
    batch_tasks_store[batch_id] = batch_status
    
    # Start background task to send all requests
    background_tasks.add_task(
        send_all_tasks,
        request.server_name,
        request.video_files,
        request.model_size,
        request.language,
        request.concurrency,
        batch_id
    )
    
    batch_tasks_store[batch_id].status = "processing"
    
    return {
        "batch_id": batch_id,
        "server_name": request.server_name,
        "total_tasks": len(request.video_files),
        "status": "processing",
        "task_ids": []  # Will be populated by send_all_tasks
    }


@router.get("/api/batch/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get batch transcription status"""
    if batch_id not in batch_tasks_store:
        raise HTTPException(status_code=404, detail="Batch ID not found")
    
    batch_status = batch_tasks_store[batch_id]
    
    # Update status counts by checking remote server
    if batch_status.task_ids:
        try:
            server_name = batch_status.server_name
            if server_name in SERVERS:
                server_config = SERVERS[server_name]
                api_url = server_config["api_url"]
                
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    # Get status of all tasks
                    task_statuses = await asyncio.gather(
                        *[
                            session.get(f"{api_url}/transcribe/{task_id}", timeout=aiohttp.ClientTimeout(total=5))
                            for task_id in batch_status.task_ids
                        ],
                        return_exceptions=True
                    )
                    
                    completed = 0
                    failed = 0
                    processing = 0
                    pending = 0
                    
                    for response in task_statuses:
                        if isinstance(response, Exception):
                            continue
                        try:
                            if response.status == 200:
                                task_data = await response.json()
                                status = task_data.get("status", "").lower()
                                if status == "completed":
                                    completed += 1
                                elif status == "failed":
                                    failed += 1
                                elif status == "processing":
                                    processing += 1
                                else:
                                    pending += 1
                        except:
                            pass
                    
                    batch_status.completed_tasks = completed
                    batch_status.failed_tasks = failed
                    batch_status.processing_tasks = processing
                    batch_status.pending_tasks = pending
                    
                    if completed + failed == batch_status.total_tasks:
                        batch_status.status = "completed"
        except Exception as e:
            logger.error(f"Error updating batch status: {e}")
    
    return batch_status


@router.get("/api/servers")
async def get_servers():
    """Get list of configured servers"""
    return {
        "servers": [
            {
                "name": name,
                "api_url": config["api_url"],
                "color": config.get("color", "#0071e3")
            }
            for name, config in SERVERS.items()
        ]
    }

