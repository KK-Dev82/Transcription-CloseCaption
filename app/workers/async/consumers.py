"""
Consumer Setup and Registration (aio-pika - Async)

จัดการการตั้งค่าและลงทะเบียน async consumers สำหรับ RabbitMQ queues ทั้งหมด
"""
import logging
import os
from typing import Dict, Callable, Awaitable, Any
import aio_pika
from aio_pika import Queue

logger = logging.getLogger(__name__)


class AsyncConsumerManager:
    """Manage async consumer setup and registration"""
    
    def __init__(self, channel, handlers: Dict[str, Callable], connection=None):
        """
        Initialize AsyncConsumerManager
        
        Args:
            channel: aio-pika Channel instance
            handlers: Dictionary ของ async handler functions
            connection: AsyncRabbitMQConnection instance (optional, for queue arguments)
        """
        self.channel = channel
        self.handlers = handlers
        self.connection = connection  # For accessing queue arguments
        
        # Queue names (ต้อง match กับ connection.py)
        self.trim_queue_name = 'video_trim_queue'
        self.merge_queue_name = 'video_merge_queue'
        self.convert_queue_name = 'video_convert_queue'
        self.resize_queue_name = 'video_resize_queue'
        self.transcription_queue_name = 'transcription_queue'
        self.transcription_chunk_queue_name = 'transcription_chunk_queue'
        self.audio_chunk_extracted_queue_name = 'media.audio.chunk.extracted'
        self.transcription_request_queue_name = 'transcription_request_queue'
        self.audio_extraction_queue_name = 'audio_extraction_queue'
        
        # Close Caption Queues (แยกจาก transcription เพื่อลัดคิว)
        self.close_caption_request_queue_name = 'close_caption_request_queue'
        self.close_caption_extraction_queue_name = 'close_caption_extraction_queue'
        self.close_caption_queue_name = 'close_caption_queue'
        
        # Store queue objects
        self.queues: Dict[str, Queue] = {}
    
    def update_channel(self, new_channel):
        """Update channel after reconnection"""
        self.channel = new_channel
        # Clear queues as they need to be re-declared with new channel
        self.queues.clear()
    
    async def setup_consumers(self):
        """ตั้งค่า async consumers สำหรับแต่ละ queue"""
        if not self.handlers:
            logger.error("❌ Handlers not set!")
            return
        
        if not self.channel or self.channel.is_closed:
            logger.error("❌ Channel not available or closed!")
            return
        
        # ตั้งค่า QoS สำหรับ channel (global setting สำหรับทุก queue)
        # ⚠️ ใน aio-pika, set_qos() เป็น global สำหรับ channel ทั้งหมด ไม่ใช่ per-queue
        # ตั้ง prefetch_count ตาม concurrency ที่ต้องการ (25) เพื่อรองรับ 25 tasks พร้อมกัน
        # Concurrency จะถูกควบคุมด้วย GPU semaphore (GPU_CONCURRENCY) และ worker pools
        request_prefetch = int(os.getenv('TRANSCRIPTION_REQUEST_PREFETCH_COUNT', '1'))  # Default: 1
        chunk_prefetch = int(os.getenv('TRANSCRIPTION_PREFETCH_COUNT', '1'))  # Default: 1 สำหรับ backward compatibility
        audio_extraction_prefetch = int(os.getenv('AUDIO_EXTRACTION_PREFETCH_COUNT', '1'))  # Default: 1
        # ใช้ค่าสูงสุดระหว่าง chunk_prefetch, request_prefetch และ audio_extraction_prefetch
        # เพื่อรองรับ 25 concurrency ในทุก queue
        global_prefetch = max(chunk_prefetch, request_prefetch, audio_extraction_prefetch)
        await self.channel.set_qos(prefetch_count=global_prefetch)
        logger.info(f"✅ Set QoS: prefetch_count={global_prefetch} (chunk={chunk_prefetch}, request={request_prefetch}, audio_extraction={audio_extraction_prefetch})")
        logger.info(f"   📌 Note: Concurrency is controlled by GPU semaphore (GPU_CONCURRENCY={os.getenv('GPU_CONCURRENCY', '25')})")
        logger.info(f"   📌 Worker will receive up to {global_prefetch} messages and process up to {os.getenv('GPU_CONCURRENCY', '25')} tasks concurrently")
        
        # Video processing queues
        await self._setup_queue_consumer(self.trim_queue_name, self.handlers.get('trim'))
        await self._setup_queue_consumer(self.merge_queue_name, self.handlers.get('merge'))
        await self._setup_queue_consumer(self.convert_queue_name, self.handlers.get('convert'))
        await self._setup_queue_consumer(self.resize_queue_name, self.handlers.get('resize'))
        
        # Transcription queues
        await self._setup_queue_consumer(self.transcription_queue_name, self.handlers.get('transcription'))
        await self._setup_queue_consumer(self.transcription_chunk_queue_name, self.handlers.get('chunk_transcription'))
        await self._setup_queue_consumer(self.audio_chunk_extracted_queue_name, self.handlers.get('audio_chunk_extracted'))
        
        # 3-Queue Architecture
        await self._setup_queue_consumer(self.transcription_request_queue_name, self.handlers.get('transcription_request'))
        await self._setup_queue_consumer(self.audio_extraction_queue_name, self.handlers.get('audio_extraction'))
        
        # Close Caption Queues (แยกจาก transcription เพื่อลัดคิว)
        await self._setup_queue_consumer(self.close_caption_request_queue_name, self.handlers.get('close_caption_request'))
        await self._setup_queue_consumer(self.close_caption_extraction_queue_name, self.handlers.get('close_caption_extraction'))
        await self._setup_queue_consumer(self.close_caption_queue_name, self.handlers.get('close_caption'))
        
        logger.info("✅ ตั้งค่า async consumers เสร็จสิ้น")
        logger.info(f"📋 Listening to {len(self.queues)} queues:")
        for queue_name in self.queues.keys():
            logger.info(f"   - {queue_name}")
    
    def _get_queue_arguments_for_consumer(self, queue_name: str) -> Dict[str, Any]:
        """
        Get queue arguments for consumer setup (ใช้ arguments เดียวกับ connection.py)
        
        Args:
            queue_name: ชื่อ queue
            
        Returns:
            Dictionary ของ queue arguments หรือ None
        """
        if not self.connection:
            return None
        
        # ใช้ _get_queue_arguments จาก connection ถ้ามี
        if hasattr(self.connection, '_get_queue_arguments'):
            if queue_name == self.transcription_request_queue_name:
                max_request = int(os.getenv('MAX_QUEUE_REQUEST', '51'))
                return self.connection._get_queue_arguments(
                    queue_name,
                    max_length=max_request,
                    enable_dlx=True,
                    enable_quorum=True
                )
            elif queue_name == self.audio_extraction_queue_name:
                max_extraction = int(os.getenv('MAX_QUEUE_EXTRACTION', '80'))
                return self.connection._get_queue_arguments(
                    queue_name,
                    max_length=max_extraction,
                    enable_dlx=True,
                    enable_quorum=True,
                    enable_priority=False  # Priority ไม่จำเป็นสำหรับ audio extraction
                )
            elif queue_name == self.close_caption_request_queue_name:
                max_close_caption_request = int(os.getenv('MAX_QUEUE_CLOSE_CAPTION_REQUEST', '10'))
                return self.connection._get_queue_arguments(
                    queue_name,
                    max_length=max_close_caption_request,
                    enable_dlx=True,
                    enable_quorum=True,
                    enable_priority=False
                )
            elif queue_name == self.close_caption_extraction_queue_name:
                max_close_caption_extraction = int(os.getenv('MAX_QUEUE_CLOSE_CAPTION_EXTRACTION', '20'))
                return self.connection._get_queue_arguments(
                    queue_name,
                    max_length=max_close_caption_extraction,
                    enable_dlx=True,
                    enable_quorum=True,
                    enable_priority=False
                )
            elif queue_name == self.close_caption_queue_name:
                max_close_caption = int(os.getenv('MAX_QUEUE_CLOSE_CAPTION', '10'))
                return self.connection._get_queue_arguments(
                    queue_name,
                    max_length=max_close_caption,
                    enable_dlx=True,
                    enable_quorum=True,
                    enable_priority=False
                )
        
        return None
    
    async def _setup_queue_consumer(self, queue_name: str, handler: Callable):
        """
        Setup consumer for a queue
        
        Args:
            queue_name: ชื่อ queue
            handler: Async handler function
        """
        if not handler:
            logger.warning(f"⚠️ No handler provided for {queue_name}, skipping...")
            return
        
        try:
            # Get queue arguments สำหรับ quorum queues
            queue_args = self._get_queue_arguments_for_consumer(queue_name)
            
            # พยายาม declare queue ด้วย arguments (ถ้ามี)
            # ถ้า queue มีอยู่แล้วและ arguments ตรงกัน จะไม่เกิด error
            # ถ้า queue มีอยู่แล้วแต่ arguments ไม่ตรงกัน จะเกิด PRECONDITION_FAILED
            try:
                if queue_args:
                    # ใช้ arguments สำหรับ quorum queues
                    queue = await self.channel.declare_queue(
                        queue_name,
                        durable=True,
                        arguments=queue_args
                    )
                    logger.debug(f"✅ Declared/got queue with arguments: {queue_name}")
                else:
                    # Queue ธรรมดา (ไม่มี arguments)
                    queue = await self.channel.declare_queue(queue_name, durable=True)
                    logger.debug(f"✅ Declared/got queue: {queue_name}")
                
                self.queues[queue_name] = queue
                
                # Setup consumer
                await queue.consume(handler)
                logger.info(f"✅ Consumer registered for {queue_name}")
                
            except Exception as declare_error:
                error_str = str(declare_error)
                if 'PRECONDITION_FAILED' in error_str:
                    # Queue มีอยู่แล้วแต่ arguments ไม่ตรงกัน
                    # ใช้ get_queue() เพื่อ get queue ที่มีอยู่แล้วโดยไม่เปลี่ยน arguments
                    logger.warning(f"⚠️ Queue {queue_name} exists with different arguments, using get_queue()...")
                    try:
                        queue = await self.channel.get_queue(queue_name, ensure=True)
                        self.queues[queue_name] = queue
                        await queue.consume(handler)
                        logger.info(f"✅ Consumer registered for {queue_name} (using existing queue)")
                    except Exception as get_error:
                        logger.error(f"❌ Failed to get existing queue {queue_name}: {get_error}")
                        raise
                else:
                    raise
            
        except Exception as e:
            logger.error(f"❌ Failed to setup consumer for {queue_name}: {e}", exc_info=True)

