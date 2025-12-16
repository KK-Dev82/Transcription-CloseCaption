"""
RabbitMQ Connection Management (Pika - Blocking)

จัดการการเชื่อมต่อ RabbitMQ, queue declarations, DLX setup, และ thread-safe publishing
"""
import logging
import os
import time
import threading
from typing import Dict, Any
import pika
from pika.exceptions import AMQPConnectionError

logger = logging.getLogger(__name__)


class RabbitMQConnection:
    """Manage RabbitMQ connection and channel for sync worker"""
    
    def __init__(self):
        # RabbitMQ configuration
        self.rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        self.rabbitmq_port = int(os.getenv('RABBITMQ_PORT', '5672'))
        self.rabbitmq_user = os.getenv('RABBITMQ_USER', 'guest')
        self.rabbitmq_password = os.getenv('RABBITMQ_PASSWORD', 'guest')
        self.heartbeat = int(os.getenv('RABBITMQ_HEARTBEAT_TIMEOUT', '1800'))
        self.blocked_connection_timeout = int(os.getenv('RABBITMQ_BLOCKED_TIMEOUT', '600'))
        
        # Connections and channels
        self.connection = None
        self.channel = None
        self.publish_connection = None
        self.publish_channel = None
        
        # Thread lock สำหรับ publish channel operations
        self._publish_channel_lock = threading.Lock()
        
        # Queue names
        self.trim_queue = 'video_trim_queue'
        self.merge_queue = 'video_merge_queue'
        self.convert_queue = 'video_convert_queue'
        self.resize_queue = 'video_resize_queue'
        self.transcription_queue = 'transcription_queue'
        self.transcription_chunk_queue = 'transcription_chunk_queue'
        self.audio_chunk_extracted_queue = 'media.audio.chunk.extracted'
        
        # 3-Queue Architecture (Final Design)
        self.transcription_request_queue = 'transcription_request_queue'
        self.audio_extraction_queue = 'audio_extraction_queue'
        
        # Close Caption Queues (แยกจาก transcription เพื่อลัดคิว)
        self.close_caption_request_queue = 'close_caption_request_queue'
        self.close_caption_extraction_queue = 'close_caption_extraction_queue'
        self.close_caption_queue = 'close_caption_queue'
        
        # Transcription exchange
        self.transcription_exchange = 'transcription.exchange'
        self.transcription_chunk_completed_routing_key = 'transcription.chunk.completed'
    
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
                    heartbeat=self.heartbeat,
                    blocked_connection_timeout=self.blocked_connection_timeout,
                    connection_attempts=3,
                    retry_delay=2
                )
                
                logger.info(f"✅ RabbitMQ connection parameters: heartbeat={self.heartbeat}s ({self.heartbeat/60:.1f}min), blocked_timeout={self.blocked_connection_timeout}s ({self.blocked_connection_timeout/60:.1f}min)")
                
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
                
                # สร้าง queues เก่า (backward compatible)
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
                
                # ============================================================
                # 3-Queue Architecture (Final Design) - Queue Declarations
                # ============================================================
                self._declare_quorum_queues()
                
                # ตั้งค่า QoS สำหรับ transcription_queue (full video tasks)
                transcription_prefetch = int(os.getenv('TRANSCRIPTION_QUEUE_PREFETCH_COUNT', '1'))
                self.channel.basic_qos(prefetch_count=transcription_prefetch)
                logger.info(f"✅ Set QoS for transcription_queue: prefetch_count={transcription_prefetch}")
                
                logger.info("เชื่อมต่อ RabbitMQ สำเร็จ")
                
                # สร้าง publish connection แยกสำหรับ publishing จาก threads (thread-safe)
                self._connect_publish_channel()
                
                return True
                
            except (AMQPConnectionError, Exception) as e:
                logger.warning(f"ไม่สามารถเชื่อมต่อ RabbitMQ (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"ไม่สามารถเชื่อมต่อ RabbitMQ หลังจากลอง {max_retries} ครั้ง")
                    logger.error(f"RabbitMQ Host: {self.rabbitmq_host}:{self.rabbitmq_port}")
                    logger.error("💡 Solutions:")
                    logger.error("   1. Check if RabbitMQ is running")
                    logger.error("   2. Check RABBITMQ_HOST and RABBITMQ_PORT environment variables")
                    logger.error("   3. For local testing, use SSH Tunnel: ssh -L 5672:localhost:5672 ...")
                    return False
    
    def _connect_publish_channel(self):
        """
        สร้าง publish connection/channel แยกสำหรับ publishing จาก threads
        เพื่อแก้ปัญหา thread-safety กับ Pika BlockingConnection
        """
        # ใช้ lock เพื่อป้องกัน concurrent creation
        with self._publish_channel_lock:
            # ตรวจสอบว่า connection มีอยู่แล้วและใช้งานได้หรือไม่
            try:
                if self.publish_connection and not self.publish_connection.is_closed:
                    if self.publish_channel and not self.publish_channel.is_closed:
                        logger.debug("Publish channel already exists and is active")
                        return
            except Exception:
                pass
            
            try:
                logger.info("🔗 Creating separate publish connection for thread-safe publishing...")
                
                credentials = pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_password)
                
                parameters = pika.ConnectionParameters(
                    host=self.rabbitmq_host,
                    port=self.rabbitmq_port,
                    credentials=credentials,
                    heartbeat=self.heartbeat,
                    blocked_connection_timeout=self.blocked_connection_timeout,
                    connection_attempts=3,
                    retry_delay=2
                )
                
                self.publish_connection = pika.BlockingConnection(parameters)
                self.publish_channel = self.publish_connection.channel()
                
                logger.info("✅ Publish connection created successfully")
            except Exception as e:
                logger.error(f"❌ Failed to create publish connection: {e}")
                logger.warning("⚠️ Will fall back to main channel (may cause thread-safety issues)")
                self.publish_connection = None
                self.publish_channel = None
    
    def _get_publish_channel(self):
        """
        Get publish channel (thread-safe with lock)
        ถ้า publish connection หลุดจะลอง reconnect
        """
        # ใช้ lock เพื่อป้องกัน concurrent access
        with self._publish_channel_lock:
            # ตรวจสอบว่า publish channel ใช้งานได้หรือไม่
            if self.publish_channel and not self.publish_channel.is_closed:
                try:
                    # ตรวจสอบว่า connection ยังทำงานอยู่หรือไม่
                    if self.publish_connection and not self.publish_connection.is_closed:
                        return self.publish_channel
                except Exception:
                    pass
            
            # ถ้า publish channel ไม่มีหรือหลุด ให้ลอง reconnect
            logger.warning("⚠️ Publish channel is closed, attempting to reconnect...")
            try:
                self._connect_publish_channel()
                if self.publish_channel and not self.publish_channel.is_closed:
                    logger.info("✅ Publish channel reconnected successfully")
                    return self.publish_channel
            except Exception as e:
                logger.error(f"❌ Failed to reconnect publish channel: {e}")
            
            # Fallback to main channel (not recommended, but better than crashing)
            if self.channel and not self.channel.is_closed:
                logger.warning("⚠️ Using main channel for publishing (not thread-safe, but connection is available)")
                return self.channel
            else:
                raise RuntimeError("No available channel for publishing (both publish and main channels are closed)")
    
    def _safe_publish(self, exchange: str, routing_key: str, body: str, properties: pika.BasicProperties = None, max_retries: int = 3):
        """
        Thread-safe publish message with retry logic เพื่อป้องกัน IndexError และ StreamLostError
        
        Args:
            exchange: Exchange name
            routing_key: Routing key
            body: Message body (string)
            properties: Message properties
            max_retries: Maximum number of retry attempts
        
        Returns:
            bool: True if published successfully, False otherwise
        """
        for attempt in range(max_retries):
            try:
                publish_ch = self._get_publish_channel()
                publish_ch.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=body,
                    properties=properties or pika.BasicProperties(
                        delivery_mode=2,  # Persistent
                        content_type='application/json'
                    )
                )
                return True
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    IndexError, AttributeError, RuntimeError) as e:
                logger.warning(f"⚠️ Publish failed (attempt {attempt + 1}/{max_retries}): {type(e).__name__}: {e}")
                if attempt < max_retries - 1:
                    # Reset publish channel and retry
                    try:
                        with self._publish_channel_lock:
                            if self.publish_channel and not self.publish_channel.is_closed:
                                try:
                                    self.publish_channel.close()
                                except:
                                    pass
                            self.publish_channel = None
                            if self.publish_connection and not self.publish_connection.is_closed:
                                try:
                                    self.publish_connection.close()
                                except:
                                    pass
                            self.publish_connection = None
                    except:
                        pass
                    time.sleep(1)  # Wait before retry
                else:
                    logger.error(f"❌ Failed to publish after {max_retries} attempts")
                    return False
            except Exception as e:
                logger.error(f"❌ Unexpected error during publish: {e}", exc_info=True)
                return False
        return False
    
    def _get_queue_arguments(
        self,
        queue_name: str,
        max_length: int = 0,
        enable_dlx: bool = True,
        enable_quorum: bool = True
    ) -> Dict[str, Any]:
        """
        สร้าง queue arguments สำหรับ quorum queue ตาม Final Architecture Design
        
        Args:
            queue_name: ชื่อ queue
            max_length: จำนวน messages สูงสุด (0 = no limit)
            enable_dlx: เปิดใช้งาน Dead Letter Exchange
            enable_quorum: ใช้ quorum queue type
        
        Returns:
            Dictionary ของ queue arguments
        """
        arguments = {}
        
        # Quorum Queue Type
        use_quorum = os.getenv('USE_QUORUM_QUEUES', 'true').lower() == 'true'
        if enable_quorum and use_quorum:
            arguments['x-queue-type'] = 'quorum'
        
        # Queue Max Length & Overflow
        if max_length > 0:
            arguments['x-max-length'] = max_length
            arguments['x-overflow'] = 'reject-publish'
        
        # Dead Letter Exchange (DLX)
        enable_dlx_flag = os.getenv('ENABLE_DLX', 'true').lower() == 'true'
        if enable_dlx and enable_dlx_flag:
            dlx_exchange = f'{queue_name}.dlx'
            dlx_queue = f'{queue_name}.dlq'
            arguments['x-dead-letter-exchange'] = dlx_exchange
            arguments['x-dead-letter-routing-key'] = dlx_queue
        
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
            
            logger.debug(f"✅ DLX setup: {queue_name} -> {dlx_exchange} -> {dlx_queue}")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to setup DLX for {queue_name}: {e}")
    
    def _declare_quorum_queues(self):
        """
        สร้าง Quorum Queues สำหรับ 3-Queue Architecture ตาม Final Design
        """
        try:
            # 1. Transcription Request Queue (max 51: 50 video + 1 close caption)
            max_request = int(os.getenv('MAX_QUEUE_REQUEST', '51'))
            request_args = self._get_queue_arguments(
                self.transcription_request_queue,
                max_length=max_request,
                enable_dlx=True,
                enable_quorum=True
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
                enable_quorum=True
            )
            self.channel.queue_declare(
                queue=self.audio_extraction_queue,
                durable=True,
                arguments=extraction_args if extraction_args else None
            )
            self._setup_dlx_for_queue(self.audio_extraction_queue)
            logger.info(f"✅ Created {self.audio_extraction_queue} (max: {max_extraction}, quorum: {extraction_args.get('x-queue-type', 'classic')})")
            
            # 3. Transcription Queue (max 20) - Note: ยังใช้ queue เดิม (backward compatible)
            # Queue เดิมจะยังทำงาน แต่ถ้าต้องการ quorum จะต้องสร้าง queue ใหม่
            
            # ============================================================
            # Close Caption Queues (แยกจาก transcription เพื่อลัดคิว)
            # ============================================================
            
            # 1. Close Caption Request Queue (max 10)
            max_close_caption_request = int(os.getenv('MAX_QUEUE_CLOSE_CAPTION_REQUEST', '10'))
            close_caption_request_args = self._get_queue_arguments(
                self.close_caption_request_queue,
                max_length=max_close_caption_request,
                enable_dlx=True,
                enable_quorum=True,
                enable_priority=False
            )
            self.channel.queue_declare(
                queue=self.close_caption_request_queue,
                durable=True,
                arguments=close_caption_request_args if close_caption_request_args else None
            )
            self._setup_dlx_for_queue(self.close_caption_request_queue)
            logger.info(f"✅ Created {self.close_caption_request_queue} (max: {max_close_caption_request}, quorum: {close_caption_request_args.get('x-queue-type', 'classic')})")
            
            # 2. Close Caption Extraction Queue (max 20)
            max_close_caption_extraction = int(os.getenv('MAX_QUEUE_CLOSE_CAPTION_EXTRACTION', '20'))
            close_caption_extraction_args = self._get_queue_arguments(
                self.close_caption_extraction_queue,
                max_length=max_close_caption_extraction,
                enable_dlx=True,
                enable_quorum=True,
                enable_priority=False
            )
            self.channel.queue_declare(
                queue=self.close_caption_extraction_queue,
                durable=True,
                arguments=close_caption_extraction_args if close_caption_extraction_args else None
            )
            self._setup_dlx_for_queue(self.close_caption_extraction_queue)
            logger.info(f"✅ Created {self.close_caption_extraction_queue} (max: {max_close_caption_extraction}, quorum: {close_caption_extraction_args.get('x-queue-type', 'classic')})")
            
            # 3. Close Caption Queue (max 10)
            max_close_caption = int(os.getenv('MAX_QUEUE_CLOSE_CAPTION', '10'))
            close_caption_args = self._get_queue_arguments(
                self.close_caption_queue,
                max_length=max_close_caption,
                enable_dlx=True,
                enable_quorum=True,
                enable_priority=False
            )
            self.channel.queue_declare(
                queue=self.close_caption_queue,
                durable=True,
                arguments=close_caption_args if close_caption_args else None
            )
            self._setup_dlx_for_queue(self.close_caption_queue)
            logger.info(f"✅ Created {self.close_caption_queue} (max: {max_close_caption}, quorum: {close_caption_args.get('x-queue-type', 'classic')})")
            
            logger.info("📋 3-Queue Architecture: Queues declared successfully")
            logger.info("📋 Close Caption Queues: 3-Queue (close_caption_request → close_caption_extraction → close_caption)")
            
        except Exception as e:
            logger.error(f"❌ Failed to declare quorum queues: {e}", exc_info=True)
            # Continue anyway - queues might already exist
    
    def close(self):
        """Close all connections"""
        try:
            if self.publish_channel and not self.publish_channel.is_closed:
                self.publish_channel.close()
            if self.publish_connection and not self.publish_connection.is_closed:
                self.publish_connection.close()
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("✅ All RabbitMQ connections closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing connections: {e}")
    
    def is_connected(self):
        """Check if connection is alive"""
        try:
            return (self.connection and not self.connection.is_closed and
                    self.channel and not self.channel.is_closed)
        except:
            return False
