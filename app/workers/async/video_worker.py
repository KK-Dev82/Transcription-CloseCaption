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
from .health_server import start_health_server, update_worker_status

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
        self.start_time = None  # สำหรับคำนวณ uptime
        
        # Async tasks สำหรับ parallel chunk processing
        max_workers = int(os.getenv('TRANSCRIPTION_MAX_WORKERS', '5'))
        self.max_concurrent_chunks = max_workers
        self.active_chunks = {}  # Track active chunk tasks: {delivery_tag: asyncio.Task}
        
        # Health check server
        self.health_server_task = None
        self.health_server_port = int(os.getenv('WORKER_HEALTH_PORT', '8030'))
        
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
        signal_name = signal.Signals(signum).name if hasattr(signal.Signals, '__members__') else f"signal {signum}"
        logger.info(f"ได้รับ {signal_name} ({signum}) กำลังปิด worker gracefully...")
        # Set running to False เพื่อให้ worker exit gracefully
        # แต่ main() loop จะ restart worker อัตโนมัติ (ยกเว้น KeyboardInterrupt)
        self.running = False
    
    async def start(self):
        """เริ่มต้น async worker"""
        logger.info("=" * 80)
        logger.info("🚀 Starting Video Worker (aio-pika - Async)")
        logger.info("=" * 80)
        logger.info(f"RabbitMQ Configuration: {self.connection.rabbitmq_host}:{self.connection.rabbitmq_port}")
        
        self.start_time = asyncio.get_event_loop().time()
        
        # Update worker status
        update_worker_status(running=True)
        
        # Start health check server (background task)
        logger.info(f"🚀 Starting health check server on port {self.health_server_port}...")
        self.health_server_task = asyncio.create_task(
            start_health_server(port=self.health_server_port)
        )
        logger.info(f"✅ Health check server started on port {self.health_server_port}")
        
        # Infinite retry loop for connection
        while self.running:
            try:
                # เชื่อมต่อ RabbitMQ (with retry)
                if not await self.connection.connect(max_retries=10, retry_delay=5):
                    logger.error("ไม่สามารถเชื่อมต่อ RabbitMQ ได้ - Worker will retry")
                    logger.warning("💡 Video Worker will retry connection in 30 seconds...")
                    update_worker_status(rabbitmq_connected=False)
                    await asyncio.sleep(30)
                    continue
                
                logger.info("✅ Connected to RabbitMQ")
                update_worker_status(rabbitmq_connected=True)
                
                # Initialize consumers with channel and connection (for queue arguments)
                self.consumers = AsyncConsumerManager(self.connection.channel, self._get_handlers_dict(), self.connection)
                
                # ตั้งค่า consumers
                await self.consumers.setup_consumers()
                logger.info("✅ Consumers registered")
                update_worker_status(consumers_registered=True)
                
                # Setup reconnect callback to re-register consumers after RabbitMQ restart
                async def re_register_consumers():
                    """Re-register consumers after reconnection"""
                    try:
                        logger.info("🔄 Re-registering consumers after RabbitMQ reconnect...")
                        # Update consumer manager with new channel
                        self.consumers.update_channel(self.connection.channel)
                        # Re-register all consumers
                        await self.consumers.setup_consumers()
                        logger.info("✅ All consumers re-registered after RabbitMQ reconnect")
                    except Exception as e:
                        logger.error(f"❌ Failed to re-register consumers after reconnect: {e}", exc_info=True)
                        # Don't raise - let worker retry in main loop
                
                # Set reconnect callback
                self.connection.set_reconnect_callback(re_register_consumers)
                
                logger.info("✅ Video Worker พร้อมรับงาน...")
                logger.info("=" * 80)
                
                # Update worker status
                update_worker_status(
                    running=True,
                    rabbitmq_connected=True,
                    consumers_registered=True
                )
                
                # เริ่ม background tasks
                monitor_task = asyncio.create_task(self._monitor_stuck_tasks())
                logger.info("✅ Started stuck tasks monitor")
                
                # เริ่มรับ messages (จะรอตลอดไปจนกว่าจะถูก interrupt)
                logger.info("🔄 เริ่มรับ messages จาก RabbitMQ...")
                logger.info("💓 Video Worker is alive and waiting for messages...")
                
                # Monitor connection state และ re-register consumers เมื่อ reconnect
                connection_monitor_task = asyncio.create_task(self._monitor_connection_and_reconnect())
                
                # Wait for connection to close (หรือจนกว่าจะได้รับ signal)
                # ใช้ loop ตรวจสอบ self.running แทน asyncio.sleep(float('inf'))
                # เพื่อให้ตอบสนองต่อ SIGTERM ทันที
                # Update uptime และ active tasks ใน health check
                last_health_update = 0
                try:
                    # Wait until connection is closed or interrupted
                    # ตรวจสอบ self.running ทุก 1 วินาที แทน asyncio.sleep(float('inf'))
                    while self.running:
                        await asyncio.sleep(1)  # Check every 1 second
                        
                        # Update health check status ทุก 5 วินาที
                        current_time = asyncio.get_event_loop().time()
                        if current_time - last_health_update >= 5:
                            if self.start_time:
                                uptime = current_time - self.start_time
                                update_worker_status(
                                    active_tasks=len(self.active_chunks),
                                    uptime_seconds=int(uptime)
                                )
                            last_health_update = current_time
                    logger.info("Worker shutdown requested (self.running = False)")
                    break
                except asyncio.CancelledError:
                    logger.info("Received cancellation signal")
                    break
                finally:
                    # Cancel background tasks
                    monitor_task.cancel()
                    connection_monitor_task.cancel()
                    try:
                        await monitor_task
                        await connection_monitor_task
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
            # Close Caption handlers (แยกจาก transcription เพื่อลัดคิว)
            'close_caption_request': self.handlers.handle_close_caption_request,
            'close_caption_extraction': self.handlers.handle_close_caption_extraction,
            'close_caption': self.handlers.handle_close_caption,
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
    
    async def _monitor_connection_and_reconnect(self):
        """
        Monitor connection state และ re-register consumers เมื่อ reconnect
        
        ทำงาน:
        1. Monitor connection state ทุก 5 วินาที
        2. Detect เมื่อ connection reconnect (จาก closed → open)
        3. Re-register consumers เมื่อ reconnect
        4. Heartbeat logging ทุก 25 วินาที พร้อม ping RabbitMQ (เพื่อป้องกัน idle timeout)
        """
        logger.info("🔍 Started connection monitor for reconnection handling")
        
        last_connection_state = None
        last_heartbeat_time = 0
        heartbeat_interval = 25  # Heartbeat every 25 seconds (ป้องกัน idle timeout)
        
        try:
            while self.running:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                try:
                    current_time = asyncio.get_event_loop().time()
                    
                    # Check connection state using is_connected() method
                    if self.connection:
                        # Use is_connected() method instead of direct attribute access
                        is_connected = self.connection.is_connected()
                        current_state = "open" if is_connected else "closed"
                        
                        # Detect reconnection: closed → open
                        if last_connection_state == "closed" and current_state == "open":
                            logger.info("🔄 Detected connection reconnection, re-registering consumers...")
                            
                            # Handle reconnection
                            if await self.connection.handle_reconnection():
                                logger.info("✅ Successfully handled reconnection")
                            else:
                                logger.warning("⚠️ Reconnection handling failed, will retry")
                        
                        last_connection_state = current_state
                        
                        # Heartbeat: Ping RabbitMQ และ log activity ทุก 25 วินาที
                        # เพื่อป้องกัน platform (RunPod) มองว่า idle แล้ว terminate
                        if current_time - last_heartbeat_time >= heartbeat_interval:
                            try:
                                # Ping RabbitMQ ด้วย lightweight operation (declare queue passive)
                                if self.connection.channel and not self.connection.channel.is_closed:
                                    # Try to get a queue (passive check - lightweight operation)
                                    test_queue = await self.connection.channel.get_queue(
                                        'transcription_request_queue', 
                                        ensure=False
                                    )
                                    if test_queue:
                                        logger.info("💓 [Heartbeat] Worker alive - RabbitMQ connection healthy")
                                    else:
                                        logger.warning("⚠️ [Heartbeat] RabbitMQ queue check returned None")
                                else:
                                    logger.warning("⚠️ [Heartbeat] Channel not available")
                                
                                last_heartbeat_time = current_time
                            except Exception as heartbeat_error:
                                logger.warning(f"⚠️ [Heartbeat] Error pinging RabbitMQ: {heartbeat_error}")
                                # Continue anyway - don't let heartbeat failure stop monitoring
                    else:
                        last_connection_state = None
                        
                except Exception as e:
                    logger.error(f"❌ Error in connection monitor: {e}", exc_info=True)
                    await asyncio.sleep(10)  # Wait a bit before retrying
        
        except asyncio.CancelledError:
            logger.info("🔍 Connection monitor cancelled")
            raise
        except Exception as e:
            logger.error(f"❌ Fatal error in connection monitor: {e}", exc_info=True)
    
    async def cleanup(self):
        """
        Cleanup resources - SIMPLE & FAST version
        
        หลักการ:
        - ทำ cleanup ให้เร็วที่สุด (ไม่รอ)
        - ใช้ try/finally เพื่อให้ cleanup() เสร็จแม้ถูก interrupt
        - ไม่ต้องรอ RabbitMQ close (ให้ OS จัดการเอง)
        - Cancel tasks แบบ non-blocking
        """
        logger.info("🧹 Starting fast cleanup...")
        
        # Update worker status
        update_worker_status(
            running=False,
            rabbitmq_connected=False,
            consumers_registered=False,
            active_tasks=0
        )
        
        # Cancel health server task
        if self.health_server_task and not self.health_server_task.done():
            self.health_server_task.cancel()
            try:
                await self.health_server_task
            except asyncio.CancelledError:
                logger.info("✅ Health check server stopped")
        
        # Cancel all active chunk tasks (non-blocking)
        try:
            cancelled_count = 0
            for delivery_tag, task in list(self.active_chunks.items()):
                if not task.done():
                    task.cancel()
                    cancelled_count += 1
            self.active_chunks.clear()
            if cancelled_count > 0:
                logger.info(f"✅ Cancelled {cancelled_count} active chunk task(s)")
        except Exception as e:
            logger.warning(f"⚠️ Error cancelling chunk tasks: {e}")
        
        # Close RabbitMQ connections - SIMPLE & FAST
        # ⚠️ สำคัญ: aio-pika จะ nack messages ที่ยังไม่ ack อัตโนมัติเมื่อ connection close
        # แต่ถ้า connection close เร็วเกินไป messages อาจไม่ถูก nack
        # ดังนั้นเราจะรอสักครู่เพื่อให้ messages ถูก nack ก่อน close
        try:
            logger.info("🔄 Closing RabbitMQ connections (ensuring unacked messages are nacked)...")
            
            # รอสักครู่เพื่อให้ messages ที่ยังไม่ ack ถูก nack
            # aio-pika จะ nack messages อัตโนมัติเมื่อ connection close
            # แต่ถ้า close เร็วเกินไป อาจไม่ทัน nack
            await asyncio.sleep(0.2)  # รอ 0.2 วินาที (น้อยกว่า timeout)
            
            # Close immediately with timeout
            # ใช้ asyncio.wait_for เพื่อ timeout ถ้า close ใช้เวลานาน
            await asyncio.wait_for(
                self.connection.close(),
                timeout=0.3  # Timeout 0.3 วินาที - ถ้าเกินให้ skip
            )
            logger.info("✅ RabbitMQ connections closed (unacked messages should be requeued)")
        except asyncio.TimeoutError:
            logger.warning("⚠️ Connection close timeout - messages will be requeued by RabbitMQ")
        except asyncio.CancelledError:
            logger.warning("⚠️ Connection close cancelled - messages will be requeued by RabbitMQ")
        except Exception as e:
            logger.warning(f"⚠️ Error closing RabbitMQ connection: {e} - messages will be requeued by RabbitMQ")
        
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
    # Worker จะ restart อัตโนมัติเมื่อ:
    # 1. Worker exit unexpectedly (worker.running = True แต่ exit)
    # 2. Worker crash (exception)
    # 3. Worker ได้รับ SIGTERM (worker.running = False แต่จะ restart)
    # ยกเว้น: KeyboardInterrupt (SIGINT) - จะ shutdown แบบถาวร
    while True:
        try:
            logger.info("🔄 Creating new worker instance...")
            worker = VideoWorkerAsync()
            logger.info("🚀 Starting worker...")
            await worker.start()
            logger.info("ℹ️ Worker start() returned")
            
            # Worker exited - check reason
            if not worker.running:
                # Worker shutdown gracefully (อาจมาจาก SIGTERM หรือ manual shutdown)
                # Restart worker อัตโนมัติ (ยกเว้นถ้าเป็น KeyboardInterrupt ซึ่งจะไม่มาถึงตรงนี้)
                logger.warning("⚠️ Worker shutdown gracefully (อาจได้รับ SIGTERM), restarting in 1 second...")
                try:
                    # ใช้ sleep แบบธรรมดา (ไม่ใช้ wait_for) เพื่อให้ SIGKILL interrupt ได้
                    # แต่เพิ่ม logging เพื่อ track restart process
                    logger.info("🔄 Restarting in 1 second...")
                    await asyncio.sleep(1)
                    logger.info("✅ Wait completed, restarting worker now...")
                except (asyncio.CancelledError, KeyboardInterrupt):
                    logger.warning("⚠️ Restart wait cancelled, restarting immediately.")
                except Exception as e:
                    logger.error(f"❌ Error during restart wait: {e}", exc_info=True)
                logger.info("🔄 Creating new worker instance for restart...")
                continue
            else:
                # Worker exited unexpectedly (ไม่ควรเกิดขึ้น)
                logger.warning("⚠️ Worker exited unexpectedly, restarting in 1 second...")
                try:
                    # ใช้ sleep แบบธรรมดา (ไม่ใช้ wait_for) เพื่อให้ SIGKILL interrupt ได้
                    # แต่เพิ่ม logging เพื่อ track restart process
                    logger.info("🔄 Restarting in 1 second...")
                    await asyncio.sleep(1)
                    logger.info("✅ Wait completed, restarting worker now...")
                except (asyncio.CancelledError, KeyboardInterrupt):
                    logger.warning("⚠️ Restart wait cancelled, restarting immediately.")
                except Exception as e:
                    logger.error(f"❌ Error during restart wait: {e}", exc_info=True)
                logger.info("🔄 Creating new worker instance for restart...")
                continue
                
        except KeyboardInterrupt:
            # SIGINT (Ctrl+C) - shutdown แบบถาวร
            logger.info("ได้รับ interrupt signal (SIGINT) - Shutting down permanently...")
            break
        except Exception as e:
            # Log to error file with full traceback
            logger.error(f"❌ Fatal error in worker: {e}", exc_info=True)
            logger.error(f"❌ Worker crash details: type={type(e).__name__}, message={str(e)}", exc_info=True)
            
            # Check for GPU-related errors
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['cuda', 'gpu', 'out of memory', 'oom', 'nvidia', 'cudnn']):
                logger.error("🚨 GPU-related error detected! This may indicate GPU overload or memory issues.")
            
                logger.warning("⚠️ Worker crashed, restarting in 1 second...")
                try:
                    # ใช้ sleep แบบธรรมดา (ไม่ใช้ wait_for) เพื่อให้ SIGKILL interrupt ได้
                    # แต่เพิ่ม logging เพื่อ track restart process
                    logger.info("🔄 Restarting in 1 second...")
                    await asyncio.sleep(1)
                    logger.info("✅ Wait completed, restarting worker now...")
                except (asyncio.CancelledError, KeyboardInterrupt):
                    logger.warning("⚠️ Restart wait cancelled, restarting immediately.")
                except Exception as e:
                    logger.error(f"❌ Error during restart wait: {e}", exc_info=True)
                logger.info("🔄 Creating new worker instance for restart...")
                continue


if __name__ == "__main__":
    asyncio.run(main())

