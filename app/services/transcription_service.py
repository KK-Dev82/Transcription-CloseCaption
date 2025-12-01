import asyncio
import uuid
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import aiohttp
import aiofiles
import json
from urllib.parse import urlparse, unquote
import inspect

from .file_service import FileService
from .whisper_service import WhisperService
from .video_service import VideoService
from .rabbitmq_service import RabbitMQService
from .webhook_service import webhook_service
from .websocket_service import websocket_manager
from ..models.transcription import TranscriptionChunk, TranscriptionResponse
from ..utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(self):
        self.file_service = FileService()
        self.whisper_service = WhisperService()
        self.video_service = VideoService()
        self.rabbitmq_service = RabbitMQService()
        self.webhook_service = webhook_service
        self.json_storage = JSONStorage()
        
        self.tasks: Dict[str, TranscriptionResponse] = {}
        self.task_contexts: Dict[str, Dict[str, Optional[str]]] = {}
        
        # DEPRECATED: ไม่ใช้ api_server_url แล้ว
        # ระบบใช้ SignalR ผ่าน senate-backend แทน WebSocket
        # Transcription service ส่ง callback ไปที่ senate-backend ผ่าน webhook endpoint
        # senate-backend จะส่ง SignalR notification เองหลังจากรับ webhook callback
    
    def _safe_cat(self, a, b) -> str:
        """
        ต่อสตริงแบบกันตาย + ตัดช่องว่างเกิน
        """
        sa = "" if a is None else str(a)
        sb = "" if b is None else str(b)
        s = (sa + " " + sb).strip()
        return s
    
    def _normalize_time_value(self, value) -> float:
        """แปลงค่าเวลาให้เป็น float วินาที"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return 0.0
            # รองรับ timestamp รูปแบบ HH:MM:SS,mmm
            if ":" in cleaned or "," in cleaned:
                try:
                    return self.whisper_service._timestamp_to_seconds(cleaned)
                except Exception:
                    pass
            try:
                return float(cleaned)
            except ValueError:
                try:
                    return float(cleaned.replace(",", "."))
                except ValueError:
                    return 0.0
        return 0.0
    
    def _coerce_optional_float(self, value) -> Optional[float]:
        if value is None:
            return None
        return self._normalize_time_value(value)
    
    def _parse_datetime(self, value) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except Exception:
            try:
                return datetime.fromtimestamp(float(value))
            except Exception:
                return None
    
    def _build_task_from_storage(self, task_id: str, data: Dict, existing: Optional[TranscriptionResponse] = None) -> Optional[TranscriptionResponse]:
        try:
            chunk_entries = data.get("chunks") or []
            chunk_objects: List[TranscriptionChunk] = []
            for chunk in chunk_entries:
                start_value = chunk.get("start_time", chunk.get("start"))
                end_value = chunk.get("end_time", chunk.get("end"))
                chunk_objects.append(
                    TranscriptionChunk(
                        start_time=self._normalize_time_value(start_value),
                        end_time=self._normalize_time_value(end_value),
                        text=str(chunk.get("text", "")),
                        confidence=chunk.get("confidence")
                    )
                )
            
            created_at = self._parse_datetime(data.get("created_at")) or (existing.created_at if existing else datetime.now())
            updated_at = self._parse_datetime(data.get("updated_at"))
            completed_at = self._parse_datetime(data.get("completed_at"))
            
            progress_value = data.get("progress", getattr(existing, "progress", 0) if existing else 0)
            try:
                progress_value = int(progress_value)
            except Exception:
                progress_value = 0
            
            # ถ้า task completed แต่ progress ไม่ใช่ 100 ให้ set เป็น 100
            status = str(data.get("status", getattr(existing, "status", "pending") if existing else "pending"))
            if status == "completed" and progress_value < 100:
                logger.debug(f"⚠️  Task {task_id} is completed but progress={progress_value}, setting to 100")
                progress_value = 100
            
            response = TranscriptionResponse(
                task_id=task_id,
                status=str(data.get("status", getattr(existing, "status", "pending"))),
                file_path=str(data.get("file_path") or getattr(existing, "file_path", "")),
                file_url=data.get("file_url") or getattr(existing, "file_url", None),
                file_name=data.get("file_name") or getattr(existing, "file_name", None),
                total_duration=self._coerce_optional_float(data.get("total_duration")),
                chunks=chunk_objects or None,
                full_text=data.get("full_text"),
                partial_text=data.get("partial_text", getattr(existing, "partial_text", None)),
                language=data.get("language") or getattr(existing, "language", None),
                created_at=created_at,
                completed_at=completed_at,
                error_message=data.get("error_message"),
                progress=progress_value,
                updated_at=updated_at
            )
            
            # เติมข้อมูลที่เก็บไว้เพิ่มเติม
            response.job_id = data.get("job_id", getattr(existing, "job_id", None))
            response.user_id = data.get("user_id", getattr(existing, "user_id", None))
            response.callback_url = data.get("callback_url", getattr(existing, "callback_url", None))
            
            return response
        except Exception as error:
            logger.error(f"ไม่สามารถสร้าง TranscriptionResponse จาก storage สำหรับ task {task_id}: {error}")
            return existing
    
    async def start_transcription(
        self,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        language: str = "th",
        model_size: str = "base",
        chunk_duration: int = 30,
        use_chunking: bool = False,  # Default: false - transcribe ทั้งไฟล์เลย
        callback_url: str = None,
        job_id: int = None,
        user_id: str = None
    ) -> str:
        """เริ่มการแปลงเสียงเป็นข้อความ - ส่งไปยัง RabbitMQ queue"""
        
        # ส่งไปยัง RabbitMQ queue และรับ task_id
        try:
            send_kwargs = dict(
                file_path=file_path,
                file_url=file_url,
                file_name=file_name,
                language=language,
                model_size=model_size,
                chunk_duration=chunk_duration,
                use_chunking=use_chunking,
                job_id=job_id,
                user_id=user_id,
            )

            try:
                signature = inspect.signature(self.rabbitmq_service.send_transcription_task)
                if "callback_url" in signature.parameters and callback_url:
                    send_kwargs["callback_url"] = callback_url
                elif callback_url:
                    logger.warning(
                        "RabbitMQService.send_transcription_task does not accept 'callback_url'. Skipping this parameter to maintain compatibility."
                    )
            except (ValueError, TypeError):
                if callback_url:
                    logger.warning(
                        "Unable to inspect send_transcription_task signature; skipping 'callback_url' parameter."
                    )

            task_id = self.rabbitmq_service.send_transcription_task(**send_kwargs)
            
            # สร้าง task response
            task = TranscriptionResponse(
                task_id=task_id,
                status="pending",
                file_path=file_path or (file_name or file_url or ""),
                file_url=file_url,
                file_name=file_name,
                language=language,
                created_at=datetime.now()
            )
            
            # เก็บ callback_url, job_id สำหรับ callback ภายหลัง
            if callback_url:
                task.callback_url = callback_url
            if job_id:
                task.job_id = job_id
            if user_id:
                task.user_id = user_id
            
            self.tasks[task_id] = task
            self.task_contexts[task_id] = {
                "file_url": file_url,
                "file_name": file_name
            }
            
            logger.info(f"ส่ง transcription task ไปยัง queue: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง task ไปยัง queue: {e}")
            # สร้าง task_id ใหม่สำหรับ error case
            task_id = str(uuid.uuid4())
            task = TranscriptionResponse(
                task_id=task_id,
                status="failed",
                file_path=file_path or (file_name or file_url or ""),
                file_url=file_url,
                file_name=file_name,
                language=language,
                created_at=datetime.now(),
                error_message=str(e)
            )
            self.tasks[task_id] = task
            
            # บันทึกลง storage ด้วย
            try:
                task_data = {
                    "task_id": task_id,
                    "task_type": "transcription",
                    "file_path": file_path,
                    "file_url": file_url,
                    "file_name": file_name,
                    "language": language,
                    "status": "failed",
                    "error_message": str(e),
                    "created_at": datetime.now().timestamp()
                }
                self.json_storage.save_transcription(task_id, task_data)
            except Exception as storage_error:
                logger.error(f"ไม่สามารถบันทึก task ลง storage: {storage_error}")
            
            return task_id
    
    async def _process_transcription(
        self,
        task_id: str,
        file_path: Optional[str],
        language: str,
        model_size: str,
        chunk_duration: int,
        use_chunking: bool = False,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None
    ):
        """ประมวลผลการแปลงเสียง"""
        logger.info(f"🎬 Starting _process_transcription: task_id={task_id}, file_path={file_path}, model={model_size}, language={language}")
        
        if task_id not in self.tasks:
            logger.error(f"❌ Task {task_id} not found in transcription_service.tasks")
            raise ValueError(f"Task {task_id} not found")
        
        task = self.tasks[task_id]
        task.status = "processing"
        logger.info(f"📋 Task object found: status={task.status}, file_path={task.file_path}")
        
        # Note: ไม่ต้องส่ง WebSocket notification จาก transcription-api แล้ว
        # เพราะ senate-backend จะส่ง SignalR notification เองหลังจากรับ webhook callback
        
        chunks: List[str] = []
        local_file_path = file_path
        download_temp_dir: Optional[str] = None
        downloaded_file_path: Optional[str] = None
        
        try:
            # Resolve absolute path ถ้าเป็น relative path
            if local_file_path:
                local_file_path = str(Path(local_file_path).resolve())
                logger.info(f"📂 Resolved file path: {local_file_path}")
            
            # ตรวจสอบไฟล์ ถ้าไม่พบและมี file_url ให้ดาวน์โหลด
            if not local_file_path or not Path(local_file_path).exists():
                logger.warning(f"⚠️ File not found: {local_file_path}")
                if not file_url:
                    raise FileNotFoundError(f"ไฟล์ไม่พบและไม่มี file_url สำหรับงาน {task_id}")
                
                local_file_path, download_temp_dir = await self._download_source_file(
                    task_id,
                    file_url,
                    file_name
                )
                downloaded_file_path = local_file_path
                logger.info("ดาวน์โหลดไฟล์สำเร็จสำหรับ task %s: %s", task_id, local_file_path)
            
            task.file_path = local_file_path
            if file_url:
                task.file_url = file_url
            if file_name:
                task.file_name = file_name
            
            # ดึงข้อมูลไฟล์
            file_info = self.file_service.get_file_info(local_file_path)
            task.total_duration = file_info.get("duration")
            logger.info(f"📊 File info: duration={task.total_duration}s, size={file_info.get('size', 'N/A')} bytes")
            
            # ตรวจสอบว่าใช้ chunking หรือไม่
            if not use_chunking:
                # ⚡ Simplified Flow: Extract audio (ถ้าเป็น video) → Transcribe ทั้งไฟล์เลย (ไม่ chunk)
                logger.info("⚡ Simplified Flow: ไม่ใช้ chunking - จะ transcribe ทั้งไฟล์เลย")
                logger.info(f"   File path: {local_file_path}")
                
                # ตรวจสอบว่าเป็น audio file หรือ video file
                is_audio = self.file_service.is_audio_file(local_file_path)
                is_video = self.file_service.is_video_file(local_file_path)
                logger.info(f"   File type: {'audio' if is_audio else 'video' if is_video else 'unknown'}")
                
                # Extract audio ถ้าเป็น video
                audio_path = local_file_path
                if is_video:
                    logger.info("🎬 ไฟล์เป็น video - กำลัง extract audio...")
                    try:
                        # Extract audio ทั้งไฟล์ (ไม่ chunk)
                        audio_path = self.video_service.extract_audio(local_file_path)
                        logger.info(f"✅ Extract audio สำเร็จ: {audio_path}")
                    except Exception as e:
                        logger.error(f"❌ ไม่สามารถ extract audio ได้: {e}", exc_info=True)
                        raise
                elif not is_audio:
                    logger.warning("⚠️ ไม่ทราบประเภทไฟล์ - ลองใช้ extract_audio()")
                    try:
                        audio_path = self.video_service.extract_audio(local_file_path)
                        logger.info(f"✅ Extract audio สำเร็จ: {audio_path}")
                    except Exception as e:
                        logger.warning(f"⚠️ extract_audio() ล้มเหลว: {e}")
                        # ใช้ไฟล์เดิม (อาจเป็น audio อยู่แล้ว)
                        audio_path = local_file_path
                
                # Transcribe ทั้งไฟล์เลย
                logger.info("🎯 เริ่ม transcription ทั้งไฟล์ (ไม่ chunk)...")
                task.status = "transcribing"
                task.progress = 20
                self.json_storage.save_transcription(task_id, task.__dict__)
                
                try:
                    # เรียกใช้ whisper service โดยตรง (ไม่ผ่าน queue)
                    result = await self.whisper_service.transcribe_file(
                        audio_path,
                        language=language,
                        model_size=model_size
                    )
                    
                    # เก็บผลลัพธ์
                    task.full_text = result.text
                    task.language = result.language
                    task.chunks = result.segments if result.segments else []
                    task.status = "completed"
                    task.progress = 100
                    
                    logger.info(f"✅ Transcription สำเร็จ: text length={len(result.text)}, segments={len(result.segments)}")
                    
                    # บันทึกผลลัพธ์
                    self.json_storage.save_transcription(task_id, task.__dict__)
                    
                    # Cleanup temporary audio file (ถ้า extract จาก video)
                    if audio_path != local_file_path and Path(audio_path).exists():
                        try:
                            Path(audio_path).unlink()
                            logger.info(f"🧹 ลบ temporary audio file: {audio_path}")
                        except Exception as e:
                            logger.warning(f"⚠️ ไม่สามารถลบ temporary audio file: {e}")
                    
                    return
                    
                except Exception as e:
                    logger.error(f"❌ Transcription failed: {e}", exc_info=True)
                    task.status = "failed"
                    task.error_message = str(e)
                    self.json_storage.save_transcription(task_id, task.__dict__)
                    raise
            
            # ⚡ Chunking Flow (use_chunking=true): Extract → Chunk → Queue → Transcribe
            logger.info("📦 Chunking Flow: จะแบ่งไฟล์เป็น chunks และส่งไปยัง queue")
            logger.info(f"   File path: {local_file_path}")
            logger.info(f"   Chunk duration: {chunk_duration}s")
            
            try:
                # ตรวจสอบว่าเป็น audio file หรือ video file
                is_audio = self.file_service.is_audio_file(local_file_path)
                is_video = self.file_service.is_video_file(local_file_path)
                
                logger.info(f"   File type: {'audio' if is_audio else 'video' if is_video else 'unknown'}")
                
                if is_audio:
                    # ถ้าเป็น audio file (ที่ extract แล้วจาก Media Processor)
                    # ใช้ file_service.create_chunks() เพื่อแบ่งเป็น chunks โดยตรง
                    logger.info("📁 ไฟล์เป็น audio file - ใช้ create_chunks() โดยตรง (ไม่ต้อง extract audio)")
                    chunks = self.file_service.create_chunks(local_file_path, chunk_duration)
                elif is_video:
                    # ถ้าเป็น video file ใช้ video_service.extract_audio_chunks()
                    logger.info("🎬 ไฟล์เป็น video file - ใช้ extract_audio_chunks() เพื่อ extract audio ก่อน")
                    chunks = self.video_service.extract_audio_chunks(local_file_path, chunk_duration)
                else:
                    # ถ้าไม่ทราบประเภทไฟล์ ลองใช้ extract_audio_chunks() (รองรับทั้ง video และ audio)
                    logger.warning("⚠️ ไม่ทราบประเภทไฟล์ - ลองใช้ extract_audio_chunks()")
                    try:
                        chunks = self.video_service.extract_audio_chunks(local_file_path, chunk_duration)
                    except Exception as e:
                        logger.warning(f"⚠️ extract_audio_chunks() ล้มเหลว - ลองใช้ create_chunks() แทน: {e}")
                        chunks = self.file_service.create_chunks(local_file_path, chunk_duration)
                
                logger.info(f"✅ สร้าง audio chunks สำเร็จ: {len(chunks)} chunks")
                
                if not chunks or len(chunks) == 0:
                    logger.error(f"❌ ไม่สามารถสร้าง audio chunks ได้ - chunks list is empty!")
                    raise ValueError(f"ไม่สามารถสร้าง audio chunks จากไฟล์ {local_file_path} ได้")
                
                # ตรวจสอบว่า chunks มีไฟล์จริงหรือไม่
                for i, chunk_path in enumerate(chunks[:3]):  # ตรวจสอบแค่ 3 chunks แรก
                    chunk_file = Path(chunk_path)
                    if chunk_file.exists():
                        logger.info(f"   Chunk {i+1}: {chunk_path} exists ({chunk_file.stat().st_size} bytes)")
                    else:
                        logger.error(f"   ❌ Chunk {i+1}: {chunk_path} NOT FOUND!")
                        
            except Exception as e:
                logger.error(f"❌ เกิดข้อผิดพลาดในการสร้าง audio chunks: {e}", exc_info=True)
                raise
            
            # ส่ง chunks ไปยัง queue สำหรับ parallel processing
            logger.info(f"📤 ส่ง {len(chunks)} chunks ไปยัง transcription_chunk_queue สำหรับ parallel processing...")
            task.status = "processing_chunks"
            task.progress = 10  # เริ่มต้น
            
            # Initialize chunks array with None values for workers to fill in
            task.chunks = [None] * len(chunks)
            task_data = task.__dict__
            task_data['chunks'] = [None] * len(chunks)  # Ensure chunks array is initialized
            
            self.json_storage.save_transcription(task_id, task_data)
            
            total_chunks = len(chunks)
            
            # ส่งแต่ละ chunk ไปยัง queue
            for i, chunk_path in enumerate(chunks):
                chunk_task = {
                    "task_id": f"{task_id}_chunk_{i}",
                    "parent_task_id": task_id,
                    "chunk_path": chunk_path,
                    "chunk_index": i,
                    "total_chunks": total_chunks,
                    "chunk_duration": chunk_duration,
                    "model_size": model_size,
                    "language": language,
                    "file_path": local_file_path,
                    "file_name": file_name,
                    "created_at": datetime.now().isoformat()
                }
                
                try:
                    self.rabbitmq_service.send_chunk_transcription_task(chunk_task)
                    logger.info(f"✅ ส่ง chunk {i+1}/{total_chunks} ไปยัง queue: {chunk_path}")
                except Exception as e:
                    logger.error(f"❌ ไม่สามารถส่ง chunk {i+1}/{total_chunks} ไปยัง queue: {e}")
                    # Continue sending other chunks even if one fails
            
            # อัปเดตสถานะ - รอ workers ประมวลผล chunks
            task.status = "waiting_for_chunks"
            task.progress = 15
            self.json_storage.save_transcription(task_id, task.__dict__)
            logger.info(f"📋 ส่ง chunks ทั้งหมดแล้ว - รอ workers ประมวลผล...")
            
            # รอจนกว่าทุก chunks จะเสร็จ (polling)
            # Note: Workers จะอัปเดต progress และ chunks ใน storage
            max_wait_time = 3600  # 1 hour max
            check_interval = 1  # Check every 1 second (เพิ่มความถี่เพื่อให้ progress update บ่อยขึ้น)
            elapsed_time = 0
            last_logged_progress = -1
            last_logged_status = ""
            
            while elapsed_time < max_wait_time:
                await asyncio.sleep(check_interval)
                elapsed_time += check_interval
                
                # ตรวจสอบสถานะจาก storage
                stored_data = self.json_storage.load_transcription(task_id)
                if stored_data:
                    stored_chunks = stored_data.get('chunks', [])
                    current_progress = stored_data.get('progress', 0)
                    current_status = stored_data.get('status', '')
                    
                    # Ensure chunks array has correct size
                    if not stored_chunks or len(stored_chunks) < total_chunks:
                        # Chunks array not initialized yet, continue waiting
                        if elapsed_time % 10 == 0:  # Log every 10 seconds
                            logger.info(f"⏳ Waiting for chunks to be initialized... ({elapsed_time}s elapsed)")
                        continue
                    
                    # ตรวจสอบว่า status เป็น merging_results หรือ completed แล้วหรือยัง
                    if current_status in ["merging_results", "completed"]:
                        logger.info(f"✅ Task reached {current_status} status - chunks processing complete")
                        break
                    
                    # นับ chunks ที่เสร็จแล้ว (ต้องมี text และไม่เป็น None)
                    completed_chunks = sum(1 for c in stored_chunks if c is not None and isinstance(c, dict) and c.get('text') and c.get('text').strip())
                    
                    # ถ้า chunks เสร็จหมดแล้ว แต่ status ยังไม่เป็น merging_results ให้รอต่อ
                    if completed_chunks >= total_chunks:
                        logger.info(f"✅ ทุก chunks เสร็จแล้ว ({completed_chunks}/{total_chunks}) - waiting for status update...")
                        # รออีกสักครู่เพื่อให้ worker อัปเดต status เป็น merging_results
                        await asyncio.sleep(2)
                        # ตรวจสอบอีกครั้ง
                        stored_data = self.json_storage.load_transcription(task_id)
                        if stored_data:
                            current_status = stored_data.get('status', '')
                            if current_status in ["merging_results", "completed"]:
                                logger.info(f"✅ Status updated to {current_status}")
                                break
                        continue
                    
                    # อัปเดต progress (อัปเดตทุกครั้งที่ progress หรือ status เปลี่ยน)
                    if current_progress != task.progress or current_status != task.status:
                        task.progress = current_progress
                        task.status = current_status
                        self.json_storage.save_transcription(task_id, task.__dict__)
                        # Log เฉพาะเมื่อ progress หรือ status เปลี่ยน (ลด log spam)
                        if current_progress != last_logged_progress or current_status != last_logged_status:
                            logger.info(f"📊 Progress: {current_progress}% - Status: {current_status} - Chunks: {completed_chunks}/{total_chunks}")
                            last_logged_progress = current_progress
                            last_logged_status = current_status
                else:
                    if elapsed_time % 10 == 0:  # Log every 10 seconds
                        logger.warning(f"⚠️  ไม่พบ task {task_id} ใน storage (waiting...)")
            
            if elapsed_time >= max_wait_time:
                logger.error(f"❌ Timeout: ไม่สามารถรอ chunks เสร็จได้ภายใน {max_wait_time} วินาที")
                task.status = "timeout"
                task.error_message = f"Timeout waiting for chunks to complete"
                self.json_storage.save_transcription(task_id, task.__dict__)
                return
            
            # ดึงผลลัพธ์จาก storage
            stored_data = self.json_storage.load_transcription(task_id)
            if not stored_data:
                logger.error(f"❌ ไม่พบ task {task_id} ใน storage หลังจาก chunks เสร็จ")
                task.status = "failed"
                task.error_message = "Task data not found after chunks completed"
                self.json_storage.save_transcription(task_id, task.__dict__)
                return
            
            # รวมผลลัพธ์จาก chunks
            logger.info("กำลังรวมผลลัพธ์จาก chunks...")
            stored_chunks = stored_data.get('chunks', [])
            
            # Filter out None chunks and ensure they are dicts
            chunk_results = [c for c in stored_chunks if c is not None and isinstance(c, dict)]
            
            if not chunk_results:
                logger.error(f"❌ ไม่พบ chunk results ที่ถูกต้อง (found {len(stored_chunks)} chunks, {len(chunk_results)} valid)")
                task.status = "failed"
                task.error_message = "No valid chunk results found"
                self.json_storage.save_transcription(task_id, task.__dict__)
                return
            
            logger.info(f"📊 Found {len(chunk_results)} valid chunks out of {len(stored_chunks)} total")
            
            # เรียง chunks ตาม chunk_index (start_time) เพื่อให้ได้ลำดับที่ถูกต้อง (1,2,3,4...)
            # แม้ว่า workers จะประมวลผล parallel และเสร็จไม่ตามลำดับ แต่เราจะเรียงผลลัพธ์ตามลำดับ
            chunk_results_sorted = sorted(chunk_results, key=lambda c: c.get('start_time', 0))
            logger.info(f"✅ Sorted {len(chunk_results_sorted)} chunks by start_time (order: 1,2,3,4...)")
            
            # เก็บ partial results
            partial_text = ""
            partial_chunks = []
            
            # Process chunks ที่ได้จาก storage (เรียงตามลำดับแล้ว)
            for i, chunk_data in enumerate(chunk_results_sorted):
                try:
                    # chunk_data มาจาก storage ที่ workers บันทึกไว้แล้ว
                    if not isinstance(chunk_data, dict):
                        logger.warning(f"⚠️  Chunk {i+1} is not a dict: {type(chunk_data)}")
                        continue
                    chunk_text = chunk_data.get("text", "") or ""
                    chunk_segments = chunk_data.get("segments", []) or []
                    
                    logger.info(f"📋 Processing stored chunk {i+1}/{total_chunks}: text length={len(chunk_text)}, segments={len(chunk_segments)}")
                    
                    # สร้าง partial results สำหรับ real-time display
                    if chunk_segments:
                        for segment in chunk_segments:
                            start_time = self._normalize_time_value(segment.get("start_time", segment.get("start", 0)))
                            end_time = self._normalize_time_value(segment.get("end_time", segment.get("end", 0)))
                            chunk_obj = {
                                "start_time": start_time,
                                "end_time": end_time,
                                "text": segment.get("text", ""),
                                "confidence": segment.get("confidence", segment.get("avg_logprob"))
                            }
                            partial_chunks.append(chunk_obj)
                    
                    # รวมข้อความที่แปลงได้
                    if chunk_text:
                        partial_text = self._safe_cat(partial_text, chunk_text)
                        partial_text = partial_text.strip()
                    
                except Exception as e:
                    logger.error(f"เกิดข้อผิดพลาดในการประมวลผล chunk {i} จาก storage: {e}")
            
            # เก็บ partial results ใน task
            task.partial_text = partial_text
            task.chunks = partial_chunks
            
            # รวมผลลัพธ์
            logger.info("กำลังรวมผลลัพธ์...")
            logger.info(f"📊 Chunk results summary: total={len(chunk_results)}, "
                       f"with_text={sum(1 for r in chunk_results if r and r.get('text') and r.get('text').strip())}, "
                       f"with_segments={sum(1 for r in chunk_results if r and r.get('segments'))}, "
                       f"errors={sum(1 for r in chunk_results if r and 'error' in r)}")
            
            task.progress = 90
            task.status = "merging_results"
            self.json_storage.save_transcription(task_id, task.__dict__)
            
            # Ensure chunk_results is not None or empty before merging
            if not chunk_results:
                logger.error(f"❌ No valid chunk results to merge")
                task.status = "failed"
                task.error_message = "No valid chunk results to merge"
                self.json_storage.save_transcription(task_id, task.__dict__)
                return
            
            logger.info(f"🔄 Merging {len(chunk_results)} chunks...")
            merged_result = self.whisper_service.merge_transcriptions(
                chunk_results, chunk_duration
            )
            
            if not merged_result:
                logger.error(f"❌ merge_transcriptions returned None or empty result")
                task.status = "failed"
                task.error_message = "Failed to merge chunk results"
                self.json_storage.save_transcription(task_id, task.__dict__)
                return
            
            merged_text = merged_result.get("text", "") or ""
            merged_segments = merged_result.get("segments", []) or []
            logger.info(f"📊 Merged result: text length={len(merged_text)}, segments count={len(merged_segments)}")
            if merged_text:
                logger.info(f"   Text preview: {merged_text[:200]}...")
            else:
                logger.warning(f"⚠️  Merged result has no text!")
                logger.warning(f"   Chunk results details:")
                for i, chunk_result in enumerate(chunk_results):
                    if chunk_result:
                        if "error" in chunk_result:
                            logger.warning(f"   Chunk {i+1}: ERROR - {chunk_result.get('error')}")
                        else:
                            chunk_text = chunk_result.get("text", "") or ""
                            chunk_segments = chunk_result.get("segments", []) or []
                            logger.warning(f"   Chunk {i+1}: text length={len(chunk_text)}, segments count={len(chunk_segments)}")
                    else:
                        logger.warning(f"   Chunk {i+1}: None/Empty")
            
            # แปลงเป็น TranscriptionChunk objects
            task.chunks = []
            if "segments" in merged_result and merged_result["segments"]:
                logger.info(f"📦 Converting {len(merged_result['segments'])} segments to TranscriptionChunk objects...")
                for segment in merged_result["segments"]:
                    chunk = TranscriptionChunk(
                        start_time=self._normalize_time_value(segment.get("start")),
                        end_time=self._normalize_time_value(segment.get("end")),
                        text=segment.get("text", ""),
                        confidence=segment.get("avg_logprob", None)
                    )
                    task.chunks.append(chunk)
                logger.info(f"✅ Created {len(task.chunks)} TranscriptionChunk objects")
            else:
                logger.warning(f"⚠️  No segments found in merged result. Merged result keys: {list(merged_result.keys())}")
                # ถ้าไม่มี segments แต่มี text ให้สร้าง chunk เดียว
                if merged_result.get("text") and merged_result.get("text").strip():
                    logger.warning(f"⚠️  Creating single chunk from text (no segments available)")
                    task.chunks = [TranscriptionChunk(
                        start_time=0.0,
                        end_time=task.total_duration or 0.0,
                        text=merged_result.get("text", ""),
                        confidence=None
                    )]
            
            task.full_text = merged_result.get("text", "") or ""
            task.progress = 95
            task.status = "finalizing"
            task.updated_at = datetime.now()
            
            logger.info(f"📋 Final task data - full_text length: {len(task.full_text)}, chunks count: {len(task.chunks)}")
            if task.full_text:
                logger.info(f"   Full text preview: {task.full_text[:200]}...")
            else:
                logger.error(f"❌ Final task data has NO full_text!")
            
            # แปลง task เป็น dict ที่ JSON serializable ได้
            chunks_list = [chunk.dict() for chunk in task.chunks] if task.chunks else []
            task_data = {
                "task_id": task.task_id,
                "status": task.status,
                "file_path": task.file_path,
                "file_url": task.file_url,
                "file_name": task.file_name,
                "total_duration": task.total_duration,
                "chunks": chunks_list,
                "full_text": task.full_text,
                "language": task.language,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "error_message": task.error_message,
                "progress": task.progress
            }
            
            # บันทึกข้อมูลทันทีหลังจาก merge เสร็จ (ก่อนที่ video_worker จะดึงข้อมูล)
            logger.info(f"💾 Saving transcription to storage: task_id={task_id}, full_text length={len(task.full_text) if task.full_text else 0}, chunks count={len(chunks_list)}")
            try:
                self.json_storage.save_transcription(task_id, task_data)
                logger.info(f"✅ Transcription saved to storage successfully: {task_id}")
                
                # Verify that data was saved correctly
                verify_data = self.json_storage.get_transcription(task_id)
                if verify_data:
                    verify_full_text = verify_data.get('full_text', '') or ''
                    verify_chunks = verify_data.get('chunks', []) or []
                    logger.info(f"✅ Verified saved data: full_text length={len(verify_full_text)}, chunks count={len(verify_chunks)}")
                    
                    # Log final results summary
                    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    logger.info(f"🎉 Transcription completed successfully: {task_id}")
                    logger.info(f"   📝 Full text: {len(verify_full_text)} characters")
                    logger.info(f"   📦 Chunks: {len(verify_chunks)} segments")
                    logger.info(f"   ⏱️  Duration: {task.total_duration} seconds")
                    if verify_full_text:
                        logger.info(f"   📄 Text preview: {verify_full_text[:300]}...")
                    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                else:
                    logger.error(f"❌ Verification failed: Could not retrieve saved data for {task_id}")
            except Exception as e:
                logger.error(f"❌ Failed to save transcription to storage: {e}", exc_info=True)
                raise
            
            task.status = "completed"
            task.progress = 100
            task.completed_at = datetime.now()
            
            # 🧹 ลบ temp files หลังเสร็จสิ้น
            try:
                self.file_service.cleanup_temp_files(chunks)
                logger.info(f"ลบ temp files สำเร็จ: {len(chunks)} files")
            except Exception as e:
                logger.warning(f"ไม่สามารถลบ temp files: {e}")
            
            # 📞 Callback to Backend (ถ้ามี callback_url)
            # Note: ไม่ต้องส่ง WebSocket notification จาก transcription-api แล้ว
            # เพราะ senate-backend จะส่ง SignalR notification เองหลังจากรับ webhook callback
            if hasattr(task, 'callback_url') and task.callback_url:
                try:
                    await self._send_callback(task, "completed")
                except Exception as e:
                    logger.warning(f"Backend callback failed: {e}")
            
            # บันทึกข้อมูลสุดท้าย - อัปเดต metadata เพิ่มเติม (job_id, user_id, callback_url)
            # Note: full_text และ chunks ถูกบันทึกไปแล้วที่บรรทัด 470
            logger.info("กำลังบันทึกผลลัพธ์สุดท้าย (metadata update)...")
            
            # คำนวณ processing time
            completed_time = datetime.now()
            created_time = task.created_at if task.created_at else completed_time
            processing_time_seconds = (completed_time - created_time).total_seconds()
            
            final_data = {
                "task_id": task.task_id,
                "status": "completed",  # อัปเดต status เป็น completed
                "file_path": task.file_path,
                "file_url": task.file_url,
                "file_name": task.file_name,
                "total_duration": task.total_duration,
                "chunks": [chunk.dict() for chunk in task.chunks] if task.chunks else [],
                "full_text": task.full_text,
                "partial_text": task.partial_text,
                "language": task.language,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "start_time": task.created_at.isoformat() if task.created_at else None,  # Alias for compatibility
                "completed_at": completed_time.isoformat(),  # อัปเดต completed_at
                "end_time": completed_time.isoformat(),  # Alias for compatibility
                "updated_at": completed_time.isoformat(),
                "processing_time": processing_time_seconds,  # เวลาที่ใช้ในการประมวลผล (วินาที)
                "result_time": processing_time_seconds,  # Alias for compatibility
                "error_message": task.error_message,
                "progress": 100,  # อัปเดต progress เป็น 100
                "job_id": getattr(task, "job_id", None),
                "user_id": getattr(task, "user_id", None),
                "callback_url": getattr(task, "callback_url", None)
            }
            
            # บันทึก metadata อัปเดต (จะ merge กับข้อมูลเดิม)
            logger.info(f"💾 Updating final metadata: task_id={task_id}, full_text length={len(task.full_text) if task.full_text else 0}, chunks count={len(final_data['chunks'])}")
            self.json_storage.save_transcription(task_id, final_data)
            
            logger.info(f"✅ แปลงเสียงเสร็จสิ้น: {task_id}")
            
            # ลบไฟล์ชั่วคราวหลังจากประมวลผลเสร็จแล้ว (ปิดไว้เพื่อ debug)
            # if 'chunks' in locals():
            #     self.file_service.cleanup_temp_files(chunks)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแปลงเสียง {task_id}: {e}")
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            
            # Note: ไม่ต้องส่ง WebSocket notification จาก transcription-api แล้ว
            # เพราะ senate-backend จะส่ง SignalR notification เองหลังจากรับ webhook callback
            
            # ลบไฟล์ชั่วคราวในกรณีเกิดข้อผิดพลาด (ปิดไว้เพื่อ debug)
            # if 'chunks' in locals():
            #     self.file_service.cleanup_temp_files(chunks)
        finally:
            context = self.task_contexts.get(task_id, {})
            if downloaded_file_path:
                try:
                    Path(downloaded_file_path).unlink(missing_ok=True)
                    logger.info("ลบไฟล์ที่ดาวน์โหลดสำหรับ task %s: %s", task_id, downloaded_file_path)
                except Exception as cleanup_error:
                    logger.warning("ไม่สามารถลบไฟล์ที่ดาวน์โหลด (%s): %s", downloaded_file_path, cleanup_error)
            if download_temp_dir:
                try:
                    self.file_service.cleanup_temp_folder(download_temp_dir)
                except Exception as cleanup_dir_error:
                    logger.warning("ไม่สามารถลบ temp folder %s: %s", download_temp_dir, cleanup_dir_error)
            extra_download_dir = context.get("download_temp_dir")
            if extra_download_dir and extra_download_dir != download_temp_dir:
                try:
                    self.file_service.cleanup_temp_folder(extra_download_dir)
                except Exception as extra_cleanup_error:
                    logger.warning("ไม่สามารถลบ temp folder ที่เก็บไว้ใน context (%s): %s", extra_download_dir, extra_cleanup_error)
            if task_id in self.task_contexts:
                self.task_contexts.pop(task_id, None)
    
    async def _download_source_file(
        self,
        task_id: str,
        file_url: str,
        file_name: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """ดาวน์โหลดไฟล์จาก URL มาเก็บแบบชั่วคราว"""
        logger.info("เริ่มดาวน์โหลดไฟล์จาก URL สำหรับ task %s: %s", task_id, file_url)
        download_root = self.file_service.temp_dir / f"download_{task_id}"
        download_root.mkdir(parents=True, exist_ok=True)
        
        resolved_name = file_name
        if not resolved_name:
            parsed = urlparse(file_url)
            candidate = Path(unquote(parsed.path)).name
            resolved_name = candidate or f"{task_id}"
        destination = download_root / resolved_name
        
        timeout = aiohttp.ClientTimeout(total=60 * 30)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(file_url) as response:
                    if response.status != 200:
                        body = await response.text()
                        raise RuntimeError(f"ดาวน์โหลดไฟล์ไม่สำเร็จ (status: {response.status}): {body}")
                    
                    async with aiofiles.open(destination, 'wb') as file_obj:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            await file_obj.write(chunk)
            
            try:
                os.chmod(destination, 0o644)
            except Exception as chmod_error:
                logger.warning("ตั้งค่า permission ให้ไฟล์ดาวน์โหลดไม่สำเร็จ (%s): %s", destination, chmod_error)
            
            self.task_contexts.setdefault(task_id, {})["download_temp_dir"] = str(download_root)
            return str(destination), str(download_root)
        except Exception:
            if destination.exists():
                try:
                    destination.unlink()
                except Exception as cleanup_error:
                    logger.warning("ไม่สามารถลบไฟล์ที่ดาวน์โหลดไม่สำเร็จ (%s): %s", destination, cleanup_error)
            raise

    def get_task_status(self, task_id: str) -> Optional[TranscriptionResponse]:
        """ดึงสถานะของ task พร้อม fallback ไปยัง storage"""
        # ดึงข้อมูลจาก storage เสมอ (เพราะ Video Worker update storage โดยตรง)
        # Memory cache อาจไม่ sync กับ storage เมื่อ task กำลัง processing
        stored_data = self.json_storage.load_transcription(task_id)
        existing_task = self.tasks.get(task_id)
        
        if stored_data:
            # Log สำหรับ debugging
            logger.debug(f"📋 Loaded task {task_id} from storage: status={stored_data.get('status')}, progress={stored_data.get('progress')}, full_text length={len(stored_data.get('full_text', '') or '')}, chunks count={len(stored_data.get('chunks', []) or [])}")
            
            # Build task จาก storage data (priority สูงสุด)
            task = self._build_task_from_storage(task_id, stored_data, existing=existing_task)
            if task:
                # Update memory cache เพื่อให้เร็วขึ้นในครั้งถัดไป
                self.tasks[task_id] = task
                logger.debug(f"✅ Built task {task_id}: status={task.status}, progress={task.progress}")
                return task
            else:
                logger.warning(f"⚠️  Failed to build task {task_id} from storage data")
        else:
            logger.debug(f"⚠️  No storage data found for task {task_id}")
        
        # Fallback: ถ้าไม่มีใน storage แต่มีใน memory (สำหรับ pending tasks ที่ยังไม่เริ่ม)
        if existing_task:
            logger.debug(f"📋 Using memory cache for task {task_id}: status={existing_task.status}, progress={existing_task.progress}")
            return existing_task
        
        logger.warning(f"❌ Task {task_id} not found in storage or memory")
        return None
    
    def get_all_tasks(self) -> List[TranscriptionResponse]:
        """ดึงรายการ tasks ทั้งหมด"""
        responses: List[TranscriptionResponse] = []
        seen_ids = set()
        
        # โหลดจาก storage ทั้งหมดก่อน
        stored_tasks = self.json_storage.list_all_transcriptions()
        for stored in stored_tasks:
            task_id = stored.get("task_id")
            if not task_id:
                continue
            task = self._build_task_from_storage(task_id, stored, existing=self.tasks.get(task_id))
            if task:
                self.tasks[task_id] = task
                responses.append(task)
                seen_ids.add(task_id)
        
        # เติม tasks ที่อยู่ในหน่วยความจำ แต่ยังไม่อยู่ใน storage list
        for task_id, task in self.tasks.items():
            if task_id not in seen_ids:
                responses.append(task)
        
        return responses
    
    async def cancel_task(self, task_id: str) -> bool:
        """ยกเลิก task"""
        logger.info(f"🛑 Attempting to cancel task: {task_id}")
        
        # ตรวจสอบจาก storage ก่อน (เพราะ task อาจถูก load จาก storage)
        stored_data = self.json_storage.load_transcription(task_id)
        if stored_data:
            current_status = stored_data.get('status', '')
            logger.info(f"   Task status from storage: {current_status}")
            
            # ตรวจสอบว่าสามารถยกเลิกได้หรือไม่
            # รองรับ status: pending, processing, processing_chunks, waiting_for_chunks, processing_chunk_*, merging_results
            cancellable_statuses = ["pending", "processing", "processing_chunks", "waiting_for_chunks", "merging_results"]
            is_cancellable = (
                current_status in cancellable_statuses or 
                current_status.startswith("processing_chunk_")
            )
            
            if is_cancellable:
                # อัปเดตสถานะเป็น cancelled
                stored_data['status'] = 'cancelled'
                stored_data['completed_at'] = datetime.now().isoformat()
                stored_data['updated_at'] = datetime.now().isoformat()
                self.json_storage.save_transcription(task_id, stored_data)
                
                # อัปเดตใน memory cache ด้วย
                if task_id in self.tasks:
                    self.tasks[task_id].status = "cancelled"
                    self.tasks[task_id].completed_at = datetime.now()
                
                logger.info(f"✅ Task {task_id} cancelled successfully")
                return True
            elif current_status == "cancelled":
                logger.info(f"⚠️  Task {task_id} is already cancelled")
                return True  # ถ้ายกเลิกแล้วก็ถือว่าสำเร็จ
            else:
                logger.warning(f"⚠️  Cannot cancel task {task_id} with status: {current_status}")
                return False
        
        # ตรวจสอบจาก memory cache
        if task_id in self.tasks:
            task = self.tasks[task_id]
            # รองรับ status: pending, processing, processing_chunks, waiting_for_chunks, processing_chunk_*, merging_results
            cancellable_statuses = ["pending", "processing", "processing_chunks", "waiting_for_chunks", "merging_results"]
            is_cancellable = (
                task.status in cancellable_statuses or 
                task.status.startswith("processing_chunk_")
            )
            
            if is_cancellable:
                task.status = "cancelled"
                task.completed_at = datetime.now()
                
                # บันทึกลง storage ด้วย
                task_data = task.__dict__
                task_data['status'] = 'cancelled'
                task_data['completed_at'] = datetime.now().isoformat()
                task_data['updated_at'] = datetime.now().isoformat()
                self.json_storage.save_transcription(task_id, task_data)
                
                logger.info(f"✅ Task {task_id} cancelled successfully")
                return True
            elif task.status == "cancelled":
                logger.info(f"⚠️  Task {task_id} is already cancelled")
                return True
            else:
                logger.warning(f"⚠️  Cannot cancel task {task_id} with status: {task.status}")
                return False
        
        logger.warning(f"⚠️  Task {task_id} not found")
        return False
    
    def cleanup_tasks(
        self,
        max_age_hours: int = 24,
        statuses: Optional[List[str]] = None
    ) -> int:
        """ลบ tasks ตามสถานะที่กำหนด (ค่าเริ่มต้นล้าง completed/failed/cancelled)"""
        if statuses is None or not statuses:
            statuses = ["completed", "failed", "cancelled"]
        
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        removed_count = 0
        tasks_to_remove: List[str] = []
        
        for task_id, task in list(self.tasks.items()):
            try:
                created_ts = task.created_at.timestamp() if task.created_at else 0
            except Exception:
                created_ts = 0
            if task.status in statuses and created_ts < cutoff_time:
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            removed_count += 1
            self.tasks.pop(task_id, None)
            self.task_contexts.pop(task_id, None)
            try:
                self.json_storage.delete_transcription(task_id)
            except Exception as storage_error:
                logger.warning(f"ไม่สามารถลบ transcription {task_id} จาก storage: {storage_error}")
        
        logger.info(
            "ลบ tasks เก่า %s รายการ (statuses=%s, max_age_hours=%s)",
            removed_count,
            statuses,
            max_age_hours
        )
        return removed_count
    
    def cleanup_tasks(
        self,
        statuses: Optional[List[str]] = None,
        max_age_hours: Optional[float] = None
    ) -> Dict[str, object]:
        """ลบ tasks ทั้งจากหน่วยความจำและ storage ตามเงื่อนไข"""
        removed_ids: List[str] = []
        failed_ids: List[str] = []
        now = datetime.now()
        
        status_set = {status.strip().lower() for status in statuses} if statuses else None
        age_threshold: Optional[datetime] = None
        if max_age_hours is not None and max_age_hours >= 0:
            age_threshold = now - timedelta(hours=max_age_hours)
        
        all_tasks = self.json_storage.list_all_transcriptions()
        for task_metadata in all_tasks:
            task_id = task_metadata.get("task_id")
            if not task_id:
                continue
            
            status_value = str(task_metadata.get("status", "")).lower()
            if status_set and status_value not in status_set:
                continue
            
            created_at_value = task_metadata.get("created_at")
            created_at = self._parse_datetime(created_at_value)
            if age_threshold and created_at and created_at > age_threshold:
                continue
            
            try:
                self.tasks.pop(task_id, None)
                self.json_storage.delete_transcription(task_id)
                removed_ids.append(task_id)
            except Exception as cleanup_error:
                logger.warning("ไม่สามารถลบ task %s จาก storage ได้: %s", task_id, cleanup_error)
                failed_ids.append(task_id)
        
        logger.info(
            "ลบ transcription tasks จาก storage แล้ว %s รายการ (fail %s)",
            len(removed_ids),
            len(failed_ids)
        )
        
        return {
            "removed_count": len(removed_ids),
            "failed_count": len(failed_ids),
            "removed_task_ids": removed_ids,
            "failed_task_ids": failed_ids
        }
    
    # ฟังก์ชันใหม่สำหรับการค้นหา
    def search_transcription(self, task_id: str, query: str, 
                           case_sensitive: bool = False) -> List[Dict]:
        """ค้นหาข้อความใน transcription"""
        return self.json_storage.search_transcription(task_id, query, case_sensitive)
    
    def search_all_transcriptions(self, query: str, 
                                case_sensitive: bool = False) -> List[Dict]:
        """ค้นหาข้อความใน transcription ทั้งหมด"""
        return self.json_storage.search_all_transcriptions(query, case_sensitive)
    
    def get_transcription_stats(self, task_id: str) -> Dict:
        """ดึงสถิติของ transcription"""
        return self.json_storage.get_transcription_stats(task_id)
    
    def list_all_transcriptions(self) -> List[Dict]:
        """ดึงรายการ transcription ทั้งหมด"""
        return self.json_storage.list_all_transcriptions()
    
    def delete_transcription(self, task_id: str) -> bool:
        """ลบ transcription"""
        # ลบจาก memory
        if task_id in self.tasks:
            del self.tasks[task_id]
        
        # ลบจาก JSON storage
        return self.json_storage.delete_transcription(task_id)
    
    # DEPRECATED: ไม่ใช้ WebSocket notification แล้ว
    # ระบบใช้ SignalR ผ่าน senate-backend แทน
    # Transcription service ส่ง callback ไปที่ senate-backend ผ่าน webhook endpoint
    # senate-backend จะส่ง SignalR notification เองหลังจากรับ webhook callback
    # async def _notify_api_server(self, event_type: str, task_id: str, data: dict):
    #     """ส่ง notification ไปยัง API server เพื่อ broadcast ผ่าน WebSocket"""
    #     pass
    
    async def _send_callback(self, task, status: str):
        """ส่ง callback ไปยัง Backend เมื่อเสร็จสิ้น"""
        import httpx
        
        try:
            callback_url = task.callback_url
            if not callback_url:
                return
            
            # ดึงข้อมูลจาก task object
            full_text = getattr(task, 'full_text', '') or ''
            chunks = getattr(task, 'chunks', []) or []
            
            # ถ้าไม่มีข้อมูลใน task object ให้ลองดึงจาก storage
            if not full_text or not chunks:
                logger.warning(f"⚠️ Task object missing data for callback: full_text length={len(full_text)}, chunks count={len(chunks)}")
                stored_data = self.json_storage.get_transcription(task.task_id)
                if stored_data:
                    logger.info(f"📋 Loading data from storage for callback: task_id={task.task_id}")
                    if not full_text:
                        full_text = stored_data.get('full_text', '') or ''
                    if not chunks:
                        chunks = stored_data.get('chunks', []) or []
                    logger.info(f"📋 Loaded from storage: full_text length={len(full_text)}, chunks count={len(chunks)}")
            
            # เตรียมข้อมูลสำหรับ callback
            segments = []
            if chunks:
                # ถ้า chunks เป็น list of dict
                if isinstance(chunks[0], dict):
                    segments = [
                        {
                            "start_time": chunk.get("start_time") or chunk.get("start"),
                            "end_time": chunk.get("end_time") or chunk.get("end"),
                            "text": chunk.get("text", ""),
                            "confidence": chunk.get("confidence")
                        }
                        for chunk in chunks
                    ]
                # ถ้า chunks เป็น TranscriptionChunk objects
                else:
                    segments = [
                        {
                            "start_time": chunk.start_time,
                            "end_time": chunk.end_time,
                            "text": chunk.text,
                            "confidence": getattr(chunk, 'confidence', None)
                        }
                        for chunk in chunks
                    ]
            
            # ตรวจสอบว่ามีข้อมูลจริงก่อนส่ง callback
            if not full_text and not segments:
                logger.error(f"❌ Cannot send callback: No transcription data available for task {task.task_id}")
                logger.error(f"   full_text: {len(full_text)} chars, segments: {len(segments)} items")
                return
            
            payload = {
                "jobId": getattr(task, 'job_id', None),
                "taskId": task.task_id,
                "status": status,
                "text": full_text,
                "segments": segments,
                "audioDuration": getattr(task, 'total_duration', None),
                "wordCount": len(full_text.split()) if full_text else 0,
                "averageConfidence": None,  # คำนวณได้ถ้าต้องการ
                "completedAt": datetime.now().isoformat()
            }
            
            logger.info(f"📤 Sending callback: job_id={payload['jobId']}, task_id={task.task_id}, text_length={len(full_text)}, segments_count={len(segments)}")
            
            # ส่ง callback
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(
                    "ส่ง callback ไปยัง Backend: job_id=%s task_id=%s status=%s url=%s",
                    payload["jobId"],
                    task.task_id,
                    status,
                    callback_url
                )
                response = await client.post(callback_url, json=payload)
                
                if response.status_code == 200:
                    logger.info(f"✅ Backend callback sent successfully to {callback_url}")
                else:
                    logger.warning(f"⚠️ Backend callback failed: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"❌ Failed to send backend callback: {e}") 