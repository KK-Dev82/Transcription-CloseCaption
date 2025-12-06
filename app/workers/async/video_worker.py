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

# Import async worker components
from app.workers.async.connection import AsyncRabbitMQConnection
from app.workers.async.consumers import AsyncConsumerManager
from app.workers.async.handlers import AsyncMessageHandlers
from app.workers.async.processors import AsyncTaskProcessors
from app.workers.async.utils import AsyncWorkerUtils

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
                
                # Initialize consumers with channel
                self.consumers = AsyncConsumerManager(self.connection.channel, self._get_handlers_dict())
                
                # ตั้งค่า consumers
                await self.consumers.setup_consumers()
                
                logger.info("✅ Video Worker พร้อมรับงาน...")
                logger.info("=" * 80)
                
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
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("=" * 80)
    logger.info("🚀 Starting Video Worker (aio-pika - Async)")
    logger.info("=" * 80)
    
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
            logger.error(f"❌ Fatal error in worker: {e}", exc_info=True)
            logger.warning("⚠️ Worker crashed, restarting in 10 seconds...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())

