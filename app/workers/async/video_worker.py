"""
Video Worker (aio-pika - Async) - Main Orchestrator

รวมทุก components เข้าด้วยกัน: connection, consumers, handlers, processors, utils
ใช้ async/await ทั้งหมด ไม่มีปัญหา thread safety
"""
import asyncio
import logging
import os
import signal
import sys
import psutil
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
from app.utils.json_storage import JSONStorage

# Import async worker components (ใช้ relative import เพราะ 'async' เป็น keyword)
from .connection import AsyncRabbitMQConnection
from .consumers import AsyncConsumerManager
from .handlers import AsyncMessageHandlers
from .processors import AsyncTaskProcessors
from .utils import AsyncWorkerUtils

logger = logging.getLogger(__name__)


class VideoWorkerAsync:
    """Video Worker (aio-pika - Async) - Main Orchestrator"""
    
    def __init__(self):
        """Initialize Video Worker with all components"""
        # Initialize services
        self.video_service = VideoService()
        self.transcription_service = TranscriptionService()
        self.json_storage = JSONStorage()
        
        # Worker state
        self.running = True
        
        # Async tasks สำหรับ parallel chunk processing
        max_workers = int(os.getenv('TRANSCRIPTION_MAX_WORKERS', '5'))
        self.max_concurrent_chunks = max_workers
        self.active_chunks = {}  # Track active chunk tasks: {delivery_tag: asyncio.Task}
        
        logger.info(f"🔧 Async worker initialized with max_concurrent_chunks={max_workers}")
        
        # Initialize worker components
        self.connection = AsyncRabbitMQConnection()
        self.processors = AsyncTaskProcessors(self)
        self.utils = AsyncWorkerUtils(self)
        self.handlers = AsyncMessageHandlers(self)
        
        # Inject handlers into consumers (will be set up after connection)
        self.consumers = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """จัดการ signal สำหรับ graceful shutdown"""
        logger.info(f"ได้รับ signal {signum} กำลังปิด worker...")
        self.running = False
    
    async def start(self):
        """เริ่มต้น async worker"""
        logger.info("=" * 80)
        logger.info("🚀 Starting Video Worker (aio-pika - Async)")
        logger.info("=" * 80)
        logger.info(f"RabbitMQ Configuration: {self.connection.rabbitmq_host}:{self.connection.rabbitmq_port}")
        
        # Infinite retry loop for connection
        while self.running:
            try:
                # เชื่อมต่อ RabbitMQ (with retry)
                if not await self.connection.connect(max_retries=10, retry_delay=5):
                    logger.error("ไม่สามารถเชื่อมต่อ RabbitMQ ได้ - Worker will retry")
                    logger.warning("💡 Video Worker will retry connection in 30 seconds...")
                    await asyncio.sleep(30)
                    continue
                
                # Initialize consumers with channel and connection (for queue arguments)
                self.consumers = AsyncConsumerManager(self.connection.channel, self._get_handlers_dict(), self.connection)
                
                # ตั้งค่า consumers
                await self.consumers.setup_consumers()
                
                logger.info("✅ Video Worker พร้อมรับงาน...")
                logger.info("=" * 80)
                
                # เริ่ม background tasks
                monitor_task = asyncio.create_task(self._monitor_stuck_tasks())
                logger.info("✅ Started stuck tasks monitor")
                
                # เริ่มรับ messages (จะรอตลอดไปจนกว่าจะถูก interrupt)
                logger.info("🔄 เริ่มรับ messages จาก RabbitMQ...")
                logger.info("💓 Video Worker is alive and waiting for messages...")
                
                # Wait for connection to close (หรือจนกว่าจะได้รับ signal)
                try:
                    # Wait until connection is closed or interrupted
                    await asyncio.sleep(float('inf'))  # Wait indefinitely
                except asyncio.CancelledError:
                    logger.info("Received cancellation signal")
                    break
                finally:
                    # Cancel background tasks
                    monitor_task.cancel()
                    try:
                        await monitor_task
                    except asyncio.CancelledError:
                        pass
                
            except KeyboardInterrupt:
                logger.info("ได้รับ interrupt signal")
                self.running = False
                break
            except Exception as e:
                logger.error(f"❌ Fatal error in worker: {e}", exc_info=True)
                logger.warning("💡 Worker will retry in 30 seconds...")
                await asyncio.sleep(30)
        
        # Cleanup
        await self.cleanup()
    
    def _get_handlers_dict(self) -> dict:
        """Get handlers dictionary for consumers"""
        return {
            'trim': self.handlers.handle_trim,
            'merge': self.handlers.handle_merge,
            'convert': self.handlers.handle_convert,
            'resize': self.handlers.handle_resize,
            'transcription': self.handlers.handle_transcription,
            'chunk_transcription': self.handlers.handle_chunk_transcription,
            'audio_chunk_extracted': self.handlers.handle_audio_chunk_extracted,
            'transcription_request': self.handlers.handle_transcription_request,
            'audio_extraction': self.handlers.handle_audio_extraction,
        }
    
    async def _monitor_stuck_tasks(self):
        """
        Background task เพื่อตรวจสอบและจัดการ stuck tasks
        
        ทำงาน:
        1. ตรวจสอบ tasks ที่ติดค้างทุก 60 วินาที
        2. ถ้าพบ stuck task ให้ mark as failed และ log warning
        3. (Optional) Re-queue task เพื่อให้ worker อื่นลองประมวลผล
        """
        import time
        from datetime import datetime
        
        check_interval = int(os.getenv('STUCK_TASK_CHECK_INTERVAL_SECONDS', '60'))  # Check every 60 seconds
        
        logger.info(f"🔍 Started stuck tasks monitor (check interval: {check_interval}s)")
        
        try:
            while self.running:
                await asyncio.sleep(check_interval)
                
                try:
                    # Get stuck tasks from utils
                    stuck_tasks = self.utils.get_stuck_tasks()
                    
                    if stuck_tasks:
                        logger.warning(f"⚠️  Found {len(stuck_tasks)} stuck tasks:")
                        for task_id, task_info in stuck_tasks.items():
                            elapsed = task_info.get('elapsed_time', 0)
                            time_since_heartbeat = task_info.get('time_since_heartbeat', 0)
                            task_type = task_info.get('task_type', 'unknown')
                            
                            logger.warning(f"   - {task_id}: {task_type} - elapsed: {elapsed:.1f}s, no heartbeat: {time_since_heartbeat:.1f}s")
                            
                            # Mark task as failed
                            try:
                                task_data = self.json_storage.get_transcription(task_id)
                                if task_data and task_data.get('status') == 'processing':
                                    task_data['status'] = 'failed'
                                    task_data['error_message'] = f"Task stuck - no progress for {time_since_heartbeat:.1f}s, total elapsed: {elapsed:.1f}s"
                                    task_data['failed_at'] = datetime.now().isoformat()
                                    task_data['failed_reason'] = 'stuck_task_detected'
                                    self.json_storage.save_transcription(task_id, task_data)
                                    
                                    # Mark as failed in tracking
                                    self.utils.track_task_complete(task_id, 'failed')
                                    
                                    logger.warning(f"   ✅ Marked task {task_id} as failed")
                                    
                                    # TODO: Optionally re-queue task if needed
                                    # This could be done by publishing to the original queue
                                    # But be careful to avoid infinite loops
                                    
                            except Exception as e:
                                logger.error(f"   ❌ Failed to handle stuck task {task_id}: {e}", exc_info=True)
                    
                except Exception as e:
                    logger.error(f"❌ Error in stuck tasks monitor: {e}", exc_info=True)
                    await asyncio.sleep(10)  # Wait a bit before retrying
        
        except asyncio.CancelledError:
            logger.info("🔍 Stuck tasks monitor cancelled")
            raise
        except Exception as e:
            logger.error(f"❌ Fatal error in stuck tasks monitor: {e}", exc_info=True)
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("🧹 Starting cleanup...")
        
        # Cancel all active chunk tasks
        try:
            for delivery_tag, task in list(self.active_chunks.items()):
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            self.active_chunks.clear()
            logger.info("✅ All active chunk tasks cancelled")
        except Exception as e:
            logger.warning(f"⚠️ Error cancelling chunk tasks: {e}")
        
        # Close RabbitMQ connections
        try:
            await self.connection.close()
        except Exception as e:
            logger.warning(f"⚠️ Error closing RabbitMQ connection: {e}")
        
        logger.info("✅ Video Worker cleanup completed")
        logger.info("Video Worker ปิดตัวลง")


async def main():
    """Main async function สำหรับรัน worker"""
    # Setup logging with separate error log file
    LOG_DIR = Path("logs")
    LOG_DIR.mkdir(exist_ok=True)
    WORKER_LOG_FILE = LOG_DIR / "video-worker.log"
    WORKER_ERROR_LOG_FILE = LOG_DIR / "video-worker-errors.log"
    
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s\n%(pathname)s:%(lineno)d\n%(funcName)s\n%(exc_info)s'
    )
    
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    file_handler = logging.FileHandler(WORKER_LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    error_file_handler = logging.FileHandler(WORKER_ERROR_LOG_FILE, encoding='utf-8')
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(error_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_file_handler)
    
    logger.info("=" * 80)
    logger.info("🚀 Starting Video Worker (aio-pika - Async)")
    logger.info("=" * 80)
    logger.info(f"📁 Log files: {WORKER_LOG_FILE}, {WORKER_ERROR_LOG_FILE}")
    
    # Infinite retry loop for worker crashes
    while True:
        try:
            worker = VideoWorkerAsync()
            await worker.start()
            
            # If we exit normally, break the loop
            if not worker.running:
                logger.info("✅ Worker shutdown gracefully")
                break
            else:
                logger.warning("⚠️ Worker exited unexpectedly, restarting in 10 seconds...")
                await asyncio.sleep(10)
                
        except KeyboardInterrupt:
            logger.info("ได้รับ interrupt signal - Shutting down...")
            break
        except Exception as e:
            # Log to error file with full traceback
            logger.error(f"❌ Fatal error in worker: {e}", exc_info=True)
            logger.error(f"❌ Worker crash details: type={type(e).__name__}, message={str(e)}", exc_info=True)
            
            # Check for GPU-related errors
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['cuda', 'gpu', 'out of memory', 'oom', 'nvidia', 'cudnn']):
                logger.error("🚨 GPU-related error detected! This may indicate GPU overload or memory issues.")
            
            logger.warning("⚠️ Worker crashed, restarting in 10 seconds...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())

