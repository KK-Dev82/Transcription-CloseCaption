"""
Redis Queue Service สำหรับ Multi-GPU Transcription
ใช้ RQ (Redis Queue) เพื่อจัดการ job queue แทน HTTP request แบบ sync
"""
import os
import json
import logging
import uuid
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
from redis import Redis
from rq import Queue, Worker, Connection
from rq.job import Job
from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry

# Load .env.runpod if exists (ต้องทำก่อนใช้ os.getenv)
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent.parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass  # python-dotenv not installed, will use system env vars
except Exception:
    pass  # Failed to load, will use system env vars

logger = logging.getLogger(__name__)


class QueueFullError(Exception):
    """Exception เมื่อ queue เต็ม"""
    
    def __init__(self, current_count: int, max_size: int, queue_name: str):
        self.current_count = current_count
        self.max_size = max_size
        self.queue_name = queue_name
        self.message = f"Queue เต็มแล้ว (มี {current_count}/{max_size} jobs ในคิว {queue_name}) โปรดรอซักครู่แล้วลองใหม่"
        super().__init__(self.message)


class RedisQueueService:
    """Redis Queue Service สำหรับจัดการ transcription jobs"""
    
    def __init__(self):
        # FIX: บังคับให้ต้องมี REDIS_URL ไม่งั้น error (ป้องกัน enqueue ไป localhost)
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            error_msg = "REDIS_URL is not set. Cannot connect to Redis. Please set REDIS_URL environment variable."
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        # Log REDIS_URL เพื่อ debug (แต่ซ่อน password)
        redis_url_log = redis_url
        if '@' in redis_url:
            # Mask password in log
            parts = redis_url.split('@')
            if len(parts) == 2:
                auth_part = parts[0]
                if ':' in auth_part:
                    user_pass = auth_part.split('://', 1)[1] if '://' in auth_part else auth_part
                    if ':' in user_pass:
                        user, _ = user_pass.split(':', 1)
                        redis_url_log = redis_url.replace(f':{user_pass.split(":")[1]}', ':****')
        
        logger.info(f"🔍 RedisQueueService.__init__() - REDIS_URL={redis_url_log}")
        
        try:
            self.redis_conn = Redis.from_url(redis_url, decode_responses=False)  # RQ ต้องการ bytes
            self.redis_conn.ping()
            logger.info(f"✅ Connected to Redis: {redis_url_log}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis ({redis_url_log}): {e}")
            raise
        
        # สร้าง queues สำหรับแต่ละ GPU worker
        # แต่ละ queue จะถูก consume โดย worker ที่ fix GPU ของตัวเอง
        # รองรับ 4 GPUs (gpu0, gpu1, gpu2, gpu3)
        num_gpus = int(os.getenv('NUM_GPUS', '4'))
        self.queues = {}
        
        # ตั้งค่า default_result_ttl (12 hours = 43200 seconds)
        # สำหรับ use-case 50 งาน/วัน ไม่ต้องเก็บนาน 24h
        # เพื่อให้ job results ถูก cleanup อัตโนมัติหลังจาก 12 ชั่วโมง
        default_result_ttl = int(os.getenv('RQ_DEFAULT_RESULT_TTL', '43200'))  # 12 hours
        
        # สร้าง queue สำหรับแต่ละ GPU (ไม่ใช้ default queue)
        for i in range(num_gpus):
            gpu_key = f'gpu{i}'
            queue_name = f'transcription_gpu{i}'
            self.queues[gpu_key] = Queue(
                queue_name, 
                connection=self.redis_conn,
                default_result_ttl=default_result_ttl
            )
        
        # Round-robin counter สำหรับ load balancing
        self._rr_counter = 0
        self._num_gpus = num_gpus
        
        logger.info(f"✅ Created {num_gpus} GPU queues: {list(self.queues.keys())} (default_result_ttl={default_result_ttl}s)")
        
        # Queue สำหรับ priority tasks (เช่น live streaming)
        self.priority_queue = Queue(
            'transcription_priority', 
            connection=self.redis_conn,
            default_result_ttl=default_result_ttl
        )
        
        # CPU queue สำหรับ aggregator และ CPU-intensive tasks
        self.cpu_queue = Queue(
            'transcription_cpu', 
            connection=self.redis_conn,
            default_result_ttl=default_result_ttl
        )
        
        # Preprocess queue แยก (สำหรับ extract + chunking)
        self.preprocess_queue = Queue(
            'transcription_preprocess', 
            connection=self.redis_conn,
            default_result_ttl=default_result_ttl
        )
        
        logger.info("✅ Redis Queue Service initialized (GPU queues + CPU queue + Preprocess queue)")
    
    def _check_preprocess_queue_limit(self):
        """
        ตรวจสอบว่า preprocess queue เต็มหรือไม่
        
        Raises:
            QueueFullError: ถ้า queue เต็ม (current >= max)
        """
        max_size = int(os.getenv('MAX_PREPROCESS_QUEUE_SIZE', '25'))
        queue_length = len(self.preprocess_queue)
        
        # รวม started jobs ด้วย (jobs ที่กำลังประมวลผล)
        from rq.registry import StartedJobRegistry
        started_count = len(StartedJobRegistry(queue=self.preprocess_queue))
        total_count = queue_length + started_count
        
        if total_count >= max_size:
            logger.warning(f"⚠️ Preprocess queue เต็ม: {total_count}/{max_size} (queued: {queue_length}, started: {started_count})")
            raise QueueFullError(
                current_count=total_count,
                max_size=max_size,
                queue_name="transcription_preprocess"
            )
        
        logger.debug(f"✅ Preprocess queue OK: {total_count}/{max_size} (queued: {queue_length}, started: {started_count})")
    
    def enqueue_transcription(
        self,
        task_id: str,
        file_path: str,
        language: str = "th",
        model_size: str = "base",
        chunk_duration: int = 150,
        priority: bool = False,
        worker_gpu: Optional[str] = None
    ) -> str:
        """
        เพิ่ม transcription job เข้า queue
        
        Args:
            task_id: Task ID
            file_path: Path to audio/video file
            language: Language code
            model_size: Whisper model size
            chunk_duration: Chunk duration in seconds
            priority: Whether this is a priority task (live streaming)
            worker_gpu: Specific GPU worker to use ('gpu0', 'gpu1', 'gpu2', 'gpu3', or None for round-robin)
        
        Returns:
            Job ID
        """
        # เลือก queue
        if priority:
            queue = self.priority_queue
            logger.info(f"📌 Enqueueing priority job {task_id} to priority queue")
        elif worker_gpu and worker_gpu in self.queues:
            queue = self.queues[worker_gpu]
            logger.info(f"🎯 Enqueueing job {task_id} to {worker_gpu} queue")
        else:
            # Round-robin: เลือก GPU queue ที่มี load น้อยที่สุด
            # ใช้ least-loaded strategy: ดู queue length + started jobs
            from rq.registry import StartedJobRegistry
            
            best_queue = None
            best_load = float('inf')
            
            for i in range(self._num_gpus):
                gpu_key = f'gpu{i}'
                gpu_queue = self.queues[gpu_key]
                queue_length = len(gpu_queue)
                started_count = len(StartedJobRegistry(queue=gpu_queue))
                total_load = queue_length + started_count
                
                if total_load < best_load:
                    best_load = total_load
                    best_queue = gpu_queue
            
            if best_queue is None:
                # Fallback: round-robin
                self._rr_counter = (self._rr_counter + 1) % self._num_gpus
                gpu_key = f'gpu{self._rr_counter}'
                best_queue = self.queues[gpu_key]
                logger.info(f"🔄 Enqueueing job {task_id} to {gpu_key} (round-robin fallback)")
            else:
                logger.info(f"⚖️  Enqueueing job {task_id} to least-loaded queue (load: {best_load})")
            
            queue = best_queue
        
        # สร้าง job data
        job_data = {
            'task_id': task_id,
            'file_path': file_path,
            'language': language,
            'model_size': model_size,
            'chunk_duration': chunk_duration,
        }
        
        # เพิ่ม job เข้า queue
        # ใช้ worker function ที่จะถูกเรียกโดย RQ worker
        # ใช้ persistent worker module แทน
        job = queue.enqueue(
            'app.workers.rq_worker.process_transcription_job',  # ใช้ persistent worker
            task_id,
            file_path,
            language,
            model_size,
            chunk_duration,
            job_id=task_id,  # ใช้ task_id เป็น job_id เพื่อให้ track ได้ง่าย
            job_timeout=3600,  # 1 hour timeout
            result_ttl=43200,  # Keep result for 12 hours (reduced from 24h)
        )
        
        logger.info(f"✅ Job {task_id} enqueued to {queue.name} (Job ID: {job.id})")
        return job.id
    
    def enqueue_preprocess(
        self,
        task_id: str,
        file_path: str,
        language: str = "th",
        model_size: str = "base",
        chunk_duration: int = 90
    ) -> str:
        """
        Enqueue preprocessing job ไปยัง preprocess queue
        
        Args:
            task_id: Task ID
            file_path: Path to video/audio file
            language: Language code
            model_size: Whisper model size
            chunk_duration: Chunk duration in seconds
        
        Returns:
            Job ID
        
        Raises:
            QueueFullError: ถ้า queue เต็ม (current >= max)
        """
        # ตรวจสอบ queue limit ก่อน enqueue
        self._check_preprocess_queue_limit()
        
        # Preprocessing ไป preprocess queue
        job = self.preprocess_queue.enqueue(
            'app.workers.rq_worker.process_preprocess_job',
            task_id,
            file_path,
            language,
            model_size,
            chunk_duration,
            job_id=f"{task_id}_preprocess",
            job_timeout=1800,  # 30 minutes timeout
            result_ttl=43200,  # Keep result for 12 hours (reduced from 24h)
        )
        logger.info(f"✅ Preprocess job {task_id} enqueued to Preprocess queue (Job ID: {job.id})")
        return job.id
    
    def enqueue_aggregator(
        self,
        task_id: str,
        language: str = "th",
        model_size: str = "base",
        chunk_duration: int = 90
    ) -> str:
        """
        Enqueue aggregator job ไปยัง CPU queue
        
        Args:
            task_id: Aggregator task ID (ควรเป็น {main_task_id}_aggregator)
            language: Language code
            model_size: Whisper model size
            chunk_duration: Chunk duration in seconds
        
        Returns:
            Job ID
        """
        # Aggregator ไป CPU queue เท่านั้น
        job = self.cpu_queue.enqueue(
            'app.workers.rq_worker.process_transcription_job',
            task_id,
            "",  # file_path ไม่ใช้ (aggregator จะไม่ใช้)
            language,
            model_size,
            chunk_duration,
            job_id=task_id,
            job_timeout=3600,
            result_ttl=43200,  # Keep result for 12 hours (reduced from 24h)
        )
        logger.info(f"✅ Aggregator job {task_id} enqueued to CPU queue (Job ID: {job.id})")
        return job.id
    
    def get_job_status(self, job_id: str) -> Dict:
        """Get job status"""
        try:
            job = Job.fetch(job_id, connection=self.redis_conn)
            
            status = {
                'job_id': job_id,
                'status': job.get_status(),
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'ended_at': job.ended_at.isoformat() if job.ended_at else None,
                'result': job.result if job.is_finished else None,
                'exc_info': job.exc_info if job.is_failed else None,
            }
            
            return status
        except Exception as e:
            logger.error(f"❌ Error getting job status: {e}")
            return {
                'job_id': job_id,
                'status': 'not_found',
                'error': str(e)
            }
    
    def get_queue_stats(self) -> Dict:
        """Get queue statistics"""
        stats = {}
        
        for queue_name, queue in self.queues.items():
            stats[queue_name] = {
                'length': len(queue),
                'started': len(StartedJobRegistry(queue=queue)),
                'finished': len(FinishedJobRegistry(queue=queue)),
                'failed': len(FailedJobRegistry(queue=queue)),
            }
        
        # Priority queue stats
        stats['priority'] = {
            'length': len(self.priority_queue),
            'started': len(StartedJobRegistry(queue=self.priority_queue)),
            'finished': len(FinishedJobRegistry(queue=self.priority_queue)),
            'failed': len(FailedJobRegistry(queue=self.priority_queue)),
        }
        
        return stats
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        try:
            job = Job.fetch(job_id, connection=self.redis_conn)
            job.cancel()
            logger.info(f"✅ Job {job_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"❌ Error cancelling job: {e}")
            return False
    
    def cleanup_finished_jobs(self, max_age_hours: int = 24) -> Dict:
        """
        Cleanup finished jobs ที่เก่ากว่า max_age_hours
        
        Args:
            max_age_hours: อายุสูงสุดของ finished jobs (default: 24 hours)
        
        Returns:
            Dict with cleanup statistics
        """
        from datetime import datetime, timedelta
        from rq.registry import FinishedJobRegistry
        
        stats = {
            'cleaned': 0,
            'errors': 0,
            'queues': {}
        }
        
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        # Cleanup all queues
        all_queues = list(self.queues.values()) + [self.priority_queue, self.cpu_queue, self.preprocess_queue]
        
        for queue in all_queues:
            queue_name = queue.name
            try:
                finished_registry = FinishedJobRegistry(queue=queue, connection=self.redis_conn)
                job_ids = finished_registry.get_job_ids()
                
                cleaned_count = 0
                for job_id in job_ids:
                    try:
                        job = Job.fetch(job_id, connection=self.redis_conn)
                        # ตรวจสอบอายุของ job
                        if job.ended_at and job.ended_at < cutoff_time:
                            finished_registry.remove(job_id, ttl=-1)  # Remove from registry
                            job.delete()  # Delete job data
                            cleaned_count += 1
                    except Exception as e:
                        logger.debug(f"Error cleaning job {job_id}: {e}")
                        stats['errors'] += 1
                
                stats['queues'][queue_name] = cleaned_count
                stats['cleaned'] += cleaned_count
                logger.info(f"✅ Cleaned {cleaned_count} finished jobs from {queue_name}")
            except Exception as e:
                logger.error(f"❌ Error cleaning finished jobs from {queue_name}: {e}")
                stats['errors'] += 1
        
        logger.info(f"✅ Cleanup finished: {stats['cleaned']} jobs cleaned, {stats['errors']} errors")
        return stats
    
    def cleanup_failed_jobs(self, max_age_hours: int = 24) -> Dict:
        """
        Cleanup failed jobs ที่เก่ากว่า max_age_hours
        
        Args:
            max_age_hours: อายุสูงสุดของ failed jobs (default: 24 hours)
        
        Returns:
            Dict with cleanup statistics
        """
        from datetime import datetime, timedelta
        from rq.registry import FailedJobRegistry
        
        stats = {
            'cleaned': 0,
            'errors': 0,
            'queues': {}
        }
        
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        # Cleanup all queues
        all_queues = list(self.queues.values()) + [self.priority_queue, self.cpu_queue, self.preprocess_queue]
        
        for queue in all_queues:
            queue_name = queue.name
            try:
                failed_registry = FailedJobRegistry(queue=queue, connection=self.redis_conn)
                job_ids = failed_registry.get_job_ids()
                
                cleaned_count = 0
                for job_id in job_ids:
                    try:
                        job = Job.fetch(job_id, connection=self.redis_conn)
                        # ตรวจสอบอายุของ job
                        if job.ended_at and job.ended_at < cutoff_time:
                            failed_registry.remove(job_id, ttl=-1)  # Remove from registry
                            job.delete()  # Delete job data
                            cleaned_count += 1
                    except Exception as e:
                        logger.debug(f"Error cleaning job {job_id}: {e}")
                        stats['errors'] += 1
                
                stats['queues'][queue_name] = cleaned_count
                stats['cleaned'] += cleaned_count
                logger.info(f"✅ Cleaned {cleaned_count} failed jobs from {queue_name}")
            except Exception as e:
                logger.error(f"❌ Error cleaning failed jobs from {queue_name}: {e}")
                stats['errors'] += 1
        
        logger.info(f"✅ Cleanup failed: {stats['cleaned']} jobs cleaned, {stats['errors']} errors")
        return stats
    
    def cleanup_all_jobs(self, max_age_hours: int = 24) -> Dict:
        """
        Cleanup ทั้ง finished และ failed jobs
        
        Args:
            max_age_hours: อายุสูงสุดของ jobs (default: 24 hours)
        
        Returns:
            Dict with cleanup statistics
        """
        finished_stats = self.cleanup_finished_jobs(max_age_hours=max_age_hours)
        failed_stats = self.cleanup_failed_jobs(max_age_hours=max_age_hours)
        
        return {
            'finished': finished_stats,
            'failed': failed_stats,
            'total_cleaned': finished_stats['cleaned'] + failed_stats['cleaned'],
            'total_errors': finished_stats['errors'] + failed_stats['errors']
        }

# Worker function ถูกย้ายไปที่ app.workers.rq_worker.process_transcription_job
# เพื่อใช้ persistent TranscriptionService (ไม่ init ใหม่ทุก job)

# Global instance
_redis_queue_service: Optional[RedisQueueService] = None

def get_redis_queue_service() -> RedisQueueService:
    """Get or create Redis Queue Service instance"""
    global _redis_queue_service
    if _redis_queue_service is None:
        _redis_queue_service = RedisQueueService()
    return _redis_queue_service
