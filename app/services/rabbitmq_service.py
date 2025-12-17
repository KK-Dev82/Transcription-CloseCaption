"""
RabbitMQ Service สำหรับจัดการ message queue
"""

import json
import logging
import os
from typing import Dict, Any, Optional
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError, ChannelClosedByBroker, UnroutableError
from fastapi import HTTPException
import uuid
from datetime import datetime
import time
import threading
import signal

logger = logging.getLogger(__name__)

class RabbitMQService:
    def __init__(self):
        """เริ่มต้น RabbitMQ Service"""
        self.connection = None
        self.channel = None
        self.host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.username = os.getenv("RABBITMQ_USER", "admin")
        self.password = os.getenv("RABBITMQ_PASSWORD", "admin123")
        self.virtual_host = os.getenv("RABBITMQ_VHOST", "/")
        
        # Publisher confirms tracking
        self.publish_confirms = {}  # Track pending publishes: {delivery_tag: task_id}
        self.publish_lock = threading.Lock()  # Lock for thread-safe access
        
        # ใช้ Storage Factory เพื่อเลือก storage type (SQLite หรือ JSON)
        from ..utils.storage_factory import get_storage
        self.json_storage = get_storage()  # จะ return SQLiteStorage หรือ JSONStorage ตาม STORAGE_TYPE
        
        # Queue names
        self.trim_queue = 'video_trim_queue'
        self.merge_queue = 'video_merge_queue'
        self.convert_queue = 'video_convert_queue'
        self.transcription_queue = 'transcription_queue'
        self.transcription_chunk_queue = 'transcription_chunk_queue'
        self.resize_queue = 'video_resize_queue'
        
        # 3-Queue Architecture (Final Design)
        self.transcription_request_queue = 'transcription_request_queue'
        self.audio_extraction_queue = 'audio_extraction_queue'
        # transcription_queue ใช้ queue เดิม (backward compatible)
        
        # Close Caption Queues (แยกจาก transcription เพื่อลัดคิว)
        self.close_caption_request_queue = 'close_caption_request_queue'
        self.close_caption_extraction_queue = 'close_caption_extraction_queue'
        self.close_caption_queue = 'close_caption_queue'
    
    def _connect(self):
        """เชื่อมต่อกับ RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                virtual_host=self.virtual_host,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Enable publisher confirms เพื่อยืนยันว่า message ถูก publish สำเร็จ
            self.channel.confirm_delivery()
            logger.info("✅ Publisher confirms enabled - จะยืนยันทุก publish")
            
            # สร้าง queues เก่า (backward compatible)
            self.channel.queue_declare(queue=self.trim_queue, durable=True)
            self.channel.queue_declare(queue=self.merge_queue, durable=True)
            self.channel.queue_declare(queue=self.convert_queue, durable=True)
            self.channel.queue_declare(queue=self.resize_queue, durable=True)
            
            # Transcription Queue (Legacy - ยังใช้อยู่)
            # ตั้ง max-length เพื่อรองรับ 25 concurrency + buffer
            max_transcribe = int(os.getenv('MAX_QUEUE_TRANSCRIBE', '30'))
            try:
                # พยายามสร้าง queue ใหม่ด้วย max-length
                transcription_args = self._get_queue_arguments(
                    self.transcription_queue,
                    max_length=max_transcribe,
                    enable_dlx=True,
                    enable_quorum=False,  # Legacy queue ไม่ใช้ quorum
                    enable_priority=False
                )
                self.channel.queue_declare(
                    queue=self.transcription_queue,
                    durable=True,
                    arguments=transcription_args if transcription_args else None
                )
                logger.info(f"✅ Created/Updated {self.transcription_queue} (max: {max_transcribe})")
            except Exception as e:
                # ถ้า queue มีอยู่แล้วและ arguments ไม่ตรงกัน จะใช้ queue เดิม
                logger.warning(f"⚠️ Transcription queue exists with different arguments, using existing queue: {e}")
                self.channel.queue_declare(queue=self.transcription_queue, durable=True)
            
            self.channel.queue_declare(queue=self.transcription_chunk_queue, durable=True)
            
            # ============================================================
            # 3-Queue Architecture (Final Design)
            # ============================================================
            
            # 1. Transcription Request Queue (max 51: 50 video + 1 close caption)
            max_request = int(os.getenv('MAX_QUEUE_REQUEST', '51'))
            request_args = self._get_queue_arguments(
                self.transcription_request_queue,
                max_length=max_request,
                enable_dlx=True,
                enable_quorum=True,
                enable_priority=True  # Enable priority for close caption
            )
            self.channel.queue_declare(
                queue=self.transcription_request_queue,
                durable=True,
                arguments=request_args if request_args else None
            )
            self._setup_dlx_for_queue(self.transcription_request_queue)
            logger.info(f"✅ Created {self.transcription_request_queue} (max: {max_request}, quorum: {request_args.get('x-queue-type', 'classic')})")
            
            # 2. Audio Extraction Queue (max 80)
            max_extraction = int(os.getenv('MAX_QUEUE_EXTRACTION', '80'))
            extraction_args = self._get_queue_arguments(
                self.audio_extraction_queue,
                max_length=max_extraction,
                enable_dlx=True,
                enable_quorum=True,
                enable_priority=True  # Enable priority for close caption
            )
            self.channel.queue_declare(
                queue=self.audio_extraction_queue,
                durable=True,
                arguments=extraction_args if extraction_args else None
            )
            self._setup_dlx_for_queue(self.audio_extraction_queue)
            logger.info(f"✅ Created {self.audio_extraction_queue} (max: {max_extraction}, quorum: {extraction_args.get('x-queue-type', 'classic')})")
            
            # ============================================================
            # Close Caption Queues (แยกจาก transcription เพื่อลัดคิว)
            # ============================================================
            
            # 1. Close Caption Request Queue (max 10 - สำหรับ close caption)
            max_close_caption_request = int(os.getenv('MAX_QUEUE_CLOSE_CAPTION_REQUEST', '10'))
            close_caption_request_args = self._get_queue_arguments(
                self.close_caption_request_queue,
                max_length=max_close_caption_request,
                enable_dlx=True,
                enable_quorum=True,
                enable_priority=False  # ไม่ต้องใช้ priority เพราะแยก queue แล้ว
            )
            self.channel.queue_declare(
                queue=self.close_caption_request_queue,
                durable=True,
                arguments=close_caption_request_args if close_caption_request_args else None
            )
            self._setup_dlx_for_queue(self.close_caption_request_queue)
            logger.info(f"✅ Created {self.close_caption_request_queue} (max: {max_close_caption_request}, quorum: {close_caption_request_args.get('x-queue-type', 'classic')})")
            
            # 2. Close Caption Extraction Queue (max 20 - สำหรับ close caption)
            max_close_caption_extraction = int(os.getenv('MAX_QUEUE_CLOSE_CAPTION_EXTRACTION', '20'))
            close_caption_extraction_args = self._get_queue_arguments(
                self.close_caption_extraction_queue,
                max_length=max_close_caption_extraction,
                enable_dlx=True,
                enable_quorum=True,
                enable_priority=False  # ไม่ต้องใช้ priority เพราะแยก queue แล้ว
            )
            self.channel.queue_declare(
                queue=self.close_caption_extraction_queue,
                durable=True,
                arguments=close_caption_extraction_args if close_caption_extraction_args else None
            )
            self._setup_dlx_for_queue(self.close_caption_extraction_queue)
            logger.info(f"✅ Created {self.close_caption_extraction_queue} (max: {max_close_caption_extraction}, quorum: {close_caption_extraction_args.get('x-queue-type', 'classic')})")
            
            # 3. Close Caption Queue (max 10 - สำหรับ close caption transcription)
            max_close_caption = int(os.getenv('MAX_QUEUE_CLOSE_CAPTION', '10'))
            close_caption_args = self._get_queue_arguments(
                self.close_caption_queue,
                max_length=max_close_caption,
                enable_dlx=True,
                enable_quorum=True,
                enable_priority=False  # ไม่ต้องใช้ priority เพราะแยก queue แล้ว
            )
            self.channel.queue_declare(
                queue=self.close_caption_queue,
                durable=True,
                arguments=close_caption_args if close_caption_args else None
            )
            self._setup_dlx_for_queue(self.close_caption_queue)
            logger.info(f"✅ Created {self.close_caption_queue} (max: {max_close_caption}, quorum: {close_caption_args.get('x-queue-type', 'classic')})")
            
            logger.info("เชื่อมต่อ RabbitMQ สำเร็จ")
            logger.info("📋 Queue Architecture: 3-Queue (request → extraction → transcription)")
            logger.info("📋 Close Caption Queues: 3-Queue (close_caption_request → close_caption_extraction → close_caption)")
            
        except AMQPConnectionError as e:
            logger.error(f"ไม่สามารถเชื่อมต่อ RabbitMQ: {e}")
            raise
    
    def _ensure_connection(self):
        """ตรวจสอบการเชื่อมต่อและเชื่อมต่อใหม่หากจำเป็น"""
        # ตรวจสอบ connection state
        connection_ok = False
        try:
            if self.connection and not self.connection.is_closed:
                # ตรวจสอบ channel state ด้วย
                if self.channel and not self.channel.is_closed:
                    # ลอง process data events เพื่อตรวจสอบว่า connection ยังทำงานอยู่
                    try:
                        self.connection.process_data_events(time_limit=0.001)
                        connection_ok = True
                    except Exception:
                        connection_ok = False
        except Exception as e:
            logger.debug(f"Connection check failed: {e}")
            connection_ok = False
        
        if not connection_ok:
            logger.info(f"🔌 เชื่อมต่อ RabbitMQ ใหม่...")
            logger.info(f"   Host: {self.host}:{self.port}")
            logger.info(f"   User: {self.username}")
            self._reset_connection()  # Reset ก่อน connect ใหม่
            self._connect()
        else:
            logger.debug(f"✅ RabbitMQ connection is active: {self.host}:{self.port}")
    
    def _reset_connection(self):
        """รีเซ็ตการเชื่อมต่อ RabbitMQ"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
        
        self.connection = None
        self.channel = None
        logger.info("รีเซ็ตการเชื่อมต่อ RabbitMQ")
    
    def _get_queue_arguments(
        self,
        queue_name: str,
        max_length: int = 0,
        enable_dlx: bool = True,
        enable_quorum: bool = True,
        enable_priority: bool = True
    ) -> Dict[str, Any]:
        """
        สร้าง queue arguments สำหรับ quorum queue ตาม Final Architecture Design
        
        Args:
            queue_name: ชื่อ queue
            max_length: จำนวน messages สูงสุด (0 = no limit)
            enable_dlx: เปิดใช้งาน Dead Letter Exchange
            enable_quorum: ใช้ quorum queue type
            enable_priority: เปิดใช้งาน Priority Queue (0-10)
        
        Returns:
            Dictionary ของ queue arguments
        """
        arguments = {}
        
        # Quorum Queue Type
        use_quorum = os.getenv('USE_QUORUM_QUEUES', 'true').lower() == 'true'
        if enable_quorum and use_quorum:
            arguments['x-queue-type'] = 'quorum'
            logger.debug(f"✅ Quorum queue enabled for {queue_name}")
        
        # Priority Queue (รองรับ priority 0-10)
        # CloseCaption (realtime_chunks) → priority 10 (สูงสุด)
        # Normal transcription → priority 5 (ปกติ)
        # ⚠️ หมายเหตุ: Quorum queues ไม่รองรับ x-max-priority
        # ต้องใช้ classic queue ถ้าต้องการ priority queue
        if enable_priority and not (enable_quorum and use_quorum):
            max_priority = int(os.getenv('RABBITMQ_MAX_PRIORITY', '10'))
            arguments['x-max-priority'] = max_priority
            logger.debug(f"✅ Priority queue enabled for {queue_name}: max_priority={max_priority}")
        elif enable_priority and enable_quorum and use_quorum:
            logger.warning(f"⚠️  Priority queue disabled for {queue_name} (quorum queues don't support x-max-priority)")
        
        # Queue Max Length & Overflow
        if max_length > 0:
            arguments['x-max-length'] = max_length
            arguments['x-overflow'] = 'reject-publish'
            logger.debug(f"✅ Max length set: {queue_name} = {max_length} messages")
        
        # Dead Letter Exchange (DLX)
        enable_dlx_flag = os.getenv('ENABLE_DLX', 'true').lower() == 'true'
        if enable_dlx and enable_dlx_flag:
            dlx_exchange = f'{queue_name}.dlx'
            dlx_queue = f'{queue_name}.dlq'
            arguments['x-dead-letter-exchange'] = dlx_exchange
            arguments['x-dead-letter-routing-key'] = dlx_queue
            logger.debug(f"✅ DLX enabled for {queue_name}: {dlx_exchange} -> {dlx_queue}")
        
        return arguments
    
    def _setup_dlx_for_queue(self, queue_name: str):
        """
        สร้าง Dead Letter Exchange และ Queue สำหรับ queue ที่ระบุ
        
        Args:
            queue_name: ชื่อ queue หลัก
        """
        try:
            enable_dlx = os.getenv('ENABLE_DLX', 'true').lower() == 'true'
            if not enable_dlx:
                logger.debug(f"DLX disabled, skipping DLX setup for {queue_name}")
                return
            
            use_quorum = os.getenv('USE_QUORUM_QUEUES', 'true').lower() == 'true'
            dlx_exchange = f'{queue_name}.dlx'
            dlx_queue = f'{queue_name}.dlq'
            
            # สร้าง DLX Exchange
            self.channel.exchange_declare(
                exchange=dlx_exchange,
                exchange_type='direct',
                durable=True
            )
            
            # สร้าง DLQ Queue
            dlq_arguments = {}
            if use_quorum:
                dlq_arguments['x-queue-type'] = 'quorum'
            
            self.channel.queue_declare(
                queue=dlx_queue,
                durable=True,
                arguments=dlq_arguments if dlq_arguments else None
            )
            
            # Bind DLQ to DLX
            self.channel.queue_bind(
                exchange=dlx_exchange,
                queue=dlx_queue,
                routing_key=dlx_queue
            )
            
            logger.info(f"✅ DLX setup complete: {queue_name} -> {dlx_exchange} -> {dlx_queue}")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to setup DLX for {queue_name}: {e}")
            # Continue anyway - DLX is optional
    
    def send_trim_task(self, input_file: str, start_time: float, end_time: float, 
                      output_format: str = "mp4", quality: str = "medium", 
                      segment_number: int = 1) -> str:
        """ส่งงานตัดวิดีโอไปยัง queue"""
        try:
            # เชื่อมต่อ RabbitMQ ก่อนใช้งาน
            self._ensure_connection()
            
            task_id = str(uuid.uuid4())
            task_data = {
                "task_id": task_id,
                "task_type": "trim",
                "input_file": input_file,
                "start_time": start_time,
                "end_time": end_time,
                "output_format": output_format,
                "quality": quality,
                "segment_number": segment_number,
                "status": "pending",
                "created_at": time.time()
            }
            
            # บันทึก task ลง storage
            self.json_storage.save_video_task(task_id, task_data)
            
            # ส่งไปยัง queue
            self.channel.basic_publish(
                exchange='',
                routing_key='video_trim_queue',
                body=json.dumps(task_data)
            )
            
            logger.info(f"ส่งงานตัดวิดีโอไปยัง queue: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่งงานตัดวิดีโอ: {e}")
            raise
    
    def send_transcription_task(
        self,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        language: str = "th",
        model_size: str = "base",
        chunk_duration: int = 30,
        use_chunking: bool = False,
        display_mode: str = "full_text",
        callback_url: Optional[str] = None,
        job_id: Optional[int] = None,
        user_id: Optional[str] = None
    ) -> str:
        """ส่งงาน transcription ไปยัง queue พร้อม retry mechanism"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        task_id = None  # Initialize outside try block
        for attempt in range(max_retries):
            try:
                # เชื่อมต่อ RabbitMQ ก่อนใช้งาน
                logger.info(f"🔌 Ensuring RabbitMQ connection (attempt {attempt + 1}/{max_retries})...")
                logger.info(f"   RabbitMQ Host: {self.host}:{self.port}")
                logger.info(f"   RabbitMQ User: {self.username}")
                self._ensure_connection()
                logger.info(f"✅ RabbitMQ connection ensured")
                
                if task_id is None:
                    task_id = str(uuid.uuid4())
                task_data = {
                    "task_id": task_id,
                    "task_type": "transcription",
                    "file_path": file_path,
                    "file_url": file_url,
                    "file_name": file_name,
                    "language": language,
                    "model_size": model_size,
                    "chunk_duration": chunk_duration,
                    "use_chunking": use_chunking,
                    "display_mode": display_mode,
                    "status": "pending",
                    "created_at": time.time(),
                    "callback_url": callback_url,
                    "job_id": job_id,
                    "user_id": user_id
                }
                
                # บันทึก task ลง storage ก่อน
                self.json_storage.save_transcription(task_id, task_data)
                
                # ส่งไปยัง queue
                logger.info(f"📤 Publishing message to queue: {self.transcription_queue}")
                logger.info(f"   Task ID: {task_id}")
                logger.info(f"   Message size: {len(json.dumps(task_data))} bytes")
                
                self.channel.basic_publish(
                    exchange='',
                    routing_key=self.transcription_queue,
                    body=json.dumps(task_data),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # ทำให้ message persistent
                    )
                )
                
                logger.info(f"✅ ส่งงาน transcription ไปยัง queue สำเร็จ: {task_id}")
                logger.info(f"   Queue: {self.transcription_queue}")
                logger.info(f"   Exchange: (default)")
                logger.info(f"   Routing Key: {self.transcription_queue}")
                return task_id
                
            except Exception as e:
                logger.error(f"❌ Attempt {attempt + 1}/{max_retries} failed: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                if attempt < max_retries - 1:
                    # Reset connection และ retry
                    logger.warning(f"🔄 Resetting connection and retrying in {retry_delay * (attempt + 1)} seconds...")
                    self._reset_connection()
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    # ถ้า retry หมดแล้ว ให้บันทึก task เป็น failed
                    logger.error(f"❌ เกิดข้อผิดพลาดในการส่งงาน transcription หลังจาก retry {max_retries} ครั้ง: {e}")
                    if task_id is not None:
                        # อัปเดต status เป็น failed
                        try:
                            task_data['status'] = 'failed'
                            task_data['error_message'] = str(e)
                            self.json_storage.save_transcription(task_id, task_data)
                        except Exception as save_error:
                            logger.error(f"ไม่สามารถบันทึก failed task: {save_error}")
                    raise
    
    def send_transcription_request_task(
        self,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        language: str = "th",
        model_size: str = "base",
        chunk_duration: int = 30,
        use_chunking: bool = False,
        display_mode: str = "full_text",
        callback_url: Optional[str] = None,
        job_id: Optional[int] = None,
        user_id: Optional[str] = None,
        initial_prompt: Optional[str] = None
    ) -> str:
        """
        ส่งงาน transcription ไปยัง transcription_request_queue (3-Queue Architecture)
        
        ใช้ queue นี้แทน send_transcription_task() สำหรับ Final Architecture
        """
        max_retries = 3
        retry_delay = 1
        
        task_id = None
        for attempt in range(max_retries):
            try:
                self._ensure_connection()
                
                if task_id is None:
                    task_id = str(uuid.uuid4())
                
                task_data = {
                    "task_id": task_id,
                    "task_type": "transcription_request",
                    "file_path": file_path,
                    "file_url": file_url,
                    "file_name": file_name,
                    "language": language,
                    "model_size": model_size,
                    "chunk_duration": chunk_duration,
                    "use_chunking": use_chunking,
                    "display_mode": display_mode,
                    "status": "pending",
                    "created_at": time.time(),
                    "callback_url": callback_url,
                    "job_id": job_id,
                    "user_id": user_id,
                    "initial_prompt": initial_prompt  # เพิ่ม initial_prompt
                }
                
                # บันทึก task ลง storage
                self.json_storage.save_transcription(task_id, task_data)
                
                # ตรวจสอบ connection state ก่อน publish
                self._ensure_connection()
                if not self.connection or self.connection.is_closed:
                    raise Exception("RabbitMQ connection is closed")
                if not self.channel or self.channel.is_closed:
                    raise Exception("RabbitMQ channel is closed")
                
                # ตรวจสอบ queue status ก่อน publish
                try:
                    queue_declare_result = self.channel.queue_declare(
                        queue=self.transcription_request_queue,
                        durable=True,
                        passive=True  # Only check if queue exists, don't create
                    )
                    current_queue_size = queue_declare_result.method.message_count
                    MAX_QUEUE_REQUEST = int(os.getenv('MAX_QUEUE_REQUEST', '51'))
                    available_slots = MAX_QUEUE_REQUEST - current_queue_size
                    logger.info(f"📊 Queue status before publish: current={current_queue_size}/{MAX_QUEUE_REQUEST}, available={available_slots}")
                    if available_slots <= 0:
                        logger.warning(f"⚠️  Queue is full! current={current_queue_size}, max={MAX_QUEUE_REQUEST}")
                except Exception as queue_check_error:
                    logger.warning(f"⚠️  Could not check queue status: {queue_check_error}")
                
                # ส่งไปยัง transcription_request_queue
                logger.info(f"📤 Publishing to {self.transcription_request_queue}: {task_id}")
                logger.debug(f"   Connection state: open={not self.connection.is_closed}, channel={not self.channel.is_closed if self.channel else 'None'}")
                
                # กำหนด priority ตาม display_mode
                # CloseCaption (realtime_chunks) → priority 10 (สูงสุด)
                # Normal transcription → priority 5 (ปกติ)
                priority = 10 if display_mode == "realtime_chunks" else 5
                
                try:
                    # Note: With x-overflow=reject-publish, RabbitMQ will reject publish when queue is full
                    # This will raise ChannelClosedByBroker exception that we catch below
                    # Add timeout for publish operation (1-2 seconds) to prevent API hang
                    PUBLISH_TIMEOUT = int(os.getenv('RABBITMQ_PUBLISH_TIMEOUT', '2'))  # Default 2 seconds
                    
                    # Use threading to implement timeout for synchronous publish
                    publish_success = [False]
                    publish_error = [None]
                    publish_confirmed = [False]
                    
                    def publish_with_timeout():
                        try:
                            # Publisher confirms enabled - จะ raise exception ถ้า publish ไม่สำเร็จ
                            result = self.channel.basic_publish(
                                exchange='',
                                routing_key=self.transcription_request_queue,
                                body=json.dumps(task_data),
                                properties=pika.BasicProperties(
                                    delivery_mode=2,  # Persistent
                                    content_type='application/json',
                                    priority=priority  # Priority: 10 for CloseCaption, 5 for normal
                                ),
                                mandatory=True  # Ensure message is routed to a queue
                            )
                            # With confirm_delivery(), basic_publish returns True if confirmed, False if nacked
                            # If it raises exception, it means publish failed
                            publish_success[0] = True
                            publish_confirmed[0] = True
                            logger.debug(f"✅ Publisher confirm received for task {task_id}")
                        except Exception as e:
                            publish_error[0] = e
                            logger.error(f"❌ Publish error for task {task_id}: {e}")
                    
                    # Run publish in a thread with timeout
                    publish_thread = threading.Thread(target=publish_with_timeout)
                    publish_thread.daemon = True
                    publish_thread.start()
                    publish_thread.join(timeout=PUBLISH_TIMEOUT)
                    
                    if publish_thread.is_alive():
                        # Timeout occurred
                        logger.error(f"⏱️  Publish timeout after {PUBLISH_TIMEOUT}s for task {task_id}")
                        raise TimeoutError(f"RabbitMQ publish timeout after {PUBLISH_TIMEOUT} seconds")
                    
                    if publish_error[0]:
                        raise publish_error[0]
                    
                    if not publish_success[0]:
                        raise Exception("Publish failed without error")
                    
                    if not publish_confirmed[0]:
                        logger.warning(f"⚠️  Publish may not be confirmed for task {task_id}")
                    
                    logger.info(f"📤 Published with priority={priority} (display_mode={display_mode})")
                    logger.info(f"✅ Confirmed publish to {self.transcription_request_queue}: {task_id}")
                    return task_id
                except TimeoutError as timeout_error:
                    # Publish timeout - RabbitMQ may be slow or unresponsive
                    logger.error(f"⏱️  Publish timeout for task {task_id}: {timeout_error}")
                    MAX_QUEUE_REQUEST = int(os.getenv('MAX_QUEUE_REQUEST', '51'))
                    RETRY_AFTER_SECONDS = int(os.getenv('RETRY_AFTER_SECONDS', '30'))
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "error": "Service temporarily unavailable",
                            "message": f"RabbitMQ publish timeout. Please try again later.",
                            "queue_status": {
                                "current": "unknown",
                                "max": MAX_QUEUE_REQUEST,
                                "available": "unknown"
                            },
                            "retry_after_seconds": RETRY_AFTER_SECONDS,
                            "suggestion": "RabbitMQ may be slow or unresponsive. Please wait and retry, or check queue status at /api/queue/status"
                        },
                        headers={"Retry-After": str(RETRY_AFTER_SECONDS)}
                    ) from timeout_error
                except (pika.exceptions.ChannelClosedByBroker, pika.exceptions.AMQPChannelError) as publish_error:
                    # RabbitMQ closed channel - likely queue is full (max-length reached with reject-publish)
                    error_str = str(publish_error).lower()
                    logger.warning(f"⚠️ Queue is full (RabbitMQ rejected publish): {publish_error}")
                    MAX_QUEUE_REQUEST = int(os.getenv('MAX_QUEUE_REQUEST', '51'))
                    RETRY_AFTER_SECONDS = int(os.getenv('RETRY_AFTER_SECONDS', '30'))
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "error": "Service temporarily unavailable",
                            "message": f"Request queue is full ({MAX_QUEUE_REQUEST} tasks). Please try again later.",
                            "queue_status": {
                                "current": MAX_QUEUE_REQUEST,
                                "max": MAX_QUEUE_REQUEST,
                                "available": 0
                            },
                            "retry_after_seconds": RETRY_AFTER_SECONDS,
                            "suggestion": "Queue is full. Please wait and retry, or check queue status at /api/queue/status"
                        },
                        headers={"Retry-After": str(RETRY_AFTER_SECONDS)}
                    ) from publish_error
                except Exception as publish_error:
                    error_str = str(publish_error).lower()
                    # ตรวจสอบว่าเป็น queue full error หรือไม่
                    if 'resource_locked' in error_str or 'precondition_failed' in error_str or 'queue' in error_str:
                        logger.warning(f"⚠️ Queue may be full or locked: {publish_error}")
                        MAX_QUEUE_REQUEST = int(os.getenv('MAX_QUEUE_REQUEST', '51'))
                        RETRY_AFTER_SECONDS = int(os.getenv('RETRY_AFTER_SECONDS', '30'))
                        raise HTTPException(
                            status_code=503,
                            detail={
                                "error": "Service temporarily unavailable",
                                "message": f"Queue is full. Please try again later.",
                                "retry_after_seconds": RETRY_AFTER_SECONDS
                            },
                            headers={"Retry-After": str(RETRY_AFTER_SECONDS)}
                        ) from publish_error
                    raise
                
            except HTTPException:
                # Re-raise HTTPException (503)
                raise
            except Exception as e:
                logger.error(f"❌ Attempt {attempt + 1}/{max_retries} failed: {e}")
                
                if attempt < max_retries - 1:
                    self._reset_connection()
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    if task_id:
                        try:
                            task_data['status'] = 'failed'
                            task_data['error_message'] = str(e)
                            self.json_storage.save_transcription(task_id, task_data)
                        except Exception:
                            pass
                    raise
    
    def send_transcription_request_task_thread_safe(
        self,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        language: str = "th",
        model_size: str = "base",
        chunk_duration: int = 30,
        use_chunking: bool = False,
        display_mode: str = "full_text",
        callback_url: Optional[str] = None,
        job_id: Optional[int] = None,
        user_id: Optional[str] = None,
        initial_prompt: Optional[str] = None
    ) -> str:
        """
        Thread-safe version: สร้าง connection ใหม่ใน thread
        """
        connection = None
        try:
            connection, channel = self._create_thread_safe_connection()
            
            task_id = str(uuid.uuid4())
            
            task_data = {
                "task_id": task_id,
                "task_type": "transcription_request",
                "file_path": file_path,
                "file_url": file_url,
                "file_name": file_name,
                "language": language,
                "model_size": model_size,
                "chunk_duration": chunk_duration,
                "use_chunking": use_chunking,
                "display_mode": display_mode,
                "status": "pending",
                "created_at": time.time(),
                "callback_url": callback_url,
                "job_id": job_id,
                "user_id": user_id,
                "initial_prompt": initial_prompt
            }
            
            # บันทึก task ลง storage
            self.json_storage.save_transcription(task_id, task_data)
            
            # ส่งไปยัง transcription_request_queue
            priority = 10 if display_mode == "realtime_chunks" else 5
            
            channel.basic_publish(
                exchange='',
                routing_key=self.transcription_request_queue,
                body=json.dumps(task_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json',
                    priority=priority
                )
            )
            
            logger.info(f"✅ Thread-safe: Sent to {self.transcription_request_queue}: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"❌ Thread-safe send failed: {e}")
            raise
        finally:
            if connection and not connection.is_closed:
                try:
                    connection.close()
                except:
                    pass
    
    def send_close_caption_request_task(
        self,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        language: str = "th",
        model_size: str = "base",
        chunk_duration: int = 3,  # Close caption ใช้ chunk เล็กกว่า (3 วินาที)
        use_chunking: bool = True,  # Close caption ต้องใช้ chunking
        display_mode: str = "realtime_chunks",
        callback_url: Optional[str] = None,
        job_id: Optional[int] = None,
        user_id: Optional[str] = None,
        initial_prompt: Optional[str] = None
    ) -> str:
        """
        ส่งงาน close caption ไปยัง close_caption_request_queue (แยกจาก transcription)
        """
        max_retries = 3
        retry_delay = 1
        
        task_id = None
        for attempt in range(max_retries):
            try:
                self._ensure_connection()
                
                if task_id is None:
                    task_id = str(uuid.uuid4())
                
                task_data = {
                    "task_id": task_id,
                    "task_type": "close_caption_request",
                    "file_path": file_path,
                    "file_url": file_url,
                    "file_name": file_name,
                    "language": language,
                    "model_size": model_size,
                    "chunk_duration": chunk_duration,
                    "use_chunking": use_chunking,
                    "display_mode": display_mode,
                    "status": "pending",
                    "created_at": time.time(),
                    "callback_url": callback_url,
                    "job_id": job_id,
                    "user_id": user_id,
                    "initial_prompt": initial_prompt
                }
                
                # บันทึก task ลง storage
                self.json_storage.save_transcription(task_id, task_data)
                
                # ส่งไปยัง close_caption_request_queue
                logger.info(f"📤 Publishing to {self.close_caption_request_queue}: {task_id}")
                
                PUBLISH_TIMEOUT = int(os.getenv('RABBITMQ_PUBLISH_TIMEOUT', '2'))
                publish_success = [False]
                publish_error = [None]
                
                def publish_with_timeout():
                    try:
                        self.channel.basic_publish(
                            exchange='',
                            routing_key=self.close_caption_request_queue,
                            body=json.dumps(task_data),
                            properties=pika.BasicProperties(
                                delivery_mode=2,  # Persistent
                                content_type='application/json'
                            )
                        )
                        publish_success[0] = True
                    except Exception as e:
                        publish_error[0] = e
                
                publish_thread = threading.Thread(target=publish_with_timeout)
                publish_thread.daemon = True
                publish_thread.start()
                publish_thread.join(timeout=PUBLISH_TIMEOUT)
                
                if publish_thread.is_alive():
                    logger.error(f"⏱️  Publish timeout after {PUBLISH_TIMEOUT}s for task {task_id}")
                    raise TimeoutError(f"RabbitMQ publish timeout after {PUBLISH_TIMEOUT} seconds")
                
                if publish_error[0]:
                    raise publish_error[0]
                
                if not publish_success[0]:
                    raise Exception("Publish failed without error")
                
                logger.info(f"✅ Sent to {self.close_caption_request_queue}: {task_id}")
                return task_id
                
            except (ChannelClosedByBroker, UnroutableError) as publish_error:
                logger.error(f"❌ Queue full or rejected for task {task_id}: {publish_error}")
                MAX_QUEUE_CLOSE_CAPTION_REQUEST = int(os.getenv('MAX_QUEUE_CLOSE_CAPTION_REQUEST', '10'))
                RETRY_AFTER_SECONDS = int(os.getenv('RETRY_AFTER_SECONDS', '30'))
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Service temporarily unavailable",
                        "message": f"Close caption queue is full. Please try again later.",
                        "retry_after_seconds": RETRY_AFTER_SECONDS
                    },
                    headers={"Retry-After": str(RETRY_AFTER_SECONDS)}
                ) from publish_error
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ Attempt {attempt + 1}/{max_retries} failed: {e}")
                
                if attempt < max_retries - 1:
                    self._reset_connection()
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    if task_id:
                        try:
                            task_data['status'] = 'failed'
                            task_data['error_message'] = str(e)
                            self.json_storage.save_transcription(task_id, task_data)
                        except Exception:
                            pass
                    raise
    
    def send_close_caption_request_task_thread_safe(
        self,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        language: str = "th",
        model_size: str = "base",
        chunk_duration: int = 3,
        use_chunking: bool = True,
        display_mode: str = "realtime_chunks",
        callback_url: Optional[str] = None,
        job_id: Optional[int] = None,
        user_id: Optional[str] = None,
        initial_prompt: Optional[str] = None
    ) -> str:
        """
        Thread-safe version: สร้าง connection ใหม่ใน thread
        """
        connection = None
        try:
            connection, channel = self._create_thread_safe_connection()
            
            task_id = str(uuid.uuid4())
            task_data = {
                "task_id": task_id,
                "task_type": "close_caption_request",
                "file_path": file_path,
                "file_url": file_url,
                "file_name": file_name,
                "language": language,
                "model_size": model_size,
                "chunk_duration": chunk_duration,
                "use_chunking": use_chunking,
                "display_mode": display_mode,
                "status": "pending",
                "created_at": time.time(),
                "callback_url": callback_url,
                "job_id": job_id,
                "user_id": user_id,
                "initial_prompt": initial_prompt
            }
            
            # บันทึก task ลง storage
            self.json_storage.save_transcription(task_id, task_data)
            
            # ส่งไปยัง close_caption_request_queue
            channel.basic_publish(
                exchange='',
                routing_key=self.close_caption_request_queue,
                body=json.dumps(task_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            )
            
            logger.info(f"✅ Thread-safe: Sent to {self.close_caption_request_queue}: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"❌ Error in thread-safe close caption request: {e}")
            raise
        finally:
            if connection:
                try:
                    connection.close()
                except:
                    pass
    
    def send_transcription_task_thread_safe(
        self,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        language: str = "th",
        model_size: str = "base",
        chunk_duration: int = 30,
        use_chunking: bool = False,
        display_mode: str = "full_text",
        callback_url: Optional[str] = None,
        job_id: Optional[int] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Thread-safe version: สร้าง connection ใหม่ใน thread
        """
        connection = None
        try:
            connection, channel = self._create_thread_safe_connection()
            
            task_id = str(uuid.uuid4())
            task_data = {
                "task_id": task_id,
                "task_type": "transcription",
                "file_path": file_path,
                "file_url": file_url,
                "file_name": file_name,
                "language": language,
                "model_size": model_size,
                "chunk_duration": chunk_duration,
                "use_chunking": use_chunking,
                "display_mode": display_mode,
                "status": "pending",
                "created_at": time.time(),
                "callback_url": callback_url,
                "job_id": job_id,
                "user_id": user_id
            }
            
            # บันทึก task ลง storage
            self.json_storage.save_transcription(task_id, task_data)
            
            # ส่งไปยัง queue
            channel.basic_publish(
                exchange='',
                routing_key=self.transcription_queue,
                body=json.dumps(task_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                )
            )
            
            logger.info(f"✅ Thread-safe: Sent to {self.transcription_queue}: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"❌ Thread-safe send failed: {e}")
            raise
        finally:
            if connection and not connection.is_closed:
                try:
                    connection.close()
                except:
                    pass
    
    def send_chunk_transcription_task(self, chunk_task: Dict[str, Any]) -> str:
        """ส่ง chunk transcription task ไปยัง queue สำหรับ parallel processing"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        chunk_task_id = chunk_task.get('task_id')
        if not chunk_task_id:
            chunk_task_id = str(uuid.uuid4())
            chunk_task['task_id'] = chunk_task_id
        
        for attempt in range(max_retries):
            try:
                self._ensure_connection()
                
                # ส่งไปยัง transcription_chunk_queue
                logger.info(f"📤 Publishing chunk task to queue: {self.transcription_chunk_queue}")
                logger.info(f"   Chunk Task ID: {chunk_task_id}")
                logger.info(f"   Parent Task ID: {chunk_task.get('parent_task_id')}")
                logger.info(f"   Chunk Index: {chunk_task.get('chunk_index')}/{chunk_task.get('total_chunks')}")
                
                self.channel.basic_publish(
                    exchange='',
                    routing_key=self.transcription_chunk_queue,
                    body=json.dumps(chunk_task),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Persistent
                        content_type='application/json'
                    )
                )
                
                logger.info(f"✅ ส่ง chunk task ไปยัง queue สำเร็จ: {chunk_task_id}")
                return chunk_task_id
                
            except Exception as e:
                logger.error(f"❌ Attempt {attempt + 1}/{max_retries} failed: {e}")
                
                if attempt < max_retries - 1:
                    self._reset_connection()
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(f"❌ ไม่สามารถส่ง chunk task ได้หลังจาก retry {max_retries} ครั้ง: {e}")
                    raise
    
    def send_merge_task(self, input_files: list, output_format: str = "mp4",
                       quality: str = "medium") -> str:
        """ส่ง merge video task ไปยัง queue"""
        task_id = str(uuid.uuid4())
        
        task_data = {
            "task_id": task_id,
            "type": "merge",
            "status": "pending",
            "input_files": input_files,
            "output_format": output_format,
            "quality": quality,
            "created_at": datetime.now().isoformat()
        }
        
        try:
            self._ensure_connection()
            
            # ส่ง message ไปยัง queue
            self.channel.basic_publish(
                exchange='',
                routing_key=self.merge_queue,
                body=json.dumps(task_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info(f"ส่ง merge task ไปยัง queue: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง merge task: {e}")
            raise
    
    def send_convert_task(self, input_file: str, output_format: str,
                         quality: str = "medium") -> str:
        """ส่ง convert format task ไปยัง queue"""
        task_id = str(uuid.uuid4())
        
        task_data = {
            "task_id": task_id,
            "type": "convert",
            "status": "pending",
            "input_file": input_file,
            "output_format": output_format,
            "quality": quality,
            "created_at": datetime.now().isoformat()
        }
        
        try:
            self._ensure_connection()
            
            # ส่ง message ไปยัง queue
            self.channel.basic_publish(
                exchange='',
                routing_key=self.convert_queue,
                body=json.dumps(task_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info(f"ส่ง convert task ไปยัง queue: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง convert task: {e}")
            raise
    
    def send_resize_task(self, input_file: str, width: int, height: int,
                        output_format: str = "mp4", quality: str = "medium") -> str:
        """ส่ง resize video task ไปยัง queue"""
        task_id = str(uuid.uuid4())
        
        task_data = {
            "task_id": task_id,
            "type": "resize",
            "status": "pending",
            "input_file": input_file,
            "width": width,
            "height": height,
            "output_format": output_format,
            "quality": quality,
            "created_at": datetime.now().isoformat()
        }
        
        try:
            self._ensure_connection()
            
            # ส่ง message ไปยัง queue
            self.channel.basic_publish(
                exchange='',
                routing_key=self.resize_queue,
                body=json.dumps(task_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info(f"ส่ง resize task ไปยัง queue: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง resize task: {e}")
            raise
    
    def send_batch_tasks(self, tasks: list) -> list:
        """ส่ง batch tasks ไปยัง queue"""
        task_ids = []
        
        for task in tasks:
            task_type = task.get('type')
            
            if task_type == 'trim':
                task_id = self.send_trim_task(
                    input_file=task['input_file'],
                    start_time=task['start_time'],
                    end_time=task['end_time'],
                    output_format=task.get('output_format', 'mp4'),
                    quality=task.get('quality', 'medium')
                )
            elif task_type == 'merge':
                task_id = self.send_merge_task(
                    input_files=task['input_files'],
                    output_format=task.get('output_format', 'mp4'),
                    quality=task.get('quality', 'medium')
                )
            elif task_type == 'convert':
                task_id = self.send_convert_task(
                    input_file=task['input_file'],
                    output_format=task['output_format'],
                    quality=task.get('quality', 'medium')
                )
            elif task_type == 'resize':
                task_id = self.send_resize_task(
                    input_file=task['input_file'],
                    width=task['width'],
                    height=task['height'],
                    output_format=task.get('output_format', 'mp4'),
                    quality=task.get('quality', 'medium')
                )
            else:
                logger.warning(f"ไม่รู้จัก task type: {task_type}")
                continue
            
            task_ids.append(task_id)
        
        return task_ids
    
    def get_queue_info(self) -> Dict[str, Any]:
        """ดึงข้อมูล queue"""
        try:
            self._ensure_connection()
            
            queue_info = {}
            
            # ตรวจสอบแต่ละ queue (รวม queues ใหม่)
            queue_names = [
                self.trim_queue, 
                self.merge_queue, 
                self.convert_queue, 
                self.resize_queue, 
                self.transcription_queue,
                self.transcription_request_queue,  # 3-Queue Architecture
                self.audio_extraction_queue        # 3-Queue Architecture
            ]
            
            for queue_name in queue_names:
                try:
                    method = self.channel.queue_declare(queue=queue_name, passive=True)
                    queue_info[queue_name] = {
                        'name': queue_name,
                        'message_count': method.method.message_count,
                        'consumer_count': method.method.consumer_count
                    }
                except Exception as e:
                    logger.warning(f"⚠️ Could not get info for queue {queue_name}: {e}")
                    queue_info[queue_name] = {
                        'name': queue_name,
                        'message_count': 0,
                        'consumer_count': 0,
                        'error': str(e)
                    }
            
            return queue_info
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูล queue: {e}")
            return {}
    
    def _create_thread_safe_connection(self):
        """สร้าง connection ใหม่สำหรับใช้ใน thread (thread-safe)"""
        credentials = pika.PlainCredentials(self.username, self.password)
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.virtual_host,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        return connection, channel
    
    def get_queue_info_thread_safe(self) -> Dict[str, Any]:
        """ดึงข้อมูล queue (thread-safe version - สร้าง connection ใหม่)"""
        connection = None
        try:
            connection, channel = self._create_thread_safe_connection()
            
            queue_info = {}
            
            # ตรวจสอบแต่ละ queue (รวม queues ใหม่)
            queue_names = [
                self.trim_queue, 
                self.merge_queue, 
                self.convert_queue, 
                self.resize_queue, 
                self.transcription_queue,
                self.transcription_request_queue,  # 3-Queue Architecture
                self.audio_extraction_queue        # 3-Queue Architecture
            ]
            
            for queue_name in queue_names:
                try:
                    method = channel.queue_declare(queue=queue_name, passive=True)
                    queue_info[queue_name] = {
                        'name': queue_name,
                        'message_count': method.method.message_count,
                        'consumer_count': method.method.consumer_count
                    }
                except Exception as e:
                    logger.warning(f"⚠️ Could not get info for queue {queue_name}: {e}")
                    queue_info[queue_name] = {
                        'name': queue_name,
                        'message_count': 0,
                        'consumer_count': 0,
                        'error': str(e)
                    }
            
            return queue_info
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูล queue: {e}")
            return {}
        finally:
            if connection and not connection.is_closed:
                try:
                    connection.close()
                except:
                    pass
    
    def purge_queue(self, queue_name: str) -> bool:
        """ลบ messages ทั้งหมดใน queue"""
        try:
            self._ensure_connection()
            
            if queue_name in [self.trim_queue, self.merge_queue, 
                            self.convert_queue, self.resize_queue]:
                self.channel.queue_purge(queue=queue_name)
                logger.info(f"ลบ messages ใน queue {queue_name} เรียบร้อย")
                return True
            else:
                logger.warning(f"ไม่พบ queue: {queue_name}")
                return False
                
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการลบ queue: {e}")
            return False
    
    def close(self):
        """ปิดการเชื่อมต่อ"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("ปิดการเชื่อมต่อ RabbitMQ")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() 