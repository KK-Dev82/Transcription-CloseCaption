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

# Load env ตามจำนวน GPU (1 GPU → .env.runpod-1GPU ป้องกัน OOM)
try:
    from app.utils.load_env_by_gpu import load_env_by_gpu
    load_env_by_gpu()
except Exception:
    try:
        from dotenv import load_dotenv
        env_file = Path(__file__).parent.parent.parent / ".env.runpod"
        if env_file.exists():
            load_dotenv(env_file)
    except ImportError:
        pass

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
        # queues = legacy (deprecated), queues_record/queues_upload = Shared Pool + Priority
        for i in range(num_gpus):
            gpu_key = f'gpu{i}'
            queue_name = f'transcription_gpu{i}'
            self.queues[gpu_key] = Queue(
                queue_name,
                connection=self.redis_conn,
                default_result_ttl=default_result_ttl
            )
        
        # Record queues (Shared Pool + Priority: Record แซง Upload)
        self.queues_record = {}
        for i in range(num_gpus):
            gpu_key = f'gpu{i}'
            queue_name = f'transcription_gpu_record_{i}'
            self.queues_record[gpu_key] = Queue(
                queue_name,
                connection=self.redis_conn,
                default_result_ttl=default_result_ttl
            )
        
        # Upload queues (Shared Pool + Priority)
        self.queues_upload = {}
        for i in range(num_gpus):
            gpu_key = f'gpu{i}'
            queue_name = f'transcription_gpu_upload_{i}'
            self.queues_upload[gpu_key] = Queue(
                queue_name,
                connection=self.redis_conn,
                default_result_ttl=default_result_ttl
            )
        
        # Round-robin counter สำหรับ load balancing
        self._rr_counter = 0
        self._rr_counter_record = 0
        self._rr_counter_upload = 0
        self._num_gpus = num_gpus
        
        logger.info(f"✅ Created {num_gpus} GPU queues + record + upload (default_result_ttl={default_result_ttl}s)")
        
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
        
        # Preprocess queue สำหรับ Video Record — ลัดคิว (workers ฟังคิวนี้ก่อน)
        self.preprocess_video_record_queue = Queue(
            'transcription_preprocess_video_record',
            connection=self.redis_conn,
            default_result_ttl=default_result_ttl
        )
        
        logger.info("✅ Redis Queue Service initialized (GPU queues + CPU queue + Preprocess queue + Preprocess Video Record)")
    
    def _check_preprocess_queue_limit(self, source: Optional[str] = None):
        """
        ตรวจสอบว่า preprocess queue เต็มหรือไม่
        
        Args:
            source: "video_record" = Record (+5 slots), "fe_cc" = FE CC (ข้าม check), ปกติ = Upload (25)
        
        Logic: Upload 25, Record +5, FE CC รับได้ตลอด
        
        Raises:
            QueueFullError: ถ้า queue เต็ม (current >= max)
        """
        # FE CC: รับได้ตลอด ไม่ตรวจสอบ limit
        if source == 'fe_cc':
            return

        max_size = int(os.getenv('MAX_PREPROCESS_QUEUE_SIZE', '25'))
        video_record_slots = int(os.getenv('MAX_PREPROCESS_QUEUE_VIDEO_RECORD_SLOTS', '5'))
        
        from rq.registry import StartedJobRegistry
        preprocess_len = len(self.preprocess_queue)
        video_record_len = len(self.preprocess_video_record_queue)
        started_preprocess = len(StartedJobRegistry(queue=self.preprocess_queue))
        started_video_record = len(StartedJobRegistry(queue=self.preprocess_video_record_queue))
        total_count = preprocess_len + video_record_len + started_preprocess + started_video_record
        
        # Video Record: ใช้ slot พิเศษ รวมสูงสุด max_size + video_record_slots
        if source == 'video_record':
            max_total = max_size + video_record_slots
            queue_name = "transcription_preprocess_video_record"
        else:
            max_total = max_size
            queue_name = "transcription_preprocess"
        
        if total_count >= max_total:
            logger.warning(f"⚠️ Preprocess queue เต็ม: {total_count}/{max_total} (preprocess: {preprocess_len}+{started_preprocess}, video_record: {video_record_len}+{started_video_record})")
            raise QueueFullError(
                current_count=total_count,
                max_size=max_total,
                queue_name=queue_name
            )
        
        logger.debug(f"✅ Preprocess queue OK: {total_count}/{max_total} (source={source})")
    
    def enqueue_transcription(
        self,
        task_id: str,
        file_path: str,
        language: str = "th",
        model_size: str = "base",
        chunk_duration: int = 150,
        priority: bool = False,
        worker_gpu: Optional[str] = None,
        source: Optional[str] = None
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
            source: "video_record" = Record queue (แซง Upload), อื่นๆ = Upload queue
        
        Returns:
            Job ID
        """
        # เลือก queue: priority -> record -> upload
        if priority:
            queue = self.priority_queue
            logger.info(f"📌 Enqueueing priority job {task_id} to priority queue")
        elif source == "video_record":
            # Record queue (Shared Pool + Priority)
            queue_set = self.queues_record
            rr_attr = "_rr_counter_record"
            if worker_gpu and worker_gpu in queue_set:
                queue = queue_set[worker_gpu]
                logger.info(f"🎯 Enqueueing Record job {task_id} to {worker_gpu} (record queue)")
            else:
                from rq.registry import StartedJobRegistry
                best_queue = None
                best_load = float('inf')
                for i in range(self._num_gpus):
                    gpu_key = f'gpu{i}'
                    gpu_queue = queue_set[gpu_key]
                    total_load = len(gpu_queue) + len(StartedJobRegistry(queue=gpu_queue))
                    if total_load < best_load:
                        best_load = total_load
                        best_queue = gpu_queue
                if best_queue is None:
                    counter = (getattr(self, rr_attr) + 1) % self._num_gpus
                    setattr(self, rr_attr, counter)
                    queue = queue_set[f'gpu{counter}']
                else:
                    queue = best_queue
                logger.info(f"⚖️  Enqueueing Record job {task_id} to least-loaded record queue (load: {best_load})")
        else:
            # Upload queue (Shared Pool + Priority)
            queue_set = self.queues_upload
            rr_attr = "_rr_counter_upload"
            if worker_gpu and worker_gpu in queue_set:
                queue = queue_set[worker_gpu]
                logger.info(f"🎯 Enqueueing Upload job {task_id} to {worker_gpu} (upload queue)")
            else:
                from rq.registry import StartedJobRegistry
                best_queue = None
                best_load = float('inf')
                for i in range(self._num_gpus):
                    gpu_key = f'gpu{i}'
                    gpu_queue = queue_set[gpu_key]
                    total_load = len(gpu_queue) + len(StartedJobRegistry(queue=gpu_queue))
                    if total_load < best_load:
                        best_load = total_load
                        best_queue = gpu_queue
                if best_queue is None:
                    counter = (getattr(self, rr_attr) + 1) % self._num_gpus
                    setattr(self, rr_attr, counter)
                    queue = queue_set[f'gpu{counter}']
                else:
                    queue = best_queue
                logger.info(f"⚖️  Enqueueing Upload job {task_id} to least-loaded upload queue (load: {best_load})")
        
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
        model_size: Optional[str] = None,
        chunk_duration: int = 90,
        source: Optional[str] = None
    ) -> str:
        """
        Enqueue preprocessing job ไปยัง preprocess queue
        
        Args:
            task_id: Task ID
            file_path: Path to video/audio file
            language: Language code
            model_size: Whisper model size
            chunk_duration: Chunk duration in seconds
            source: "video_record" = ลัดคิว (ใช้ slot พิเศษ +1)
        
        Returns:
            Job ID
        
        Raises:
            QueueFullError: ถ้า queue เต็ม (current >= max)
        """
        # model_size: None / ว่าง / "base" = ใช้ WHISPER_MODEL (turbo) จาก .env
        if not model_size or str(model_size).strip().lower() in ("", "base", "default"):
            try:
                from app.services.close_caption_config import get_transcription_model_display
                model_size = get_transcription_model_display()
            except Exception:
                model_size = os.getenv("WHISPER_MODEL", "base")
        
        # ตรวจสอบ queue limit ก่อน enqueue (fe_cc ข้าม check)
        self._check_preprocess_queue_limit(source=source)
        
        # เลือก queue: video_record / fe_cc → ลัดคิว (workers ฟังคิวนี้ก่อน)
        queue = self.preprocess_video_record_queue if source in ('video_record', 'fe_cc') else self.preprocess_queue
        queue_name = queue.name
        
        # Preprocessing ไป preprocess queue
        job = queue.enqueue(
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
        logger.info(f"✅ Preprocess job {task_id} enqueued to {queue_name} (Job ID: {job.id})")
        return job.id
    
    def enqueue_preprocess_chunk_group(
        self,
        task_id: str,
        file_paths: List[str],
        language: str = "th",
        model_size: Optional[str] = None,
        source: Optional[str] = None
    ) -> str:
        """
        Enqueue preprocessing job โหมด chunk group
        ข้าม extract + create_chunks ใช้ file_paths เป็น chunks โดยตรง
        """
        if not model_size or str(model_size).strip().lower() in ("", "base", "default"):
            try:
                from app.services.close_caption_config import get_transcription_model_display
                model_size = get_transcription_model_display()
            except Exception:
                model_size = os.getenv("WHISPER_MODEL", "base")
        
        self._check_preprocess_queue_limit(source=source)
        queue = self.preprocess_video_record_queue if source in ('video_record', 'fe_cc') else self.preprocess_queue
        queue_name = queue.name
        
        job = queue.enqueue(
            'app.workers.rq_worker.process_preprocess_job_chunk_group',
            task_id,
            file_paths,
            language,
            model_size,
            job_id=f"{task_id}_preprocess",
            job_timeout=1800,
            result_ttl=43200,
        )
        logger.info(f"✅ Chunk group preprocess job {task_id} enqueued to {queue_name} (Job ID: {job.id})")
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
    
    def enqueue_live_chunk(
        self,
        session_id: str,
        meeting_id: str,
        chunk_index: int,
        start_time: float,
        duration: float,
        audio_path: str,
        model_size: Optional[str] = None
    ) -> str:
        """
        Enqueue live chunk job ไปยัง priority queue (สูงสุด)
        
        Args:
            session_id: Session ID
            meeting_id: Meeting ID
            chunk_index: Chunk index
            start_time: Start time in seconds
            duration: Duration in seconds
            audio_path: Path to audio file
            model_size: Model size (optional, will use default if not provided)
        
        Returns:
            Job ID
        """
        # ใช้ priority queue สำหรับ live-chunk (สูงสุด)
        job = self.priority_queue.enqueue(
            'app.workers.rq_worker.process_live_chunk_job',
            session_id,
            meeting_id,
            chunk_index,
            start_time,
            duration,
            audio_path,
            model_size,  # ส่ง model_size ไป worker
            job_id=f"live-chunk-{meeting_id}-{chunk_index}",
            job_timeout=300,  # 5 minutes timeout (สำหรับ real-time)
            result_ttl=3600,  # Keep result for 1 hour (shorter than normal jobs)
        )
        logger.info(f"📌 Live chunk job {session_id} enqueued to PRIORITY queue (Job ID: {job.id})")
        return job.id
    
    def get_record_backlog_count(self) -> int:
        """
        จำนวน Record jobs ที่รอหรือกำลังรัน (preprocess + GPU record queues)
        ใช้สำหรับ On Hold: เมื่อ record_backlog > 0 ให้ hold Upload chunks
        """
        from rq.registry import StartedJobRegistry
        count = 0
        # Preprocess video_record queue
        count += len(self.preprocess_video_record_queue)
        count += len(StartedJobRegistry(queue=self.preprocess_video_record_queue))
        # Record chunks ใน GPU queues
        for gpu_key, q in self.queues_record.items():
            count += len(q)
            count += len(StartedJobRegistry(queue=q))
        return count
    
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
        
        for queue_name, queue in self.queues_record.items():
            stats[f'record_{queue_name}'] = {
                'length': len(queue),
                'started': len(StartedJobRegistry(queue=queue)),
                'finished': len(FinishedJobRegistry(queue=queue)),
                'failed': len(FailedJobRegistry(queue=queue)),
            }
        
        for queue_name, queue in self.queues_upload.items():
            stats[f'upload_{queue_name}'] = {
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
    
    def cancel_task(self, task_id: str) -> Dict:
        """
        ยกเลิก transcription task และ jobs ที่เกี่ยวข้องใน Redis queue
        
        - Cancel preprocess job: {task_id}_preprocess
        - Cancel aggregator job: {task_id}_aggregator  
        - Cancel chunk jobs: {task_id}_chunk_{0..N}
        - Cancel full job (non-chunked): task_id
        - ลบ Redis keys: task:{task_id}:*
        
        Returns:
            Dict with cancelled_jobs, redis_keys_deleted, success
        """
        result = {"cancelled_jobs": 0, "redis_keys_deleted": 0, "success": False}
        
        # รายการ job IDs ที่อาจมี (ตามลำดับความน่าจะเป็น)
        known_job_ids = [
            f"{task_id}_preprocess",
            f"{task_id}_aggregator",
            task_id,  # full file job (non-chunked)
        ]
        
        # หา chunk jobs จาก Redis chunks_metadata หรือ scan
        try:
            chunks_meta_key = f"task:{task_id}:chunks_metadata"
            chunks_meta = self.redis_conn.get(chunks_meta_key)
            if chunks_meta:
                meta = json.loads(chunks_meta.decode("utf-8") if isinstance(chunks_meta, bytes) else chunks_meta)
                total = meta.get("total_chunks", 0)
                for i in range(total):
                    known_job_ids.append(f"{task_id}_chunk_{i}")
        except Exception as e:
            logger.debug(f"Could not get chunks_metadata for {task_id}: {e}")
        
        # Cancel แต่ละ job
        for job_id in known_job_ids:
            try:
                job = Job.fetch(job_id, connection=self.redis_conn)
                status = job.get_status()
                if status in ("queued", "started", "deferred"):
                    job.cancel()
                    result["cancelled_jobs"] += 1
                    logger.info(f"✅ Cancelled job {job_id} (was: {status})")
            except Exception as e:
                # Job อาจไม่มีหรือเสร็จไปแล้ว - ไม่ถือว่า error
                if "No such job" not in str(e) and "Could not find" not in str(e):
                    logger.debug(f"Job {job_id}: {e}")
        
        # Scan และลบ Redis keys ที่เกี่ยวกับ task นี้
        prefix = f"task:{task_id}:"
        try:
            keys = list(self.redis_conn.scan_iter(match=prefix + "*", count=500))
            if keys:
                self.redis_conn.delete(*keys)
                result["redis_keys_deleted"] = len(keys)
                logger.info(f"✅ Deleted {len(keys)} Redis keys for task {task_id}")
        except Exception as e:
            logger.error(f"❌ Error deleting Redis keys for {task_id}: {e}")
        
        result["success"] = True
        return result
    
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
        all_queues = (
            list(self.queues.values())
            + list(self.queues_record.values())
            + list(self.queues_upload.values())
            + [self.priority_queue, self.cpu_queue, self.preprocess_queue, self.preprocess_video_record_queue]
        )
        
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
        all_queues = (
            list(self.queues.values())
            + list(self.queues_record.values())
            + list(self.queues_upload.values())
            + [self.priority_queue, self.cpu_queue, self.preprocess_queue, self.preprocess_video_record_queue]
        )
        
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
