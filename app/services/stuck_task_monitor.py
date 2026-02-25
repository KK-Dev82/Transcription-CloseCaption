"""
Stuck Task Monitor Service
ตรวจสอบและแก้ไข tasks ที่ค้าง (stuck tasks)
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from redis import Redis
from rq import Queue
from rq.job import Job
from rq.registry import StartedJobRegistry, FailedJobRegistry

# Load .env.runpod
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent.parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
except:
    pass

logger = logging.getLogger(__name__)


class StuckTaskMonitor:
    """Monitor และแก้ไข stuck tasks"""
    
    def __init__(self):
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            raise ValueError("REDIS_URL is not set")
        
        self.redis_conn = Redis.from_url(redis_url, decode_responses=False, socket_connect_timeout=10)
        self.stuck_threshold_seconds = int(os.getenv('STUCK_TASK_THRESHOLD_SECONDS', '60'))
        self.check_interval_seconds = int(os.getenv('STUCK_TASK_CHECK_INTERVAL_SECONDS', '30'))
        
        # Storage
        storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
        if storage_type == 'sqlite':
            from app.utils.sqlite_storage import SQLiteStorage
            self.storage = SQLiteStorage()
        else:
            from app.utils.json_storage import JSONStorage
            self.storage = JSONStorage()
    
    def is_task_really_stuck(self, task_id: str, task_data: Dict) -> tuple[bool, Optional[str]]:
        """
        ตรวจสอบว่า task ค้างจริงๆ หรือแค่ใช้เวลานาน
        
        Returns:
            (is_stuck, reason)
        """
        status = task_data.get('status', 'unknown')
        
        # ข้าม tasks ที่เสร็จแล้ว
        if status in ['completed', 'failed']:
            return False, None
        
        # ตรวจสอบ updated_at
        updated_at_str = task_data.get('updated_at')
        if not updated_at_str:
            return True, "No updated_at timestamp"
        
        try:
            if isinstance(updated_at_str, str):
                if updated_at_str.endswith('Z'):
                    updated_at_str = updated_at_str[:-1] + '+00:00'
                elif '+' not in updated_at_str and 'Z' not in updated_at_str:
                    updated_at_str = updated_at_str + '+00:00'
                updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
            else:
                return True, "Invalid updated_at format"
            
            time_diff = (datetime.now(timezone.utc) - updated_at).total_seconds()
            
            # ถ้ายังไม่ถึง threshold → ไม่ค้าง
            if time_diff < self.stuck_threshold_seconds:
                return False, None
            
            # ตรวจสอบ Redis status
            return self._check_redis_status(task_id, task_data, time_diff)
            
        except Exception as e:
            logger.warning(f"Error checking task {task_id}: {e}")
            return False, None
    
    def _check_redis_status(self, task_id: str, task_data: Dict, time_diff: float) -> Tuple[bool, Optional[str]]:
        """ตรวจสอบ Redis status เพื่อดูว่า task ค้างจริงๆ หรือไม่"""
        try:
            # ตรวจสอบ chunk status
            total_key = f"task:{task_id}:total_chunks"
            done_key = f"task:{task_id}:done_chunks"
            inflight_key = f"task:{task_id}:inflight_chunks"
            
            total = self.redis_conn.get(total_key)
            done = self.redis_conn.get(done_key)
            inflight = self.redis_conn.get(inflight_key)
            
            if not total:
                # ไม่มี chunk metadata → อาจเป็น task เก่าหรือยังไม่เริ่ม preprocess
                return True, "No chunk metadata in Redis"
            
            total = int(total.decode('utf-8')) if total else 0
            done = int(done.decode('utf-8')) if done else 0
            inflight = int(inflight.decode('utf-8')) if inflight else 0
            
            # ตรวจสอบว่า chunks กำลัง process อยู่หรือไม่
            if inflight > 0:
                # มี chunks กำลัง process → ตรวจสอบว่า jobs ยังอยู่หรือไม่
                if self._has_active_jobs(task_id, total):
                    # มี active jobs → ไม่ค้าง (แค่ใช้เวลานาน)
                    return False, None
                else:
                    # ไม่มี active jobs แต่ inflight > 0 → ค้าง (jobs หาย)
                    return True, f"Inflight={inflight} but no active jobs"
            
            # ไม่มี chunks กำลัง process
            if done < total:
                # ยังมี chunks ที่ไม่เสร็จ → ตรวจสอบว่า chunks ถูก enqueue หรือไม่
                missing_chunks = self._get_missing_chunks(task_id, total, done)
                if missing_chunks:
                    # มี chunks ที่ยังไม่ถูก enqueue → ค้าง
                    return True, f"Missing chunks: {missing_chunks}"
                else:
                    # Chunks ถูก enqueue แล้ว แต่ยังไม่เสร็จ → อาจใช้เวลานาน
                    # ตรวจสอบว่า jobs ยังอยู่หรือไม่
                    if self._has_active_jobs(task_id, total):
                        return False, None  # มี jobs กำลังทำงาน → ไม่ค้าง
                    else:
                        return True, "No active jobs but chunks not done"
            
            # done >= total → ควรเสร็จแล้ว
            if done >= total:
                # ตรวจสอบ aggregator
                aggregator_key = f"task:{task_id}:aggregator_triggered"
                aggregator_triggered = self.redis_conn.exists(aggregator_key)
                
                if not aggregator_triggered:
                    return True, "All chunks done but aggregator not triggered"
                
                # Aggregator ถูก trigger แล้ว → ตรวจสอบว่า aggregator job ยังทำงานอยู่หรือไม่
                # ถ้า aggregator ถูก trigger แล้วแต่ task ยังไม่เสร็จนานเกินไป → อาจ aggregator fail
                aggregator_job_id = f"{task_id}_aggregator"
                has_aggregator_job = self._has_active_jobs(aggregator_job_id, 1)  # ตรวจสอบ aggregator job
                
                # ตรวจสอบ task result
                result_key = f"task:{task_id}:result"
                result_exists = self.redis_conn.exists(result_key)
                
                if not result_exists and not has_aggregator_job:
                    # Aggregator ถูก trigger แล้วแต่ไม่มี aggregator job และไม่มี result → aggregator อาจ fail
                    return True, "All chunks done, aggregator triggered but no result (aggregator may have failed)"
                
                return False, None  # กำลังรอ aggregator → ไม่ค้าง
            
        except Exception as e:
            logger.warning(f"Error checking Redis status for {task_id}: {e}")
            return True, f"Error: {str(e)}"
    
    def _has_active_jobs(self, task_id: str, total_chunks: int) -> bool:
        """ตรวจสอบว่ามี active jobs สำหรับ task นี้หรือไม่"""
        try:
            # ตรวจสอบในทุก queue
            queues = ['gpu0', 'gpu1', 'cpu0', 'cpu1', 'preprocess0', 'preprocess1', 'PRIORITY']
            
            for queue_name in queues:
                queue = Queue(queue_name, connection=self.redis_conn)
                for job_id in queue.job_ids:
                    if task_id in job_id:
                        try:
                            job = Job.fetch(job_id, connection=self.redis_conn)
                            if job.get_status() in ['queued', 'started']:
                                return True
                        except:
                            pass
            
            # ตรวจสอบ started registry
            for queue_name in ['gpu0', 'gpu1']:
                try:
                    registry = StartedJobRegistry(queue_name, connection=self.redis_conn)
                    for job_id in registry.get_job_ids():
                        if task_id in job_id:
                            return True
                except:
                    pass
            
            return False
        except Exception as e:
            logger.warning(f"Error checking active jobs for {task_id}: {e}")
            return False
    
    def _get_missing_chunks(self, task_id: str, total: int, done: int) -> List[int]:
        """หาช่วง chunks ที่ยังไม่เสร็จและยังไม่ถูก enqueue หรือ guard มีแต่ chunk ไม่มี"""
        missing = []
        
        # ตรวจสอบ guard keys
        for i in range(total):
            guard_key = f"task:{task_id}:enqueued:{i}"
            chunk_key = f"task:{task_id}:chunk:{i}"
            
            guard_exists = self.redis_conn.exists(guard_key)
            chunk_exists = self.redis_conn.exists(chunk_key)
            
            # ถ้า chunk ยังไม่เสร็จ → ต้อง re-enqueue
            if not chunk_exists:
                # กรณี 1: guard ไม่มี → ยังไม่เคย enqueue
                # กรณี 2: guard มีแต่ chunk ไม่มี → enqueue แล้วแต่ job หาย/ fail → ต้อง re-enqueue
                missing.append(i)
        
        return missing
    
    def fix_stuck_task(self, task_id: str, reason: str) -> bool:
        """แก้ไข stuck task โดย re-enqueue chunks ที่หาย"""
        try:
            logger.info(f"🔧 Fixing stuck task {task_id}: {reason}")
            
            # ตรวจสอบ chunk metadata
            chunks_metadata_key = f"task:{task_id}:chunks_metadata"
            chunks_metadata_str = self.redis_conn.get(chunks_metadata_key)
            
            if not chunks_metadata_str:
                logger.warning(f"⚠️  No chunk metadata for {task_id}, cannot fix")
                return False
            
            chunks_metadata = json.loads(chunks_metadata_str.decode('utf-8'))
            chunk_paths = chunks_metadata.get('chunk_paths', [])
            total_chunks = chunks_metadata.get('total_chunks', 0)
            language = chunks_metadata.get('language', 'th')
            model_size = chunks_metadata.get('model_size', 'base')
            chunk_duration = chunks_metadata.get('chunk_duration', 150)
            source = chunks_metadata.get('source', 'upload')
            
            # หา chunks ที่ต้อง re-enqueue
            missing_chunks = self._get_missing_chunks(task_id, total_chunks, 0)
            
            if not missing_chunks:
                # ไม่มี chunks ที่ต้อง enqueue → อาจเป็นปัญหาอื่น
                # ลอง fix done_chunks counter
                done_key = f"task:{task_id}:done_chunks"
                done = self.redis_conn.get(done_key)
                done_value = int(done.decode('utf-8')) if done else 0
                
                # ตรวจสอบ chunks ที่เสร็จแล้วแต่ counter ไม่ถูกอัปเดต
                for i in range(total_chunks):
                    chunk_key = f"task:{task_id}:chunk:{i}"
                    if self.redis_conn.exists(chunk_key) and i >= done_value:
                        # Chunk เสร็จแล้วแต่ counter ไม่ถูกอัปเดต
                        new_done = self.redis_conn.incr(done_key)
                        logger.info(f"✅ Fixed done_chunks counter: {new_done}/{total_chunks}")
                
                # ตรวจสอบ aggregator
                if done_value >= total_chunks:
                    aggregator_key = f"task:{task_id}:aggregator_triggered"
                    aggregator_triggered = self.redis_conn.exists(aggregator_key)
                    result_key = f"task:{task_id}:result"
                    result_exists = self.redis_conn.exists(result_key)
                    
                    # ตรวจสอบ aggregator job
                    aggregator_job_id = f"{task_id}_aggregator"
                    has_aggregator_job = self._has_active_jobs(aggregator_job_id, 1)
                    
                    if not aggregator_triggered:
                        # Aggregator ยังไม่ถูก trigger → trigger
                        ttl = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))
                        self.redis_conn.setex(aggregator_key, ttl, b"1")
                        logger.info(f"✅ Triggered aggregator")
                    elif aggregator_triggered and not result_exists and not has_aggregator_job:
                        # Aggregator ถูก trigger แล้วแต่ไม่มี result และไม่มี aggregator job → re-enqueue aggregator
                        logger.info(f"🔄 Re-enqueueing aggregator job (aggregator may have failed)")
                        try:
                            from app.services.redis_queue_service import get_redis_queue_service
                            queue_service = get_redis_queue_service()
                            job_id = queue_service.enqueue_aggregator(
                                task_id=aggregator_job_id,
                                language=language,
                                model_size=model_size,
                                chunk_duration=chunk_duration
                            )
                            logger.info(f"✅ Re-enqueued aggregator job: {job_id}")
                        except Exception as e:
                            logger.error(f"❌ Failed to re-enqueue aggregator: {e}")
                
                return True
            
            # Re-enqueue missing chunks
            from app.services.redis_queue_service import get_redis_queue_service
            queue_service = get_redis_queue_service()
            num_gpus = int(os.getenv('NUM_GPUS', '1'))
            
            re_enqueued = 0
            for chunk_index in missing_chunks:
                if chunk_index >= len(chunk_paths):
                    continue
                
                chunk_path = chunk_paths[chunk_index]
                chunk_task_id = f"{task_id}_chunk_{chunk_index}"
                gpu_index = chunk_index % num_gpus
                worker_gpu = f'gpu{gpu_index}'
                
                try:
                    guard_key = f"task:{task_id}:enqueued:{chunk_index}"
                    chunk_key = f"task:{task_id}:chunk:{chunk_index}"
                    ttl = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))
                    
                    # ตรวจสอบว่า chunk result มีอยู่หรือไม่
                    chunk_exists = self.redis_conn.exists(chunk_key)
                    guard_exists = self.redis_conn.exists(guard_key)
                    
                    # ถ้า guard มีอยู่แต่ chunk result ไม่มี → clear guard และ re-enqueue
                    if guard_exists and not chunk_exists:
                        logger.info(f"🔓 Clearing guard key for chunk {chunk_index} (chunk result missing)")
                        self.redis_conn.delete(guard_key)
                        guard_exists = False
                    
                    # Re-enqueue ถ้า guard ไม่มี
                    if not guard_exists:
                        self.redis_conn.setex(guard_key, ttl, b"1")
                        
                        # Enqueue chunk
                        job_id = queue_service.enqueue_transcription(
                            task_id=chunk_task_id,
                            file_path=chunk_path,
                            language=language,
                            model_size=model_size,
                            chunk_duration=chunk_duration,
                            priority=False,
                            worker_gpu=worker_gpu,
                            source=source
                        )
                        
                        # Increment inflight
                        inflight_key = f"task:{task_id}:inflight_chunks"
                        self.redis_conn.incr(inflight_key)
                        self.redis_conn.expire(inflight_key, ttl)
                        
                        re_enqueued += 1
                        logger.info(f"✅ Re-enqueued chunk {chunk_index}: {job_id}")
                    elif chunk_exists:
                        logger.debug(f"⏭️  Skipping chunk {chunk_index} (already completed)")
                    else:
                        logger.debug(f"⏭️  Skipping chunk {chunk_index} (guard exists, may be processing)")
                except Exception as e:
                    logger.error(f"❌ Failed to re-enqueue chunk {chunk_index}: {e}")
            
            if re_enqueued > 0:
                logger.info(f"✅ Re-enqueued {re_enqueued} chunks for {task_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error fixing stuck task {task_id}: {e}", exc_info=True)
            return False
    
    def check_and_fix_stuck_tasks(self) -> Dict:
        """ตรวจสอบและแก้ไข stuck tasks ทั้งหมด"""
        try:
            # ดึง tasks ทั้งหมด
            if hasattr(self.storage, 'list_all_transcriptions'):
                all_tasks_list = self.storage.list_all_transcriptions()
                all_tasks = []
                for task in all_tasks_list:
                    task_id = task.get('task_id')
                    if task_id:
                        task_data = self.storage.load_transcription(task_id, skip_migration=True)
                        if task_data:
                            all_tasks.append((task_id, task_data))
            else:
                # Fallback to JSON storage
                storage_dir = Path("storage/transcriptions")
                all_tasks = []
                if storage_dir.exists():
                    for task_file in storage_dir.glob("*.json"):
                        task_id = task_file.stem
                        task_data = self.storage.load_transcription(task_id)
                        if task_data:
                            all_tasks.append((task_id, task_data))
            
            stuck_tasks = []
            fixed_tasks = []
            
            for task_id, task_data in all_tasks:
                is_stuck, reason = self.is_task_really_stuck(task_id, task_data)
                
                if is_stuck:
                    stuck_tasks.append({
                        'task_id': task_id,
                        'reason': reason,
                        'status': task_data.get('status'),
                        'progress': task_data.get('progress', 0)
                    })
                    
                    # พยายามแก้ไข
                    if self.fix_stuck_task(task_id, reason):
                        fixed_tasks.append(task_id)
            
            return {
                'checked': len(all_tasks),
                'stuck': len(stuck_tasks),
                'fixed': len(fixed_tasks),
                'stuck_tasks': stuck_tasks,
                'fixed_tasks': fixed_tasks
            }
            
        except Exception as e:
            logger.error(f"❌ Error checking stuck tasks: {e}", exc_info=True)
            return {
                'checked': 0,
                'stuck': 0,
                'fixed': 0,
                'error': str(e)
            }
    
    async def run_periodic_check(self):
        """รัน periodic check ใน background"""
        logger.info(f"🔄 Stuck Task Monitor started (check every {self.check_interval_seconds}s)")
        
        while True:
            try:
                result = self.check_and_fix_stuck_tasks()
                logger.info(
                    f"📊 Stuck Task Check: {result['checked']} checked, "
                    f"{result['stuck']} stuck, {result['fixed']} fixed"
                )
                
                if result['stuck'] > 0:
                    logger.warning(f"⚠️  Found {result['stuck']} stuck tasks")
                
            except Exception as e:
                logger.error(f"❌ Error in periodic check: {e}", exc_info=True)
            
            await asyncio.sleep(self.check_interval_seconds)
