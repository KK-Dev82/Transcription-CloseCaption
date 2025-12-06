"""
RabbitMQ Connection Management (aio-pika - Async)

จัดการการเชื่อมต่อ RabbitMQ, queue declarations, DLX setup, และ async publishing
ไม่มีปัญหา thread safety เนื่องจากใช้ async/await ทั้งหมด
"""
import logging
import os
from typing import Dict, Any, Optional
import aio_pika
from aio_pika import Connection, Channel, Exchange, Queue
from aio_pika.exceptions import AMQPConnectionError
from aio_pika.message import Message

logger = logging.getLogger(__name__)


class AsyncRabbitMQConnection:
    """Manage RabbitMQ connection and channel for async worker"""
    
    def __init__(self):
        # RabbitMQ configuration
        self.rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        self.rabbitmq_port = int(os.getenv('RABBITMQ_PORT', '5672'))
        self.rabbitmq_user = os.getenv('RABBITMQ_USER', 'guest')
        self.rabbitmq_password = os.getenv('RABBITMQ_PASSWORD', 'guest')
        self.heartbeat = int(os.getenv('RABBITMQ_HEARTBEAT_TIMEOUT', '1800'))
        
        # Connections and channels
        self.connection: Optional[Connection] = None
        self.channel: Optional[Channel] = None
        
        # Exchanges
        self.media_exchange: Optional[Exchange] = None
        self.transcription_exchange: Optional[Exchange] = None
        
        # Queue names
        self.trim_queue_name = 'video_trim_queue'
        self.merge_queue_name = 'video_merge_queue'
        self.convert_queue_name = 'video_convert_queue'
        self.resize_queue_name = 'video_resize_queue'
        self.transcription_queue_name = 'transcription_queue'
        self.transcription_chunk_queue_name = 'transcription_chunk_queue'
        self.audio_chunk_extracted_queue_name = 'media.audio.chunk.extracted'
        
        # 3-Queue Architecture (Final Design)
        self.transcription_request_queue_name = 'transcription_request_queue'
        self.audio_extraction_queue_name = 'audio_extraction_queue'
        
        # Transcription exchange
        self.transcription_exchange_name = 'transcription.exchange'
        self.transcription_chunk_completed_routing_key = 'transcription.chunk.completed'
    
    async def connect(self, max_retries: int = 5, retry_delay: int = 5) -> bool:
        """เชื่อมต่อกับ RabbitMQ พร้อม retry logic (auto-reconnect via connect_robust)"""
        url = f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/"
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to connect to RabbitMQ at {self.rabbitmq_host}:{self.rabbitmq_port} (attempt {attempt + 1}/{max_retries})...")
                
                # ใช้ connect_robust สำหรับ auto-reconnect
                self.connection = await aio_pika.connect_robust(
                    url,
                    heartbeat=self.heartbeat
                )
                self.channel = await self.connection.channel()
                
                logger.info(f"✅ RabbitMQ connection parameters: heartbeat={self.heartbeat}s ({self.heartbeat/60:.1f}min)")
                
                # สร้าง exchanges
                await self._declare_exchanges()
                
                # สร้าง queues เก่า (backward compatible)
                await self._declare_legacy_queues()
                
                # 3-Queue Architecture (Final Design)
                await self._declare_quorum_queues()
                
                logger.info("✅ Connected to RabbitMQ successfully and all queues/exchanges declared")
                return True
                
            except (AMQPConnectionError, Exception) as e:
                logger.warning(f"ไม่สามารถเชื่อมต่อ RabbitMQ (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    import asyncio
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"ไม่สามารถเชื่อมต่อ RabbitMQ หลังจากลอง {max_retries} ครั้ง")
                    logger.error(f"RabbitMQ Host: {self.rabbitmq_host}:{self.rabbitmq_port}")
                    return False
        
        return False
    
    async def _declare_exchanges(self):
        """สร้าง exchanges"""
        try:
            # Media Exchange
            self.media_exchange = await self.channel.declare_exchange(
                'media.exchange',
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            # Transcription Exchange
            self.transcription_exchange = await self.channel.declare_exchange(
                self.transcription_exchange_name,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            logger.info("✅ Exchanges declared: media.exchange, transcription.exchange")
        except Exception as e:
            logger.error(f"❌ Failed to declare exchanges: {e}", exc_info=True)
    
    async def _declare_legacy_queues(self):
        """สร้าง queues เก่า (backward compatible)"""
        try:
            # Video processing queues
            await self.channel.declare_queue(self.trim_queue_name, durable=True)
            await self.channel.declare_queue(self.merge_queue_name, durable=True)
            await self.channel.declare_queue(self.convert_queue_name, durable=True)
            await self.channel.declare_queue(self.resize_queue_name, durable=True)
            
            # Transcription queues
            await self.channel.declare_queue(self.transcription_queue_name, durable=True)
            await self.channel.declare_queue(self.transcription_chunk_queue_name, durable=True)
            
            # Queue สำหรับ audio chunk extracted (จาก Backend)
            audio_queue = await self.channel.declare_queue(
                self.audio_chunk_extracted_queue_name,
                durable=True
            )
            await audio_queue.bind(
                self.media_exchange,
                routing_key='media.audio.chunk.extracted'
            )
            
            logger.info("✅ Legacy queues declared successfully")
        except Exception as e:
            logger.error(f"❌ Failed to declare legacy queues: {e}", exc_info=True)
    
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
        
        # Queue Max Length & Overflow
        if max_length > 0:
            arguments['x-max-length'] = max_length
            arguments['x-overflow'] = 'reject-publish'
        
        # Priority Queue (รองรับ priority 0-10)
        # CloseCaption (realtime_chunks) → priority 10
        # Normal transcription → priority 5
        if enable_priority:
            max_priority = int(os.getenv('RABBITMQ_MAX_PRIORITY', '10'))
            arguments['x-max-priority'] = max_priority
            logger.debug(f"✅ Priority queue enabled for {queue_name}: max_priority={max_priority}")
        
        # Dead Letter Exchange (DLX)
        enable_dlx_flag = os.getenv('ENABLE_DLX', 'true').lower() == 'true'
        if enable_dlx and enable_dlx_flag:
            dlx_exchange = f'{queue_name}.dlx'
            dlx_queue = f'{queue_name}.dlq'
            arguments['x-dead-letter-exchange'] = dlx_exchange
            arguments['x-dead-letter-routing-key'] = dlx_queue
        
        return arguments
    
    async def _setup_dlx_for_queue(self, queue_name: str):
        """
        สร้าง Dead Letter Exchange และ Queue สำหรับ queue ที่ระบุ (async)
        
        Args:
            queue_name: ชื่อ queue หลัก
        """
        try:
            enable_dlx = os.getenv('ENABLE_DLX', 'true').lower() == 'true'
            if not enable_dlx:
                return
            
            use_quorum = os.getenv('USE_QUORUM_QUEUES', 'true').lower() == 'true'
            dlx_exchange_name = f'{queue_name}.dlx'
            dlx_queue_name = f'{queue_name}.dlq'
            
            # สร้าง DLX Exchange
            dlx_exchange = await self.channel.declare_exchange(
                dlx_exchange_name,
                aio_pika.ExchangeType.DIRECT,
                durable=True
            )
            
            # สร้าง DLQ Queue
            dlq_arguments = {}
            if use_quorum:
                dlq_arguments['x-queue-type'] = 'quorum'
            
            dlq_queue = await self.channel.declare_queue(
                dlx_queue_name,
                durable=True,
                arguments=dlq_arguments if dlq_arguments else None
            )
            
            # Bind DLQ to DLX
            await dlq_queue.bind(
                dlx_exchange,
                routing_key=dlx_queue_name
            )
            
            logger.debug(f"✅ DLX setup: {queue_name} -> {dlx_exchange_name} -> {dlx_queue_name}")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to setup DLX for {queue_name}: {e}")
    
    async def _declare_quorum_queues(self):
        """
        สร้าง Quorum Queues สำหรับ 3-Queue Architecture ตาม Final Design (async)
        """
        try:
            # 1. Transcription Request Queue (max 50)
            max_request = int(os.getenv('MAX_QUEUE_REQUEST', '50'))
            request_args = self._get_queue_arguments(
                self.transcription_request_queue_name,
                max_length=max_request,
                enable_dlx=True,
                enable_quorum=True
            )
            await self.channel.declare_queue(
                self.transcription_request_queue_name,
                durable=True,
                arguments=request_args if request_args else None
            )
            await self._setup_dlx_for_queue(self.transcription_request_queue_name)
            logger.info(f"✅ Created {self.transcription_request_queue_name} (max: {max_request}, quorum: {request_args.get('x-queue-type', 'classic')})")
            
            # 2. Audio Extraction Queue (max 80)
            max_extraction = int(os.getenv('MAX_QUEUE_EXTRACTION', '80'))
            extraction_args = self._get_queue_arguments(
                self.audio_extraction_queue_name,
                max_length=max_extraction,
                enable_dlx=True,
                enable_quorum=True,
                enable_priority=True  # Enable priority for CloseCaption
            )
            await self.channel.declare_queue(
                self.audio_extraction_queue_name,
                durable=True,
                arguments=extraction_args if extraction_args else None
            )
            await self._setup_dlx_for_queue(self.audio_extraction_queue_name)
            logger.info(f"✅ Created {self.audio_extraction_queue_name} (max: {max_extraction}, quorum: {extraction_args.get('x-queue-type', 'classic')})")
            
            logger.info("📋 3-Queue Architecture: Queues declared successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to declare quorum queues: {e}", exc_info=True)
            # Continue anyway - queues might already exist
    
    async def publish(
        self,
        exchange: str,
        routing_key: str,
        body: bytes,
        properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish message (async) - ไม่ต้องใช้ locks เพราะ async/await thread-safe
        
        Args:
            exchange: Exchange name
            routing_key: Routing key
            body: Message body (bytes)
            properties: Message properties (optional)
        
        Returns:
            bool: True if published successfully, False otherwise
        """
        try:
            if not self.channel or self.channel.is_closed:
                logger.error("❌ Channel is closed, cannot publish")
                return False
            
            # Get exchange object
            exchange_obj = None
            if exchange == 'media.exchange':
                exchange_obj = self.media_exchange
            elif exchange == self.transcription_exchange_name:
                exchange_obj = self.transcription_exchange
            else:
                # Use default exchange
                exchange_obj = self.channel.default_exchange
            
            if not exchange_obj:
                logger.error(f"❌ Exchange {exchange} not found")
                return False
            
            # Create message with priority support
            message_properties = {
                'delivery_mode': aio_pika.DeliveryMode.PERSISTENT,
                'content_type': 'application/json'
            }
            
            # Add priority if provided (0-10, higher = more priority)
            if properties and 'priority' in properties:
                message_properties['priority'] = properties['priority']
            
            # Add other properties if any
            if properties:
                for key, value in properties.items():
                    if key != 'priority' and key not in message_properties:
                        message_properties[key] = value
            
            message = Message(
                body,
                **message_properties
            )
            
            # Publish
            await exchange_obj.publish(
                message,
                routing_key=routing_key
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to publish message: {e}", exc_info=True)
            return False
    
    async def async_safe_publish(
        self,
        exchange_name: str,
        routing_key: str,
        body: str,
        properties: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> bool:
        """
        Async-safe publish message with retry logic.
        
        Args:
            exchange_name: Exchange name (empty string for default exchange)
            routing_key: Routing key
            body: Message body (string)
            properties: Message properties
            max_retries: Maximum number of retry attempts
        
        Returns:
            bool: True if published successfully, False otherwise
        """
        import asyncio
        
        for attempt in range(max_retries):
            try:
                if not self.is_connected():
                    logger.warning(f"⚠️ Connection lost, attempting to reconnect before publish (attempt {attempt + 1}/{max_retries})...")
                    if not await self.connect():
                        raise AMQPConnectionError("Failed to reconnect for publishing")
                
                # Use publish method with body as bytes
                success = await self.publish(
                    exchange=exchange_name,
                    routing_key=routing_key,
                    body=body.encode('utf-8') if isinstance(body, str) else body,
                    properties=properties
                )
                
                if success:
                    return True
                else:
                    raise RuntimeError("Publish returned False")
                    
            except Exception as e:
                logger.warning(f"⚠️ Async publish failed (attempt {attempt + 1}/{max_retries}): {type(e).__name__}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Wait before retry
                else:
                    logger.error(f"❌ Failed to publish after {max_retries} attempts: {e}", exc_info=True)
                    return False
        return False
    
    async def close(self):
        """Close all connections (async)"""
        try:
            if self.channel:
                await self.channel.close()
            if self.connection:
                await self.connection.close()
            logger.info("✅ All RabbitMQ connections closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing connections: {e}")
    
    def is_connected(self) -> bool:
        """Check if connection is alive"""
        try:
            return (self.connection and not self.connection.is_closed and
                    self.channel and not self.channel.is_closed)
        except:
            return False
