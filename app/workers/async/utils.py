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
    
    def save_chunk_result(self, parent_task_id: str, chunk_index: int, chunk_data: Dict, total_chunks: int):
        """บันทึกผลลัพธ์ของ chunk ลง storage และอัปเดต progress"""
        try:
            from datetime import datetime, timezone
            
            logger.debug(f"💾 save_chunk_result called: task={parent_task_id}, chunk={chunk_index+1}/{total_chunks}")
            
            # Load parent task
            parent_task = self.worker.json_storage.get_transcription(parent_task_id)
            if not parent_task:
                logger.error(f"❌ Parent task {parent_task_id} not found in storage")
                return
            
            # Initialize chunks array if not exists
            if 'chunks' not in parent_task or parent_task['chunks'] is None:
                parent_task['chunks'] = [None] * total_chunks
                logger.debug(f"   Initialized chunks array with {total_chunks} slots")
            
            # Ensure chunks array has correct size
            current_length = len(parent_task['chunks'])
            if current_length < total_chunks:
                # Extend array if needed
                parent_task['chunks'].extend([None] * (total_chunks - current_length))
                logger.debug(f"   Extended chunks array from {current_length} to {total_chunks}")
            elif current_length > total_chunks:
                # Truncate if too large (shouldn't happen, but handle it)
                parent_task['chunks'] = parent_task['chunks'][:total_chunks]
                logger.warning(f"   Truncated chunks array from {current_length} to {total_chunks}")
            
            # Validate chunk_index
            if chunk_index < 0 or chunk_index >= total_chunks:
                logger.error(f"❌ Invalid chunk_index {chunk_index} (valid range: 0-{total_chunks-1})")
                return
            
            # Save chunk result
            parent_task['chunks'][chunk_index] = chunk_data
            logger.debug(f"   Saved chunk {chunk_index+1} data (text length: {len(chunk_data.get('text', ''))})")
            
            # Update progress
            completed_chunks = sum(1 for c in parent_task['chunks'] if c is not None)
            
            # อัปเดต total_chunks และ completed_chunks
            parent_task['total_chunks'] = total_chunks
            parent_task['completed_chunks'] = completed_chunks
            
            # คำนวณ progress percentage
            # สำหรับ display_mode='full_text': progress = 10 + (completed_chunks / total_chunks) * 80
            # สำหรับ display_mode='realtime_chunks': progress = (completed_chunks / total_chunks) * 100
            display_mode = parent_task.get('display_mode', 'full_text')
            if display_mode == 'realtime_chunks':
                progress = int((completed_chunks / total_chunks) * 100) if total_chunks > 0 else 0
            else:
                # Full text: 10% = starting, 10-90% = processing chunks, 90-100% = merging/finalizing
                progress = 10 + int((completed_chunks / total_chunks) * 80) if total_chunks > 0 else 0
            
            parent_task['progress'] = progress
            
            # อัปเดต status
            if completed_chunks == total_chunks:
                # ถ้า chunks เสร็จหมดแล้ว แต่ยังไม่ finalize ให้รอ finalize
                if parent_task.get('status') != 'completed':
                    parent_task['status'] = 'processing'  # ยังไม่ completed จนกว่าจะ finalize
                    parent_task['current_stage'] = 'merging_results'
                    parent_task['current_stage_description'] = 'กำลังรวมผลลัพธ์จาก chunks'
            elif parent_task.get('status') == 'pending':
                parent_task['status'] = 'processing'
                if not parent_task.get('current_stage'):
                    parent_task['current_stage'] = 'transcribing_chunks'
                    parent_task['current_stage_description'] = f'กำลังแปลงเสียง chunk {completed_chunks}/{total_chunks}'
            
            # อัปเดต updated_at ทุกครั้งที่บันทึก chunk result
            parent_task['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # อัปเดต total_tasks และ completed_tasks
            audio_extraction_done = parent_task.get('audio_extraction_time') is not None
            total_tasks = (1 if audio_extraction_done else 0) + total_chunks
            completed_tasks = (1 if audio_extraction_done else 0) + completed_chunks
            parent_task['total_tasks'] = total_tasks
            parent_task['completed_tasks'] = completed_tasks
            
            # Save to storage
            self.worker.json_storage.save_transcription(parent_task_id, parent_task)
            
            logger.info(f"📊 Task {parent_task_id}: Progress {progress}% ({completed_chunks}/{total_chunks} chunks completed)")
            
        except Exception as e:
            logger.error(f"❌ Error saving chunk result for task {parent_task_id}, chunk {chunk_index+1}: {e}", exc_info=True)
            # Re-raise เพื่อให้ caller รู้ว่ามี error
            raise
    
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
