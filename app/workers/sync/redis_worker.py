"""
Redis Worker - Main Orchestrator สำหรับ Redis Queue
"""

import logging
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# เพิ่ม app directory เข้าไปใน Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Load .env.runpod if exists
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent.parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
        logger_temp = logging.getLogger(__name__)
        logger_temp.info(f"✅ Loaded environment from: {env_file}")
except ImportError:
    pass
except Exception as e:
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning(f"⚠️  Failed to load .env.runpod: {e}")

from app.services.video_service import VideoService
from app.services.transcription_service import TranscriptionService
from app.services.redis_queue_service import RedisQueueService
from app.utils.json_storage import JSONStorage

# Import worker components
from app.workers.sync.handlers import MessageHandlers
from app.workers.sync.processors import TaskProcessors
from app.workers.sync.utils import WorkerUtils

logger = logging.getLogger(__name__)


class VideoWorkerRedis:
    """Video Worker (Redis) - Main Orchestrator"""
    
    def __init__(self):
        """Initialize Video Worker with all components"""
        # Initialize services
        self.video_service = VideoService()
        self.transcription_service = TranscriptionService()
        self.json_storage = JSONStorage()
        self.redis_queue_service = RedisQueueService()
        
        # Worker state
        self.running = True
        
        # Thread pool สำหรับ parallel chunk processing
        max_workers = int(os.getenv('TRANSCRIPTION_MAX_WORKERS', '5'))
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="chunk_worker")
        logger.info(f"🔧 ThreadPoolExecutor initialized with {max_workers} workers")
        self.active_chunks = {}  # Track active chunk tasks: {task_id: future}
        
        # Initialize worker components
        self.processors = TaskProcessors(self)
        self.utils = WorkerUtils(self)
        self.handlers = MessageHandlers(self)
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """จัดการ signal สำหรับ graceful shutdown"""
        logger.info(f"ได้รับ signal {signum} กำลังปิด worker...")
        self.running = False
    
    def _process_transcription_request(self, task_data: dict, message_id: str = None):
        """Process transcription request from Redis queue"""
        try:
            task_id = task_data.get('task_id')
            file_path = task_data.get('file_path')
            file_url = task_data.get('file_url')
            file_name = task_data.get('file_name')
            language = task_data.get('language', 'th')
            model_size = task_data.get('model_size', 'base')
            chunk_duration = task_data.get('chunk_duration', 30)
            use_chunking = task_data.get('use_chunking', False)
            initial_prompt = task_data.get('initial_prompt')
            
            logger.info("=" * 80)
            logger.info("📨 📨 📨 RECEIVED TRANSCRIPTION REQUEST FROM Redis!")
            logger.info(f"   Task ID: {task_id}")
            logger.info(f"   File: {file_path or file_name}")
            logger.info(f"   Model: {model_size}, Language: {language}")
            logger.info(f"   Use Chunking: {use_chunking}")
            logger.info("=" * 80)
            
            # เรียก _process_transcription โดยตรง
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self.transcription_service._process_transcription(
                        task_id=task_id,
                        file_path=file_path,
                        language=language,
                        model_size=model_size,
                        chunk_duration=chunk_duration,
                        use_chunking=use_chunking,
                        file_url=file_url,
                        file_name=file_name,
                        initial_prompt=initial_prompt
                    )
                )
                logger.info(f"✅ Completed transcription request: {task_id}")
            finally:
                loop.close()
                asyncio.set_event_loop(None)
            
        except Exception as e:
            logger.error(f"❌ Error processing transcription request: {e}", exc_info=True)
    
    def _process_chunk_task(self, chunk_task: dict):
        """Process chunk task from Redis queue"""
        try:
            parent_task_id = chunk_task.get('parent_task_id')
            chunk_path = chunk_task.get('chunk_path')
            # Convert to int (Redis Streams returns strings)
            chunk_index = int(chunk_task.get('chunk_index', 0))
            total_chunks = int(chunk_task.get('total_chunks', 0))
            model_size = chunk_task.get('model_size', 'base')
            language = chunk_task.get('language', 'th')
            
            logger.info("=" * 80)
            logger.info("📨 📨 📨 RECEIVED MESSAGE FROM Redis transcription_chunk_queue!")
            logger.info(f"   Chunk Index: {chunk_index+1}/{total_chunks}")
            logger.info(f"   Parent Task ID: {parent_task_id}")
            logger.info(f"   Chunk path: {chunk_path}")
            logger.info(f"   Model: {model_size}, Language: {language}")
            logger.info("=" * 80)
            
            logger.info(f"🎬 Processing chunk {chunk_index+1}/{total_chunks} for task {parent_task_id}")
            logger.info(f"   Active chunks in executor: {len(self.active_chunks)}")
            
            # ส่งไปยัง thread pool เพื่อประมวลผล parallel (ไม่ block)
            future = self.executor.submit(
                self.utils.execute_chunk_transcription_sync,
                chunk_task,
                None,  # No channel for Redis
                None   # No delivery_tag for Redis
            )
            task_id = chunk_task.get('task_id', f"{parent_task_id}_chunk_{chunk_index}")
            self.active_chunks[task_id] = future
            
            logger.info(f"🚀 Chunk {chunk_index+1}/{total_chunks} submitted to thread pool (total active: {len(self.active_chunks)})")
            
        except Exception as e:
            logger.error(f"❌ Error processing chunk task: {e}", exc_info=True)
    
    def run(self):
        """เริ่มต้น worker"""
        logger.info("=" * 80)
        logger.info("🚀 Starting Video Worker (Redis)")
        logger.info("=" * 80)
        logger.info(f"Redis Configuration: {self.redis_queue_service.host}:{self.redis_queue_service.port}")
        
        # Infinite retry loop
        while self.running:
            try:
                # ตรวจสอบ connection
                self.redis_queue_service._ensure_connection()
                
                logger.info("✅ Video Worker พร้อมรับงาน...")
                logger.info("=" * 80)
                
                # เริ่มรับ messages
                logger.info("🔄 เริ่มรับ messages จาก Redis...")
                message_count = 0
                
                while self.running:
                    try:
                        # Consume transcription requests (blocking with 1 second timeout)
                        consumed_request = self.redis_queue_service.consume_transcription_tasks(
                            callback=self._process_transcription_request,
                            timeout=1,
                            use_streams=True,
                            consumer_group='workers',
                            consumer_name=f'worker_{os.getpid()}'
                        )
                        
                        # Consume chunk transcription tasks (blocking with 1 second timeout)
                        # ใช้ Redis Streams (มี acknowledgment support)
                        consumed_chunk = self.redis_queue_service.consume_chunk_transcription_tasks(
                            callback=self._process_chunk_task,
                            timeout=1,
                            use_streams=True,  # ใช้ Redis Streams
                            consumer_group='workers',
                            consumer_name=f'worker_{os.getpid()}'  # Unique consumer name
                        )
                        
                        consumed = consumed_request or consumed_chunk
                        
                        if consumed:
                            message_count += 1
                            if message_count % 10 == 0:
                                logger.info(f"📊 Processed {message_count} messages so far...")
                        
                        # Log every 30 seconds to show we're alive
                        if message_count == 0:
                            current_time = time.time()
                            if not hasattr(self, '_last_heartbeat') or (current_time - self._last_heartbeat) > 30:
                                logger.debug("💓 Video Worker is alive and waiting for messages...")
                                self._last_heartbeat = current_time
                        
                        # Clean up completed futures
                        completed_tasks = []
                        for task_id, future in list(self.active_chunks.items()):
                            if future.done():
                                completed_tasks.append(task_id)
                        
                        for task_id in completed_tasks:
                            del self.active_chunks[task_id]
                            if len(completed_tasks) > 0:
                                logger.debug(f"✅ Completed chunk task: {task_id} (active: {len(self.active_chunks)})")
                    
                    except KeyboardInterrupt:
                        logger.info("ได้รับ interrupt signal")
                        self.running = False
                        break
                    
                    except Exception as e:
                        logger.error(f"❌ Unexpected error in message processing loop: {e}", exc_info=True)
                        # Continue to next iteration
                        time.sleep(1)
                
                # If we break from inner loop, try to reconnect
                if self.running:
                    logger.info("🔄 Attempting to reconnect to Redis...")
                    time.sleep(5)
                    continue
                else:
                    # Normal shutdown
                    break
                    
            except KeyboardInterrupt:
                logger.info("ได้รับ interrupt signal")
                self.running = False
                break
            except Exception as e:
                logger.error(f"❌ Fatal error in worker: {e}", exc_info=True)
                logger.warning("💡 Worker will retry in 30 seconds...")
                time.sleep(30)
        
        # Cleanup
        self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        logger.info("🧹 Starting cleanup...")
        
        # Wait for active chunks to complete (with timeout)
        if self.active_chunks:
            logger.info(f"⏳ Waiting for {len(self.active_chunks)} active chunks to complete...")
            import concurrent.futures
            for task_id, future in list(self.active_chunks.items()):
                try:
                    future.result(timeout=30)
                    logger.info(f"✅ Chunk task {task_id} completed")
                except concurrent.futures.TimeoutError:
                    logger.warning(f"⚠️ Chunk task {task_id} timeout")
                except Exception as e:
                    logger.error(f"❌ Chunk task {task_id} error: {e}")
        
        # Shutdown executor
        try:
            self.executor.shutdown(wait=True, timeout=60)
            logger.info("✅ ThreadPoolExecutor shutdown complete")
        except Exception as e:
            logger.warning(f"⚠️ Error shutting down executor: {e}")
        
        logger.info("✅ Cleanup complete")


def main():
    """Main entry point"""
    worker = VideoWorkerRedis()
    try:
        worker.run()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

