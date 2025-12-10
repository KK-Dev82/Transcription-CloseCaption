"""
Message Handlers (aio-pika - Async)

จัดการ message handlers สำหรับ RabbitMQ queues ทั้งหมด (9 handlers)
ใช้ async/await ทั้งหมด ไม่มีปัญหา thread safety
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import aio_pika
from aio_pika import IncomingMessage

logger = logging.getLogger(__name__)

# Import timeout decorator
from .utils import with_timeout


class AsyncMessageHandlers:
    """Async message handlers สำหรับ RabbitMQ queues"""
    
    def __init__(self, worker):
        """
        Initialize async message handlers
        
        Args:
            worker: Worker instance ที่มี services, storage, processors, utils
        """
        self.worker = worker
    
    async def handle_trim(self, message: IncomingMessage):
        """ประมวลผล trim video task"""
        async with message.process():
            try:
                task_data = json.loads(message.body.decode('utf-8'))
                logger.info(f"เริ่มประมวลผล trim task: {task_data.get('task_id')}")
                
                # อัปเดตสถานะเป็น processing
                task_data['status'] = 'processing'
                self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
                
                # ประมวลผลการตัดวิดีโอ
                await self.worker.processors.execute_trim_task(task_data)
                
                logger.info(f"trim task เสร็จสิ้น: {task_data.get('task_id')}")
                
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการประมวลผล trim task: {e}", exc_info=True)
                # ไม่ requeue เพื่อป้องกัน infinite retry loop - ส่งไป DLQ แทน
                raise  # Raise เพื่อให้ message.process() nack อัตโนมัติ
    
    async def handle_merge(self, message: IncomingMessage):
        """ประมวลผล merge video task"""
        async with message.process():
            try:
                task_data = json.loads(message.body.decode('utf-8'))
                logger.info(f"เริ่มประมวลผล merge task: {task_data.get('task_id')}")
                
                # อัปเดตสถานะเป็น processing
                task_data['status'] = 'processing'
                self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
                
                # ประมวลผลการรวมวิดีโอ
                await self.worker.processors.execute_merge_task(task_data)
                
                logger.info(f"merge task เสร็จสิ้น: {task_data.get('task_id')}")
                
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการประมวลผล merge task: {e}", exc_info=True)
                raise
    
    async def handle_convert(self, message: IncomingMessage):
        """ประมวลผล convert format task"""
        async with message.process():
            try:
                task_data = json.loads(message.body.decode('utf-8'))
                logger.info(f"เริ่มประมวลผล convert task: {task_data.get('task_id')}")
                
                # อัปเดตสถานะเป็น processing
                task_data['status'] = 'processing'
                self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
                
                # ประมวลผลการแปลงรูปแบบ
                await self.worker.processors.execute_convert_task(task_data)
                
                logger.info(f"convert task เสร็จสิ้น: {task_data.get('task_id')}")
                
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการประมวลผล convert task: {e}", exc_info=True)
                raise
    
    async def handle_resize(self, message: IncomingMessage):
        """ประมวลผล resize video task"""
        async with message.process():
            try:
                task_data = json.loads(message.body.decode('utf-8'))
                logger.info(f"เริ่มประมวลผล resize task: {task_data.get('task_id')}")
                
                # อัปเดตสถานะเป็น processing
                task_data['status'] = 'processing'
                self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
                
                # ประมวลผลการปรับขนาดวิดีโอ
                await self.worker.processors.execute_resize_task(task_data)
                
                logger.info(f"resize task เสร็จสิ้น: {task_data.get('task_id')}")
                
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการประมวลผล resize task: {e}", exc_info=True)
                raise
    
    async def handle_audio_chunk_extracted(self, message: IncomingMessage):
        """ประมวลผล audio chunk extracted message (จาก Backend)"""
        async with message.process():
            try:
                message_data = json.loads(message.body.decode('utf-8'))
                # Backend ใช้ JsonSerializerDefaults.Web (camelCase)
                chunk_id = message_data.get('chunkId') or message_data.get('ChunkId')
                logger.info(f"รับ audio chunk extracted message: {chunk_id}")
                
                # ประมวลผล audio chunk และ transcribe
                await self.worker.processors.execute_audio_chunk_transcription(message_data)
                
                logger.info(f"audio chunk transcription เสร็จสิ้น: {chunk_id}")
                
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการประมวลผล audio chunk extracted: {e}", exc_info=True)
                raise
    
    async def handle_chunk_transcription(self, message: IncomingMessage):
        """ประมวลผล chunk transcription task (สำหรับ parallel processing)"""
        async with message.process():
            try:
                # Log immediately when message is received
                logger.info("=" * 80)
                logger.info("📨 📨 📨 RECEIVED MESSAGE FROM transcription_chunk_queue!")
                logger.info(f"   Message size: {len(message.body)} bytes")
                logger.info(f"   Delivery tag: {message.delivery_tag}")
                logger.info(f"   Active chunks: {len(self.worker.active_chunks)}")
                
                chunk_task = json.loads(message.body.decode('utf-8'))
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
                logger.info(f"   Active chunks: {len(self.worker.active_chunks)}")
                
                # ส่งไปยัง asyncio task เพื่อประมวลผล parallel (ไม่ block)
                # Acknowledge message ทันที (ไม่รอให้เสร็จ) เพื่อให้ worker รับ message ใหม่ได้
                # สร้าง background task
                async def process_chunk():
                    try:
                        await self.worker.utils.execute_chunk_transcription_async(chunk_task)
                    finally:
                        # Clean up from active_chunks
                        if message.delivery_tag in self.worker.active_chunks:
                            del self.worker.active_chunks[message.delivery_tag]
                            logger.debug(f"🧹 Cleaned up chunk {chunk_index+1} (remaining active: {len(self.worker.active_chunks)})")
                
                task = asyncio.create_task(process_chunk())
                self.worker.active_chunks[message.delivery_tag] = task
                
                logger.info(f"🚀 Chunk {chunk_index+1}/{total_chunks} submitted to asyncio task (total active: {len(self.worker.active_chunks)})")
                logger.info(f"✅ Chunk {chunk_index+1}/{total_chunks} acknowledged - processing in background")
                
                # Message จะถูก ack อัตโนมัติเมื่อออกจาก message.process()
                
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการประมวลผล chunk transcription: {e}", exc_info=True)
                # Requeue เพื่อให้ worker อื่นลองประมวลผล
                raise  # จะถูก nack อัตโนมัติ
    
    async def handle_audio_extraction(self, message: IncomingMessage):
        """
        ประมวลผล audio extraction task (3-Queue Architecture: Stage 2)
        
        Logic:
        1. Extract audio from video file
        2. Send audio file to transcription_queue
        """
        async with message.process():
            try:
                task_data = json.loads(message.body.decode('utf-8'))
                task_id = task_data.get('task_id')
                video_file_path = task_data.get('file_path')
                language = task_data.get('language', 'th')
                model_size = task_data.get('model_size', 'base')
                chunk_duration = task_data.get('chunk_duration', 30)
                use_chunking = task_data.get('use_chunking', False)
                display_mode = task_data.get('display_mode', 'full_text')
                callback_url = task_data.get('callback_url')
                job_id = task_data.get('job_id')
                user_id = task_data.get('user_id')
                
                logger.info("=" * 80)
                logger.info(f"🎬 [Audio Extraction] Processing extraction task: {task_id}")
                logger.info(f"   Video file: {video_file_path}")
                logger.info("=" * 80)
                
                # Update status with detailed stage information
                task_data['status'] = 'extracting_audio'
                task_data['progress'] = 15
                task_data['current_stage'] = 'extracting_audio'
                task_data['current_stage_description'] = 'กำลังแยกเสียงจากวิดีโอ'
                task_data['stage_progress'] = 0
                self.worker.json_storage.save_transcription(task_id, task_data)
                
                # Check file exists
                if not video_file_path or not Path(video_file_path).exists():
                    raise FileNotFoundError(f"Video file not found: {video_file_path}")
                
                # Extract audio using VideoService (uses Thread Pool)
                logger.info(f"🎬 [Audio Extraction] Starting audio extraction...")
                import time
                extraction_start_time = time.time()
                
                # Run extract_audio in thread pool (blocking operation)
                audio_path = await asyncio.to_thread(
                    self.worker.video_service.extract_audio,
                    video_file_path,
                    task_id=task_id
                )
                extraction_time = time.time() - extraction_start_time
                logger.info(f"✅ [Audio Extraction] Audio extracted: {audio_path}")
                logger.info(f"   ⏱️  ใช้เวลา: {extraction_time:.2f} วินาที")
                
                # บันทึก audio_extraction_time ใน task metadata
                task_data['audio_extraction_time'] = extraction_time
                
                # Update stage progress to 100% (completed)
                task_data['stage_progress'] = 100
                task_data['current_stage_description'] = 'แยกเสียงเสร็จสิ้น'
                
                # Initialize task_breakdown ถ้ายังไม่มี
                if 'task_breakdown' not in task_data:
                    task_data['task_breakdown'] = []
                
                # เพิ่ม audio extraction task ใน task_breakdown
                task_data['task_breakdown'].append({
                    'type': 'audio_extraction',
                    'status': 'completed',
                    'time': extraction_time,
                    'completed_at': datetime.now().isoformat()
                })
                
                # อัปเดต total_tasks และ completed_tasks
                task_data['total_tasks'] = task_data.get('total_tasks', 0) + 1  # Audio extraction task
                task_data['completed_tasks'] = task_data.get('completed_tasks', 0) + 1
                
                # Update status - routing to transcription
                task_data['status'] = 'routing_to_transcription'
                task_data['progress'] = 25
                task_data['current_stage'] = 'transcribing'
                task_data['current_stage_description'] = 'กำลังเตรียมแปลงเสียง'
                task_data['stage_progress'] = 0
                self.worker.json_storage.save_transcription(task_id, task_data)
                
                # Send to transcription_queue
                transcription_message = {
                    "task_id": task_id,
                    "file_path": audio_path,  # Send audio file path
                    "file_url": task_data.get('file_url'),  # Keep original URL
                    "file_name": task_data.get('file_name'),
                    "language": language,
                    "model_size": model_size,
                    "chunk_duration": chunk_duration,
                    "use_chunking": use_chunking,
                    "display_mode": display_mode,
                    "callback_url": callback_url,
                    "job_id": job_id,
                    "user_id": user_id,
                    "initial_prompt": task_data.get('initial_prompt'),  # ส่ง initial_prompt ต่อไป
                    "created_at": datetime.now().isoformat(),
                    "audio_extracted_from": video_file_path  # Track original video
                }
                
                logger.info(f"📤 [Audio Extraction] Sending to transcription_queue: {task_id}")
                # กำหนด priority ตาม display_mode (ต่อเนื่องจาก transcription_request_queue)
                priority = 10 if display_mode == "realtime_chunks" else 5
                # ใช้ async_safe_publish สำหรับ async publishing
                success = await self.worker.connection.async_safe_publish(
                    exchange_name='',
                    routing_key=self.worker.connection.transcription_queue_name,
                    body=json.dumps(transcription_message),
                    properties={'priority': priority}
                )
                if success:
                    logger.info(f"✅ [Audio Extraction] Sent to transcription_queue: {task_id}")
                else:
                    logger.error(f"❌ [Audio Extraction] Failed to send to transcription_queue: {task_id}")
                    raise RuntimeError(f"Failed to publish to transcription_queue: {task_id}")
                
                logger.info(f"✅ [Audio Extraction] Acknowledged message: {task_id}")
                
            except Exception as e:
                logger.error(f"❌ [Audio Extraction] Error processing extraction task {task_id if 'task_id' in locals() else 'unknown'}: {e}", exc_info=True)
                raise
    
    async def handle_transcription_request(self, message: IncomingMessage):
        """
        ประมวลผล transcription request task (3-Queue Architecture: Stage 1)
        
        Logic:
        1. Download file from file_url
        2. Check file type (video/audio)
        3. Route to appropriate queue:
           - Video → audio_extraction_queue
           - Audio → transcription_queue
        """
        async with message.process():
            try:
                task_data = json.loads(message.body.decode('utf-8'))
                task_id = task_data.get('task_id')
                file_url = task_data.get('file_url')
                file_path = task_data.get('file_path')
                file_name = task_data.get('file_name')
                language = task_data.get('language', 'th')
                model_size = task_data.get('model_size', 'base')
                chunk_duration = task_data.get('chunk_duration', 30)
                use_chunking = task_data.get('use_chunking', False)
                display_mode = task_data.get('display_mode', 'full_text')
                callback_url = task_data.get('callback_url')
                job_id = task_data.get('job_id')
                user_id = task_data.get('user_id')
                initial_prompt = task_data.get('initial_prompt')  # ดึง initial_prompt
                
                logger.info("=" * 80)
                logger.info(f"🎯 [Download & Route] Processing transcription request: {task_id}")
                logger.info(f"   File URL: {file_url}")
                logger.info(f"   File Path: {file_path}")
                if initial_prompt:
                    logger.info(f"   Initial Prompt: {initial_prompt[:100]}..." if len(initial_prompt) > 100 else f"   Initial Prompt: {initial_prompt}")
                logger.info("=" * 80)
                
                # Update status
                task_data['status'] = 'downloading'
                task_data['progress'] = 5
                self.worker.json_storage.save_transcription(task_id, task_data)
                
                # Step 1: Download file (ถ้าไม่มี file_path หรือ file_path ไม่มีอยู่)
                local_file_path = file_path
                if file_url:
                    if not local_file_path or not Path(local_file_path).exists():
                        logger.info(f"📥 [Download & Route] Downloading file from URL: {file_url}")
                        local_file_path, _ = await self.worker.transcription_service._download_source_file(
                            task_id, file_url, file_name
                        )
                        logger.info(f"✅ [Download & Route] File downloaded: {local_file_path}")
                    else:
                        logger.info(f"✅ [Download & Route] Using existing file: {local_file_path}")
                elif not local_file_path or not Path(local_file_path).exists():
                    raise FileNotFoundError(f"ไฟล์ไม่พบและไม่มี file_url: {file_path}")
                
                # Update status - routing
                task_data['file_path'] = local_file_path
                task_data['status'] = 'routing'
                task_data['progress'] = 10
                task_data['current_stage'] = 'routing'
                task_data['current_stage_description'] = 'กำลังตรวจสอบประเภทไฟล์'
                task_data['stage_progress'] = 50
                self.worker.json_storage.save_transcription(task_id, task_data)
                
                # Step 2: Check file type (run in thread pool because it's synchronous)
                from app.services.file_service import FileService
                file_service = FileService()
                is_video = await asyncio.to_thread(file_service.is_video_file, local_file_path)
                is_audio = await asyncio.to_thread(file_service.is_audio_file, local_file_path)
                
                logger.info(f"🔍 [Download & Route] File type: {'video' if is_video else 'audio' if is_audio else 'unknown'}")
                
                # Step 3: Route to appropriate queue
                route_message = {
                    "task_id": task_id,
                    "file_path": local_file_path,
                    "file_url": file_url,
                    "file_name": file_name,
                    "language": language,
                    "model_size": model_size,
                    "chunk_duration": chunk_duration,
                    "use_chunking": use_chunking,
                    "display_mode": display_mode,
                    "callback_url": callback_url,
                    "job_id": job_id,
                    "user_id": user_id,
                    "initial_prompt": initial_prompt,  # ส่ง initial_prompt ต่อไป
                    "created_at": datetime.now().isoformat()
                }
                
                if is_video:
                    # Route to audio_extraction_queue
                    # กำหนด priority ตาม display_mode (ต่อเนื่องจาก transcription_request_queue)
                    priority = 10 if display_mode == "realtime_chunks" else 5
                    logger.info(f"📤 [Download & Route] Routing video file to audio_extraction_queue (priority={priority})")
                    success = await self.worker.connection.async_safe_publish(
                        exchange_name='',
                        routing_key=self.worker.connection.audio_extraction_queue_name,
                        body=json.dumps(route_message),
                        properties={'priority': priority}
                    )
                    if success:
                        logger.info(f"✅ [Download & Route] Routed to audio_extraction_queue: {task_id}")
                    else:
                        logger.error(f"❌ [Download & Route] Failed to route to audio_extraction_queue: {task_id}")
                        raise RuntimeError(f"Failed to publish to audio_extraction_queue: {task_id}")
                elif is_audio:
                    # Route directly to transcription_queue
                    # กำหนด priority ตาม display_mode (ต่อเนื่องจาก transcription_request_queue)
                    priority = 10 if display_mode == "realtime_chunks" else 5
                    logger.info(f"📤 [Download & Route] Routing audio file to transcription_queue (priority={priority})")
                    success = await self.worker.connection.async_safe_publish(
                        exchange_name='',
                        routing_key=self.worker.connection.transcription_queue_name,
                        body=json.dumps(route_message),
                        properties={'priority': priority}
                    )
                    if success:
                        logger.info(f"✅ [Download & Route] Routed to transcription_queue: {task_id}")
                    else:
                        logger.error(f"❌ [Download & Route] Failed to route to transcription_queue: {task_id}")
                        raise RuntimeError(f"Failed to publish to transcription_queue: {task_id}")
                else:
                    # Unknown file type - try to route to extraction first
                    # กำหนด priority ตาม display_mode (ต่อเนื่องจาก transcription_request_queue)
                    priority = 10 if display_mode == "realtime_chunks" else 5
                    logger.warning(f"⚠️ [Download & Route] Unknown file type - routing to audio_extraction_queue (priority={priority})")
                    success = await self.worker.connection.async_safe_publish(
                        exchange_name='',
                        routing_key=self.worker.connection.audio_extraction_queue_name,
                        body=json.dumps(route_message),
                        properties={'priority': priority}
                    )
                    if not success:
                        logger.error(f"❌ [Download & Route] Failed to route: {task_id}")
                        raise RuntimeError(f"Failed to publish: {task_id}")
                
                logger.info(f"✅ [Download & Route] Acknowledged message: {task_id}")
                
            except Exception as e:
                logger.error(f"❌ [Download & Route] Error processing request task {task_id if 'task_id' in locals() else 'unknown'}: {e}", exc_info=True)
                raise
    
    async def handle_transcription(self, message: IncomingMessage):
        """ประมวลผล transcription task"""
        async with message.process():
            task_id = None
            try:
                # Log immediately when message is received (BEFORE parsing)
                logger.info("=" * 80)
                logger.info("📨 📨 📨 RECEIVED MESSAGE FROM transcription_queue!")
                logger.info(f"   Message size: {len(message.body)} bytes")
                logger.info(f"   Delivery tag: {message.delivery_tag}")
                try:
                    task_data_preview = json.loads(message.body.decode('utf-8'))
                    task_id_preview = task_data_preview.get('task_id', 'unknown')
                    logger.info(f"   Task ID: {task_id_preview}")
                except Exception as e:
                    logger.warning(f"   Could not parse message preview: {e}")
                logger.info("=" * 80)
                
                task_data = json.loads(message.body.decode('utf-8'))
                task_id = task_data.get('task_id')
                file_path = task_data.get('file_path', 'N/A')
                model_size = task_data.get('model_size', 'base')
                language = task_data.get('language', 'th')
                use_chunking = task_data.get('use_chunking', False)  # Default: false
                initial_prompt = task_data.get('initial_prompt')  # ดึง initial_prompt
                
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"🎬 เริ่มประมวลผล transcription task: {task_id}")
                logger.info(f"   File: {file_path}")
                logger.info(f"   Model: {model_size}, Language: {language}")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                # ตรวจสอบว่า task นี้ถูกประมวลผลไปแล้วหรือไม่ (ป้องกัน duplicate processing)
                existing_task = self.worker.json_storage.get_transcription(task_id)
                if existing_task:
                    existing_status = existing_task.get('status', '')
                    if existing_status in ['completed', 'processing']:
                        logger.warning(f"⚠️ Task {task_id} มีสถานะ '{existing_status}' แล้ว, ข้ามการประมวลผลซ้ำ (อาจเป็น duplicate message)")
                        # Message จะถูก ack อัตโนมัติเมื่อออกจาก message.process()
                        return
                
                # Start task tracking
                task_timeout = int(os.getenv('TRANSCRIPTION_TASK_TIMEOUT_SECONDS', '1800'))  # 30 minutes
                self.worker.utils.track_task_start(task_id, 'transcription', timeout=task_timeout)
                
                # อัปเดตสถานะเป็น processing
                task_data['status'] = 'processing'
                task_data['started_at'] = datetime.now().isoformat()
                task_data['progress'] = 0
                task_data['current_stage'] = 'transcribing'
                task_data['current_stage_description'] = 'กำลังแปลงเสียงเป็นข้อความ'
                task_data['stage_progress'] = 0
                self.worker.json_storage.save_transcription(task_id, task_data)
                logger.info(f"📝 อัปเดตสถานะเป็น 'processing' (Progress: 0%)")
                
                # เริ่ม monitor progress ใน background task
                monitor_task = asyncio.create_task(
                    self.worker.utils.monitor_transcription_progress(task_id)
                )
                
                try:
                    # ประมวลผล transcription with timeout protection
                    logger.info(f"🚀 เริ่มประมวลผล transcription...")
                    transcription_timeout = int(os.getenv('TRANSCRIPTION_PROCESSING_TIMEOUT_SECONDS', '1800'))
                    
                    try:
                        await asyncio.wait_for(
                            self.worker.processors.execute_transcription_task(task_data),
                            timeout=transcription_timeout
                        )
                        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        logger.info(f"✅ Transcription task เสร็จสิ้น: {task_id}")
                        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        self.worker.utils.track_task_complete(task_id, 'completed')
                    
                    except asyncio.TimeoutError:
                        task_start_time = self.worker.utils.active_tasks.get(task_id, {}).get('started_at', time.time())
                        elapsed = time.time() - task_start_time
                        logger.error(f"⏱️  Transcription processing TIMEOUT after {elapsed:.2f}s (limit: {transcription_timeout}s) for task: {task_id}")
                        
                        # Mark task as failed
                        task_data['status'] = 'failed'
                        task_data['error_message'] = f"Transcription processing timeout after {elapsed:.2f}s"
                        task_data['failed_at'] = datetime.now().isoformat()
                        self.worker.json_storage.save_transcription(task_id, task_data)
                        self.worker.utils.track_task_complete(task_id, 'failed')
                        
                        # Raise to trigger message nack
                        raise
                    
                finally:
                    # Stop monitoring
                    monitor_task.cancel()
                    try:
                        await monitor_task
                    except asyncio.CancelledError:
                        pass
                
            except asyncio.TimeoutError:
                # Already handled above, just re-raise
                raise
            except Exception as e:
                logger.error(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.error(f"❌ เกิดข้อผิดพลาดในการประมวลผล transcription task {task_id if task_id else 'unknown'}: {e}", exc_info=True)
                logger.error(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                # Mark task as failed if we have task_id
                if task_id:
                    try:
                        task_data = self.worker.json_storage.get_transcription(task_id) or {}
                        task_data['status'] = 'failed'
                        task_data['error_message'] = str(e)[:500]  # Limit error message length
                        task_data['failed_at'] = datetime.now().isoformat()
                        self.worker.json_storage.save_transcription(task_id, task_data)
                        self.worker.utils.track_task_complete(task_id, 'failed')
                    except Exception as save_error:
                        logger.error(f"❌ Failed to mark task {task_id} as failed: {save_error}")
                
                # ไม่ requeue เพื่อป้องกัน infinite retry loop - ส่งไป DLQ แทน
                raise

