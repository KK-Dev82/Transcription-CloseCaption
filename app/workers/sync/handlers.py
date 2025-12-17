"""
Message Handlers (Pika - Blocking)

จัดการ message handlers สำหรับ RabbitMQ queues ทั้งหมด (9 handlers)
"""
import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
import pika

logger = logging.getLogger(__name__)


class MessageHandlers:
    """Message handlers สำหรับ RabbitMQ queues"""
    
    def __init__(self, worker):
        """
        Initialize message handlers
        
        Args:
            worker: Worker instance ที่มี services, storage, processors, utils
        """
        self.worker = worker
    
    def _process_trim_task(self, ch, method, properties, body):
        """ประมวลผล trim video task"""
        try:
            task_data = json.loads(body.decode('utf-8'))
            logger.info(f"เริ่มประมวลผล trim task: {task_data.get('task_id')}")
            
            # อัปเดตสถานะเป็น processing
            task_data['status'] = 'processing'
            self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
            
            # ประมวลผลการตัดวิดีโอ - สร้าง event loop ใหม่เพื่อป้องกัน conflict
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.worker.processors.execute_trim_task(task_data))
            finally:
                loop.close()
                asyncio.set_event_loop(None)
            
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
            self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
            
            # ประมวลผลการรวมวิดีโอ - สร้าง event loop ใหม่เพื่อป้องกัน conflict
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.worker.processors.execute_merge_task(task_data))
            finally:
                loop.close()
                asyncio.set_event_loop(None)
            
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
            self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
            
            # ประมวลผลการแปลงรูปแบบ - สร้าง event loop ใหม่เพื่อป้องกัน conflict
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.worker.processors.execute_convert_task(task_data))
            finally:
                loop.close()
                asyncio.set_event_loop(None)
            
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
            self.worker.json_storage.save_video_task(task_data['task_id'], task_data)
            
            # ประมวลผลการปรับขนาดวิดีโอ - สร้าง event loop ใหม่เพื่อป้องกัน conflict
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.worker.processors.execute_resize_task(task_data))
            finally:
                loop.close()
                asyncio.set_event_loop(None)
            
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
    
    def _process_audio_chunk_extracted(self, ch, method, properties, body):
        """ประมวลผล audio chunk extracted message (จาก Backend)"""
        try:
            message_data = json.loads(body.decode('utf-8'))
            # Backend ใช้ JsonSerializerDefaults.Web (camelCase)
            chunk_id = message_data.get('chunkId') or message_data.get('ChunkId')
            logger.info(f"รับ audio chunk extracted message: {chunk_id}")
            
            # ประมวลผล audio chunk และ transcribe
            # สร้าง event loop ใหม่เพื่อป้องกัน conflict
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.worker.processors.execute_audio_chunk_transcription(message_data))
            finally:
                loop.close()
                asyncio.set_event_loop(None)
            
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
            logger.info(f"   Active chunks in executor: {len(self.worker.active_chunks)}")
            
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
            logger.info(f"   Active chunks in executor: {len(self.worker.active_chunks)}")
            
            # ส่งไปยัง thread pool เพื่อประมวลผล parallel (ไม่ block)
            future = self.worker.executor.submit(
                self.worker.utils.execute_chunk_transcription_sync,
                chunk_task,
                ch,
                delivery_tag
            )
            self.worker.active_chunks[delivery_tag] = future
            
            logger.info(f"🚀 Chunk {chunk_index+1}/{total_chunks} submitted to thread pool (total active: {len(self.worker.active_chunks)})")
            
            # Acknowledge message ทันที (ไม่รอให้เสร็จ) เพื่อให้ worker รับ message ใหม่ได้
            # ⚠️ หมายเหตุ: ถ้า task fail จะไม่สามารถ requeue ได้ แต่จะบันทึก error ใน storage
            try:
                if ch and not ch.is_closed:
                    ch.basic_ack(delivery_tag=delivery_tag)
                    logger.info(f"✅ Chunk {chunk_index+1}/{total_chunks} acknowledged - processing in background (active: {len(self.worker.active_chunks)})")
                else:
                    logger.warning(f"⚠️ Channel is closed, cannot acknowledge chunk task")
            except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed,
                    pika.exceptions.AMQPConnectionError, AttributeError) as ack_error:
                logger.error(f"❌ Cannot acknowledge chunk task: {ack_error}")
                # ถ้า acknowledge ไม่ได้ ให้ cancel future
                if delivery_tag in self.worker.active_chunks:
                    self.worker.active_chunks[delivery_tag].cancel()
                    del self.worker.active_chunks[delivery_tag]
            
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
            if delivery_tag in self.worker.active_chunks:
                del self.worker.active_chunks[delivery_tag]
    
    def _process_audio_extraction_task(self, ch, method, properties, body):
        """
        ประมวลผล audio extraction task (3-Queue Architecture: Stage 2)
        
        Logic:
        1. Extract audio from video file
        2. Send audio file to transcription_queue
        """
        def process_in_thread():
            task_id = None
            try:
                task_data = json.loads(body.decode('utf-8'))
                task_id = task_data.get('task_id')
                test_mode = task_data.get('test_mode', False)
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
                if test_mode:
                    logger.info(f"🧪 [TEST MODE] Test message: {task_data.get('test_message', 'N/A')}")
                logger.info(f"   Video file: {video_file_path}")
                logger.info("=" * 80)
                
                # Update status
                task_data['status'] = 'extracting_audio' if not test_mode else 'routing_to_transcription'
                task_data['progress'] = 15 if not test_mode else 25
                self.worker.json_storage.save_transcription(task_id, task_data)
                
                # Extract audio (skip for test mode)
                if test_mode:
                    logger.info(f"🧪 [TEST MODE] Skipping audio extraction - using fake audio path")
                    audio_path = f"/tmp/test_audio_{task_id}.wav"  # Fake path for test
                    extraction_time = 0.0
                else:
                    # Check file exists
                    if not video_file_path or not Path(video_file_path).exists():
                        raise FileNotFoundError(f"Video file not found: {video_file_path}")
                    
                    # Extract audio using VideoService (uses Thread Pool)
                    logger.info(f"🎬 [Audio Extraction] Starting audio extraction...")
                    import time
                    extraction_start_time = time.time()
                    audio_path = self.worker.video_service.extract_audio(video_file_path, task_id=task_id)
                    extraction_time = time.time() - extraction_start_time
                    logger.info(f"✅ [Audio Extraction] Audio extracted: {audio_path}")
                    logger.info(f"   ⏱️  ใช้เวลา: {extraction_time:.2f} วินาที")
                    
                    # บันทึก audio_extraction_time ใน task metadata
                    task_data['audio_extraction_time'] = extraction_time
                    
                    # Initialize task_breakdown ถ้ายังไม่มี
                    if 'task_breakdown' not in task_data:
                        task_data['task_breakdown'] = []
                    
                    # เพิ่ม audio extraction task ใน task_breakdown
                    task_data['task_breakdown'].append({
                        'type': 'audio_extraction',
                        'status': 'completed',
                        'time': extraction_time,
                        'completed_at': datetime.now(timezone.utc).isoformat()
                    })
                    
                    # อัปเดต total_tasks และ completed_tasks
                    task_data['total_tasks'] = task_data.get('total_tasks', 0) + 1  # Audio extraction task
                    task_data['completed_tasks'] = task_data.get('completed_tasks', 0) + 1
                
                # Update status
                task_data['status'] = 'routing_to_transcription'
                task_data['progress'] = 25
                self.worker.json_storage.save_transcription(task_id, task_data)
                
                # Send to transcription_queue
                # หมายเหตุ: ไม่ส่ง status ใน message เพราะจะถูก set โดย transcription processor
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
                    # ไม่ส่ง status เพราะจะถูก set โดย transcription processor
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "audio_extracted_from": video_file_path  # Track original video
                }
                
                # Add test_mode flag to transcription message
                if test_mode:
                    transcription_message['test_mode'] = True
                    transcription_message['test_message'] = task_data.get('test_message', 'Test message')
                
                logger.info(f"📤 [Audio Extraction] Sending to transcription_queue: {task_id}")
                # ใช้ safe_publish สำหรับ publishing จาก threads (thread-safe)
                success = self.worker.connection._safe_publish(
                    exchange='',
                    routing_key=self.worker.connection.transcription_queue,
                    body=json.dumps(transcription_message)
                )
                if success:
                    logger.info(f"✅ [Audio Extraction] Sent to transcription_queue: {task_id}")
                else:
                    logger.error(f"❌ [Audio Extraction] Failed to send to transcription_queue: {task_id}")
                
                # Acknowledge message
                try:
                    if ch and not ch.is_closed:
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        logger.info(f"✅ [Audio Extraction] Acknowledged message: {task_id}")
                except Exception as ack_error:
                    logger.error(f"❌ [Audio Extraction] Failed to acknowledge: {ack_error}")
                    
            except Exception as e:
                logger.error(f"❌ [Audio Extraction] Error processing extraction task {task_id}: {e}", exc_info=True)
                
                # Update task status to failed
                try:
                    if task_id:
                        task_data['status'] = 'failed'
                        task_data['error_message'] = str(e)
                        self.worker.json_storage.save_transcription(task_id, task_data)
                except Exception as save_error:
                    logger.error(f"❌ [Audio Extraction] Failed to save error status: {save_error}")
                
                # Cleanup resources
                try:
                    # Cleanup any temporary files
                    if 'video_file_path' in locals() and video_file_path and Path(video_file_path).exists():
                        # Don't delete source file, just log
                        logger.debug(f"Source file still exists: {video_file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ [Audio Extraction] Cleanup error: {cleanup_error}")
                
                # Nack message
                try:
                    if ch and not ch.is_closed:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    else:
                        logger.warning(f"⚠️ [Audio Extraction] Channel is closed, cannot nack message")
                except Exception as nack_error:
                    logger.error(f"❌ [Audio Extraction] Failed to nack message: {nack_error}")
        
        # Process in separate thread
        thread = threading.Thread(target=process_in_thread, daemon=True)
        thread.start()
    
    def _process_transcription_request_task(self, ch, method, properties, body):
        """
        ประมวลผล transcription request task (3-Queue Architecture: Stage 1)
        
        Logic:
        1. Download file from file_url
        2. Check file type (video/audio)
        3. Route to appropriate queue:
           - Video → audio_extraction_queue
           - Audio → transcription_queue
        """
        def process_in_thread():
            task_id = None
            try:
                task_data = json.loads(body.decode('utf-8'))
                task_id = task_data.get('task_id')
                test_mode = task_data.get('test_mode', False)
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
                
                logger.info("=" * 80)
                logger.info(f"🎯 [Download & Route] Processing transcription request: {task_id}")
                if test_mode:
                    logger.info(f"🧪 [TEST MODE] Test message: {task_data.get('test_message', 'N/A')}")
                logger.info(f"   File URL: {file_url}")
                logger.info(f"   File Path: {file_path}")
                logger.info("=" * 80)
                
                # Update status
                task_data['status'] = 'downloading' if not test_mode else 'routing'
                task_data['progress'] = 5 if not test_mode else 10
                self.worker.json_storage.save_transcription(task_id, task_data)
                
                # Step 1: Download file (ถ้าไม่มี file_path หรือ file_path ไม่มีอยู่)
                # Skip download if test mode
                local_file_path = file_path
                if test_mode:
                    logger.info(f"🧪 [TEST MODE] Skipping file download - using test file path")
                    local_file_path = f"/tmp/test_{task_id}.mp4"  # Fake path for test
                elif file_url:
                    if not local_file_path or not Path(local_file_path).exists():
                        logger.info(f"📥 [Download & Route] Downloading file from URL: {file_url}")
                        # สร้าง event loop ใหม่เพื่อป้องกัน conflict
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            local_file_path, _ = loop.run_until_complete(
                                self.worker.transcription_service._download_source_file(task_id, file_url, file_name)
                            )
                        finally:
                            loop.close()
                            asyncio.set_event_loop(None)
                        logger.info(f"✅ [Download & Route] File downloaded: {local_file_path}")
                    else:
                        logger.info(f"✅ [Download & Route] Using existing file: {local_file_path}")
                elif not local_file_path or not Path(local_file_path).exists():
                    raise FileNotFoundError(f"ไฟล์ไม่พบและไม่มี file_url: {file_path}")
                
                # Update status
                task_data['file_path'] = local_file_path
                task_data['status'] = 'routing'
                task_data['progress'] = 10
                self.worker.json_storage.save_transcription(task_id, task_data)
                
                # Step 2: Check file type (skip for test mode)
                is_video = True  # Default to video for test mode
                is_audio = False
                if not test_mode:
                    from app.services.file_service import FileService
                    file_service = FileService()
                    is_video = file_service.is_video_file(local_file_path)
                    is_audio = file_service.is_audio_file(local_file_path)
                
                logger.info(f"🔍 [Download & Route] File type: {'video' if is_video else 'audio' if is_audio else 'unknown'}")
                if test_mode:
                    logger.info(f"🧪 [TEST MODE] Treating as video file for test flow")
                
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
                    "created_at": datetime.now().isoformat()
                }
                
                # Add test_mode flag to route message
                if test_mode:
                    route_message['test_mode'] = True
                    route_message['test_message'] = task_data.get('test_message', 'Test message')
                
                if is_video:
                    # Route to audio_extraction_queue
                    logger.info(f"📤 [Download & Route] Routing {'test' if test_mode else 'video'} file to audio_extraction_queue")
                    success = self.worker.connection._safe_publish(
                        exchange='',
                        routing_key=self.worker.connection.audio_extraction_queue,
                        body=json.dumps(route_message)
                    )
                    if success:
                        logger.info(f"✅ [Download & Route] Routed to audio_extraction_queue: {task_id}")
                    else:
                        logger.error(f"❌ [Download & Route] Failed to route to audio_extraction_queue: {task_id}")
                elif is_audio:
                    # Route directly to transcription_queue
                    logger.info(f"📤 [Download & Route] Routing audio file to transcription_queue")
                    success = self.worker.connection._safe_publish(
                        exchange='',
                        routing_key=self.worker.connection.transcription_queue,
                        body=json.dumps(route_message)
                    )
                    if success:
                        logger.info(f"✅ [Download & Route] Routed to transcription_queue: {task_id}")
                    else:
                        logger.error(f"❌ [Download & Route] Failed to route to transcription_queue: {task_id}")
                else:
                    # Unknown file type - try to route to extraction first
                    logger.warning(f"⚠️ [Download & Route] Unknown file type - routing to audio_extraction_queue")
                    success = self.worker.connection._safe_publish(
                        exchange='',
                        routing_key=self.worker.connection.audio_extraction_queue,
                        body=json.dumps(route_message)
                    )
                    if not success:
                        logger.error(f"❌ [Download & Route] Failed to route: {task_id}")
                
                # Acknowledge message
                try:
                    if ch and not ch.is_closed:
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        logger.info(f"✅ [Download & Route] Acknowledged message: {task_id}")
                except Exception as ack_error:
                    logger.error(f"❌ [Download & Route] Failed to acknowledge: {ack_error}")
                    
            except Exception as e:
                logger.error(f"❌ [Download & Route] Error processing request task {task_id}: {e}", exc_info=True)
                try:
                    if ch and not ch.is_closed:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                except Exception as nack_error:
                    logger.error(f"❌ [Download & Route] Failed to nack message: {nack_error}")
        
        # Process in separate thread
        thread = threading.Thread(target=process_in_thread, daemon=True)
        thread.start()
    
    def _process_transcription_task(self, ch, method, properties, body):
        """ประมวลผล transcription task - ใช้ threading เพื่อให้ worker รับงานใหม่ได้ทันที"""
        
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
                test_mode = task_data.get('test_mode', False)
                file_path = task_data.get('file_path', 'N/A')
                model_size = task_data.get('model_size', 'base')
                language = task_data.get('language', 'th')
                use_chunking = task_data.get('use_chunking', False)  # Default: false
                
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.info(f"🎬 เริ่มประมวลผล transcription task: {task_id}")
                if test_mode:
                    logger.info(f"🧪 [TEST MODE] Test message: {task_data.get('test_message', 'N/A')}")
                logger.info(f"   File: {file_path}")
                logger.info(f"   Model: {model_size}, Language: {language}")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                # Skip actual transcription for test mode
                if test_mode:
                    logger.info(f"🧪 [TEST MODE] Skipping actual transcription - test flow completed")
                    # Update status to completed for test
                    task_data['status'] = 'completed'
                    task_data['progress'] = 100
                    task_data['test_completed'] = True
                    self.worker.json_storage.save_transcription(task_id, task_data)
                    # Acknowledge message
                    try:
                        if ch and not ch.is_closed:
                            ch.basic_ack(delivery_tag=method.delivery_tag)
                            logger.info(f"✅ [TEST MODE] Test transcription task completed and acknowledged: {task_id}")
                        else:
                            logger.warning(f"⚠️ Channel is closed, cannot acknowledge test message")
                    except Exception as ack_error:
                        logger.error(f"❌ [TEST MODE] Failed to acknowledge test message: {ack_error}")
                    return  # Exit early for test mode
                
                # ตรวจสอบว่า task นี้ถูกประมวลผลไปแล้วหรือไม่ (ป้องกัน duplicate processing)
                existing_task = self.worker.json_storage.get_transcription(task_id)
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
                self.worker.json_storage.save_transcription(task_id, task_data)
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
                            task_info = self.worker.json_storage.get_transcription(task_id)
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
                # สร้าง event loop ใหม่สำหรับ thread นี้ (ไม่ใช้ asyncio.run() เพราะอาจมี conflict)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.worker.processors.execute_transcription_task(task_data))
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)
                
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
                                time.sleep(0.5)  # Wait a bit before retry
                    except (pika.exceptions.StreamLostError, pika.exceptions.ConnectionClosed, 
                            pika.exceptions.AMQPConnectionError, AttributeError, IndexError) as ack_error:
                        logger.warning(f"⚠️ Cannot acknowledge message (attempt {ack_attempt + 1}/{max_ack_retries}): {ack_error}")
                        if ack_attempt < max_ack_retries - 1:
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
