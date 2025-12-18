"""
Video Worker (Pika - Blocking) - Main Orchestrator

รวมทุก components เข้าด้วยกัน: connection, consumers, handlers, processors, utils
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

# Load .env.runpod if exists (ต้องทำก่อน import services ที่ใช้ environment variables)
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent.parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
        logger_temp = logging.getLogger(__name__)
        logger_temp.info(f"✅ Loaded environment from: {env_file}")
except ImportError:
    pass  # python-dotenv not installed, will use system env vars
except Exception as e:
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning(f"⚠️  Failed to load .env.runpod: {e}")

from app.services.video_service import VideoService
from app.services.transcription_service import TranscriptionService
from app.utils.json_storage import JSONStorage

# Import worker components
from app.workers.sync.connection import RabbitMQConnection
from app.workers.sync.consumers import RabbitMQConsumers
from app.workers.sync.handlers import MessageHandlers
from app.workers.sync.processors import TaskProcessors
from app.workers.sync.utils import WorkerUtils

import pika
from pika.exceptions import StreamLostError, ConnectionClosed, AMQPConnectionError

logger = logging.getLogger(__name__)


class VideoWorkerPika:
    """Video Worker (Pika - Blocking) - Main Orchestrator"""
    
    def __init__(self):
        """Initialize Video Worker with all components"""
        # Initialize services
        self.video_service = VideoService()
        self.transcription_service = TranscriptionService()
        self.json_storage = JSONStorage()
        
        # Worker state
        self.running = True
        
        # Thread pool สำหรับ parallel chunk processing
        max_workers = int(os.getenv('TRANSCRIPTION_MAX_WORKERS', '5'))
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="chunk_worker")
        logger.info(f"🔧 ThreadPoolExecutor initialized with {max_workers} workers")
        self.active_chunks = {}  # Track active chunk tasks: {delivery_tag: future}
        
        # Initialize worker components
        self.connection = RabbitMQConnection()
        self.consumers = RabbitMQConsumers(self.connection)
        self.processors = TaskProcessors(self)
        self.utils = WorkerUtils(self)
        self.handlers = MessageHandlers(self)
        
        # Inject handlers into consumers
        self.consumers.set_handlers(self.handlers)
        
        # Background thread สำหรับ maintain RabbitMQ connection
        self._maintenance_thread = None
        self._maintenance_thread_running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """จัดการ signal สำหรับ graceful shutdown"""
        logger.info(f"ได้รับ signal {signum} กำลังปิด worker...")
        self.running = False
        self._maintenance_thread_running = False  # Stop maintenance thread
    
    def run(self):
        """เริ่มต้น worker"""
        logger.info("=" * 80)
        logger.info("🚀 Starting Video Worker (Pika - Blocking)")
        logger.info("=" * 80)
        logger.info(f"RabbitMQ Configuration: {self.connection.rabbitmq_host}:{self.connection.rabbitmq_port}")
        
        # Infinite retry loop for connection
        while self.running:
            try:
                # เชื่อมต่อ RabbitMQ (with retry)
                if not self.connection.connect_rabbitmq(max_retries=10, retry_delay=5):
                    logger.error("ไม่สามารถเชื่อมต่อ RabbitMQ ได้ - Worker will retry")
                    logger.warning("💡 Video Worker will retry connection in 30 seconds...")
                    time.sleep(30)
                    continue
                
                # ตั้งค่า consumers
                self.consumers.setup_consumers()
                
                # Start background thread สำหรับ maintain connection
                self.utils.start_maintenance_thread()
                
                logger.info("✅ Video Worker พร้อมรับงาน...")
                logger.info("=" * 80)
                
                # เริ่มรับ messages
                logger.info("🔄 เริ่มรับ messages จาก RabbitMQ...")
                message_count = 0
                
                while self.running:
                    try:
                        # Process data events (this will trigger callbacks if messages arrive)
                        if self.connection.connection and not self.connection.connection.is_closed:
                            self.connection.connection.process_data_events(time_limit=1)
                        else:
                            logger.warning("⚠️ Connection is closed, attempting to reconnect...")
                            break
                        
                        # Log every 30 seconds to show we're alive
                        if message_count == 0:
                            current_time = time.time()
                            if not hasattr(self, '_last_heartbeat') or (current_time - self._last_heartbeat) > 30:
                                logger.debug("💓 Video Worker is alive and waiting for messages...")
                                self._last_heartbeat = current_time
                        
                    except (StreamLostError, ConnectionClosed, AMQPConnectionError, 
                            ConnectionResetError, AttributeError, IndexError) as e:
                        logger.warning(f"⚠️ RabbitMQ connection lost: {type(e).__name__}: {e}")
                        logger.info("Attempting to reconnect to RabbitMQ...")
                        
                        # Stop maintenance thread temporarily
                        self.utils.stop_maintenance_thread()
                        
                        # Close existing connections
                        try:
                            self.connection.close()
                        except Exception:
                            pass
                        
                        # Break inner loop to reconnect
                        break
                    
                    except KeyboardInterrupt:
                        logger.info("ได้รับ interrupt signal")
                        self.running = False
                        break
                    
                    except Exception as e:
                        logger.error(f"❌ Unexpected error in message processing loop: {e}", exc_info=True)
                        # Continue to next iteration
                        time.sleep(1)
                
                # If we break from inner loop due to connection loss, try to reconnect
                if self.running:
                    logger.info("🔄 Attempting to reconnect to RabbitMQ...")
                    # Continue outer loop to reconnect
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
        
        # Stop maintenance thread
        try:
            self.utils.stop_maintenance_thread()
        except Exception as e:
            logger.warning(f"⚠️ Error stopping maintenance thread: {e}")
        
        # Close RabbitMQ connections
        try:
            self.connection.close()
        except Exception as e:
            logger.warning(f"⚠️ Error closing RabbitMQ connection: {e}")
        
        # Shutdown thread pool executor
        try:
            if hasattr(self, 'executor') and self.executor:
                logger.info("Shutting down thread pool executor...")
                self.executor.shutdown(wait=True)
                logger.info("✅ Thread pool executor shut down")
        except Exception as e:
            logger.warning(f"⚠️ Error shutting down executor: {e}")
        
        logger.info("✅ Video Worker cleanup completed")
        logger.info("Video Worker ปิดตัวลง")


def main():
    """Main function สำหรับรัน worker"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("=" * 80)
    logger.info("🚀 Starting Video Worker (Pika - Blocking)")
    logger.info("=" * 80)
    
    # Infinite retry loop for worker crashes
    while True:
        try:
            worker = VideoWorkerPika()
            worker.run()
            
            # If we exit normally, break the loop
            if not worker.running:
                logger.info("✅ Worker shutdown gracefully")
                break
            else:
                logger.warning("⚠️ Worker exited unexpectedly, restarting in 10 seconds...")
                time.sleep(10)
                
        except KeyboardInterrupt:
            logger.info("ได้รับ interrupt signal - Shutting down...")
            break
        except Exception as e:
            logger.error(f"❌ Fatal error in worker: {e}", exc_info=True)
            logger.warning("⚠️ Worker crashed, restarting in 10 seconds...")
            time.sleep(10)


if __name__ == "__main__":
    main()

