"""
Worker Utilities (aio-pika - Async)

Utility functions สำหรับ async worker: monitoring, tracking, timeout protection
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Awaitable
import functools

logger = logging.getLogger(__name__)


class AsyncWorkerUtils:
    """
    Async worker utilities สำหรับ monitoring, tracking, และ helper functions
    """
    
    def __init__(self, worker):
        """
        Initialize worker utils
        
        Args:
            worker: Worker instance ที่มี services, storage, connection, etc.
        """
        self.worker = worker
        
        # Task tracking
        self.active_tasks: Dict[str, Dict[str, Any]] = {}  # {task_id: {started_at, timeout, handler_info}}
        
        # Configuration
        self.default_task_timeout = int(os.getenv('TASK_TIMEOUT_SECONDS', '1800'))  # 30 minutes default
        self.stuck_task_threshold = int(os.getenv('STUCK_TASK_THRESHOLD_SECONDS', '600'))  # 10 minutes
        
        logger.info(f"🔧 Worker utils initialized: default_timeout={self.default_task_timeout}s, stuck_threshold={self.stuck_task_threshold}s")
    
    def track_task_start(self, task_id: str, task_type: str, timeout: Optional[int] = None):
        """
        Track task processing start
        
        Args:
            task_id: Task ID
            task_type: Type of task (e.g., 'transcription', 'audio_extraction')
            timeout: Optional timeout in seconds (uses default if not provided)
        """
        self.active_tasks[task_id] = {
            'task_id': task_id,
            'task_type': task_type,
            'started_at': time.time(),
            'timeout': timeout or self.default_task_timeout,
            'status': 'processing',
            'last_heartbeat': time.time()
        }
        logger.debug(f"📊 Started tracking task: {task_id} (type: {task_type}, timeout: {timeout or self.default_task_timeout}s)")
    
    def track_task_heartbeat(self, task_id: str, stage: Optional[str] = None, progress: Optional[int] = None):
        """
        Update task heartbeat (indicates task is still processing)
        
        Args:
            task_id: Task ID
            stage: Optional current stage
            progress: Optional progress percentage
        """
        if task_id in self.active_tasks:
            self.active_tasks[task_id]['last_heartbeat'] = time.time()
            if stage:
                self.active_tasks[task_id]['current_stage'] = stage
            if progress is not None:
                self.active_tasks[task_id]['progress'] = progress
            logger.debug(f"📊 Task heartbeat: {task_id} (stage: {stage}, progress: {progress}%)")
    
    def track_task_complete(self, task_id: str, status: str = 'completed'):
        """
        Track task completion
        
        Args:
            task_id: Task ID
            status: Final status ('completed', 'failed')
        """
        if task_id in self.active_tasks:
            task_info = self.active_tasks[task_id]
            duration = time.time() - task_info['started_at']
            task_info['status'] = status
            task_info['completed_at'] = time.time()
            task_info['duration'] = duration
            logger.info(f"📊 Task completed: {task_id} (status: {status}, duration: {duration:.2f}s)")
            # Keep in active_tasks for a while for analysis, but mark as completed
        else:
            logger.warning(f"⚠️  Tried to track completion for unknown task: {task_id}")
    
    def get_stuck_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        Detect stuck tasks (no heartbeat for too long)
        
        Returns:
            Dictionary of stuck tasks: {task_id: task_info}
        """
        stuck_tasks = {}
        now = time.time()
        
        for task_id, task_info in self.active_tasks.items():
            if task_info['status'] == 'processing':
                time_since_heartbeat = now - task_info['last_heartbeat']
                elapsed_time = now - task_info['started_at']
                
                # Task is stuck if:
                # 1. No heartbeat for longer than threshold, OR
                # 2. Total elapsed time exceeds timeout
                if time_since_heartbeat > self.stuck_task_threshold or elapsed_time > task_info['timeout']:
                    stuck_tasks[task_id] = {
                        **task_info,
                        'time_since_heartbeat': time_since_heartbeat,
                        'elapsed_time': elapsed_time
                    }
        
        return stuck_tasks
    
    async def monitor_transcription_progress(self, task_id: str):
        """Monitor progress และ log updates (async version)"""
        last_progress = -1
        last_status = ""
        last_log_time = 0
        
        try:
            while True:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                # Update heartbeat
                self.track_task_heartbeat(task_id)
                
                try:
                    task_info = self.worker.json_storage.get_transcription(task_id)
                    if task_info:
                        current_progress = task_info.get('progress', 0)
                        current_status = task_info.get('status', '')
                        current_stage = task_info.get('current_stage', '')
                        current_time = time.time()
                        
                        progress_changed = (current_progress != last_progress or current_status != last_status)
                        time_since_last_log = current_time - last_log_time
                        
                        if progress_changed or time_since_last_log >= 30:
                            # Update heartbeat with stage and progress
                            self.track_task_heartbeat(task_id, stage=current_stage, progress=current_progress)
                            
                            if progress_changed:
                                logger.info(f"📊 Task {task_id}: Progress {current_progress}% - Status: {current_status} - Stage: {current_stage}")
                            else:
                                logger.debug(f"📊 Task {task_id}: Progress {current_progress}% - Status: {current_status} (heartbeat)")
                            
                            last_progress = current_progress
                            last_status = current_status
                            last_log_time = current_time
                    
                    # ถ้า task completed หรือ failed ให้หยุด monitoring
                    if task_info:
                        status = task_info.get('status', '')
                        if status in ['completed', 'failed']:
                            logger.info(f"📊 Task {task_id} finished with status: {status}")
                            self.track_task_complete(task_id, status)
                            break
                    
                except Exception as e:
                    logger.error(f"❌ Error monitoring task {task_id}: {e}", exc_info=True)
                    await asyncio.sleep(5)
        
        except asyncio.CancelledError:
            logger.debug(f"📊 Monitoring cancelled for task {task_id}")
            raise
        except Exception as e:
            logger.error(f"❌ Monitor error for task {task_id}: {e}", exc_info=True)
    
    async def execute_chunk_transcription_async(self, chunk_task: Dict[str, Any]):
        """Execute chunk transcription async (สำหรับ asyncio tasks)"""
        chunk_index = chunk_task.get('chunk_index', 0)
        total_chunks = chunk_task.get('total_chunks', 0)
        parent_task_id = chunk_task.get('parent_task_id', 'unknown')
        
        logger.info(f"🔄 Starting chunk {chunk_index+1}/{total_chunks} for task {parent_task_id}")
        
        try:
            await self.worker.processors.execute_chunk_transcription(chunk_task)
            logger.info(f"✅ Completed chunk {chunk_index+1}/{total_chunks} for task {parent_task_id}")
            
        except Exception as e:
            logger.error(f"❌ Error in chunk {chunk_index+1} transcription: {e}", exc_info=True)
        finally:
            # Clean up from active_chunks (หา delivery_tag จาก task หรือใช้ index)
            # Note: ใน async worker เราใช้ asyncio tasks แทน ThreadPoolExecutor
            # ดังนั้น active_chunks จะเก็บ asyncio.Task objects
            pass


def with_timeout(timeout_seconds: int, task_type: str = "task"):
    """
    Decorator สำหรับเพิ่ม timeout protection ให้กับ async handler functions
    
    Args:
        timeout_seconds: Timeout in seconds
        task_type: Type of task (for logging)
    
    Usage:
        @with_timeout(1800, "transcription")
        async def handle_transcription(self, message):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract task_id if available
            task_id = None
            if args and len(args) > 1:
                # Try to get task_id from message or task_data
                message_or_data = args[1]
                if hasattr(message_or_data, 'body'):
                    # It's a message
                    try:
                        data = json.loads(message_or_data.body.decode('utf-8'))
                        task_id = data.get('task_id')
                    except:
                        pass
                elif isinstance(message_or_data, dict):
                    # It's task_data
                    task_id = message_or_data.get('task_id')
            
            start_time = time.time()
            logger.info(f"⏱️  Starting {task_type} handler: timeout={timeout_seconds}s" + (f", task_id={task_id}" if task_id else ""))
            
            try:
                # Run with timeout
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
                elapsed = time.time() - start_time
                logger.info(f"✅ {task_type} handler completed in {elapsed:.2f}s" + (f", task_id={task_id}" if task_id else ""))
                return result
            
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                logger.error(f"⏱️  {task_type} handler TIMEOUT after {elapsed:.2f}s (limit: {timeout_seconds}s)" + (f", task_id={task_id}" if task_id else ""))
                raise
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"❌ {task_type} handler failed after {elapsed:.2f}s: {e}" + (f", task_id={task_id}" if task_id else ""), exc_info=True)
                raise
        
        return wrapper
    return decorator


# Note: safe_handler_execution removed - use @with_timeout decorator instead
