"""
Consumer Setup and Registration (Pika - Blocking)

จัดการการตั้งค่าและลงทะเบียน consumers สำหรับ RabbitMQ queues ทั้งหมด
"""
import logging
import os

logger = logging.getLogger(__name__)


class RabbitMQConsumers:
    """Manage consumer setup and registration"""
    
    def __init__(self, connection):
        """
        Initialize RabbitMQConsumers
        
        Args:
            connection: RabbitMQConnection instance
        """
        self.connection = connection
        self.handlers = None  # Will be set via set_handlers()
        
        # Queue names (ต้อง match กับ connection.py)
        self.trim_queue = 'video_trim_queue'
        self.merge_queue = 'video_merge_queue'
        self.convert_queue = 'video_convert_queue'
        self.resize_queue = 'video_resize_queue'
        self.transcription_queue = 'transcription_queue'
        self.transcription_chunk_queue = 'transcription_chunk_queue'
        self.audio_chunk_extracted_queue = 'media.audio.chunk.extracted'
        self.transcription_request_queue = 'transcription_request_queue'
        self.audio_extraction_queue = 'audio_extraction_queue'
    
    def set_handlers(self, handlers):
        """Set message handlers (injected from worker)"""
        self.handlers = handlers
    
    def setup_consumers(self):
        """ตั้งค่า consumers สำหรับแต่ละ queue"""
        if not self.handlers:
            logger.error("❌ Handlers not set! Call set_handlers() first")
            return
        
        channel = self.connection.channel
        if not channel or channel.is_closed:
            logger.error("❌ Channel not available or closed!")
            return
        
        # ตั้งค่า QoS สำหรับ transcription_chunk_queue ก่อน consume
        # ⚠️ ต้องเรียก basic_qos ก่อน basic_consume สำหรับ queue นี้
        # prefetch_count ควรเท่ากับหรือสูงกว่า max_workers เล็กน้อย
        # เพื่อให้ workers มีงานรออยู่เสมอ แต่ไม่รับงานมากเกินไป
        max_workers = int(os.getenv('TRANSCRIPTION_MAX_WORKERS', '5'))
        # prefetch_count = max_workers เพื่อให้รับงานได้เท่ากับจำนวน workers ที่พร้อมทำงาน
        # RTX 4080 Super 16GB → max_workers=5, prefetch_count=5-10 (ขึ้นอยู่กับ model size)
        chunk_prefetch = int(os.getenv('TRANSCRIPTION_PREFETCH_COUNT', str(max_workers)))
        # ใช้ global_qos=False เพื่อให้ prefetch_count เป็นต่อ queue (ไม่ใช่ต่อ channel)
        channel.basic_qos(prefetch_count=chunk_prefetch, prefetch_size=0, global_qos=False)
        logger.info(f"✅ Set QoS: prefetch_count={chunk_prefetch} for transcription_chunk_queue (max_workers={max_workers})")
        
        # Trim video consumer
        channel.basic_consume(
            queue=self.trim_queue,
            on_message_callback=self.handlers._process_trim_task,
            auto_ack=False
        )
        
        # Merge video consumer
        channel.basic_consume(
            queue=self.merge_queue,
            on_message_callback=self.handlers._process_merge_task,
            auto_ack=False
        )
        
        # Convert format consumer
        channel.basic_consume(
            queue=self.convert_queue,
            on_message_callback=self.handlers._process_convert_task,
            auto_ack=False
        )
        
        # Resize video consumer
        channel.basic_consume(
            queue=self.resize_queue,
            on_message_callback=self.handlers._process_resize_task,
            auto_ack=False
        )
        
        # Transcription consumer
        channel.basic_consume(
            queue=self.transcription_queue,
            on_message_callback=self.handlers._process_transcription_task,
            auto_ack=False
        )
        
        # Audio chunk extracted consumer (สำหรับ real-time close caption)
        channel.basic_consume(
            queue=self.audio_chunk_extracted_queue,
            on_message_callback=self.handlers._process_audio_chunk_extracted,
            auto_ack=False
        )
        
        # Transcription chunk consumer (สำหรับ parallel processing)
        # ⚠️ ต้อง consume หลังจาก set QoS แล้ว
        channel.basic_consume(
            queue=self.transcription_chunk_queue,
            on_message_callback=self.handlers._process_chunk_transcription_task,
            auto_ack=False
        )
        
        # ============================================================
        # 3-Queue Architecture Consumers (New)
        # ============================================================
        
        # Set QoS for transcription_request_queue (prefetch=1)
        channel.basic_qos(prefetch_count=1, prefetch_size=0, global_qos=False)
        
        # Transcription Request Queue Consumer (Download & Route)
        # Consume from transcription_request_queue: Download file → Check type → Route
        channel.basic_consume(
            queue=self.transcription_request_queue,
            on_message_callback=self.handlers._process_transcription_request_task,
            auto_ack=False
        )
        
        # Set QoS for audio_extraction_queue (prefetch=1)
        channel.basic_qos(prefetch_count=1, prefetch_size=0, global_qos=False)
        
        # Audio Extraction Queue Consumer
        # Consume from audio_extraction_queue: Extract audio → Send to transcription_queue
        channel.basic_consume(
            queue=self.audio_extraction_queue,
            on_message_callback=self.handlers._process_audio_extraction_task,
            auto_ack=False
        )
        
        logger.info("✅ ตั้งค่า consumers เสร็จสิ้น")
        logger.info(f"📋 Listening to queues:")
        logger.info(f"   - {self.transcription_queue}")
        logger.info(f"   - {self.transcription_chunk_queue}")
        logger.info(f"   - {self.trim_queue}")
        logger.info(f"   - {self.merge_queue}")
        logger.info(f"   - {self.convert_queue}")
        logger.info(f"   - {self.resize_queue}")
        logger.info(f"   - {self.audio_chunk_extracted_queue}")
        logger.info(f"   - {self.transcription_request_queue} ⭐ (NEW)")
        logger.info(f"   - {self.audio_extraction_queue} ⭐ (NEW)")

