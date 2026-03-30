"""
Monitoring API Endpoint
สำหรับตรวจสอบ Redis memory, key count, queue depth, GPU/CPU utilization
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import logging
import os
from pathlib import Path
from redis import Redis
from rq import Queue
from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry

# Load .env.runpod if exists
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent.parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass
except Exception:
    pass

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])


class RedisStats(BaseModel):
    """Redis statistics"""
    memory_mb: float
    memory_human: str
    keys_count: int
    keys_without_ttl: int
    keys_with_ttl: int
    max_memory_mb: Optional[float] = None
    memory_usage_percent: Optional[float] = None


class QueueStats(BaseModel):
    """Queue statistics"""
    queue_name: str
    queued: int
    started: int
    finished: int
    failed: int


class SystemStats(BaseModel):
    """System statistics"""
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_used_gb: Optional[float] = None
    memory_total_gb: Optional[float] = None
    gpu_utilization: Optional[List[Dict]] = None


class MonitoringResponse(BaseModel):
    """Monitoring response"""
    redis: RedisStats
    queues: List[QueueStats]
    system: SystemStats


def get_redis_connection():
    """Get Redis connection"""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    return Redis.from_url(redis_url, decode_responses=False)


@router.get("/redis", response_model=RedisStats)
async def get_redis_stats():
    """Get Redis statistics"""
    try:
        conn = get_redis_connection()
        info = conn.info('memory')
        
        used_memory = info.get('used_memory', 0)
        used_memory_mb = used_memory / (1024**2)
        used_memory_human = info.get('used_memory_human', f"{used_memory_mb:.2f}M")
        max_memory = info.get('maxmemory', 0)
        max_memory_mb = max_memory / (1024**2) if max_memory > 0 else None
        memory_usage_percent = (used_memory_mb / max_memory_mb * 100) if max_memory_mb else None
        
        db_size = conn.dbsize()
        
        # ตรวจสอบ keys ที่ไม่มี TTL
        all_keys = list(conn.scan_iter(count=2000))
        keys_without_ttl = sum(1 for k in all_keys if conn.ttl(k) == -1)
        keys_with_ttl = len(all_keys) - keys_without_ttl
        
        return RedisStats(
            memory_mb=used_memory_mb,
            memory_human=used_memory_human,
            keys_count=db_size,
            keys_without_ttl=keys_without_ttl,
            keys_with_ttl=keys_with_ttl,
            max_memory_mb=max_memory_mb,
            memory_usage_percent=memory_usage_percent
        )
    except Exception as e:
        logger.error(f"Error getting Redis stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting Redis stats: {str(e)}")


@router.get("/queues", response_model=List[QueueStats])
async def get_queue_stats():
    """Get queue statistics"""
    try:
        conn = get_redis_connection()
        num_gpus = int(os.getenv('NUM_GPUS', '2'))
        queues_to_check = ['transcription_priority', 'transcription_preprocess', 'transcription_preprocess_video_record', 'transcription_cpu']
        for i in range(num_gpus):
            queues_to_check.append(f'transcription_gpu{i}')
            queues_to_check.append(f'transcription_gpu_record_{i}')
            queues_to_check.append(f'transcription_gpu_upload_{i}')
        
        queue_stats = []
        for queue_name in queues_to_check:
            try:
                queue = Queue(queue_name, connection=conn)
                queued_count = len(queue)
                
                started_registry = StartedJobRegistry(queue_name, connection=conn)
                finished_registry = FinishedJobRegistry(queue_name, connection=conn)
                failed_registry = FailedJobRegistry(queue_name, connection=conn)
                
                started_count = len(started_registry)
                finished_count = len(finished_registry)
                failed_count = len(failed_registry)
                
                queue_stats.append(QueueStats(
                    queue_name=queue_name,
                    queued=queued_count,
                    started=started_count,
                    finished=finished_count,
                    failed=failed_count
                ))
            except Exception as e:
                logger.warning(f"Error getting stats for queue {queue_name}: {e}")
        
        return queue_stats
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting queue stats: {str(e)}")


@router.get("/system", response_model=SystemStats)
async def get_system_stats():
    """Get system statistics (CPU, RAM, GPU)"""
    try:
        import psutil
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory
        mem = psutil.virtual_memory()
        memory_percent = mem.percent
        memory_used_gb = mem.used / (1024**3)
        memory_total_gb = mem.total / (1024**3)
        
        # GPU
        gpu_utilization = None
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=index,name,utilization.gpu,memory.used,memory.total', 
                 '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                gpu_utilization = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = [p.strip() for p in line.split(', ')]
                        if len(parts) >= 5:
                            gpu_utilization.append({
                                'index': int(parts[0]),
                                'name': parts[1],
                                'utilization_gpu_percent': float(parts[2]),
                                'memory_used_mb': float(parts[3]),
                                'memory_total_mb': float(parts[4])
                            })
        except Exception as e:
            logger.debug(f"Error getting GPU stats: {e}")
        
        return SystemStats(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_gb=memory_used_gb,
            memory_total_gb=memory_total_gb,
            gpu_utilization=gpu_utilization
        )
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting system stats: {str(e)}")


@router.get("/", response_model=MonitoringResponse)
async def get_monitoring_stats():
    """Get all monitoring statistics"""
    try:
        redis_stats = await get_redis_stats()
        queue_stats = await get_queue_stats()
        system_stats = await get_system_stats()

        return MonitoringResponse(
            redis=redis_stats,
            queues=queue_stats,
            system=system_stats
        )
    except Exception as e:
        logger.error(f"Error getting monitoring stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting monitoring stats: {str(e)}")


@router.get("/dashboard-summary")
async def get_dashboard_summary():
    """
    📊 **Dashboard Summary**

    ภาพรวมทั้งระบบใน 1 API call — queue state, workers, tasks, webhooks
    """
    try:
        import sqlite3
        from datetime import datetime, timedelta

        conn = get_redis_connection()
        num_gpus = int(os.getenv('NUM_GPUS', '2'))

        # ---- Queue ----
        pause_state = {}
        preprocess_depth = 0
        transcription_depth = 0
        eta_seconds = 0
        try:
            from ..services.redis_queue_service import get_redis_queue_service
            from rq.registry import StartedJobRegistry as SJR
            svc = get_redis_queue_service()
            pause_state = svc.get_global_pause_state()
            preprocess_depth = len(svc.preprocess_queue) + len(svc.preprocess_video_record_queue)
            transcription_depth = sum(
                len(svc.queues_record.get(f'gpu{i}', Queue(f'gpu{i}', connection=conn))) +
                len(svc.queues_upload.get(f'gpu{i}', Queue(f'gpu{i}', connection=conn)))
                for i in range(num_gpus)
            )
            avg_dur = svc.get_avg_task_duration()
            started = len(SJR(queue=svc.preprocess_queue)) + len(SJR(queue=svc.preprocess_video_record_queue))
            eta_seconds = int(preprocess_depth * avg_dur / max(1, started))
        except Exception:
            pass

        # ---- Workers ----
        workers_total = workers_busy = workers_idle = 0
        try:
            from rq import Worker
            all_workers = Worker.all(connection=conn)
            workers_total = len(all_workers)
            workers_busy = sum(1 for w in all_workers if w.get_state() == "busy")
            workers_idle = workers_total - workers_busy
        except Exception:
            pass

        # ---- Tasks ----
        tasks_by_status: Dict = {}
        tasks_by_source: Dict = {}
        completed_today = 0
        try:
            storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
            if storage_type == 'sqlite':
                from ..utils.storage_factory import get_storage
                storage = SQLiteStorage()
            else:
                from ..utils.json_storage import JSONStorage
                storage = JSONStorage()
            all_tasks = storage.list_all_transcriptions()
            today = datetime.utcnow().date()
            for t in all_tasks:
                s = t.get("status", "unknown")
                tasks_by_status[s] = tasks_by_status.get(s, 0) + 1
                src = t.get("source", "upload")
                tasks_by_source[src] = tasks_by_source.get(src, 0) + 1
                if s == "completed":
                    ca = t.get("completed_at") or t.get("updated_at", "")
                    if ca and ca[:10] == str(today):
                        completed_today += 1
        except Exception:
            pass
        tasks_by_status["completed_today"] = completed_today

        # ---- Webhook dead-letter ----
        dead_letter_count = 0
        try:
            db_path = os.getenv("SQLITE_DB_PATH", "storage/database.db")
            db_conn = sqlite3.connect(db_path, check_same_thread=False)
            row = db_conn.execute(
                "SELECT COUNT(*) FROM webhook_dead_letter WHERE resolved = 0"
            ).fetchone()
            dead_letter_count = row[0] if row else 0
            db_conn.close()
        except Exception:
            pass

        return {
            "queue": {
                "paused": pause_state.get("paused", False),
                "paused_reason": pause_state.get("reason"),
                "eta_seconds": eta_seconds,
                "depth_preprocess": preprocess_depth,
                "depth_transcription": transcription_depth,
            },
            "workers": {
                "total": workers_total,
                "busy": workers_busy,
                "idle": workers_idle,
            },
            "tasks": {
                **{k: v for k, v in tasks_by_status.items()},
                "by_source": tasks_by_source,
            },
            "webhook": {
                "dead_letter_unresolved": dead_letter_count,
            },
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_prometheus_metrics():
    """
    📈 **Prometheus Metrics**

    ข้อมูลในรูปแบบ Prometheus text format สำหรับ scraping
    """
    from fastapi.responses import PlainTextResponse
    import sqlite3
    from datetime import datetime

    lines = []

    try:
        conn = get_redis_connection()
        num_gpus = int(os.getenv('NUM_GPUS', '2'))

        # Queue depth
        try:
            from ..services.redis_queue_service import get_redis_queue_service
            svc = get_redis_queue_service()
            pause_val = 1 if svc.get_global_pause_state().get("paused") else 0
            pre_depth = len(svc.preprocess_queue) + len(svc.preprocess_video_record_queue)
            lines.append(f'transcription_queue_depth{{queue="preprocess"}} {pre_depth}')
            lines.append(f'transcription_queue_paused {pause_val}')
        except Exception:
            lines.append('transcription_queue_depth{queue="preprocess"} -1')

        # Workers
        try:
            from rq import Worker
            all_workers = Worker.all(connection=conn)
            busy = sum(1 for w in all_workers if w.get_state() == "busy")
            lines.append(f'transcription_workers_total {len(all_workers)}')
            lines.append(f'transcription_workers_busy {busy}')
        except Exception:
            lines.append('transcription_workers_total -1')

        # Tasks by status
        try:
            storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
            if storage_type == 'sqlite':
                from ..utils.storage_factory import get_storage
                storage = SQLiteStorage()
            else:
                from ..utils.json_storage import JSONStorage
                storage = JSONStorage()
            all_tasks = storage.list_all_transcriptions()
            status_counts: Dict = {}
            source_status_counts: Dict = {}
            for t in all_tasks:
                s = t.get("status", "unknown")
                src = t.get("source", "upload")
                status_counts[s] = status_counts.get(s, 0) + 1
                key = (src, s)
                source_status_counts[key] = source_status_counts.get(key, 0) + 1
            for (src, s), cnt in source_status_counts.items():
                lines.append(f'transcription_tasks_total{{status="{s}",source="{src}"}} {cnt}')
        except Exception:
            lines.append('transcription_tasks_total{status="unknown",source="unknown"} -1')

        # Dead-letter
        try:
            db_path = os.getenv("SQLITE_DB_PATH", "storage/database.db")
            db_conn = sqlite3.connect(db_path, check_same_thread=False)
            row = db_conn.execute(
                "SELECT COUNT(*) FROM webhook_dead_letter WHERE resolved = 0"
            ).fetchone()
            dead_count = row[0] if row else 0
            db_conn.close()
            lines.append(f'transcription_webhook_dead_letter_unresolved {dead_count}')
        except Exception:
            lines.append('transcription_webhook_dead_letter_unresolved -1')

    except Exception as e:
        lines.append(f'# ERROR: {e}')

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
