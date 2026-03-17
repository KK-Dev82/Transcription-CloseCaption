"""
Transcription Service - จัดการ transcription tasks
"""
import asyncio
import logging
import os
from typing import Dict, Optional
from datetime import datetime, timezone
from pathlib import Path
import aiohttp
import json

from .whisper_service import WhisperService
from .file_service import FileService
from ..utils.storage_factory import StorageFactory
from ..models.transcription import TranscriptionResponse

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service สำหรับจัดการ transcription tasks"""
    
    def __init__(self):
        self.whisper_service = WhisperService()
        self.file_service = FileService()
        # ใช้ StorageFactory เพื่อเลือก storage ตาม STORAGE_TYPE (sqlite หรือ json)
        self.storage = StorageFactory.create_storage()
        self.tasks: Dict[str, TranscriptionResponse] = {}
        storage_type = os.getenv('STORAGE_TYPE', 'json').lower()
        logger.info(f"✅ TranscriptionService initialized (storage: {storage_type})")
    
    async def _process_transcription(
        self,
        task_id: str,
        file_path: str,
        language: str = "th",
        model_size: str = "base",
        chunk_duration: int = 30,
        use_chunking: bool = False,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None
    ):
        """
        ประมวลผล transcription
        
        Args:
            task_id: Task ID
            file_path: Path ไปยังไฟล์ audio/video
            language: ภาษา (th, en, auto)
            model_size: ขนาด model (base, small, medium, large)
            chunk_duration: ความยาว chunk (วินาที) - ใช้เมื่อ use_chunking=True
            use_chunking: ใช้ chunking หรือไม่
            file_url: URL ของไฟล์ (optional)
            file_name: ชื่อไฟล์ (optional)
        """
        try:
            task = self.tasks.get(task_id)
            if not task:
                logger.error(f"❌ Task {task_id} not found")
                return
            
            # อัปเดตสถานะ
            task.status = "processing"
            task.progress = 10
            self._save_task(task)
            
            # ตรวจสอบไฟล์
            if not Path(file_path).exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            logger.info(f"📝 Starting transcription: {file_path}")
            logger.info(f"   Model: {model_size}, Language: {language}")
            logger.info(f"   Use chunking: {use_chunking}, Chunk duration: {chunk_duration}s")
            
            # ประมวลผล transcription
            if use_chunking:
                # ใช้ chunking
                result = await self._process_with_chunking(
                    task_id, file_path, language, model_size, chunk_duration
                )
            else:
                # ประมวลผลทั้งไฟล์เลย
                result = await self._process_full_file(
                    task_id, file_path, language, model_size
                )
            
            # อัปเดตผลลัพธ์
            task.status = "completed"
            task.progress = 100
            task.full_text = result.get("text", "")
            # Convert segments to chunks format
            segments = result.get("segments", [])
            if segments:
                from app.models.transcription import TranscriptionChunk
                task.chunks = [
                    TranscriptionChunk(
                        start_time=seg.get("start", 0),
                        end_time=seg.get("end", 0),
                        text=seg.get("text", ""),
                        confidence=seg.get("confidence")
                    )
                    for seg in segments
                ]
            task.total_duration = result.get("total_duration", 0)
            task.completed_at = datetime.now(timezone.utc)
            self._save_task(task)
            
            logger.info(f"✅ Transcription completed: {task_id}")
            
            # ส่ง webhook callback ถ้ามี callback_url
            if task.callback_url:
                await self._send_callback(task, "completed")
            
        except Exception as e:
            logger.error(f"❌ Error processing transcription {task_id}: {e}", exc_info=True)
            task = self.tasks.get(task_id)
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.now(timezone.utc)
                self._save_task(task)
                
                # ส่ง webhook callback สำหรับ error
                if task.callback_url:
                    await self._send_callback(task, "failed")
            raise
    
    async def _process_full_file(
        self,
        task_id: str,
        file_path: str,
        language: str,
        model_size: str
    ) -> Dict:
        """ประมวลผลทั้งไฟล์เลย (ไม่ใช้ chunking)"""
        logger.info(f"🔄 Processing full file (no chunking)...")
        
        # อัปเดต progress
        task = self.tasks.get(task_id)
        if task:
            task.progress = 20
            self._save_task(task)
        
        # ใช้ WhisperService โดยตรง - รันใน thread pool เพื่อไม่ block event loop
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.whisper_service.transcribe_file(
            file_path,
            model_size=model_size,
            language=language,
            use_thai_processor=True
            )
        )
        
        return result
    
    async def _process_with_chunking(
        self,
        task_id: str,
        file_path: str,
        language: str,
        model_size: str,
        chunk_duration: int
    ) -> Dict:
        """ประมวลผลด้วย chunking (เร็วกว่า full file)"""
        logger.info(f"🔄 Processing with chunking (chunk_duration={chunk_duration}s)...")
        
        try:
            task = self.tasks.get(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # อัปเดต progress
            task.progress = 20
            self._save_task(task)
            
            # แปลงไฟล์เป็น WAV 16k mono ก่อน chunking (ข้ามถ้าตรง format อยู่แล้ว)
            import time
            conversion_start_time = time.time()
            from app.services.video_service import VideoService
            video_service = VideoService()
            
            logger.info(f"🎬 Preparing audio for chunking (extract/convert if needed)...")
            audio_path = video_service.extract_audio(file_path, task_id)
            conversion_time = time.time() - conversion_start_time
            logger.info(f"✅ Audio conversion completed in {conversion_time:.2f}s")
            
            # แบ่งไฟล์เป็น chunks (ใช้ VideoService.create_chunks)
            chunk_start_time = time.time()
            logger.info(f"📦 Creating chunks from {audio_path}...")
            chunks = video_service.create_chunks(audio_path, chunk_duration, task_id=task_id)
            total_chunks = len(chunks)
            chunk_time = time.time() - chunk_start_time
            logger.info(f"✅ Created {total_chunks} chunks in {chunk_time:.2f}s")
            
            # อัปเดต progress
            task.progress = 30
            self._save_task(task)
            
            # Transcribe แต่ละ chunk โดยส่งเป็น RQ jobs แยก (ใช้ 4 GPUs)
            logger.info(f"📝 Enqueueing {total_chunks} chunks as separate RQ jobs (4 GPUs)...")
            chunk_results = []
            
            # ใช้ Redis Queue Service เพื่อส่ง chunks แต่ละตัวเป็น job แยก
            from app.services.redis_queue_service import get_redis_queue_service
            queue_service = get_redis_queue_service()
            
            # จำนวน GPUs สำหรับ round-robin
            num_gpus = int(os.getenv('NUM_GPUS', '4'))
            logger.info(f"🎯 Distributing {total_chunks} chunks across {num_gpus} GPUs (round-robin)")
            
            # Enqueue chunks แต่ละตัวเป็น job แยก
            chunk_job_ids = []
            for i, chunk_path in enumerate(chunks):
                chunk_task_id = f"{task_id}_chunk_{i}"
                
                # Round-robin: ส่งไปยัง GPU queue ตาม index
                gpu_index = i % num_gpus
                worker_gpu = f'gpu{gpu_index}'
                
                try:
                    job_id = queue_service.enqueue_transcription(
                        task_id=chunk_task_id,
                        file_path=chunk_path,
                        language=language,
                        model_size=model_size,
                        chunk_duration=chunk_duration,
                        priority=False,
                        worker_gpu=worker_gpu  # ระบุ GPU queue
                    )
                    chunk_job_ids.append((i, chunk_task_id, job_id, worker_gpu))
                    logger.debug(f"   Chunk {i+1}/{total_chunks} enqueued to {worker_gpu} (job: {job_id[:16]}...)")
                except Exception as e:
                    logger.error(f"❌ Failed to enqueue chunk {i+1}: {e}")
                    # Fallback: ส่งไป default queue
                    try:
                        job_id = queue_service.enqueue_transcription(
                            task_id=chunk_task_id,
                            file_path=chunk_path,
                            language=language,
                            model_size=model_size,
                            chunk_duration=chunk_duration,
                            priority=False,
                            worker_gpu=None  # default queue
                        )
                        chunk_job_ids.append((i, chunk_task_id, job_id, 'default'))
                    except Exception as e2:
                        logger.error(f"❌ Failed to enqueue chunk {i+1} to default queue: {e2}")
            
            logger.info(f"✅ Enqueued {len(chunk_job_ids)}/{total_chunks} chunks to RQ queues")
            
            # รอผลลัพธ์จาก RQ jobs
            import asyncio
            import time
            from rq import Queue
            from redis import Redis
            from rq.job import Job
            
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
            conn = Redis.from_url(redis_url, decode_responses=False)
            
            # รอผลลัพธ์จากทุก chunks
            completed_chunks = {}
            start_wait_time = time.time()
            max_wait_time = 3600  # 1 hour timeout
            
            logger.info(f"⏳ Waiting for {len(chunk_job_ids)} chunks to complete...")
            
            while len(completed_chunks) < len(chunk_job_ids):
                for chunk_index, chunk_task_id, job_id, worker_gpu in chunk_job_ids:
                    if chunk_index in completed_chunks:
                        continue
                    
                    try:
                        job = Job.fetch(job_id, connection=conn)
                        status = job.get_status()
                        
                        if status == 'finished':
                            result = job.result
                            if result and isinstance(result, dict):
                                text = result.get('text', '')
                                segments = result.get('segments', [])
                                processing_time = result.get('processing_time', 0)
                                
                                completed_chunks[chunk_index] = {
                                    "index": chunk_index,
                                    "text": text,
                                    "segments": segments,
                                    "start_time": chunk_index * chunk_duration,
                                    "end_time": (chunk_index + 1) * chunk_duration,
                                    "transcribe_time": processing_time
                                }
                                logger.info(f"✅ Chunk {chunk_index+1}/{total_chunks} completed (from {worker_gpu})")
                                
                                # อัปเดต progress
                                progress = 30 + int((len(completed_chunks) / total_chunks) * 50)
                                task.progress = progress
                                self._save_task(task)
                        elif status == 'failed':
                            logger.error(f"❌ Chunk {chunk_index+1} failed")
                            completed_chunks[chunk_index] = {
                                "index": chunk_index,
                                "text": "",
                                "segments": [],
                                "start_time": chunk_index * chunk_duration,
                                "end_time": (chunk_index + 1) * chunk_duration,
                                "transcribe_time": 0
                            }
                    except Exception as e:
                        logger.debug(f"Chunk {chunk_index+1} still processing...")
                
                # ตรวจสอบ timeout
                if time.time() - start_wait_time > max_wait_time:
                    logger.error(f"⏰ Timeout waiting for chunks (>{max_wait_time}s)")
                    break
                
                # รอสักครู่ก่อนตรวจสอบอีกครั้ง
                await asyncio.sleep(1)
            
            # เรียงลำดับตาม index
            chunk_results = [completed_chunks[i] for i in sorted(completed_chunks.keys())]
            
            logger.info(f"✅ All {len(chunk_results)}/{total_chunks} chunks completed")
            
            # รวมผลลัพธ์ (ยังไม่ใช้ Thai processor)
            import time
            merge_start_time = time.time()
            logger.info(f"📊 Merging {total_chunks} chunks...")
            merged_result = self.whisper_service.merge_transcriptions(
                chunk_results,
                chunk_duration
            )
            merge_time = time.time() - merge_start_time
            logger.info(f"✅ Merge completed in {merge_time:.2f}s")
            
            # อัปเดต progress
            task.progress = 90
            self._save_task(task)
            
            # ⚠️ ใช้ Thai processor หลังจาก merge แล้ว (แยกจากเส้นทาง GPU)
            if language == "th":
                thai_start_time = time.time()
                logger.info(f"🇹🇭 Applying Thai processor to merged result...")
                merged_result = self.whisper_service._apply_thai_processing(merged_result)
                thai_time = time.time() - thai_start_time
                logger.info(f"✅ Thai processing completed in {thai_time:.2f}s")
            
            # อัปเดต progress
            task.progress = 95
            self._save_task(task)
            
            # สรุป timing
            total_transcribe_time = sum(r.get("transcribe_time", 0) for r in chunk_results)
            logger.info(f"📊 Timing summary:")
            logger.info(f"   - Total transcribe time: {total_transcribe_time:.2f}s")
            logger.info(f"   - Merge time: {merge_time:.2f}s")
            if language == "th":
                logger.info(f"   - Thai processing time: {thai_time:.2f}s")
            logger.info(f"✅ Chunking completed: {len(merged_result.get('segments', []))} segments")
            return merged_result
            
        except Exception as e:
            logger.error(f"❌ Error in chunking: {e}", exc_info=True)
            # Fallback to full file processing
            logger.warning("⚠️  Falling back to full file processing")
        return await self._process_full_file(task_id, file_path, language, model_size)
    
    def _save_task(self, task: TranscriptionResponse):
        """บันทึก task ลง storage"""
        try:
            # Handle chunks - TranscriptionResponse uses 'chunks' not 'segments'
            chunks = []
            if hasattr(task, 'chunks') and task.chunks:
                try:
                    chunks = [chunk.dict() if hasattr(chunk, 'dict') else chunk for chunk in task.chunks]
                except:
                    chunks = task.chunks if isinstance(task.chunks, list) else []
            
            task_dict = {
                "task_id": task.task_id,
                "status": task.status,
                "progress": getattr(task, 'progress', 0),
                "file_path": getattr(task, 'file_path', None),
                "file_url": getattr(task, 'file_url', None),
                "file_name": getattr(task, 'file_name', None),
                "language": getattr(task, 'language', 'th'),
                "model_size": getattr(task, 'model_size', 'base'),  # Ensure model_size is saved
                "full_text": getattr(task, 'full_text', ''),
                "chunks": chunks,
                "total_duration": getattr(task, 'total_duration', 0),
                "error_message": getattr(task, 'error_message', None),
                "current_stage": getattr(task, 'current_stage', None),
                "current_stage_description": getattr(task, 'current_stage_description', None),
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if hasattr(task, 'completed_at') and task.completed_at else None,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            self.storage.save_transcription(task.task_id, task_dict)
            logger.debug(f"✅ Task {task.task_id} saved to storage")
        except Exception as e:
            logger.error(f"❌ Error saving task: {e}", exc_info=True)
    
    async def _send_callback(self, task: TranscriptionResponse, status: str):
        """
        ส่ง webhook callback ไปยัง callback_url
        
        Args:
            task: TranscriptionResponse object
            status: "completed" หรือ "failed"
        """
        if not task.callback_url:
            return
        
        try:
            # เตรียม payload (ให้ตรงกับข้อมูลที่ Backend ต้องการ)
            payload = {
                "task_id": task.task_id,
                "status": status,
                "progress": getattr(task, 'progress', 100 if status == "completed" else 0),
                "file_path": getattr(task, 'file_path', None),
                "file_name": getattr(task, 'file_name', None),
                "language": getattr(task, 'language', 'th'),
                "model_size": getattr(task, 'model_size', 'base'),
                "source": getattr(task, 'source', None),  # "upload" | "video_record" | "fe_cc" — ให้ผู้รับ callback รู้ประเภทไฟล์
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": task.completed_at.isoformat() if hasattr(task, 'completed_at') and task.completed_at else None,
            }
            
            # เพิ่มข้อมูลตาม status
            if status == "completed":
                payload.update({
                    "full_text": getattr(task, 'full_text', ''),
                    "chunks_count": len(getattr(task, 'chunks', [])),
                    "total_duration": getattr(task, 'total_duration', 0),
                    "error_message": None,
                    "current_stage": None,
                    "current_stage_description": None,
                })
                # เพิ่ม chunks ถ้ามี
                if hasattr(task, 'chunks') and task.chunks:
                    try:
                        chunks = [chunk.dict() if hasattr(chunk, 'dict') else chunk for chunk in task.chunks]
                        payload["chunks"] = chunks
                    except:
                        pass
            elif status == "failed":
                payload.update({
                    "full_text": getattr(task, 'full_text', ''),
                    "chunks": [],
                    "chunks_count": 0,
                    "total_duration": getattr(task, 'total_duration', 0),
                    "error_message": getattr(task, 'error_message', 'Unknown error'),
                    "current_stage": None,
                    "current_stage_description": None,
                })
            
            # ส่ง HTTP POST request
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    task.callback_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status < 400:
                        logger.info(f"✅ Webhook callback sent successfully: {task.callback_url} (Status: {response.status})")
                    else:
                        response_text = await response.text()
                        logger.warning(f"⚠️  Webhook callback returned {response.status}: {response_text[:200]}")
                        
        except aiohttp.ClientError as e:
            logger.error(f"❌ Error sending webhook callback to {task.callback_url}: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected error sending webhook callback: {e}", exc_info=True)

