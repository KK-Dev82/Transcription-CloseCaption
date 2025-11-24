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
        self.audio_chunk_extracted_queue = 'media.audio.chunk.extracted'
        
        # Transcription exchange
        self.transcription_exchange = 'transcription.exchange'
        self.transcription_chunk_completed_routing_key = 'transcription.chunk.completed'
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """จัดการ signal สำหรับ graceful shutdown"""
        logger.info(f"ได้รับ signal {signum} กำลังปิด worker...")
        self.running = False
        if self.connection and not self.connection.is_closed:
            self.connection.close()
    
    def connect_rabbitmq(self):
        """เชื่อมต่อกับ RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_password)
            parameters = pika.ConnectionParameters(
                host=self.rabbitmq_host,
                port=self.rabbitmq_port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
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
            
            # ตั้งค่า QoS
            self.channel.basic_qos(prefetch_count=1)
            
            logger.info("เชื่อมต่อ RabbitMQ สำเร็จ")
            return True
            
        except AMQPConnectionError as e:
            logger.error(f"ไม่สามารถเชื่อมต่อ RabbitMQ: {e}")
            return False
    
    def setup_consumers(self):
        """ตั้งค่า consumers สำหรับแต่ละ queue"""
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
        
        logger.info("ตั้งค่า consumers เสร็จสิ้น")
    
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
            
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"trim task เสร็จสิ้น: {task_data.get('task_id')}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล trim task: {e}")
            # ไม่ requeue เพื่อป้องกัน infinite retry loop - ส่งไป DLQ แทน
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
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
            
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"merge task เสร็จสิ้น: {task_data.get('task_id')}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล merge task: {e}")
            # ไม่ requeue เพื่อป้องกัน infinite retry loop - ส่งไป DLQ แทน
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
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
            
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"convert task เสร็จสิ้น: {task_data.get('task_id')}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล convert task: {e}")
            # ไม่ requeue เพื่อป้องกัน infinite retry loop - ส่งไป DLQ แทน
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
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
            
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"resize task เสร็จสิ้น: {task_data.get('task_id')}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล resize task: {e}")
            # ไม่ requeue เพื่อป้องกัน infinite retry loop - ส่งไป DLQ แทน
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def _process_transcription_task(self, ch, method, properties, body):
        """ประมวลผล transcription task"""
        try:
            task_data = json.loads(body.decode('utf-8'))
            task_id = task_data.get('task_id')
            logger.info(f"เริ่มประมวลผล transcription task: {task_id}")
            
            # ตรวจสอบว่า task นี้ถูกประมวลผลไปแล้วหรือไม่ (ป้องกัน duplicate processing)
            existing_task = self.json_storage.get_transcription(task_id)
            if existing_task:
                existing_status = existing_task.get('status', '')
                if existing_status in ['completed', 'processing']:
                    logger.warning(f"⚠️ Task {task_id} มีสถานะ '{existing_status}' แล้ว, ข้ามการประมวลผลซ้ำ (อาจเป็น duplicate message)")
                    # Acknowledge message เพื่อไม่ให้ requeue
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return
            
            # อัปเดตสถานะเป็น processing
            task_data['status'] = 'processing'
            task_data['started_at'] = datetime.now().isoformat()
            self.json_storage.save_transcription(task_id, task_data)
            
            # ประมวลผล transcription
            asyncio.run(self._execute_transcription_task(task_data))
            
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"transcription task เสร็จสิ้น: {task_id}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล transcription task: {e}", exc_info=True)
            # ไม่ requeue เพื่อป้องกัน infinite retry loop - ส่งไป DLQ แทน
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
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
            
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"audio chunk transcription เสร็จสิ้น: {chunk_id}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล audio chunk extracted: {e}", exc_info=True)
            # ไม่ requeue เพื่อป้องกัน infinite retry loop
            # ส่งไป DLQ แทน (requeue=False)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
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
        try:
            file_path = task_data['file_path']
            language = task_data.get('language', 'th')
            model_size = task_data.get('model_size', 'base')
            chunk_duration = task_data.get('chunk_duration', 30)
            
            logger.info(f"เริ่ม transcription: {file_path}")
            
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
            
            # เรียกใช้ transcription service
            await self.transcription_service._process_transcription(
                task_data['task_id'],
                file_path,
                language,
                model_size,
                chunk_duration,
                file_url=task_data.get('file_url'),
                file_name=task_data.get('file_name')
            )
            
            # อัปเดต task
            task_data['status'] = 'completed'
            task_data['completed_at'] = datetime.now().isoformat()
            
            # บันทึกลง JSON storage
            self.json_storage.save_transcription(task_data['task_id'], task_data)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการ transcription: {e}")
            task_data['status'] = 'failed'
            task_data['error_message'] = str(e)
            task_data['completed_at'] = datetime.now().isoformat()
            self.json_storage.save_transcription(task_data['task_id'], task_data)
    
    def run(self):
        """เริ่มต้น worker"""
        logger.info("เริ่มต้น Video Worker...")
        
        # เชื่อมต่อ RabbitMQ
        if not self.connect_rabbitmq():
            logger.error("ไม่สามารถเชื่อมต่อ RabbitMQ ได้")
            return
        
        # ตั้งค่า consumers
        self.setup_consumers()
        
        logger.info("Video Worker พร้อมรับงาน...")
        
        try:
            # เริ่มรับ messages
            while self.running:
                self.connection.process_data_events(time_limit=1)
                
        except KeyboardInterrupt:
            logger.info("ได้รับ interrupt signal")
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดใน worker: {e}")
        finally:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
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