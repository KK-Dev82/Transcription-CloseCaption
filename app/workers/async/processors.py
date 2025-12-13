"""
Task Processors (aio-pika - Async)

Async task processors สำหรับประมวลผลงานต่างๆ: video manipulation, transcription, etc.
ใช้ async/await ทั้งหมด
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import ffmpeg

logger = logging.getLogger(__name__)


class AsyncTaskProcessors:
    """Async task processors สำหรับ worker"""
    
    def __init__(self, worker):
        """
        Initialize task processors
        
        Args:
            worker: Worker instance ที่มี services, storage, connection, utils, etc.
        """
        self.worker = worker
    
    async def execute_trim_task(self, task_data: Dict[str, Any]):
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
            self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
            
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
                    estimated_duration = duration * 0.8
                    progress = min(int((elapsed / estimated_duration) * 100), 95)
                    task_data['progress'] = progress
                    self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
                    logger.info(f"Trim progress: {progress}%")
            
            # เริ่ม progress tracking
            progress_task = asyncio.create_task(update_progress())
            
            try:
                # รัน FFmpeg (run in thread pool because it's blocking)
                await asyncio.to_thread(ffmpeg.run, stream, overwrite_output=True, quiet=True)
                
                # หยุด progress tracking
                progress_running = False
                progress_task.cancel()
                
                # อัปเดต task เสร็จสิ้น
                task_data['status'] = 'completed'
                task_data['progress'] = 100
                task_data['output_file'] = str(output_path)
                task_data['completed_at'] = asyncio.get_event_loop().time()
                
                # บันทึกลง JSON storage
                self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
                
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
            self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
    
    async def execute_merge_task(self, task_data: Dict[str, Any]):
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
            
            # รัน FFmpeg (run in thread pool)
            await asyncio.to_thread(ffmpeg.run, stream, overwrite_output=True, quiet=True)
            
            # ลบไฟล์ list
            list_file.unlink(missing_ok=True)
            
            # อัปเดต task
            task_data['status'] = 'completed'
            task_data['output_file'] = str(output_path)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            
            # บันทึกลง JSON storage
            self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการรวมวิดีโอ: {e}")
            task_data['status'] = 'failed'
            task_data['error_message'] = str(e)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
    
    async def execute_convert_task(self, task_data: Dict[str, Any]):
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
            
            # รัน FFmpeg (run in thread pool)
            await asyncio.to_thread(ffmpeg.run, stream, overwrite_output=True, quiet=True)
            
            # อัปเดต task
            task_data['status'] = 'completed'
            task_data['output_file'] = str(output_path)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            
            # บันทึกลง JSON storage
            self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแปลงรูปแบบ: {e}")
            task_data['status'] = 'failed'
            task_data['error_message'] = str(e)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
    
    async def execute_resize_task(self, task_data: Dict[str, Any]):
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
            
            # รัน FFmpeg (run in thread pool)
            await asyncio.to_thread(ffmpeg.run, stream, overwrite_output=True, quiet=True)
            
            # อัปเดต task
            task_data['status'] = 'completed'
            task_data['output_file'] = str(output_path)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            
            # บันทึกลง JSON storage
            self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการปรับขนาดวิดีโอ: {e}")
            task_data['status'] = 'failed'
            task_data['error_message'] = str(e)
            task_data['completed_at'] = asyncio.get_event_loop().time()
            self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
    
    async def execute_chunk_transcription(self, chunk_task: Dict[str, Any]):
        """ดำเนินการ transcribe chunk"""
        try:
            parent_task_id = chunk_task.get('parent_task_id')
            chunk_path = chunk_task.get('chunk_path')
            chunk_index = chunk_task.get('chunk_index', 0)
            total_chunks = chunk_task.get('total_chunks', 0)
            model_size = chunk_task.get('model_size', 'base')
            language = chunk_task.get('language', 'th')
            chunk_duration = chunk_task.get('chunk_duration', 30)
            initial_prompt = chunk_task.get('initial_prompt')  # ดึง initial_prompt
            
            # ตรวจสอบไฟล์ chunk
            chunk_file = Path(chunk_path)
            if not chunk_file.exists():
                raise FileNotFoundError(f"Chunk file not found: {chunk_path}")
            
            # Transcribe chunk
            logger.info(f"📝 Transcribing chunk {chunk_index+1}/{total_chunks}...")
            if initial_prompt:
                logger.debug(f"   Using initial_prompt: {initial_prompt[:100]}..." if len(initial_prompt) > 100 else f"   Using initial_prompt: {initial_prompt}")
            transcription_result = await self.worker.transcription_service.whisper_service.provider.transcribe(
                str(chunk_path),
                language,
                model_size,
                initial_prompt=initial_prompt  # ส่ง initial_prompt ไปยัง Whisper
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
                result = self.worker.transcription_service.whisper_service._apply_thai_processing(result)
            
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
            self.worker.utils.save_chunk_result(parent_task_id, chunk_index, chunk_data, total_chunks)
            
            logger.info(f"✅ Chunk {chunk_index+1}/{total_chunks} transcribed: text length={len(chunk_data['text'])}, segments={len(chunk_data['segments'])}")
            
        except Exception as e:
            logger.error(f"❌ Error transcribing chunk {chunk_index+1}: {e}", exc_info=True)
            raise
    
    async def execute_audio_chunk_transcription(self, message_data: Dict[str, Any]):
        """ดำเนินการ transcribe audio chunk"""
        try:
            # Backend ใช้ JsonSerializerDefaults.Web (camelCase naming)
            chunk_id = str(message_data.get('chunkId') or message_data.get('ChunkId', ''))
            audio_file_id = str(message_data.get('audioFileId') or message_data.get('AudioFileId', ''))
            audio_file_url = message_data.get('audioFileUrl') or message_data.get('AudioFileUrl')
            meeting_id = str(message_data.get('meetingId') or message_data.get('MeetingId', ''))
            chapter_id = message_data.get('chapterId') or message_data.get('ChapterId')
            if chapter_id:
                chapter_id = str(chapter_id)
            start_time_str = message_data.get('startTime') or message_data.get('StartTime', '00:00:00')
            duration_str = message_data.get('duration') or message_data.get('Duration', '00:00:05')
            chunk_index = message_data.get('chunkIndex') or message_data.get('ChunkIndex', 0)
            
            logger.info(f"เริ่ม transcribe audio chunk {chunk_index} สำหรับ meeting {meeting_id}, audio_file_url: {audio_file_url}")
            
            # Download audio file จาก URL ที่ Backend ส่งมา
            if not audio_file_url:
                logger.error(f"ไม่พบ AudioFileUrl ใน message สำหรับ chunk {chunk_index}")
                return
            
            audio_file_path = await self.worker.utils.download_audio_file_from_url(
                audio_file_url,
                chunk_id
            )
            
            # Transcribe audio chunk ด้วย Whisper
            language = 'th'  # Default ภาษาไทย
            model_size = 'base'  # Default model size
            
            transcription_result = self.worker.transcription_service.whisper_service.transcribe_file(
                audio_file_path,
                model_size=model_size,
                language=language,
                use_thai_processor=True
            )
            
            if not transcription_result:
                logger.error(f"ไม่สามารถ transcribe audio chunk {chunk_index} ได้")
                return
            
            # สร้าง message สำหรับส่งกลับไป Backend (ใช้ camelCase)
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
                "createdAt": datetime.now(timezone.utc).isoformat()
            }
            
            # Publish result กลับไป Backend (ใช้ async publish)
            success = await self.worker.connection.publish(
                exchange=self.worker.connection.transcription_exchange_name,
                routing_key=self.worker.connection.transcription_chunk_completed_routing_key,
                body=json.dumps(result_message).encode('utf-8')
            )
            
            if success:
                logger.info(f"ส่ง transcription result กลับไป Backend: {chunk_id}")
            else:
                logger.error(f"❌ Failed to publish transcription result: {chunk_id}")
            
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
    
    async def execute_transcription_task(self, task_data: Dict[str, Any]):
        """ดำเนินการ transcription"""
        task_id = task_data.get('task_id')
        try:
            file_path = task_data['file_path']
            language = task_data.get('language', 'th')
            model_size = task_data.get('model_size', 'base')
            chunk_duration = task_data.get('chunk_duration', 30)
            use_chunking = task_data.get('use_chunking', False)  # Default: false
            initial_prompt = task_data.get('initial_prompt')  # ดึง initial_prompt
            
            logger.info(f"📂 เริ่ม transcription: {file_path}")
            logger.info(f"   Model: {model_size}, Language: {language}, Chunk Duration: {chunk_duration}s, Use Chunking: {use_chunking}")
            if initial_prompt:
                logger.info(f"   Initial Prompt: {initial_prompt[:100]}..." if len(initial_prompt) > 100 else f"   Initial Prompt: {initial_prompt}")
            
            # สร้าง task object สำหรับ transcription service
            from app.models.transcription import TranscriptionResponse
            
            task = TranscriptionResponse(
                task_id=task_data['task_id'],
                status="processing",
                file_path=file_path,
                file_url=task_data.get('file_url'),
                file_name=task_data.get('file_name'),
                language=language,
                created_at=datetime.now(timezone.utc)
            )
            task.job_id = task_data.get('job_id')
            task.user_id = task_data.get('user_id')
            task.callback_url = task_data.get('callback_url')
            
            # เพิ่ม task เข้าไปใน transcription service
            self.worker.transcription_service.tasks[task_data['task_id']] = task
            
            logger.info(f"🔄 เรียกใช้ transcription service...")
            logger.info(f"   Task ID: {task_data['task_id']}")
            logger.info(f"   File path: {file_path}")
            logger.info(f"   Model: {model_size}, Language: {language}, Chunk Duration: {chunk_duration}s, Use Chunking: {use_chunking}")
            
            # เรียกใช้ transcription service
            try:
                logger.info(f"📞 Calling transcription_service._process_transcription...")
                await self.worker.transcription_service._process_transcription(
                    task_data['task_id'],
                    file_path,
                    language,
                    model_size,
                    chunk_duration,
                    use_chunking=use_chunking,
                    file_url=task_data.get('file_url'),
                    file_name=task_data.get('file_name'),
                    initial_prompt=initial_prompt  # ส่ง initial_prompt
                )
                logger.info(f"✅ transcription_service._process_transcription completed")
            except Exception as e:
                logger.error(f"❌ Error in transcription_service._process_transcription: {e}", exc_info=True)
                raise
            
            # ดึงข้อมูล transcription ที่บันทึกไว้แล้วจาก transcription_service
            max_retries = 10
            retry_delay = 0.5
            existing_transcription = None
            
            for attempt in range(max_retries):
                await asyncio.sleep(retry_delay)
                existing_transcription = self.worker.json_storage.get_transcription(task_data['task_id'])
                
                if existing_transcription:
                    full_text = existing_transcription.get('full_text', '') or ''
                    chunks = existing_transcription.get('chunks', []) or []
                    
                    if full_text or chunks:
                        logger.info(f"📋 Found transcription data (attempt {attempt + 1}/{max_retries}): full_text length={len(full_text)}, chunks count={len(chunks)}")
                        break
                    else:
                        logger.warning(f"⚠️  Transcription data found but empty (attempt {attempt + 1}/{max_retries})")
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
                    task_in_service = self.worker.transcription_service.tasks.get(task_data['task_id'])
                    if task_in_service:
                        logger.info(f"📋 Found task in transcription_service: full_text length={len(task_in_service.full_text) if task_in_service.full_text else 0}, chunks count={len(task_in_service.chunks) if task_in_service.chunks else 0}")
                        full_text = task_in_service.full_text if task_in_service.full_text else ''
                        chunks = [chunk.dict() for chunk in task_in_service.chunks] if task_in_service.chunks else []
                
                # ดึง transcription_time จาก existing_transcription
                transcription_time = existing_transcription.get('transcription_time') or existing_transcription.get('processing_time') or existing_transcription.get('time_used')
                
                # คำนวณ chunks ข้อมูล
                valid_chunks = [c for c in chunks if c is not None]
                total_chunks = len(valid_chunks) if valid_chunks else (existing_transcription.get('total_chunks') or 0)
                
                task_data['status'] = 'completed'
                task_data['completed_at'] = datetime.now(timezone.utc).isoformat()
                task_data['progress'] = 100
                task_data['current_stage'] = 'finalizing'
                task_data['current_stage_description'] = 'การแปลงเสียงเสร็จสมบูรณ์'
                task_data['stage_progress'] = 100
                task_data['full_text'] = full_text
                task_data['chunks'] = chunks
                task_data['total_duration'] = existing_transcription.get('total_duration', task_data.get('total_duration'))
                
                # บันทึก transcription_time ใน task metadata
                if transcription_time:
                    task_data['transcription_time'] = transcription_time
                
                # ตรวจสอบ audio_extraction_time
                if 'audio_extraction_time' not in task_data:
                    audio_extraction_time = existing_transcription.get('audio_extraction_time') if existing_transcription else None
                    task_data['audio_extraction_time'] = audio_extraction_time
                
                # อัปเดต total_chunks และ completed_chunks
                task_data['total_chunks'] = total_chunks if total_chunks > 0 else len(valid_chunks)
                task_data['completed_chunks'] = len(valid_chunks)
                
                # อัปเดต total_tasks และ completed_tasks
                audio_extraction_done = task_data.get('audio_extraction_time') is not None
                total_tasks = (1 if audio_extraction_done else 0) + (total_chunks if total_chunks > 0 else 1)
                completed_tasks = (1 if audio_extraction_done else 0) + len(valid_chunks)
                task_data['total_tasks'] = total_tasks if total_tasks > 0 else 1
                task_data['completed_tasks'] = completed_tasks
                
                # สร้าง task_breakdown ถ้ายังไม่มี
                if 'task_breakdown' not in task_data:
                    task_data['task_breakdown'] = []
                
                # เพิ่ม transcription task ใน task_breakdown ถ้ายังไม่มี
                transcription_task_exists = any(
                    t.get('type') == 'transcription' for t in task_data.get('task_breakdown', [])
                )
                if transcription_time and not transcription_task_exists:
                    task_data['task_breakdown'].append({
                        'type': 'transcription',
                        'status': 'completed',
                        'time': transcription_time,
                        'chunks_count': len(valid_chunks),
                        'completed_at': datetime.now(timezone.utc).isoformat()
                    })
            else:
                # ถ้าไม่มี existing_transcription ให้ลองดึงจาก task object ใน transcription_service
                logger.warning(f"⚠️  No existing transcription data found in storage for {task_id}")
                task_in_service = self.worker.transcription_service.tasks.get(task_data['task_id'])
                if task_in_service:
                    logger.info(f"📋 Found task in transcription_service: full_text length={len(task_in_service.full_text) if task_in_service.full_text else 0}, chunks count={len(task_in_service.chunks) if task_in_service.chunks else 0}")
                    task_data['status'] = 'completed'
                    task_data['completed_at'] = datetime.now(timezone.utc).isoformat()
                    task_data['progress'] = 100
                    task_data['full_text'] = task_in_service.full_text if task_in_service.full_text else ''
                    task_data['chunks'] = [chunk.dict() for chunk in task_in_service.chunks] if task_in_service.chunks else []
                    task_data['total_duration'] = task_in_service.total_duration
                else:
                    logger.error(f"❌ No transcription data found in storage or service for {task_id}")
                    task_data['status'] = 'completed'
                    task_data['completed_at'] = datetime.now(timezone.utc).isoformat()
                    task_data['progress'] = 100
            
            # บันทึกลง JSON storage
            logger.info(f"💾 Saving transcription data: full_text length={len(task_data.get('full_text', ''))}, chunks count={len(task_data.get('chunks', []))}")
            self.worker.json_storage.save_transcription(task_data['task_id'], task_data)
            
            logger.info(f"✅ Transcription completed successfully: {task_id}")
            
        except Exception as e:
            logger.error(f"❌ เกิดข้อผิดพลาดในการ transcription {task_id}: {e}", exc_info=True)
            task_data['status'] = 'failed'
            task_data['error_message'] = str(e)
            task_data['completed_at'] = datetime.now().isoformat()
            task_data['progress'] = 0
            self.worker.json_storage.save_transcription(task_data['task_id'], task_data)

