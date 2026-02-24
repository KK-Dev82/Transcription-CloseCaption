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
