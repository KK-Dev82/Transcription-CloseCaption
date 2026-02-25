"""
Redis Queue Wrapper สำหรับ Queue Management API
ใช้ Redis Queue (RQ) แทน RabbitMQ สำหรับ queue management endpoints
"""
import logging
import os
from typing import Dict, Optional
from redis import Redis
from rq import Queue
from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry

logger = logging.getLogger(__name__)


class RedisQueueWrapper:
    """
    Wrapper สำหรับ Redis Queue ที่มี interface คล้าย RabbitMQ service
    สำหรับใช้ใน queue management API
    """
    
    def __init__(self):
        """Initialize Redis connection"""
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            error_msg = "REDIS_URL is not set. Cannot connect to Redis."
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        try:
            self.redis_conn = Redis.from_url(redis_url, decode_responses=False)
            self.redis_conn.ping()
            logger.info(f"✅ Redis Queue Wrapper connected to Redis")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise
        
        # Map queue names to RQ Queue objects
        self.queue_map = {}
        self._initialize_queues()
    
    def _ensure_connection(self):
        """Ensure Redis connection is active (compatible with RabbitMQ interface)"""
        try:
            self.redis_conn.ping()
        except Exception as e:
            logger.error(f"❌ Redis connection lost: {e}")
            # Reconnect
            redis_url = os.getenv('REDIS_URL')
            self.redis_conn = Redis.from_url(redis_url, decode_responses=False)
            self.redis_conn.ping()
            self._initialize_queues()
    
    def _initialize_queues(self):
        """Initialize RQ Queue objects for all known queues"""
        # Transcription queues (RQ format)
        num_gpus = int(os.getenv('NUM_GPUS', '4'))
        for i in range(num_gpus):
            queue_name = f'transcription_gpu{i}'
            self.queue_map[queue_name] = Queue(queue_name, connection=self.redis_conn)
            self.queue_map[f'transcription_gpu_record_{i}'] = Queue(f'transcription_gpu_record_{i}', connection=self.redis_conn)
            self.queue_map[f'transcription_gpu_upload_{i}'] = Queue(f'transcription_gpu_upload_{i}', connection=self.redis_conn)
        
        # Priority and CPU queues
        self.queue_map['transcription_priority'] = Queue('transcription_priority', connection=self.redis_conn)
        self.queue_map['transcription_cpu'] = Queue('transcription_cpu', connection=self.redis_conn)
        self.queue_map['transcription_preprocess'] = Queue('transcription_preprocess', connection=self.redis_conn)
        
        # Map RabbitMQ queue names to RQ queues (for compatibility)
        # transcription_request_queue -> transcription_preprocess (closest match)
        self.queue_map['transcription_request_queue'] = self.queue_map['transcription_preprocess']
        # audio_extraction_queue -> transcription_preprocess (closest match)
        self.queue_map['audio_extraction_queue'] = self.queue_map['transcription_preprocess']
        # transcription_queue -> transcription_gpu0 (default GPU queue)
        self.queue_map['transcription_queue'] = self.queue_map.get('transcription_gpu0', self.queue_map['transcription_cpu'])
        
        logger.info(f"✅ Initialized {len(self.queue_map)} queues")
    
    def get_queue_info(self) -> Dict:
        """
        Get information about all queues (compatible with RabbitMQ interface)
        
        Returns:
            Dict with queue information in RabbitMQ-like format
        """
        self._ensure_connection()
        
        queue_info = {}
        
        for queue_name, queue in self.queue_map.items():
            try:
                # Get queue statistics
                queue_length = len(queue)
                started_count = len(StartedJobRegistry(queue=queue, connection=self.redis_conn))
                finished_count = len(FinishedJobRegistry(queue=queue, connection=self.redis_conn))
                failed_count = len(FailedJobRegistry(queue=queue, connection=self.redis_conn))
                
                queue_info[queue_name] = {
                    'message_count': queue_length,
                    'messages_unacknowledged': started_count,  # Started jobs = unacked
                    'consumer_count': 1 if queue_length > 0 or started_count > 0 else 0,  # Estimate
                    'queue_type': 'rq',  # Redis Queue
                    'started_jobs': started_count,
                    'finished_jobs': finished_count,
                    'failed_jobs': failed_count,
                }
            except Exception as e:
                logger.warning(f"⚠️ Error getting info for queue {queue_name}: {e}")
                queue_info[queue_name] = {
                    'message_count': 0,
                    'messages_unacknowledged': 0,
                    'consumer_count': 0,
                    'error': str(e)
                }
        
        return queue_info
    
    def purge_queue(self, queue_name: str) -> bool:
        """
        Purge all messages from a queue (compatible with RabbitMQ interface)
        
        Args:
            queue_name: Name of the queue to purge
            
        Returns:
            True if successful, False otherwise
        """
        self._ensure_connection()
        
        try:
            if queue_name not in self.queue_map:
                logger.warning(f"⚠️ Queue {queue_name} not found")
                return False
            
            queue = self.queue_map[queue_name]
            
            # Clear all jobs from the queue
            # Note: RQ doesn't have a direct purge method, so we need to dequeue all jobs
            job_ids = queue.job_ids
            cleared_count = 0
            
            for job_id in job_ids:
                try:
                    from rq.job import Job
                    job = Job.fetch(job_id, connection=self.redis_conn)
                    job.delete()
                    cleared_count += 1
                except Exception as e:
                    logger.debug(f"Error deleting job {job_id}: {e}")
            
            # Also clear from registries
            try:
                started_registry = StartedJobRegistry(queue=queue, connection=self.redis_conn)
                for job_id in started_registry.get_job_ids():
                    started_registry.remove(job_id, ttl=-1)
            except Exception:
                pass
            
            logger.info(f"✅ Purged {cleared_count} jobs from queue {queue_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error purging queue {queue_name}: {e}")
            return False

