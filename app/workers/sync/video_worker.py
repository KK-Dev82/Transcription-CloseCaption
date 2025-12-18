"""
Video Worker (Pika - Blocking) - Main Orchestrator

รวมทุก components เข้าด้วยกัน: connection, consumers, handlers, processors
ใช้ pika (blocking) สำหรับ RabbitMQ
"""
import logging
import os
import signal
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# เพิ่ม app directory เข้าไปใน Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

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

from app.services.video_service import VideoService
from app.services.transcription_service import TranscriptionService
from app.utils.json_storage import JSONStorage

# Import sync worker components
from .connection import RabbitMQConnection
from .consumers import RabbitMQConsumers
from .handlers import MessageHandlers
from .processors import TaskProcessors

logger = logging.getLogger(__name__)


class VideoWorkerPika:
    """
    Video Worker (Pika - Blocking)
    
    Features:
    - ใช้ pika (blocking) สำหรับ RabbitMQ
    - รองรับ multiple queues
    - Thread pool สำหรับ parallel chunk processing
    """
    
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
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Initialize worker components
        self.connection = RabbitMQConnection()
        self.processors = TaskProcessors(self)
        self.handlers = MessageHandlers(self)
        self.consumers = RabbitMQConsumers(self.connection)
        self.consumers.set_handlers(self.handlers)
        
        logger.info("✅ VideoWorkerPika initialized")
    
    def _signal_handler(self, signum, frame):
        """จัดการ signal สำหรับ graceful shutdown"""
        logger.info(f"📛 Received signal {signum}, shutting down gracefully...")
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        """Cleanup resources"""
        logger.info("🧹 Cleaning up resources...")
        
        # Shutdown executor
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
            logger.info("✅ ThreadPoolExecutor shut down")
        
        # Close connections
        if hasattr(self, 'connection') and self.connection:
            try:
                if hasattr(self.connection, 'stop_consuming'):
                    self.connection.stop_consuming()
                if hasattr(self.connection, 'close'):
                    self.connection.close()
            except Exception as e:
                logger.warning(f"⚠️  Error closing connection: {e}")
        
        logger.info("✅ Cleanup completed")
    
    def run(self):
        """Run worker - consume messages from RabbitMQ"""
        try:
            logger.info("=" * 80)
            logger.info("🚀 Starting Video Worker (Pika - Blocking)")
            logger.info("=" * 80)
            
            # Connect to RabbitMQ
            logger.info("🔌 Connecting to RabbitMQ...")
            if not self.connection.connect_rabbitmq():
                logger.error("❌ Failed to connect to RabbitMQ")
                return
            
            logger.info("✅ Connected to RabbitMQ")
            
            # Setup consumers
            logger.info("📋 Setting up consumers...")
            self.consumers.setup_consumers()
            logger.info("✅ Consumers setup completed")
            
            # Start consuming
            logger.info("🔄 Starting to consume messages...")
            logger.info("   Press Ctrl+C to stop")
            
            self.connection.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("📛 Received interrupt signal")
        except Exception as e:
            logger.error(f"❌ Error in worker: {e}", exc_info=True)
        finally:
            self.cleanup()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    worker = VideoWorkerPika()
    try:
        worker.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        worker.cleanup()

