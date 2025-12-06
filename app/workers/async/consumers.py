"""
Consumer Setup and Registration (aio-pika - Async)

จัดการการตั้งค่าและลงทะเบียน async consumers สำหรับ RabbitMQ queues ทั้งหมด
"""
import logging
import os
from typing import Dict, Callable, Awaitable
import aio_pika
from aio_pika import Queue

logger = logging.getLogger(__name__)


class AsyncConsumerManager:
    """Manage async consumer setup and registration"""
    
    def __init__(self, channel, handlers: Dict[str, Callable]):
        """
        Initialize AsyncConsumerManager
        
        Args:
            channel: aio-pika Channel instance
            handlers: Dictionary ของ async handler functions
        """
        self.channel = channel
        self.handlers = handlers
        
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
        
        # Store queue objects
        self.queues: Dict[str, Queue] = {}
    
    async def setup_consumers(self):
        """ตั้งค่า async consumers สำหรับแต่ละ queue"""
        if not self.handlers:
            logger.error("❌ Handlers not set!")
            return
        
        if not self.channel or self.channel.is_closed:
            logger.error("❌ Channel not available or closed!")
            return
        
        # ตั้งค่า QoS สำหรับ transcription_chunk_queue
        max_workers = int(os.getenv('TRANSCRIPTION_MAX_WORKERS', '5'))
        chunk_prefetch = int(os.getenv('TRANSCRIPTION_PREFETCH_COUNT', str(max_workers)))
        await self.channel.set_qos(prefetch_count=chunk_prefetch)
        logger.info(f"✅ Set QoS: prefetch_count={chunk_prefetch} for transcription_chunk_queue (max_workers={max_workers})")
        
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
        await self.channel.set_qos(prefetch_count=1)  # Prefetch=1 สำหรับ request queue
        await self._setup_queue_consumer(self.transcription_request_queue_name, self.handlers.get('transcription_request'))
        await self._setup_queue_consumer(self.audio_extraction_queue_name, self.handlers.get('audio_extraction'))
        
        logger.info("✅ ตั้งค่า async consumers เสร็จสิ้น")
        logger.info(f"📋 Listening to {len(self.queues)} queues:")
        for queue_name in self.queues.keys():
            logger.info(f"   - {queue_name}")
    
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
            # Declare queue (อาจมีอยู่แล้วแล้ว แต่ไม่เป็นไร)
            queue = await self.channel.declare_queue(queue_name, durable=True)
            self.queues[queue_name] = queue
            
            # Setup consumer
            await queue.consume(handler)
            logger.debug(f"✅ Consumer registered for {queue_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup consumer for {queue_name}: {e}", exc_info=True)

