"""
Video Worker สำหรับการประมวลผลวิดีโอแบบ asynchronous
ใช้ RabbitMQ เป็น message queue
"""

import asyncio
import json
import logging
import os
import signal
import sys
from typing import Dict, Any
import pika
from pika.exceptions import AMQPConnectionError
import ffmpeg
from pathlib import Path
import aiohttp
import aiofiles
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading

# เพิ่ม app directory เข้าไปใน Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.video_service import VideoService
from app.services.transcription_service import TranscriptionService
from app.utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

class VideoWorker:
    def __init__(self):
        self.video_service = VideoService()
        self.transcription_service = TranscriptionService()
        self.json_storage = JSONStorage()
        self.connection = None
        self.channel = None
        self.running = True
        
        # RabbitMQ configuration
        self.rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        self.rabbitmq_port = int(os.getenv('RABBITMQ_PORT', 5672))
        self.rabbitmq_user = os.getenv('RABBITMQ_USER', 'admin')
        self.rabbitmq_password = os.getenv('RABBITMQ_PASSWORD', 'admin123')
        
        # Queue names
        self.trim_queue = 'video_trim_queue'
        self.merge_queue = 'video_merge_queue'
        self.convert_queue = 'video_convert_queue'
        self.resize_queue = 'video_resize_queue'
        self.transcription_queue = 'transcription_queue'
        self.transcription_chunk_queue = 'transcription_chunk_queue'
        self.audio_chunk_extracted_queue = 'media.audio.chunk.extracted'
        
        # Transcription exchange
        self.transcription_exchange = 'transcription.exchange'
        self.transcription_chunk_completed_routing_key = 'transcription.chunk.completed'
        
        # Thread pool สำหรับ parallel chunk processing
        # ⚠️ เพิ่ม max_workers เป็น 5-10 เพื่อให้ GPU ทำงานเต็มที่ (แต่ model lock จะจัดการให้ transcription เป็น sequential)
        # RTX 4080 Super 16GB → สามารถประมวลผลได้ 5-10 chunks พร้อมกัน (ขึ้นอยู่กับ model size)
        # medium model ~2.4GB → 5-8 chunks พร้อมกัน (model lock จะจัดการให้เป็น sequential)
        # large model ~3GB → 3-5 chunks พร้อมกัน
        # Model lock จะป้องกัน CUDA OOM แต่ workers จะไม่ idle รอ
        max_workers = int(os.getenv('TRANSCRIPTION_MAX_WORKERS', '5'))
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="chunk_worker")
        logger.info(f"🔧 ThreadPoolExecutor initialized with {max_workers} workers")
        self.active_chunks = {}  # Track active chunk tasks: {delivery_tag: future}
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """จัดการ signal สำหรับ graceful shutdown"""
        logger.info(f"ได้รับ signal {signum} กำลังปิด worker...")
        self.running = False
        try:
            if self.connection:
                try:
                    if not self.connection.is_closed:
                        self.connection.close()
                except (AttributeError, pika.exceptions.ConnectionClosed):
                    pass  # Already closed
        except Exception as e:
            logger.warning(f"Error closing connection in signal handler: {e}")
    
    def connect_rabbitmq(self, max_retries=5, retry_delay=5):
        """เชื่อมต่อกับ RabbitMQ พร้อม retry logic"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to connect to RabbitMQ at {self.rabbitmq_host}:{self.rabbitmq_port} (attempt {attempt + 1}/{max_retries})...")
                
                credentials = pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_password)
                parameters = pika.ConnectionParameters(
                    host=self.rabbitmq_host,
                    port=self.rabbitmq_port,
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300,
                    connection_attempts=3,
                    retry_delay=2
                )
                
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                
                # สร้าง exchanges
                self.channel.exchange_declare(
                    exchange='media.exchange',
                    exchange_type='topic',
                    durable=True
                )
                self.channel.exchange_declare(
                    exchange=self.transcription_exchange,
                    exchange_type='topic',
                    durable=True
                )
                
                # สร้าง queues
                self.channel.queue_declare(queue=self.trim_queue, durable=True)
                self.channel.queue_declare(queue=self.merge_queue, durable=True)
                self.channel.queue_declare(queue=self.convert_queue, durable=True)
                self.channel.queue_declare(queue=self.resize_queue, durable=True)
                self.channel.queue_declare(queue=self.transcription_queue, durable=True)
                self.channel.queue_declare(queue=self.transcription_chunk_queue, durable=True)
                
                # Queue สำหรับ audio chunk extracted (จาก Backend)
                self.channel.queue_declare(
                    queue=self.audio_chunk_extracted_queue,
                    durable=True
                )
                self.channel.queue_bind(
                    exchange='media.exchange',
                    queue=self.audio_chunk_extracted_queue,
                    routing_key='media.audio.chunk.extracted'
                )
                
                # ตั้งค่า QoS - เพิ่ม prefetch_count เพื่อให้ workers รับงานได้หลายงานพร้อมกัน
                # prefetch_count=10 หมายความว่าแต่ละ worker จะรับงานได้ 10 งานพร้อมกัน (chunks)
                # ใช้ ThreadPoolExecutor (max_workers=10) เพื่อประมวลผล parallel
                # RTX 4080 Super, 16GB VRAM → สามารถประมวลผลได้ 10 chunks พร้อมกัน
                self.channel.basic_qos(prefetch_count=10)
                
                logger.info("เชื่อมต่อ RabbitMQ สำเร็จ")
                return True
                
            except (AMQPConnectionError, Exception) as e:
                logger.warning(f"ไม่สามารถเชื่อมต่อ RabbitMQ (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    import time
                    time.sleep(retry_delay)
                else:
                    logger.error(f"ไม่สามารถเชื่อมต่อ RabbitMQ หลังจากลอง {max_retries} ครั้ง")
                    logger.error(f"RabbitMQ Host: {self.rabbitmq_host}:{self.rabbitmq_port}")
                    logger.error("💡 Solutions:")
                    logger.error("   1. Check if RabbitMQ is running")
                    logger.error("   2. Check RABBITMQ_HOST and RABBITMQ_PORT environment variables")
                    logger.error("   3. For local testing, use SSH Tunnel: ssh -L 5672:localhost:5672 ...")
                    return False
    
    def setup_consumers(self):
        """ตั้งค่า consumers สำหรับแต่ละ queue"""
        # ตั้งค่า QoS สำหรับ transcription_chunk_queue ก่อน consume
        # ⚠️ ต้องเรียก basic_qos ก่อน basic_consume สำหรับ queue นี้
        # เพิ่ม prefetch_count เป็น 20 เพื่อให้ workers รับ chunks ได้มากขึ้น (ลด idle time)
        # Model lock จะจัดการให้ transcription เป็น sequential แต่ workers จะไม่ idle รอ
        max_workers = int(os.getenv('TRANSCRIPTION_MAX_WORKERS', '3'))
        # prefetch_count ควรสูงกว่า max_workers เพื่อให้ workers มีงานรออยู่เสมอ
        # RTX 4080 Super 16GB → prefetch_count=20, max_workers=5-10 (ขึ้นอยู่กับ model size)
        prefetch_count = int(os.getenv('TRANSCRIPTION_PREFETCH_COUNT', '20'))
        self.channel.basic_qos(prefetch_count=prefetch_count, prefetch_size=0, global_qos=False)
        logger.info(f"✅ Set QoS: prefetch_count={prefetch_count} for transcription_chunk_queue (max_workers={max_workers})")
        
        # Trim video consumer
        self.channel.basic_consume(
            queue=self.trim_queue,
            on_message_callback=self._process_trim_task,
            auto_ack=False
        )
        
        # Merge video consumer
        self.channel.basic_consume(
            queue=self.merge_queue,
            on_message_callback=self._process_merge_task,
            auto_ack=False
        )
        
        # Convert format consumer
        self.channel.basic_consume(
            queue=self.convert_queue,
            on_message_callback=self._process_convert_task,
            auto_ack=False
        )
        
        # Resize video consumer
        self.channel.basic_consume(
            queue=self.resize_queue,
            on_message_callback=self._process_resize_task,
            auto_ack=False
        )
        
        # Transcription consumer
        self.channel.basic_consume(
            queue=self.transcription_queue,
            on_message_callback=self._process_transcription_task,
            auto_ack=False
        )
        
        # Audio chunk extracted consumer (สำหรับ real-time close caption)
        self.channel.basic_consume(
            queue=self.audio_chunk_extracted_queue,
            on_message_callback=self._process_audio_chunk_extracted,
            auto_ack=False
        )
        
        # Transcription chunk consumer (สำหรับ parallel processing)
        # ⚠️ ต้อง consume หลังจาก set QoS แล้ว
        self.channel.basic_consume(
            queue=self.transcription_chunk_queue,
            on_message_callback=self._process_chunk_transcription_task,
            auto_ack=False
        )
        
        logger.info("ตั้งค่า consumers เสร็จสิ้น")
        logger.info(f"📋 Listening to queues:")
        logger.info(f"   - {self.transcription_queue}")
        logger.info(f"   - {self.transcription_chunk_queue}")
        logger.info(f"   - {self.trim_queue}")
        logger.info(f"   - {self.merge_queue}")
        logger.info(f"   - {self.convert_queue}")
        logger.info(f"   - {self.resize_queue}")
        logger.info(f"   - {self.audio_chunk_extracted_queue}")
    
    def _process_trim_task(self, ch, method, properties, body):
        """ประมวลผล trim video task"""
        try:
            task_data = json.loads(body.decode('utf-8'))
            logger.info(f"เริ่มประมวลผล trim task: {task_data.get('task_id')}")
            
            # อัปเดตสถานะเป็น processing
            task_data['status'] = 'processing'
            self.json_storage.save_video_task(task_data['task_id'], task_data)
            
            # ประมวลผลการตัดวิดีโอ
            asyncio.run(self._execute_trim_task(task_data))
            
            # Acknowledge message (with connection check)
            try:
                if ch and not ch.is_closed:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.info(f"trim task เสร็จสิ้น: {task_data.get('task_id')}")
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot acknowledge trim task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"❌ Cannot acknowledge trim task: {ack_error}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล trim task: {e}")
            # ไม่ requeue เพื่อป้องกัน infinite retry loop - ส่งไป DLQ แทน
            try:
                if ch and not ch.is_closed:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot nack trim task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"ไม่สามารถ nack trim task ได้: {ack_error}")
    
    def _process_merge_task(self, ch, method, properties, body):
        """ประมวลผล merge video task"""
        try:
            task_data = json.loads(body.decode('utf-8'))
            logger.info(f"เริ่มประมวลผล merge task: {task_data.get('task_id')}")
            
            # อัปเดตสถานะเป็น processing
            task_data['status'] = 'processing'
            self.json_storage.save_video_task(task_data['task_id'], task_data)
            
            # ประมวลผลการรวมวิดีโอ
            asyncio.run(self._execute_merge_task(task_data))
            
            # Acknowledge message (with connection check)
            try:
                if ch and not ch.is_closed:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.info(f"merge task เสร็จสิ้น: {task_data.get('task_id')}")
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot acknowledge merge task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"❌ Cannot acknowledge merge task: {ack_error}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล merge task: {e}")
            # ไม่ requeue เพื่อป้องกัน infinite retry loop - ส่งไป DLQ แทน
            try:
                if ch and not ch.is_closed:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot nack merge task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"ไม่สามารถ nack merge task ได้: {ack_error}")
    
    def _process_convert_task(self, ch, method, properties, body):
        """ประมวลผล convert format task"""
        try:
            task_data = json.loads(body.decode('utf-8'))
            logger.info(f"เริ่มประมวลผล convert task: {task_data.get('task_id')}")
            
            # อัปเดตสถานะเป็น processing
            task_data['status'] = 'processing'
            self.json_storage.save_video_task(task_data['task_id'], task_data)
            
            # ประมวลผลการแปลงรูปแบบ
            asyncio.run(self._execute_convert_task(task_data))
            
            # Acknowledge message (with connection check)
            try:
                if ch and not ch.is_closed:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.info(f"convert task เสร็จสิ้น: {task_data.get('task_id')}")
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot acknowledge convert task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"❌ Cannot acknowledge convert task: {ack_error}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล convert task: {e}")
            # ไม่ requeue เพื่อป้องกัน infinite retry loop - ส่งไป DLQ แทน
            try:
                if ch and not ch.is_closed:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot nack convert task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"ไม่สามารถ nack convert task ได้: {ack_error}")
    
    def _process_resize_task(self, ch, method, properties, body):
        """ประมวลผล resize video task"""
        try:
            task_data = json.loads(body.decode('utf-8'))
            logger.info(f"เริ่มประมวลผล resize task: {task_data.get('task_id')}")
            
            # อัปเดตสถานะเป็น processing
            task_data['status'] = 'processing'
            self.json_storage.save_video_task(task_data['task_id'], task_data)
            
            # ประมวลผลการปรับขนาดวิดีโอ
            asyncio.run(self._execute_resize_task(task_data))
            
            # Acknowledge message (with connection check)
            try:
                if ch and not ch.is_closed:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.info(f"resize task เสร็จสิ้น: {task_data.get('task_id')}")
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot acknowledge resize task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"❌ Cannot acknowledge resize task: {ack_error}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล resize task: {e}")
            # ไม่ requeue เพื่อป้องกัน infinite retry loop - ส่งไป DLQ แทน
            try:
                if ch and not ch.is_closed:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot nack resize task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"ไม่สามารถ nack resize task ได้: {ack_error}")
    
    def _process_transcription_task(self, ch, method, properties, body):
        """ประมวลผล transcription task - ใช้ threading เพื่อให้ worker รับงานใหม่ได้ทันที"""
        import threading
        
        # Log immediately when message is received (BEFORE parsing)
        logger.info("=" * 80)
        logger.info("📨 📨 📨 RECEIVED MESSAGE FROM transcription_queue!")
        logger.info(f"   Message size: {len(body)} bytes")
        logger.info(f"   Delivery tag: {method.delivery_tag}")
        logger.info(f"   Exchange: {method.exchange}")
        logger.info(f"   Routing key: {method.routing_key}")
        try:
            task_data_preview = json.loads(body.decode('utf-8'))
            task_id_preview = task_data_preview.get('task_id', 'unknown')
            logger.info(f"   Task ID: {task_id_preview}")
        except Exception as e:
            logger.warning(f"   Could not parse message preview: {e}")
        logger.info("=" * 80)
        
        def process_in_thread():
            """ประมวลผลใน thread แยกเพื่อไม่ block worker"""
            task_id = None
            try:
                task_data = json.loads(body.decode('utf-8'))
                task_id = task_data.get('task_id')
                file_path = task_data.get('file_path', 'N/A')
                model_size = task_data.get('model_size', 'base')
                language = task_data.get('language', 'th')
                use_chunking = task_data.get('use_chunking', False)  # Default: false
                
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"🎬 เริ่มประมวลผล transcription task: {task_id}")
                logger.info(f"   File: {file_path}")
                logger.info(f"   Model: {model_size}, Language: {language}")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                # ตรวจสอบว่า task นี้ถูกประมวลผลไปแล้วหรือไม่ (ป้องกัน duplicate processing)
                existing_task = self.json_storage.get_transcription(task_id)
                if existing_task:
                    existing_status = existing_task.get('status', '')
                    if existing_status in ['completed', 'processing']:
                        logger.warning(f"⚠️ Task {task_id} มีสถานะ '{existing_status}' แล้ว, ข้ามการประมวลผลซ้ำ (อาจเป็น duplicate message)")
                        # Acknowledge message เพื่อไม่ให้ requeue (with connection check)
                        try:
                            if ch and not ch.is_closed:
                                ch.basic_ack(delivery_tag=method.delivery_tag)
                            else:
                                logger.warning(f"⚠️ Channel is closed, cannot acknowledge duplicate message")
                        except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                                pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                            logger.warning(f"⚠️ Cannot acknowledge duplicate message: {ack_error}")
                        return
                
                # อัปเดตสถานะเป็น processing
                task_data['status'] = 'processing'
                task_data['started_at'] = datetime.now().isoformat()
                task_data['progress'] = 0
                self.json_storage.save_transcription(task_id, task_data)
                logger.info(f"📝 อัปเดตสถานะเป็น 'processing' (Progress: 0%)")
                
                # เริ่ม monitor progress ใน background thread
                import time
                monitor_running = True
                
                def monitor_progress():
                    """Monitor progress และ log updates (only when changed)"""
                    last_progress = -1
                    last_status = ""
                    last_log_time = 0
                    while monitor_running:
                        try:
                            task_info = self.json_storage.get_transcription(task_id)
                            if task_info:
                                current_progress = task_info.get('progress', 0)
                                current_status = task_info.get('status', '')
                                current_time = time.time()
                                
                                # Log เมื่อ progress หรือ status เปลี่ยน
                                # หรือทุก 30 วินาที (เพื่อให้เห็นว่า task ยังทำงานอยู่)
                                progress_changed = (current_progress != last_progress or current_status != last_status)
                                time_since_last_log = current_time - last_log_time
                                
                                if progress_changed or time_since_last_log >= 30:
                                    if progress_changed:
                                        logger.info(f"📊 Task {task_id}: Progress {current_progress}% - Status: {current_status}")
                                    else:
                                        # Log heartbeat every 30 seconds if no change
                                        logger.debug(f"📊 Task {task_id}: Progress {current_progress}% - Status: {current_status} (heartbeat)")
                                    
                                    last_progress = current_progress
                                    last_status = current_status
                                    last_log_time = current_time
                            
                            time.sleep(5)  # Check every 5 seconds
                        except Exception as e:
                            logger.warning(f"Error monitoring progress: {e}")
                            time.sleep(5)
                
                # Start progress monitor
                progress_thread = threading.Thread(target=monitor_progress, daemon=True)
                progress_thread.start()
                
                # ประมวลผล transcription
                logger.info(f"🚀 เริ่มประมวลผล transcription...")
                asyncio.run(self._execute_transcription_task(task_data))
                
                # Stop monitoring
                monitor_running = False
                
                # Acknowledge message (with connection check and retry)
                ack_success = False
                max_ack_retries = 3
                for ack_attempt in range(max_ack_retries):
                    try:
                        if ch and not ch.is_closed:
                            # Use a short timeout to avoid hanging
                            ch.basic_ack(delivery_tag=method.delivery_tag)
                            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                            logger.info(f"✅ Transcription task เสร็จสิ้น: {task_id}")
                            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                            ack_success = True
                            break
                        else:
                            logger.warning(f"⚠️ Channel is closed (attempt {ack_attempt + 1}/{max_ack_retries})")
                            if ack_attempt < max_ack_retries - 1:
                                import time
                                time.sleep(0.5)  # Wait a bit before retry
                    except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed, 
                            pika.exceptions.AMQPConnectionError, AttributeError, IndexError) as ack_error:
                        logger.warning(f"⚠️ Cannot acknowledge message (attempt {ack_attempt + 1}/{max_ack_retries}): {ack_error}")
                        if ack_attempt < max_ack_retries - 1:
                            import time
                            time.sleep(0.5)  # Wait a bit before retry
                        else:
                            logger.error(f"❌ Failed to acknowledge message after {max_ack_retries} attempts")
                            logger.warning(f"⚠️ Task {task_id} completed but message may be redelivered")
                
                if not ack_success:
                    logger.warning(f"⚠️ Task {task_id} completed but message acknowledgment failed")
                
            except Exception as e:
                logger.error(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.error(f"❌ เกิดข้อผิดพลาดในการประมวลผล transcription task {task_id}: {e}", exc_info=True)
                logger.error(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                # ไม่ requeue เพื่อป้องกัน infinite retry loop - ส่งไป DLQ แทน
                try:
                    if ch and not ch.is_closed:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    else:
                        logger.warning(f"⚠️ Channel is closed, cannot nack message for task {task_id}")
                except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                        pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                    logger.error(f"ไม่สามารถ nack message ได้: {ack_error}")
        
        # เริ่มประมวลผลใน thread แยก เพื่อให้ worker รับงานใหม่ได้ทันที
        thread = threading.Thread(target=process_in_thread, daemon=True)
        thread.start()
    
    async def _execute_trim_task(self, task_data: Dict[str, Any]):
        """ดำเนินการตัดวิดีโอ"""
        try:
            input_file = task_data['input_file']
            start_time = task_data['start_time']
            end_time = task_data['end_time']
            output_format = task_data.get('output_format', 'mp4')
            quality = task_data.get('quality', 'medium')
            
            # ตรวจสอบไฟล์ input
            input_path = Path(input_file)
            if not input_path.exists():
                raise FileNotFoundError(f"ไม่พบไฟล์: {input_file}")
            
            # สร้างชื่อไฟล์ output ด้วยลำดับตอน
            segment_number = task_data.get('segment_number', 1)
            output_filename = f"trimmed_{segment_number:02d}_{task_data['task_id']}.{output_format}"
            output_path = Path("uploads") / output_filename
            
            # อัปเดต progress เริ่มต้น
            task_data['progress'] = 0
            self.json_storage.save_video_task(task_data['task_id'], task_data)
            
            # ตั้งค่า FFmpeg parameters
            duration = end_time - start_time
            
            # ใช้ FFmpeg ตัดวิดีโอ
            stream = ffmpeg.input(
                str(input_path), 
                ss=start_time, 
                t=duration
            )
            
            # ตั้งค่า quality
            if output_format == "mp4":
                if quality == "high":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=18, preset='slow')
                elif quality == "medium":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=23, preset='medium')
                else:  # low
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=28, preset='fast')
            else:
                stream = ffmpeg.output(stream, str(output_path))
            
            # รัน FFmpeg พร้อม progress tracking
            start_time_process = asyncio.get_event_loop().time()
            
            # สร้าง task สำหรับอัปเดต progress
            progress_running = True
            async def update_progress():
                nonlocal progress_running
                while progress_running:
                    await asyncio.sleep(5)  # อัปเดตทุก 5 วินาที
                    if not progress_running:
                        break
                    elapsed = asyncio.get_event_loop().time() - start_time_process
                    # ประมาณ progress จากเวลา (สมมติว่าใช้เวลา 80% ของ duration)
                    estimated_duration = duration * 0.8
                    progress = min(int((elapsed / estimated_duration) * 100), 95)
                    task_data['progress'] = progress
                    self.json_storage.save_video_task(task_data['task_id'], task_data)
                    logger.info(f"Trim progress: {progress}%")
            
            # เริ่ม progress tracking
            progress_task = asyncio.create_task(update_progress())
            
            try:
                # รัน FFmpeg
                ffmpeg.run(stream, overwrite_output=True, quiet=True)
                
                # หยุด progress tracking
                progress_running = False
                progress_task.cancel()
                
                # อัปเดต task เสร็จสิ้น
                task_data['status'] = 'completed'
                task_data['progress'] = 100
                task_data['output_file'] = str(output_path)
                task_data['completed_at'] = asyncio.get_event_loop().time()
                
                # บันทึกลง JSON storage
                self.json_storage.save_video_task(task_data['task_id'], task_data)
                
            except Exception as e:
                # หยุด progress tracking
                progress_running = False
                progress_task.cancel()
                raise e
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการตัดวิดีโอ: {e}")
            task_data['status'] = 'failed'
            task_data['error_message'] = str(e)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            self.json_storage.save_video_task(task_data['task_id'], task_data)
    
    async def _execute_merge_task(self, task_data: Dict[str, Any]):
        """ดำเนินการรวมวิดีโอ"""
        try:
            input_files = task_data['input_files']
            output_format = task_data.get('output_format', 'mp4')
            quality = task_data.get('quality', 'medium')
            
            # ตรวจสอบไฟล์ input
            for input_file in input_files:
                if not Path(input_file).exists():
                    raise FileNotFoundError(f"ไม่พบไฟล์: {input_file}")
            
            # สร้างไฟล์ list สำหรับ FFmpeg
            list_file = Path("temp") / f"merge_list_{task_data['task_id']}.txt"
            with open(list_file, 'w', encoding='utf-8') as f:
                for input_file in input_files:
                    f.write(f"file '{input_file}'\n")
            
            # สร้างชื่อไฟล์ output
            output_filename = f"merged_{task_data['task_id']}.{output_format}"
            output_path = Path("uploads") / output_filename
            
            # ใช้ FFmpeg รวมวิดีโอ
            stream = ffmpeg.input(str(list_file), f='concat', safe=0)
            
            # ตั้งค่า quality
            if output_format == "mp4":
                if quality == "high":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=18, preset='slow')
                elif quality == "medium":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=23, preset='medium')
                else:  # low
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=28, preset='fast')
            else:
                stream = ffmpeg.output(stream, str(output_path))
            
            # รัน FFmpeg
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            # ลบไฟล์ list
            list_file.unlink(missing_ok=True)
            
            # อัปเดต task
            task_data['status'] = 'completed'
            task_data['output_file'] = str(output_path)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            
            # บันทึกลง JSON storage
            self.json_storage.save_video_task(task_data['task_id'], task_data)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการรวมวิดีโอ: {e}")
            task_data['status'] = 'failed'
            task_data['error_message'] = str(e)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            self.json_storage.save_video_task(task_data['task_id'], task_data)
    
    async def _execute_convert_task(self, task_data: Dict[str, Any]):
        """ดำเนินการแปลงรูปแบบไฟล์"""
        try:
            input_file = task_data['input_file']
            output_format = task_data['output_format']
            quality = task_data.get('quality', 'medium')
            
            # ตรวจสอบไฟล์ input
            input_path = Path(input_file)
            if not input_path.exists():
                raise FileNotFoundError(f"ไม่พบไฟล์: {input_file}")
            
            # สร้างชื่อไฟล์ output
            output_filename = f"converted_{task_data['task_id']}.{output_format}"
            output_path = Path("uploads") / output_filename
            
            # ใช้ FFmpeg แปลงรูปแบบ
            stream = ffmpeg.input(str(input_path))
            
            # ตั้งค่า quality
            if output_format == "mp4":
                if quality == "high":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=18, preset='slow')
                elif quality == "medium":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=23, preset='medium')
                else:  # low
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=28, preset='fast')
            else:
                stream = ffmpeg.output(stream, str(output_path))
            
            # รัน FFmpeg
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            # อัปเดต task
            task_data['status'] = 'completed'
            task_data['output_file'] = str(output_path)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            
            # บันทึกลง JSON storage
            self.json_storage.save_video_task(task_data['task_id'], task_data)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแปลงรูปแบบ: {e}")
            task_data['status'] = 'failed'
            task_data['error_message'] = str(e)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            self.json_storage.save_video_task(task_data['task_id'], task_data)
    
    async def _execute_resize_task(self, task_data: Dict[str, Any]):
        """ดำเนินการปรับขนาดวิดีโอ"""
        try:
            input_file = task_data['input_file']
            width = task_data['width']
            height = task_data['height']
            output_format = task_data.get('output_format', 'mp4')
            quality = task_data.get('quality', 'medium')
            
            # ตรวจสอบไฟล์ input
            input_path = Path(input_file)
            if not input_path.exists():
                raise FileNotFoundError(f"ไม่พบไฟล์: {input_file}")
            
            # สร้างชื่อไฟล์ output
            output_filename = f"resized_{task_data['task_id']}.{output_format}"
            output_path = Path("uploads") / output_filename
            
            # ใช้ FFmpeg ปรับขนาดวิดีโอ
            stream = ffmpeg.input(str(input_path))
            stream = ffmpeg.filter(stream, 'scale', width, height)
            
            # ตั้งค่า quality
            if output_format == "mp4":
                if quality == "high":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=18, preset='slow')
                elif quality == "medium":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=23, preset='medium')
                else:  # low
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=28, preset='fast')
            else:
                stream = ffmpeg.output(stream, str(output_path))
            
            # รัน FFmpeg
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            # อัปเดต task
            task_data['status'] = 'completed'
            task_data['output_file'] = str(output_path)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            
            # บันทึกลง JSON storage
            self.json_storage.save_video_task(task_data['task_id'], task_data)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการปรับขนาดวิดีโอ: {e}")
            task_data['status'] = 'failed'
            task_data['error_message'] = str(e)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            self.json_storage.save_video_task(task_data['task_id'], task_data)
    
    def _process_audio_chunk_extracted(self, ch, method, properties, body):
        """ประมวลผล audio chunk extracted message (จาก Backend)"""
        try:
            message_data = json.loads(body.decode('utf-8'))
            # Backend ใช้ JsonSerializerDefaults.Web (camelCase)
            chunk_id = message_data.get('chunkId') or message_data.get('ChunkId')
            logger.info(f"รับ audio chunk extracted message: {chunk_id}")
            
            # ประมวลผล audio chunk และ transcribe
            asyncio.run(self._execute_audio_chunk_transcription(message_data))
            
            # Acknowledge message (with connection check)
            try:
                if ch and not ch.is_closed:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.info(f"audio chunk transcription เสร็จสิ้น: {chunk_id}")
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot acknowledge audio chunk task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"❌ Cannot acknowledge audio chunk task: {ack_error}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล audio chunk extracted: {e}", exc_info=True)
            # ไม่ requeue เพื่อป้องกัน infinite retry loop
            # ส่งไป DLQ แทน (requeue=False)
            try:
                if ch and not ch.is_closed:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot nack audio chunk task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"ไม่สามารถ nack audio chunk task ได้: {ack_error}")
    
    def _process_chunk_transcription_task(self, ch, method, properties, body):
        """ประมวลผล chunk transcription task (สำหรับ parallel processing)"""
        delivery_tag = method.delivery_tag
        chunk_task = None
        
        try:
            # Log immediately when message is received
            logger.info("=" * 80)
            logger.info("📨 📨 📨 RECEIVED MESSAGE FROM transcription_chunk_queue!")
            logger.info(f"   Message size: {len(body)} bytes")
            logger.info(f"   Delivery tag: {delivery_tag}")
            logger.info(f"   Active chunks in executor: {len(self.active_chunks)}")
            
            chunk_task = json.loads(body.decode('utf-8'))
            parent_task_id = chunk_task.get('parent_task_id')
            chunk_path = chunk_task.get('chunk_path')
            chunk_index = chunk_task.get('chunk_index', 0)
            total_chunks = chunk_task.get('total_chunks', 0)
            model_size = chunk_task.get('model_size', 'base')
            language = chunk_task.get('language', 'th')
            
            logger.info(f"   Chunk Index: {chunk_index+1}/{total_chunks}")
            logger.info(f"   Parent Task ID: {parent_task_id}")
            logger.info("=" * 80)
            
            logger.info(f"🎬 Processing chunk {chunk_index+1}/{total_chunks} for task {parent_task_id}")
            logger.info(f"   Chunk path: {chunk_path}")
            logger.info(f"   Model: {model_size}, Language: {language}")
            logger.info(f"   Active chunks in executor: {len(self.active_chunks)}")
            
            # ส่งไปยัง thread pool เพื่อประมวลผล parallel (ไม่ block)
            future = self.executor.submit(self._execute_chunk_transcription_sync, chunk_task, ch, delivery_tag)
            self.active_chunks[delivery_tag] = future
            
            logger.info(f"🚀 Chunk {chunk_index+1}/{total_chunks} submitted to thread pool (total active: {len(self.active_chunks)})")
            
            # Acknowledge message ทันที (ไม่รอให้เสร็จ) เพื่อให้ worker รับ message ใหม่ได้
            # ⚠️ หมายเหตุ: ถ้า task fail จะไม่สามารถ requeue ได้ แต่จะบันทึก error ใน storage
            try:
                if ch and not ch.is_closed:
                    ch.basic_ack(delivery_tag=delivery_tag)
                    logger.info(f"✅ Chunk {chunk_index+1}/{total_chunks} acknowledged - processing in background (active: {len(self.active_chunks)})")
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot acknowledge chunk task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"❌ Cannot acknowledge chunk task: {ack_error}")
                # ถ้า acknowledge ไม่ได้ ให้ cancel future
                if delivery_tag in self.active_chunks:
                    self.active_chunks[delivery_tag].cancel()
                    del self.active_chunks[delivery_tag]
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล chunk transcription: {e}", exc_info=True)
            # Requeue เพื่อให้ worker อื่นลองประมวลผล
            try:
                if ch and not ch.is_closed:
                    ch.basic_nack(delivery_tag=delivery_tag, requeue=True)
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot nack chunk task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"ไม่สามารถ nack chunk task ได้: {ack_error}")
            # Clean up
            if delivery_tag in self.active_chunks:
                del self.active_chunks[delivery_tag]
    
    def _execute_chunk_transcription_sync(self, chunk_task: Dict[str, Any], ch, delivery_tag):
        """Execute chunk transcription in a synchronous way (for ThreadPoolExecutor)"""
        chunk_index = chunk_task.get('chunk_index', 0)
        total_chunks = chunk_task.get('total_chunks', 0)
        parent_task_id = chunk_task.get('parent_task_id', 'unknown')
        thread_name = threading.current_thread().name
        
        logger.info(f"🔄 [Thread {thread_name}] Starting chunk {chunk_index+1}/{total_chunks} for task {parent_task_id}")
        
        try:
            # สร้าง event loop ใหม่สำหรับ thread นี้ (ไม่ใช้ asyncio.run() เพราะอาจมี conflict)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._execute_chunk_transcription(chunk_task))
                logger.info(f"✅ [Thread {thread_name}] Completed chunk {chunk_index+1}/{total_chunks} for task {parent_task_id}")
            finally:
                loop.close()
            
            # Clean up
            if delivery_tag in self.active_chunks:
                del self.active_chunks[delivery_tag]
                logger.info(f"🧹 [Thread {thread_name}] Cleaned up chunk {chunk_index+1} (remaining active: {len(self.active_chunks)})")
                
        except Exception as e:
            logger.error(f"❌ [Thread {thread_name}] Error in chunk {chunk_index+1} transcription: {e}", exc_info=True)
            # Clean up
            if delivery_tag in self.active_chunks:
                del self.active_chunks[delivery_tag]
    
    async def _execute_chunk_transcription(self, chunk_task: Dict[str, Any]):
        """ดำเนินการ transcribe chunk"""
        try:
            parent_task_id = chunk_task.get('parent_task_id')
            chunk_path = chunk_task.get('chunk_path')
            chunk_index = chunk_task.get('chunk_index', 0)
            total_chunks = chunk_task.get('total_chunks', 0)
            model_size = chunk_task.get('model_size', 'base')
            language = chunk_task.get('language', 'th')
            chunk_duration = chunk_task.get('chunk_duration', 30)
            
            # ตรวจสอบไฟล์ chunk
            chunk_file = Path(chunk_path)
            if not chunk_file.exists():
                raise FileNotFoundError(f"Chunk file not found: {chunk_path}")
            
            # Transcribe chunk
            logger.info(f"📝 Transcribing chunk {chunk_index+1}/{total_chunks}...")
            # ใช้ await provider.transcribe() โดยตรง (ไม่ผ่าน transcribe_file) เพื่อหลีกเลี่ยง event loop conflict
            transcription_result = await self.transcription_service.whisper_service.provider.transcribe(
                str(chunk_path),
                language,
                model_size
            )
            
            # Convert TranscriptionResult to dict format
            result = {
                "text": transcription_result.text,
                "segments": transcription_result.segments,
                "provider": transcription_result.provider,
                "model": transcription_result.model,
                "processing_time": transcription_result.processing_time
            }
            
            # Apply Thai processing if needed
            if language == "th":
                result = self.transcription_service.whisper_service._apply_thai_processing(result)
            
            if not result or not result.get('text'):
                logger.warning(f"⚠️ Chunk {chunk_index+1} returned empty result")
                result = {"text": "", "segments": []}
            
            # คำนวณ start_time และ end_time
            start_time = chunk_index * chunk_duration
            end_time = start_time + chunk_duration
            
            # สร้าง chunk data
            chunk_data = {
                "start_time": start_time,
                "end_time": end_time,
                "text": result.get("text", ""),
                "segments": result.get("segments", []),
                "confidence": result.get("avg_logprob"),
                "processing_time": result.get("processing_time", 0)
            }
            
            # บันทึก chunk result ลง storage
            self._save_chunk_result(parent_task_id, chunk_index, chunk_data, total_chunks)
            
            logger.info(f"✅ Chunk {chunk_index+1}/{total_chunks} transcribed: text length={len(chunk_data['text'])}, segments={len(chunk_data['segments'])}")
            
        except Exception as e:
            logger.error(f"❌ Error transcribing chunk {chunk_index+1}: {e}", exc_info=True)
            raise
    
    def _save_chunk_result(self, parent_task_id: str, chunk_index: int, chunk_data: Dict, total_chunks: int):
        """บันทึกผลลัพธ์ของ chunk ลง storage"""
        try:
            # Load parent task
            parent_task = self.json_storage.get_transcription(parent_task_id)
            if not parent_task:
                logger.error(f"Parent task {parent_task_id} not found")
                return
            
            # Initialize chunks array if not exists
            if 'chunks' not in parent_task:
                parent_task['chunks'] = [None] * total_chunks
            
            # Ensure chunks array has correct size
            while len(parent_task['chunks']) < total_chunks:
                parent_task['chunks'].append(None)
            
            # Save chunk result
            parent_task['chunks'][chunk_index] = chunk_data
            
            # Update progress
            completed_chunks = sum(1 for c in parent_task['chunks'] if c is not None)
            progress = 10 + int((completed_chunks / total_chunks) * 80)  # 10-90%
            parent_task['progress'] = progress
            parent_task['status'] = f"processing_chunk_{completed_chunks}_of_{total_chunks}"
            
            # Save to storage
            self.json_storage.save_transcription(parent_task_id, parent_task)
            
            logger.info(f"💾 Saved chunk {chunk_index+1}/{total_chunks} - Progress: {progress}% ({completed_chunks}/{total_chunks} completed)")
            
            # Check if all chunks completed
            if completed_chunks >= total_chunks:
                logger.info(f"🎉 All chunks completed for task {parent_task_id}!")
                parent_task['status'] = 'merging_results'
                parent_task['progress'] = 90
                self.json_storage.save_transcription(parent_task_id, parent_task)
                
        except Exception as e:
            logger.error(f"❌ Error saving chunk result: {e}", exc_info=True)
    
    async def _execute_audio_chunk_transcription(self, message_data: Dict[str, Any]):
        """ดำเนินการ transcribe audio chunk"""
        try:
            # Backend ใช้ JsonSerializerDefaults.Web (camelCase naming)
            # รองรับทั้ง camelCase และ PascalCase เพื่อความเข้ากันได้
            chunk_id = str(message_data.get('chunkId') or message_data.get('ChunkId', ''))
            audio_file_id = str(message_data.get('audioFileId') or message_data.get('AudioFileId', ''))
            audio_file_url = message_data.get('audioFileUrl') or message_data.get('AudioFileUrl')  # 🆕 URL จาก Backend
            meeting_id = str(message_data.get('meetingId') or message_data.get('MeetingId', ''))
            chapter_id = message_data.get('chapterId') or message_data.get('ChapterId')
            if chapter_id:
                chapter_id = str(chapter_id)
            start_time_str = message_data.get('startTime') or message_data.get('StartTime', '00:00:00')
            duration_str = message_data.get('duration') or message_data.get('Duration', '00:00:05')
            chunk_index = message_data.get('chunkIndex') or message_data.get('ChunkIndex', 0)
            
            logger.info(f"เริ่ม transcribe audio chunk {chunk_index} สำหรับ meeting {meeting_id}, audio_file_url: {audio_file_url}")
            
            # Download audio file จาก URL ที่ Backend ส่งมา (Backend จัดการ FileService)
            if not audio_file_url:
                logger.error(f"ไม่พบ AudioFileUrl ใน message สำหรับ chunk {chunk_index}")
                return
            
            audio_file_path = await self._download_audio_file_from_url(
                audio_file_url,
                chunk_id
            )
            
            # Transcribe audio chunk ด้วย Whisper
            language = 'th'  # Default ภาษาไทย
            model_size = 'base'  # Default model size
            
            transcription_result = self.transcription_service.whisper_service.transcribe_file(
                audio_file_path,
                model_size=model_size,
                language=language,
                use_thai_processor=True
            )
            
            if not transcription_result:
                logger.error(f"ไม่สามารถ transcribe audio chunk {chunk_index} ได้")
                return
            
            # สร้าง message สำหรับส่งกลับไป Backend (ใช้ camelCase เพื่อให้สอดคล้องกับ Backend)
            result_message = {
                "chunkId": chunk_id,
                "meetingId": meeting_id,
                "chapterId": chapter_id,
                "text": transcription_result.get("text", ""),
                "segments": transcription_result.get("segments", []),
                "startTime": start_time_str,
                "duration": duration_str,
                "chunkIndex": chunk_index,
                "confidence": transcription_result.get("avg_logprob"),
                "audioFileId": audio_file_id,
                "language": language,
                "createdAt": datetime.now().isoformat()
            }
            
            # Publish result กลับไป Backend
            self.channel.basic_publish(
                exchange=self.transcription_exchange,
                routing_key=self.transcription_chunk_completed_routing_key,
                body=json.dumps(result_message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent message
                    content_type='application/json'
                )
            )
            
            logger.info(f"ส่ง transcription result กลับไป Backend: {chunk_id}")
            
            # Cleanup temp audio file
            try:
                if Path(audio_file_path).exists():
                    Path(audio_file_path).unlink()
                    logger.info(f"ลบ temp audio file: {audio_file_path}")
            except Exception as e:
                logger.warning(f"ไม่สามารถลบ temp audio file: {e}")
                
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการ transcribe audio chunk: {e}", exc_info=True)
            raise
    
    async def _download_audio_file_from_url(self, audio_file_url: str, chunk_id: str) -> str:
        """ดาวน์โหลด audio file จาก URL ที่ Backend ส่งมา (Backend จัดการ FileService)"""
        download_root = Path("temp") / f"audio_chunk_{chunk_id}"
        download_root.mkdir(parents=True, exist_ok=True)
        
        # ใช้ URL ที่ Backend ส่งมา (Backend เป็นผู้จัดการ FileService)
        destination = download_root / f"{chunk_id}.wav"
        
        timeout = aiohttp.ClientTimeout(total=60)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(audio_file_url) as response:
                    if response.status != 200:
                        body = await response.text()
                        raise RuntimeError(f"ดาวน์โหลด audio file ไม่สำเร็จ (status: {response.status}): {body}")
                    
                    async with aiofiles.open(destination, 'wb') as file_obj:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            await file_obj.write(chunk)
            
            # ตั้งค่า permission
            try:
                os.chmod(destination, 0o644)
            except Exception as e:
                logger.warning(f"ไม่สามารถตั้งค่า permission: {e}")
            
            logger.info(f"ดาวน์โหลด audio file สำเร็จ: {destination}")
            return str(destination)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดาวน์โหลด audio file: {e}")
            raise
    
    async def _download_audio_file_from_fileservice(self, audio_file_id: str, chunk_id: str) -> str:
        """ดาวน์โหลด audio file จาก FileService โดยใช้ file ID"""
        download_root = Path("temp") / f"audio_chunk_{chunk_id}"
        download_root.mkdir(parents=True, exist_ok=True)
        
        # Download file จาก FileService API
        file_url = f"{self.file_service_url}/api/files/{audio_file_id}"
        destination = download_root / f"{audio_file_id}.wav"
        
        timeout = aiohttp.ClientTimeout(total=60)
        headers = {}
        
        # เพิ่ม headers สำหรับ authentication (ถ้ามี)
        if self.file_service_tenant_id:
            headers['X-Tenant-Id'] = self.file_service_tenant_id
        if self.file_service_api_key:
            headers['X-Api-Key'] = self.file_service_api_key
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(file_url, headers=headers) as response:
                    if response.status != 200:
                        body = await response.text()
                        raise RuntimeError(f"ดาวน์โหลด audio file ไม่สำเร็จ (status: {response.status}): {body}")
                    
                    async with aiofiles.open(destination, 'wb') as file_obj:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            await file_obj.write(chunk)
            
            # ตั้งค่า permission
            try:
                os.chmod(destination, 0o644)
            except Exception as e:
                logger.warning(f"ไม่สามารถตั้งค่า permission: {e}")
            
            logger.info(f"ดาวน์โหลด audio file สำเร็จ: {destination}")
            return str(destination)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดาวน์โหลด audio file: {e}")
            raise
    
    async def _execute_transcription_task(self, task_data: Dict[str, Any]):
        """ดำเนินการ transcription"""
        task_id = task_data.get('task_id')
        try:
            file_path = task_data['file_path']
            language = task_data.get('language', 'th')
            model_size = task_data.get('model_size', 'base')
            chunk_duration = task_data.get('chunk_duration', 30)
            use_chunking = task_data.get('use_chunking', False)  # Default: false
            
            logger.info(f"📂 เริ่ม transcription: {file_path}")
            logger.info(f"   Model: {model_size}, Language: {language}, Chunk Duration: {chunk_duration}s, Use Chunking: {use_chunking}")
            
            # สร้าง task object สำหรับ transcription service
            from app.models.transcription import TranscriptionResponse
            from datetime import datetime
            
            task = TranscriptionResponse(
                task_id=task_data['task_id'],
                status="processing",
                file_path=file_path,
                file_url=task_data.get('file_url'),
                file_name=task_data.get('file_name'),
                language=language,
                created_at=datetime.now()
            )
            task.job_id = task_data.get('job_id')
            task.user_id = task_data.get('user_id')
            task.callback_url = task_data.get('callback_url')
            
            # เพิ่ม task เข้าไปใน transcription service
            self.transcription_service.tasks[task_data['task_id']] = task
            
            logger.info(f"🔄 เรียกใช้ transcription service...")
            logger.info(f"   Task ID: {task_data['task_id']}")
            logger.info(f"   File path: {file_path}")
            logger.info(f"   Model: {model_size}, Language: {language}, Chunk Duration: {chunk_duration}s, Use Chunking: {use_chunking}")
            
            # เรียกใช้ transcription service
            try:
                logger.info(f"📞 Calling transcription_service._process_transcription...")
                await self.transcription_service._process_transcription(
                    task_data['task_id'],
                    file_path,
                    language,
                    model_size,
                    chunk_duration,
                    use_chunking=use_chunking,
                    file_url=task_data.get('file_url'),
                    file_name=task_data.get('file_name')
                )
                logger.info(f"✅ transcription_service._process_transcription completed")
            except Exception as e:
                logger.error(f"❌ Error in transcription_service._process_transcription: {e}", exc_info=True)
                raise
            
            # ดึงข้อมูล transcription ที่บันทึกไว้แล้วจาก transcription_service
            # (transcription_service บันทึก full_text และ chunks ไว้แล้ว)
            # รอให้ transcription_service บันทึกข้อมูลเสร็จก่อน (retry mechanism)
            import time
            max_retries = 10
            retry_delay = 0.5
            existing_transcription = None
            
            for attempt in range(max_retries):
                time.sleep(retry_delay)
                existing_transcription = self.json_storage.get_transcription(task_data['task_id'])
                
                if existing_transcription:
                    full_text = existing_transcription.get('full_text', '') or ''
                    chunks = existing_transcription.get('chunks', []) or []
                    
                    # ตรวจสอบว่ามีข้อมูลจริงหรือไม่
                    if full_text or chunks:
                        logger.info(f"📋 Found transcription data (attempt {attempt + 1}/{max_retries}): full_text length={len(full_text)}, chunks count={len(chunks)}")
                        break
                    else:
                        logger.warning(f"⚠️  Transcription data found but empty (attempt {attempt + 1}/{max_retries}): full_text length={len(full_text)}, chunks count={len(chunks)}")
                        if attempt < max_retries - 1:
                            continue
                else:
                    logger.warning(f"⚠️  No transcription data found in storage (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        continue
            
            # อัปเดต task - ใช้ข้อมูลจาก existing_transcription ถ้ามี
            if existing_transcription:
                full_text = existing_transcription.get('full_text', '') or ''
                chunks = existing_transcription.get('chunks', []) or []
                
                # ถ้ายังไม่มีข้อมูล ให้ลองดึงจาก task object ใน transcription_service
                if not full_text and not chunks:
                    logger.warning(f"⚠️  Storage data is empty, trying to get from transcription_service task object...")
                    task_in_service = self.transcription_service.tasks.get(task_data['task_id'])
                    if task_in_service:
                        logger.info(f"📋 Found task in transcription_service: full_text length={len(task_in_service.full_text) if task_in_service.full_text else 0}, chunks count={len(task_in_service.chunks) if task_in_service.chunks else 0}")
                        full_text = task_in_service.full_text if task_in_service.full_text else ''
                        chunks = [chunk.dict() for chunk in task_in_service.chunks] if task_in_service.chunks else []
                
                task_data['status'] = 'completed'
                task_data['completed_at'] = datetime.now().isoformat()
                task_data['progress'] = 100
                task_data['full_text'] = full_text
                task_data['chunks'] = chunks
                task_data['total_duration'] = existing_transcription.get('total_duration', task_data.get('total_duration'))
            else:
                # ถ้าไม่มี existing_transcription ให้ลองดึงจาก task object ใน transcription_service
                logger.warning(f"⚠️  No existing transcription data found in storage for {task_id}")
                task_in_service = self.transcription_service.tasks.get(task_data['task_id'])
                if task_in_service:
                    logger.info(f"📋 Found task in transcription_service: full_text length={len(task_in_service.full_text) if task_in_service.full_text else 0}, chunks count={len(task_in_service.chunks) if task_in_service.chunks else 0}")
                    task_data['status'] = 'completed'
                    task_data['completed_at'] = datetime.now().isoformat()
                    task_data['progress'] = 100
                    task_data['full_text'] = task_in_service.full_text if task_in_service.full_text else ''
                    task_data['chunks'] = [chunk.dict() for chunk in task_in_service.chunks] if task_in_service.chunks else []
                    task_data['total_duration'] = task_in_service.total_duration
                else:
                    logger.error(f"❌ No transcription data found in storage or service for {task_id}")
                    # ถ้าไม่มีข้อมูลเลย ให้บันทึกแค่ status
                    task_data['status'] = 'completed'
                    task_data['completed_at'] = datetime.now().isoformat()
                    task_data['progress'] = 100
            
            # บันทึกลง JSON storage (จะ merge กับข้อมูลเดิมอัตโนมัติ)
            logger.info(f"💾 Saving transcription data: full_text length={len(task_data.get('full_text', ''))}, chunks count={len(task_data.get('chunks', []))}")
            self.json_storage.save_transcription(task_data['task_id'], task_data)
            
            logger.info(f"✅ Transcription completed successfully: {task_id}")
            
        except Exception as e:
            logger.error(f"❌ เกิดข้อผิดพลาดในการ transcription {task_id}: {e}", exc_info=True)
            task_data['status'] = 'failed'
            task_data['error_message'] = str(e)
            task_data['completed_at'] = datetime.now().isoformat()
            task_data['progress'] = 0
            self.json_storage.save_transcription(task_data['task_id'], task_data)
    
    def run(self):
        """เริ่มต้น worker"""
        logger.info("เริ่มต้น Video Worker...")
        logger.info(f"RabbitMQ Configuration: {self.rabbitmq_host}:{self.rabbitmq_port}")
        
        # เชื่อมต่อ RabbitMQ (with retry)
        if not self.connect_rabbitmq(max_retries=10, retry_delay=5):
            logger.error("ไม่สามารถเชื่อมต่อ RabbitMQ ได้ - Worker will exit")
            logger.warning("💡 Video Worker will not process tasks without RabbitMQ connection")
            logger.warning("💡 Services will continue running, but transcription tasks will not be processed")
            return
        
        # ตั้งค่า consumers
        self.setup_consumers()
        
        logger.info("Video Worker พร้อมรับงาน...")
        
        try:
            # เริ่มรับ messages
            logger.info("🔄 เริ่มรับ messages จาก RabbitMQ...")
            message_count = 0
            while self.running:
                try:
                    # Process data events (this will trigger callbacks if messages arrive)
                    self.connection.process_data_events(time_limit=1)
                    
                    # Log every 30 seconds to show we're alive
                    if message_count == 0:
                        import time
                        current_time = time.time()
                        if not hasattr(self, '_last_heartbeat') or (current_time - self._last_heartbeat) > 30:
                            logger.debug("💓 Video Worker is alive and waiting for messages...")
                            self._last_heartbeat = current_time
                except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed, 
                        pika.exceptions.AMQPConnectionError, ConnectionResetError,
                        AttributeError, IndexError) as e:
                    logger.warning(f"RabbitMQ connection lost: {e}")
                    logger.info("Attempting to reconnect to RabbitMQ...")
                    
                    # Reset connection state
                    try:
                        if self.channel and not self.channel.is_closed:
                            self.channel.close()
                    except:
                        pass
                    self.channel = None
                    
                    try:
                        if self.connection and not self.connection.is_closed:
                            self.connection.close()
                    except:
                        pass
                    self.connection = None
                    
                    # Try to reconnect
                    if self.connect_rabbitmq(max_retries=5, retry_delay=5):
                        logger.info("✅ Reconnected to RabbitMQ successfully")
                        # Re-setup consumers after reconnection
                        self.setup_consumers()
                        logger.info("✅ Consumers re-registered")
                    else:
                        logger.error("❌ Failed to reconnect to RabbitMQ")
                        logger.warning("💡 Video Worker will retry connection in 30 seconds...")
                        import time
                        time.sleep(30)
                        # Try to reconnect again
                        if not self.connect_rabbitmq(max_retries=10, retry_delay=5):
                            logger.error("❌ Cannot reconnect to RabbitMQ after multiple attempts")
                            logger.warning("💡 Video Worker will exit. Please check RabbitMQ connection.")
                            break
                        else:
                            self.setup_consumers()
                
        except KeyboardInterrupt:
            logger.info("ได้รับ interrupt signal")
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดใน worker: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            try:
                if self.connection:
                    try:
                        if not self.connection.is_closed:
                            self.connection.close()
                    except (AttributeError, pika.exceptions.ConnectionClosed):
                        pass  # Already closed
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            try:
                if self.channel:
                    try:
                        if not self.channel.is_closed:
                            self.channel.close()
                    except (AttributeError, pika.exceptions.ChannelClosed):
                        pass  # Already closed
            except Exception as e:
                logger.warning(f"Error closing channel: {e}")
            try:
                # Shutdown thread pool executor
                if hasattr(self, 'executor') and self.executor:
                    logger.info("Shutting down thread pool executor...")
                    # ⚠️ Python 3.10 ไม่รองรับ timeout parameter ใน shutdown()
                    self.executor.shutdown(wait=True)
                    logger.info("Thread pool executor shut down")
            except Exception as e:
                logger.warning(f"Error shutting down executor: {e}")
            logger.info("Video Worker ปิดตัวลง")

def main():
    """Main function สำหรับรัน worker"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    worker = VideoWorker()
    worker.run()

if __name__ == "__main__":
    main() 