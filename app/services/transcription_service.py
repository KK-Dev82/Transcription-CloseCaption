import asyncio
import uuid
import logging
import os
import time
from datetime import datetime, timedelta, timezone
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
from .redis_queue_service import RedisQueueService
from .webhook_service import webhook_service
from .websocket_service import websocket_manager
from .dictionary_service import DictionaryService
from .prompt_builder import PromptBuilder
from ..models.transcription import TranscriptionChunk, TranscriptionResponse
# ไม่ใช้ JSONStorage โดยตรงแล้ว ใช้ StorageFactory แทน
# from ..utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

def utc_now():
    """Helper function to get current UTC time with timezone"""
    return datetime.now(timezone.utc)

class TranscriptionService:
    def __init__(self):
        self.file_service = FileService()
        self.whisper_service = WhisperService()
        self.video_service = VideoService()
        self.redis_queue_service = RedisQueueService()
        self.webhook_service = webhook_service
        
        # ใช้ StorageFactory เพื่อเลือก storage ตาม STORAGE_TYPE (SQLite หรือ JSON)
        from ..utils.storage_factory import get_storage
        self.json_storage = get_storage()  # จะได้ SQLiteStorage หรือ JSONStorage ตาม env
        
        # Dictionary และ Prompt services สำหรับ initial_prompt
        self.dictionary_service = DictionaryService()
        self.prompt_builder = PromptBuilder()
        
        self.tasks: Dict[str, TranscriptionResponse] = {}
        self.task_contexts: Dict[str, Dict[str, Optional[str]]] = {}
        
        # Temporary files management: default ไม่เก็บไฟล์ชั่วคราว (ประหยัด volume)
        self.save_temp_files = os.getenv('SAVE_TEMP_FILES', 'not_save').lower() == 'save'
        logger.info(f"📁 Temporary files management: {'SAVE' if self.save_temp_files else 'DELETE (default)'}")
        
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
    
    async def _build_initial_prompt(
        self,
        enable_initial_prompt: bool,
        initial_prompt: Optional[str],
        use_backend_dictionary: bool,
        dictionary_scope: str,
        dictionary_max_words: int,
        user_id: Optional[str],
        language: str
    ) -> Optional[str]:
        """
        สร้าง initial_prompt จาก Dictionary หรือใช้ prompt ที่ส่งมา
        
        Args:
            enable_initial_prompt: เปิดใช้ initial_prompt หรือไม่
            initial_prompt: initial_prompt โดยตรง (ถ้ามีจะใช้แทน Dictionary)
            use_backend_dictionary: ใช้ Dictionary จาก Backend API หรือไม่
            dictionary_scope: "Global" หรือ "Personal"
            dictionary_max_words: จำนวนคำสูงสุดจาก Dictionary
            user_id: User ID (สำหรับ Personal scope)
            language: ภาษา (สำหรับ filter Dictionary)
        
        Returns:
            Optional[str]: initial_prompt string หรือ None
        """
        # ถ้าไม่เปิดใช้ initial_prompt
        if not enable_initial_prompt:
            return None
        
        # ถ้ามี initial_prompt โดยตรง ให้ใช้ทันที
        if initial_prompt:
            logger.info(f"📝 Using provided initial_prompt (length: {len(initial_prompt)} chars)")
            return initial_prompt.strip() if initial_prompt.strip() else None
        
        # ถ้าไม่ใช้ Backend Dictionary
        if not use_backend_dictionary:
            logger.debug("⚠️ initial_prompt enabled but use_backend_dictionary=False, returning None")
            return None
        
        # ดึง Dictionary words จาก Backend
        try:
            logger.info(
                f"📚 Fetching dictionary words from Backend "
                f"(scope={dictionary_scope}, user_id={user_id or 'None'}, max_words={dictionary_max_words})"
            )
            
            dictionary_words = await self.dictionary_service.fetch_dictionary_words(
                user_id=user_id if dictionary_scope == "Personal" else None,
                scope=dictionary_scope,
                language="thai" if language == "th" else language,
                limit=dictionary_max_words
            )
            
            if not dictionary_words:
                logger.warning("⚠️ No dictionary words fetched from Backend, returning None")
                return None
            
            # สร้าง initial_prompt จาก Dictionary words
            prompt = self.prompt_builder.build_initial_prompt(
                dictionary_words=dictionary_words,
                context=None,
                max_words=dictionary_max_words,
                include_common_phrases=True
            )
            
            if prompt:
                logger.info(f"✅ Built initial_prompt from Dictionary ({len(dictionary_words)} words → {len(prompt.split())} words in prompt)")
            else:
                logger.warning("⚠️ Failed to build initial_prompt from Dictionary words")
            
            return prompt
            
        except Exception as e:
            logger.error(f"❌ Error building initial_prompt from Dictionary: {e}", exc_info=True)
            return None
    
    def _build_task_from_storage(self, task_id: str, data: Dict, existing: Optional[TranscriptionResponse] = None) -> Optional[TranscriptionResponse]:
        try:
            chunk_entries = data.get("chunks") or []
            chunk_objects: List[TranscriptionChunk] = []
            for chunk in chunk_entries:
                # รองรับทั้ง start_time/end_time และ start/end
                start_value = chunk.get("start_time") or chunk.get("start")
                end_value = chunk.get("end_time") or chunk.get("end")
                
                # ถ้ายังไม่มี timestamp ให้ใช้ค่า default
                if start_value is None:
                    start_value = 0.0
                if end_value is None:
                    end_value = start_value + 30.0  # Default 30 seconds chunk
                
                chunk_objects.append(
                    TranscriptionChunk(
                        start_time=self._normalize_time_value(start_value),
                        end_time=self._normalize_time_value(end_value),
                        text=str(chunk.get("text", "")),
                        confidence=chunk.get("confidence")
                    )
                )
            
            created_at = self._parse_datetime(data.get("created_at")) or (existing.created_at if existing else utc_now())
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
            
            # ดึง time_used จาก processing_time หรือ result_time
            time_used = self._coerce_optional_float(data.get("processing_time")) or self._coerce_optional_float(data.get("result_time"))
            
            # ถ้าไม่มี processing_time แต่มี created_at และ completed_at ให้คำนวณ
            if not time_used and created_at and completed_at:
                try:
                    time_used = (completed_at - created_at).total_seconds()
                except Exception:
                    time_used = None
            
            # เก็บ processing_time ไว้ใน response เพื่อให้ frontend ใช้ได้ (fallback)
            processing_time_value = time_used
            
            # สร้าง original_text และ corrected_text จาก chunks
            original_text_parts = []
            corrected_text_parts = []
            for chunk in chunk_entries:
                # ถ้า chunk มี original_text และ text แสดงว่าได้ผ่าน correction แล้ว
                if chunk.get("original_text") and chunk.get("text"):
                    original_text_parts.append(chunk.get("original_text", ""))
                    corrected_text_parts.append(chunk.get("text", ""))
                else:
                    # ถ้าไม่มี original_text ให้ใช้ text เป็นทั้ง original และ corrected
                    chunk_text = chunk.get("text", "")
                    original_text_parts.append(chunk_text)
                    corrected_text_parts.append(chunk_text)
            
            original_text = " ".join(original_text_parts) if original_text_parts else None
            corrected_text = " ".join(corrected_text_parts) if corrected_text_parts else None
            
            # ดึง full_text จาก storage
            full_text_value = data.get("full_text")
            
            # ถ้า full_text มีอยู่แล้วและ chunks ไม่มี original_text ให้ใช้ full_text เป็น corrected_text
            if full_text_value and not corrected_text:
                corrected_text = full_text_value
            
            # ถ้า full_text ไม่มี แต่มี corrected_text ให้ใช้ corrected_text เป็น full_text
            if not full_text_value and corrected_text:
                full_text_value = corrected_text
            
            # ถ้า full_text และ corrected_text ไม่มี แต่มี chunks ให้สร้าง full_text จาก chunks
            if not full_text_value and chunk_objects:
                chunk_texts = [chunk.text for chunk in chunk_objects if chunk.text and chunk.text.strip()]
                if chunk_texts:
                    full_text_value = " ".join(chunk_texts).strip()
                    # ถ้ายังไม่มี corrected_text ให้ใช้ full_text เป็น corrected_text
                    if not corrected_text:
                        corrected_text = full_text_value
            
            response = TranscriptionResponse(
                task_id=task_id,
                status=str(data.get("status", getattr(existing, "status", "pending"))),
                file_path=str(data.get("file_path") or getattr(existing, "file_path", "")),
                file_url=data.get("file_url") or getattr(existing, "file_url", None),
                file_name=data.get("file_name") or getattr(existing, "file_name", None),
                total_duration=self._coerce_optional_float(data.get("total_duration")),
                chunks=chunk_objects or None,
                full_text=full_text_value,
                original_text=original_text or data.get("original_text"),
                corrected_text=corrected_text or data.get("corrected_text"),
                partial_text=data.get("partial_text", getattr(existing, "partial_text", None)),
                language=data.get("language") or getattr(existing, "language", None),
                created_at=created_at,
                completed_at=completed_at,
                error_message=data.get("error_message"),
                progress=progress_value,
                updated_at=updated_at,
                time_used=time_used,
                processing_time=processing_time_value  # Set processing_time for frontend fallback
            )
            
            # เติมข้อมูลที่เก็บไว้เพิ่มเติม
            response.job_id = data.get("job_id", getattr(existing, "job_id", None))
            response.user_id = data.get("user_id", getattr(existing, "user_id", None))
            response.callback_url = data.get("callback_url", getattr(existing, "callback_url", None))
            
            # เติมข้อมูล progress tracking และ time tracking ใหม่
            valid_chunks = [c for c in chunk_entries if c is not None]
            
            # Progress tracking: total_chunks, completed_chunks
            response.total_chunks = data.get("total_chunks") or (len(valid_chunks) if valid_chunks else None)
            response.completed_chunks = data.get("completed_chunks") or len(valid_chunks)
            
            # Progress tracking: total_tasks, completed_tasks
            response.total_tasks = data.get("total_tasks")
            response.completed_tasks = data.get("completed_tasks")
            
            # Time tracking: แยกตาม phase
            response.audio_extraction_time = self._coerce_optional_float(data.get("audio_extraction_time"))
            response.transcription_time = self._coerce_optional_float(data.get("transcription_time"))
            response.text_correction_time = self._coerce_optional_float(data.get("text_correction_time"))
            
            # Task breakdown
            response.task_breakdown = data.get("task_breakdown")
            
            # Detailed Stage Information
            response.current_stage = data.get("current_stage")
            response.current_stage_description = data.get("current_stage_description")
            response.stage_progress = data.get("stage_progress")
            
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
        display_mode: str = "full_text",  # "full_text" หรือ "realtime_chunks"
        callback_url: str = None,
        job_id: int = None,
        user_id: str = None,
        idempotency_key: Optional[str] = None,
        # Initial Prompt parameters
        enable_initial_prompt: bool = False,
        initial_prompt: Optional[str] = None,
        use_backend_dictionary: bool = True,
        dictionary_scope: str = "Global",
        dictionary_max_words: int = 50,
        # BackgroundTasks from FastAPI (optional)
        background_tasks = None
    ) -> str:
        """เริ่มการแปลงเสียงเป็นข้อความ - ส่งไปยัง RabbitMQ queue"""
        
        # ============================================================
        # Idempotency Check: ตรวจสอบ duplicate requests
        # ============================================================
        # ตรวจสอบว่าเคยมี task ที่ completed แล้วหรือไม่
        if idempotency_key or file_path or file_url:
            existing_task = self._check_idempotency(
                idempotency_key=idempotency_key,
                file_path=file_path,
                file_url=file_url,
                language=language,
                model_size=model_size
            )
            if existing_task:
                logger.info(f"✅ Found existing task (idempotency check): {existing_task.task_id} (status: {existing_task.status})")
                return existing_task.task_id
        
        # ============================================================
        # Admission Control: Optional - Let RabbitMQ handle queue limits
        # ============================================================
        # ใช้ 3-Queue Architecture ถ้าเปิดใช้งาน
        use_3queue_architecture = os.getenv('USE_3QUEUE_ARCHITECTURE', 'true').lower() == 'true'
        
        # Admission Control Mode:
        # - "api": API checks queue size before accepting (current behavior)
        # - "rabbitmq": API accepts all, RabbitMQ rejects when queue is full (new behavior)
        # - "disabled": No admission control (not recommended)
        admission_control_mode = os.getenv('ADMISSION_CONTROL_MODE', 'rabbitmq').lower()
        
        if admission_control_mode == 'api':
            # Original behavior: API checks queue size before accepting
            try:
                from fastapi import HTTPException
                
                if use_3queue_architecture:
                    # 3-Queue Architecture: ตรวจสอบ transcription_request_queue
                    MAX_QUEUE_REQUEST = int(os.getenv('MAX_QUEUE_REQUEST', '51'))  # 50 video + 1 close caption
                    MAX_QUEUE_EXTRACTION = int(os.getenv('MAX_QUEUE_EXTRACTION', '80'))
                    MAX_QUEUE_TRANSCRIBE = int(os.getenv('MAX_QUEUE_TRANSCRIBE', '20'))
                    RETRY_AFTER_SECONDS = int(os.getenv('RETRY_AFTER_SECONDS', '30'))
                    
                    # Run get_queue_info in executor to avoid blocking event loop
                    import asyncio
                    loop = asyncio.get_event_loop()
                    queue_info = await loop.run_in_executor(None, self.rabbitmq_service.get_queue_info)
                    
                    # Check transcription_request_queue
                    request_queue_info = queue_info.get('transcription_request_queue', {})
                    request_queue_size = request_queue_info.get('message_count', 0)
                    available_slots = MAX_QUEUE_REQUEST - request_queue_size
                    
                    if request_queue_size >= MAX_QUEUE_REQUEST:
                        error_msg = (
                            f"Request queue is full ({request_queue_size}/{MAX_QUEUE_REQUEST}). "
                            f"Please try again later. Estimated wait time: {RETRY_AFTER_SECONDS} seconds."
                        )
                        logger.warning(f"⚠️ {error_msg}")
                        raise HTTPException(
                            status_code=503,
                            detail={
                                "error": "Service temporarily unavailable",
                                "message": error_msg,
                                "queue_status": {
                                    "current": request_queue_size,
                                    "max": MAX_QUEUE_REQUEST,
                                    "available": 0
                                },
                                "retry_after_seconds": RETRY_AFTER_SECONDS,
                                "suggestion": "Please check queue status at /api/queue/status before submitting new requests"
                            },
                            headers={"Retry-After": str(RETRY_AFTER_SECONDS)}
                        )
                    elif available_slots <= 5:  # Warning when only 5 or fewer slots available
                        logger.warning(
                            f"⚠️ Queue nearly full: {request_queue_size}/{MAX_QUEUE_REQUEST} "
                            f"({available_slots} slots available)"
                        )
                    
                    # Check audio_extraction_queue (optional - for full admission control)
                    extraction_queue_info = queue_info.get('audio_extraction_queue', {})
                    extraction_queue_size = extraction_queue_info.get('message_count', 0)
                    
                    if extraction_queue_size >= MAX_QUEUE_EXTRACTION:
                        error_msg = f"Audio extraction queue is full ({extraction_queue_size}/{MAX_QUEUE_EXTRACTION}). Please try again later."
                        logger.warning(f"⚠️ {error_msg}")
                        raise HTTPException(
                            status_code=503,
                            detail=error_msg,
                            headers={"Retry-After": "60"}
                        )
                    
                    # Check transcription_queue (optional - for full admission control)
                    transcription_queue_info = queue_info.get('transcription_queue', {})
                    transcription_queue_size = transcription_queue_info.get('message_count', 0)
                    
                    if transcription_queue_size >= MAX_QUEUE_TRANSCRIBE:
                        error_msg = f"Transcription queue is full ({transcription_queue_size}/{MAX_QUEUE_TRANSCRIBE}). Please try again later."
                        logger.warning(f"⚠️ {error_msg}")
                        raise HTTPException(
                            status_code=503,
                            detail=error_msg,
                            headers={"Retry-After": "120"}
                        )
                    
                    logger.info(
                        f"✅ Admission control passed - Request: {request_queue_size}/{MAX_QUEUE_REQUEST}, "
                        f"Extraction: {extraction_queue_size}/{MAX_QUEUE_EXTRACTION}, "
                        f"Transcription: {transcription_queue_size}/{MAX_QUEUE_TRANSCRIBE}"
                    )
                else:
                    # Legacy: ตรวจสอบ transcription_queue เก่า
                    MAX_QUEUE_SIZE = int(os.getenv('TRANSCRIPTION_MAX_QUEUE_SIZE', '50'))
                    
                    # Run get_queue_info_thread_safe in executor to avoid blocking event loop
                    import asyncio
                    loop = asyncio.get_event_loop()
                    queue_info = await loop.run_in_executor(None, self.rabbitmq_service.get_queue_info_thread_safe)
                    transcription_queue_info = queue_info.get('transcription_queue', {})
                    current_queue_size = transcription_queue_info.get('message_count', 0)
                    
                    if current_queue_size >= MAX_QUEUE_SIZE:
                        error_msg = (
                            f"Queue is full ({current_queue_size}/{MAX_QUEUE_SIZE}). "
                            f"Please try again later."
                        )
                        logger.warning(f"⚠️ {error_msg}")
                        raise HTTPException(
                            status_code=503,
                            detail=error_msg
                        )
                    
                    logger.info(f"✅ Queue size check passed: {current_queue_size}/{MAX_QUEUE_SIZE} messages")
                
            except HTTPException:
                # Re-raise HTTPException (503)
                raise
            except Exception as e:
                # Log error but continue (don't block if queue check fails)
                logger.warning(f"⚠️ Queue size check failed (continuing anyway): {e}")
        elif admission_control_mode == 'rabbitmq':
            # New behavior: API accepts all requests, RabbitMQ will reject when queue is full
            # RabbitMQ queue has max-length with x-overflow: reject-publish
            # This allows API to accept requests without checking, and RabbitMQ handles the queue limit
            logger.info("✅ Admission control mode: rabbitmq - API accepts all, RabbitMQ handles queue limits")
        else:
            # Disabled: No admission control (not recommended for production)
            logger.warning("⚠️ Admission control disabled - not recommended for production")
        
        # ============================================================
        # Build initial_prompt (ถ้าเปิดใช้งาน)
        # ============================================================
        built_initial_prompt = None
        if enable_initial_prompt:
            built_initial_prompt = await self._build_initial_prompt(
                enable_initial_prompt=enable_initial_prompt,
                initial_prompt=initial_prompt,
                use_backend_dictionary=use_backend_dictionary,
                dictionary_scope=dictionary_scope,
                dictionary_max_words=dictionary_max_words,
                user_id=user_id,
                language=language
            )
        
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
                display_mode=display_mode,
                job_id=job_id,
                user_id=user_id,
            )
            
            # เพิ่ม initial_prompt ถ้ามี
            if built_initial_prompt:
                send_kwargs["initial_prompt"] = built_initial_prompt
                logger.info(f"📝 Adding initial_prompt to task (length: {len(built_initial_prompt)} chars)")

            # ============================================================
            # Routing: ส่งไปยัง queue ตาม Architecture ที่เลือก
            # ============================================================
            use_3queue_architecture = os.getenv('USE_3QUEUE_ARCHITECTURE', 'true').lower() == 'true'
            
            # แยก close caption (realtime_chunks) ไปยัง close caption queues
            is_close_caption = display_mode == "realtime_chunks"
            
            if is_close_caption:
                # Close Caption: ส่งไปยัง close_caption_request_queue (แยกจาก transcription)
                logger.info("📤 Using Close Caption Queues: sending to close_caption_request_queue")
                
                try:
                    signature = inspect.signature(self.rabbitmq_service.send_close_caption_request_task_thread_safe)
                    if "callback_url" in signature.parameters and callback_url:
                        send_kwargs["callback_url"] = callback_url
                    elif callback_url:
                        logger.warning(
                            "RabbitMQService.send_close_caption_request_task_thread_safe does not accept 'callback_url'. Skipping this parameter."
                        )
                except (ValueError, TypeError):
                    if callback_url:
                        logger.warning(
                            "Unable to inspect send_close_caption_request_task_thread_safe signature; skipping 'callback_url' parameter."
                        )
                
                # Run send_close_caption_request_task_thread_safe in executor
                import asyncio
                from functools import partial
                loop = asyncio.get_event_loop()
                task_id = await loop.run_in_executor(
                    None, 
                    partial(self.rabbitmq_service.send_close_caption_request_task_thread_safe, **send_kwargs)
                )
            elif use_3queue_architecture:
                # ใช้ Redis Streams: ส่ง request ไปยัง Redis queue แล้วให้ worker process
                logger.info("📤 Using Redis Streams: sending transcription request to queue")
                
                # สร้าง task_id
                task_id = str(uuid.uuid4())
                
                # สร้าง task response และเพิ่มเข้า self.tasks
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
                
                # ส่งไปยัง Redis Streams
                task_data = {
                    "task_id": task_id,
                    "file_path": file_path,
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
                    "initial_prompt": built_initial_prompt,
                    "created_at": datetime.now().isoformat()
                }
                
                # ใช้ Redis Streams (มี acknowledgment support)
                self.redis_queue_service.send_transcription_task(task_data, use_streams=True)
                logger.info(f"✅ ส่ง transcription request ไปยัง Redis Stream: {task_id}")
            else:
                # ใช้ Redis Streams: ส่ง request ไปยัง Redis queue แล้วให้ worker process
                logger.info("📤 Using Redis Streams: sending transcription request to queue")
                
                # สร้าง task_id
                task_id = str(uuid.uuid4())
                
                # สร้าง task response และเพิ่มเข้า self.tasks
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
                
                # ส่งไปยัง Redis Streams
                task_data = {
                    "task_id": task_id,
                    "file_path": file_path,
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
                    "initial_prompt": built_initial_prompt,
                    "created_at": datetime.now().isoformat()
                }
                
                # ใช้ Redis Streams (มี acknowledgment support)
                self.redis_queue_service.send_transcription_task(task_data, use_streams=True)
                logger.info(f"✅ ส่ง transcription request ไปยัง Redis Stream: {task_id}")
            
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
            
            # 📞 ส่ง webhook callback เมื่อได้ Task ID (started)
            if callback_url:
                try:
                    await self._send_callback(task, "started")
                except Exception as e:
                    logger.warning(f"Failed to send started callback: {e}")
            
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
                created_at=utc_now(),
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
                    "created_at": utc_now().timestamp()
                }
                self.json_storage.save_transcription(task_id, task_data)
            except Exception as storage_error:
                logger.error(f"ไม่สามารถบันทึก task ลง storage: {storage_error}")
            
            return task_id
    
    def _check_task_timeout(self, task_id: str, task: TranscriptionResponse) -> bool:
        """ตรวจสอบว่า task เกิน timeout หรือไม่"""
        TASK_TIMEOUT_SECONDS = int(os.getenv('TRANSCRIPTION_TASK_TIMEOUT_SECONDS', '3600'))  # 1 ชั่วโมง default
        
        if not task.created_at:
            return False  # ไม่สามารถตรวจสอบได้
        
        # Ensure task.created_at is timezone-aware
        created_at = task.created_at
        if isinstance(created_at, str):
            try:
                if 'Z' in created_at:
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                elif '+' in created_at or created_at.count('-') > 2:
                    created_at = datetime.fromisoformat(created_at)
                else:
                    created_at = datetime.fromisoformat(created_at.replace('Z', ''))
                    created_at = created_at.replace(tzinfo=timezone.utc)
            except:
                return False
        elif isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        else:
            return False
        
        elapsed_time = (utc_now() - created_at).total_seconds()
        
        if elapsed_time > TASK_TIMEOUT_SECONDS:
            logger.error(
                f"⏱️ Task {task_id} exceeded timeout: {elapsed_time:.1f}s > {TASK_TIMEOUT_SECONDS}s "
                f"({TASK_TIMEOUT_SECONDS/60:.1f} minutes)"
            )
            return True
        
        return False
    
    async def _process_transcription(
        self,
        task_id: str,
        file_path: Optional[str],
        language: str,
        model_size: str,
        chunk_duration: int,
        use_chunking: bool = False,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        initial_prompt: Optional[str] = None
    ):
        """ประมวลผลการแปลงเสียง"""
        logger.info(f"🎬 Starting _process_transcription: task_id={task_id}, file_path={file_path}, model={model_size}, language={language}")
        
        if task_id not in self.tasks:
            logger.error(f"❌ Task {task_id} not found in transcription_service.tasks")
            raise ValueError(f"Task {task_id} not found")
        
        task = self.tasks[task_id]
        
        # ตรวจสอบ timeout ก่อนเริ่มประมวลผล
        if self._check_task_timeout(task_id, task):
            task.status = "failed"
            task.error_message = f"Task timeout: exceeded {os.getenv('TRANSCRIPTION_TASK_TIMEOUT_SECONDS', '3600')} seconds"
            task.completed_at = utc_now()
            self.json_storage.save_transcription(task_id, task.__dict__)
            logger.error(f"❌ Task {task_id} marked as failed due to timeout")
            return
        
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
                audio_extraction_time = None  # Initialize เป็น None
                
                if is_video:
                    logger.info("🎬 ไฟล์เป็น video - กำลัง extract audio...")
                    try:
                        # Extract audio ทั้งไฟล์ (ไม่ chunk) - ใช้ Thread Pool
                        # ส่ง task_id เพื่อบันทึก metrics แยกจาก transcription
                        audio_path = self.video_service.extract_audio(local_file_path, task_id=task_id)
                        logger.info(f"✅ Extract audio สำเร็จ: {audio_path}")
                        # Note: audio_extraction_time จะถูกบันทึกใน audio_extraction_queue worker
                        # สำหรับกรณี non-chunking ที่เรียก transcription_service โดยตรง จะไม่มี audio_extraction_time
                    except Exception as e:
                        logger.error(f"❌ ไม่สามารถ extract audio ได้: {e}", exc_info=True)
                        raise
                elif is_audio:
                    logger.info("🎵 ไฟล์เป็น audio file โดยตรง - ไม่ต้อง extract audio")
                    # audio_extraction_time จะเป็น None (ไม่มีการ extract)
                else:
                    logger.warning("⚠️ ไม่ทราบประเภทไฟล์ - ลองใช้ extract_audio()")
                    try:
                        audio_path = self.video_service.extract_audio(local_file_path, task_id=task_id)
                        logger.info(f"✅ Extract audio สำเร็จ: {audio_path}")
                        # Note: ถ้าสำเร็จจะถือว่าเป็น video และ extract แล้ว
                    except Exception as e:
                        logger.warning(f"⚠️ extract_audio() ล้มเหลว: {e}")
                        # ใช้ไฟล์เดิม (อาจเป็น audio อยู่แล้ว)
                        audio_path = local_file_path
                        # audio_extraction_time จะเป็น None (ไม่มีการ extract)
                
                # ตรวจสอบ timeout อีกครั้งก่อนเริ่ม transcription
                if self._check_task_timeout(task_id, task):
                    task.status = "failed"
                    task.error_message = f"Task timeout: exceeded {os.getenv('TRANSCRIPTION_TASK_TIMEOUT_SECONDS', '3600')} seconds"
                    task.completed_at = utc_now()
                    self.json_storage.save_transcription(task_id, task.__dict__)
                    logger.error(f"❌ Task {task_id} marked as failed due to timeout before transcription")
                    return
                
                # Transcribe ทั้งไฟล์เลย
                logger.info("🎯 [Transcription] เริ่ม transcription ทั้งไฟล์ (ไม่ chunk)...")
                task.status = "transcribing"
                task.progress = 20
                self.json_storage.save_transcription(task_id, task.__dict__)
                
                # บันทึกเวลาต้นเริ่มสำหรับ transcription (แยกจาก audio extraction)
                transcription_start_time = time.time()
                
                try:
                    # เรียกใช้ whisper service โดยตรง (ไม่ผ่าน queue)
                    # ⚠️ transcribe_file ไม่ใช่ async function แต่ใช้ asyncio.run() ภายใน
                    logger.info(f"🔍 [Transcription] Calling whisper_service.transcribe_file()...")
                    if initial_prompt:
                        logger.debug(f"   Using initial_prompt: {initial_prompt[:100]}..." if len(initial_prompt) > 100 else f"   Using initial_prompt: {initial_prompt}")
                    try:
                        result = self.whisper_service.transcribe_file(
                            audio_path,
                            language=language,
                            model_size=model_size,
                            initial_prompt=initial_prompt  # ส่ง initial_prompt
                        )
                        logger.info(f"✅ [Transcription] whisper_service.transcribe_file() returned, result type: {type(result)}")
                    except Exception as transcribe_error:
                        logger.error(f"❌ [Transcription] Error in transcribe_file(): {transcribe_error}", exc_info=True)
                        raise
                    
                    # เก็บผลลัพธ์
                    if result:
                        task.full_text = result.get('text', '') if isinstance(result, dict) else result.text
                        task.language = result.get('language', language) if isinstance(result, dict) else result.language
                        task.chunks = result.get('segments', []) if isinstance(result, dict) else (result.segments if result.segments else [])
                        
                        # บันทึกเวลาที่ใช้ในการ transcription
                        transcription_time = time.time() - transcription_start_time
                        logger.info(f"✅ [Transcription] Transcription สำเร็จ")
                        logger.info(f"   ⏱️  ใช้เวลา: {transcription_time:.2f} วินาที")
                        
                        # บันทึก metrics สำหรับการวิเคราะห์ผล Transcription แยกจาก Audio Extraction
                        text_length = len(task.full_text) if task.full_text else 0
                        chunks_count = len(task.chunks) if task.chunks else 0
                        self._record_transcription_metrics(
                            task_id, audio_path, transcription_time, 
                            text_length, chunks_count, success=True
                        )
                        task.status = "completed"
                        task.progress = 100
                        
                        text_length = len(task.full_text) if task.full_text else 0
                        chunks_count = len(task.chunks) if task.chunks else 0
                        logger.info(f"✅ Transcription สำเร็จ: text length={text_length}, segments={chunks_count}")
                        
                        # บันทึก transcription_time ใน task metadata
                        task_dict = task.__dict__.copy()
                        task_dict['transcription_time'] = transcription_time
                        task_dict['time_used'] = transcription_time  # สำหรับ backward compatibility
                        
                        # อัปเดต total_chunks และ completed_chunks (สำหรับ non-chunking mode)
                        # ใน non-chunking mode: total_chunks = 1 (ทั้งไฟล์คือ 1 chunk)
                        task_dict['total_chunks'] = 1
                        task_dict['completed_chunks'] = 1
                        
                        # อัปเดต total_tasks และ completed_tasks
                        # total_tasks = 1 (audio extraction, ถ้ามี) + 1 (transcription)
                        # ตรวจสอบว่ามี audio_extraction_time หรือไม่
                        existing_data = self.json_storage.load_transcription(task_id)
                        audio_extraction_done = existing_data and existing_data.get('audio_extraction_time') is not None
                        
                        # ถ้าไม่มี audio_extraction_time (เช่น เป็น audio file โดยตรง) ให้ตั้งเป็น None ชัดเจน
                        if 'audio_extraction_time' not in task_dict:
                            if existing_data and 'audio_extraction_time' in existing_data:
                                # ดึงจาก existing_data (อาจบันทึกจาก audio extraction queue)
                                task_dict['audio_extraction_time'] = existing_data.get('audio_extraction_time')
                            else:
                                # เป็น audio file โดยตรง - ไม่มีการ extract audio
                                task_dict['audio_extraction_time'] = None
                        
                        total_tasks = (1 if audio_extraction_done else 0) + 1  # 1 transcription task
                        completed_tasks = (1 if audio_extraction_done else 0) + 1
                        task_dict['total_tasks'] = total_tasks
                        task_dict['completed_tasks'] = completed_tasks
                        
                        # สร้าง task_breakdown ถ้ายังไม่มี หรือเป็น None
                        if 'task_breakdown' not in task_dict or task_dict.get('task_breakdown') is None:
                            task_dict['task_breakdown'] = []
                        
                        # เพิ่ม transcription task ใน task_breakdown ถ้ายังไม่มี
                        task_breakdown = task_dict.get('task_breakdown') or []
                        transcription_task_exists = any(
                            t.get('type') == 'transcription' for t in task_breakdown if isinstance(t, dict)
                        )
                        if not transcription_task_exists:
                            task_dict['task_breakdown'].append({
                                'type': 'transcription',
                                'status': 'completed',
                                'time': transcription_time,
                                'chunks_count': chunks_count,
                                'completed_at': utc_now().isoformat()
                            })
                    else:
                        transcription_time = time.time() - transcription_start_time
                        logger.error(f"❌ [Transcription] Transcription returned None or empty result")
                        logger.error(f"   ⏱️  ใช้เวลา (ก่อนเกิด error): {transcription_time:.2f} วินาที")
                        
                        # บันทึก metrics สำหรับการวิเคราะห์ผล Transcription (empty result)
                        self._record_transcription_metrics(
                            task_id, audio_path, transcription_time, 
                            0, 0, success=False, error="Transcription returned empty result"
                        )
                        
                        task.status = "failed"
                        task.error_message = "Transcription returned empty result"
                        task.progress = 0
                        task_dict = task.__dict__.copy()
                        task_dict['transcription_time'] = transcription_time
                    
                    # บันทึกผลลัพธ์
                    logger.info(f"💾 Saving transcription result to storage...")
                    self.json_storage.save_transcription(task_id, task_dict)
                    logger.info(f"✅ Transcription saved to storage")
                    
                    # Cleanup temporary audio file และ wav files (ถ้า extract จาก video)
                    # ลบทันทีหลัง transcribe เสร็จและบันทึก JSON fullText แล้ว (ถ้า SAVE_TEMP_FILES=not_save)
                    if not self.save_temp_files:
                        # ลบไฟล์ wav ที่ extract จาก video
                        if audio_path != local_file_path and Path(audio_path).exists():
                            try:
                                # ลบไฟล์ wav
                                Path(audio_path).unlink()
                                logger.info(f"🧹 ลบ temporary audio file: {audio_path}")
                                
                                # ลบ temp folder ถ้ามี (เช่น temp/task_xxx/ หรือ temp/audio_xxx/)
                                audio_path_obj = Path(audio_path)
                                temp_folder = audio_path_obj.parent
                                if temp_folder.exists() and (temp_folder.name.startswith('task_') or temp_folder.name.startswith('audio_')):
                                    try:
                                        import shutil
                                        shutil.rmtree(temp_folder)
                                        logger.info(f"🧹 ลบ temp folder: {temp_folder}")
                                    except Exception as e:
                                        logger.warning(f"⚠️ ไม่สามารถลบ temp folder {temp_folder}: {e}")
                            except Exception as e:
                                logger.warning(f"⚠️ ไม่สามารถลบ temporary audio file: {e}")
                        
                        # ลบ wav files ใน uploads/tmp
                        try:
                            self.file_service.cleanup_wav_files_in_uploads_tmp()
                        except Exception as e:
                            logger.warning(f"⚠️ ไม่สามารถลบ wav files ใน uploads/tmp: {e}")
                    else:
                        logger.debug(f"💾 Keeping temporary audio file (SAVE_TEMP_FILES=save): {audio_path}")
                    
                    return
                    
                except Exception as e:
                    # บันทึกเวลาที่ใช้ในการ transcription (แม้จะล้มเหลว)
                    transcription_time = time.time() - transcription_start_time if 'transcription_start_time' in locals() else 0
                    logger.error(f"❌ [Transcription] Transcription failed: {e}", exc_info=True)
                    logger.error(f"   ⏱️  ใช้เวลา (ก่อนเกิด error): {transcription_time:.2f} วินาที")
                    
                    # บันทึก metrics สำหรับการวิเคราะห์ผล Transcription (failed)
                    audio_path_var = audio_path if 'audio_path' in locals() else None
                    self._record_transcription_metrics(
                        task_id, audio_path_var, transcription_time, 
                        0, 0, success=False, error=str(e)
                    )
                    
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
                for i, chunk_info in enumerate(chunks[:3]):  # ตรวจสอบแค่ 3 chunks แรก
                    # รองรับทั้งรูปแบบเก่า (string) และรูปแบบใหม่ (dict)
                    if isinstance(chunk_info, dict):
                        chunk_path = chunk_info.get("path")
                    else:
                        chunk_path = chunk_info
                    
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
            
            # Initialize progress tracking: total_chunks และ completed_chunks
            total_chunks = len(chunks)
            task_data['total_chunks'] = total_chunks
            task_data['completed_chunks'] = 0
            # สำหรับ chunking mode: total_tasks = 1 (audio extraction, ถ้ามี) + total_chunks (transcription)
            # แต่เราจะคำนวณเมื่อ audio extraction เสร็จแล้ว
            task_data['total_tasks'] = None  # จะอัปเดตเมื่อรู้จำนวน chunks
            task_data['completed_tasks'] = 0
            
            self.json_storage.save_transcription(task_id, task_data)
            
            # ส่งแต่ละ chunk ไปยัง queue
            for i, chunk_info in enumerate(chunks):
                # รองรับทั้งรูปแบบเก่า (string) และรูปแบบใหม่ (dict)
                if isinstance(chunk_info, dict):
                    chunk_path = chunk_info.get("path")
                    chunk_start_time = chunk_info.get("start_time", i * chunk_duration)
                    chunk_end_time = chunk_info.get("end_time", (i + 1) * chunk_duration)
                    chunk_index = chunk_info.get("chunk_index", i)
                else:
                    # Backward compatibility: ถ้าเป็น string ให้ใช้การคำนวณแบบเดิม
                    chunk_path = chunk_info
                    chunk_start_time = i * chunk_duration
                    chunk_end_time = (i + 1) * chunk_duration
                    chunk_index = i
                
                chunk_task = {
                    "task_id": f"{task_id}_chunk_{chunk_index}",
                    "parent_task_id": task_id,
                    "chunk_path": chunk_path,
                    "chunk_index": chunk_index,
                    "chunk_start_time": chunk_start_time,  # เพิ่ม timestamp จริง
                    "chunk_end_time": chunk_end_time,      # เพิ่ม timestamp จริง
                    "total_chunks": total_chunks,
                    "chunk_duration": chunk_duration,
                    "model_size": model_size,
                    "language": language,
                    "file_path": local_file_path,
                    "file_name": file_name,
                    "initial_prompt": initial_prompt,  # ส่ง initial_prompt ไปยัง chunk tasks
                    "created_at": utc_now().isoformat()
                }
                
                try:
                    # ใช้ Redis Streams (มี acknowledgment support)
                    self.redis_queue_service.send_chunk_transcription_task(chunk_task, use_streams=True)
                    logger.info(f"✅ ส่ง chunk {i+1}/{total_chunks} ไปยัง Redis Stream: {chunk_path}")
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
                        task.updated_at = utc_now()  # อัปเดต updated_at เมื่อ progress หรือ status เปลี่ยน
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
            task.updated_at = utc_now()
            
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
            task.completed_at = utc_now()
            
            # อัปเดต task object ด้วย full_text และ chunks ก่อนส่ง callback
            task.full_text = full_text
            task.chunks = chunks
            
            # 🧹 ลบ temp files หลังเสร็จสิ้น (ถ้า SAVE_TEMP_FILES=not_save)
            if not self.save_temp_files:
                try:
                    self.file_service.cleanup_temp_files(chunks)
                    logger.info(f"🧹 ลบ temp files สำเร็จ: {len(chunks)} files")
                except Exception as e:
                    logger.warning(f"⚠️ ไม่สามารถลบ temp files: {e}")
            else:
                logger.debug(f"💾 Keeping temp files (SAVE_TEMP_FILES=save): {len(chunks)} files")
            
            # 📞 Callback to Backend (ถ้ามี callback_url)
            # Note: ไม่ต้องส่ง WebSocket notification จาก transcription-api แล้ว
            # เพราะ senate-backend จะส่ง SignalR notification เองหลังจากรับ webhook callback
            if hasattr(task, 'callback_url') and task.callback_url:
                try:
                    logger.info(f"📤 Preparing to send completed callback for task {task.task_id}")
                    logger.info(f"   Full text length: {len(full_text)}, Chunks count: {len(chunks)}")
                    await self._send_callback(task, "completed")
                    logger.info(f"✅ Completed callback sent successfully for task {task.task_id}")
                except Exception as e:
                    logger.error(f"❌ Backend callback failed for task {task.task_id}: {e}", exc_info=True)
            
            # บันทึกข้อมูลสุดท้าย - อัปเดต metadata เพิ่มเติม (job_id, user_id, callback_url)
            # Note: full_text และ chunks ถูกบันทึกไปแล้วที่บรรทัด 470
            logger.info("กำลังบันทึกผลลัพธ์สุดท้าย (metadata update)...")
            
            # ดึงข้อมูลที่มีอยู่แล้วจาก storage เพื่อ merge (เช่น transcription_time, audio_extraction_time, total_tasks, etc.)
            existing_data = self.json_storage.load_transcription(task_id)
            
            # คำนวณ processing time
            # ใช้ UTC สำหรับบันทึก timestamp ทั้งหมด
            completed_time = datetime.now(timezone.utc)
            
            # Parse created_time - handle both string and datetime
            created_time = None
            if task.created_at:
                if isinstance(task.created_at, str):
                    # Parse string to datetime
                    try:
                        if 'Z' in task.created_at:
                            created_time = datetime.fromisoformat(task.created_at.replace('Z', '+00:00'))
                        elif '+' in task.created_at or task.created_at.count('-') > 2:
                            created_time = datetime.fromisoformat(task.created_at)
                        else:
                            # No timezone - assume UTC
                            created_time = datetime.fromisoformat(task.created_at.replace('Z', ''))
                            created_time = created_time.replace(tzinfo=timezone.utc)
                    except Exception as e:
                        logger.warning(f"Error parsing created_at '{task.created_at}': {e}")
                        created_time = completed_time
                elif isinstance(task.created_at, datetime):
                    created_time = task.created_at
                    # Ensure timezone-aware
                    if created_time.tzinfo is None:
                        created_time = created_time.replace(tzinfo=timezone.utc)
                else:
                    created_time = completed_time
            else:
                created_time = completed_time
            
            # Ensure both are timezone-aware before subtraction
            if created_time.tzinfo is None:
                created_time = created_time.replace(tzinfo=timezone.utc)
            
            processing_time_seconds = (completed_time - created_time).total_seconds()
            
            # ดึง transcription_time และ audio_extraction_time จาก existing_data ถ้ามี
            transcription_time = existing_data.get('transcription_time') if existing_data else None
            audio_extraction_time = existing_data.get('audio_extraction_time') if existing_data else None
            
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
                "completed_at": completed_time.isoformat(),  # อัปเดต completed_at (UTC with timezone indicator)
                "end_time": completed_time.isoformat(),  # Alias for compatibility
                "updated_at": completed_time.isoformat(),
                "processing_time": processing_time_seconds,  # เวลาที่ใช้ในการประมวลผลทั้งหมด (วินาที)
                "result_time": processing_time_seconds,  # Alias for compatibility
                "transcription_time": transcription_time,  # เวลาที่ใช้ในการ transcription โดยเฉพาะ (วินาที)
                "audio_extraction_time": audio_extraction_time,  # เวลาที่ใช้ในการ extract audio (วินาที), None ถ้าเป็น audio file โดยตรง
                "error_message": task.error_message,
                "progress": 100,  # อัปเดต progress เป็น 100
                "job_id": getattr(task, "job_id", None),
                "user_id": getattr(task, "user_id", None),
                "callback_url": getattr(task, "callback_url", None)
            }
            
            # รวมข้อมูล progress tracking จาก existing_data ถ้ามี
            if existing_data:
                for key in ['total_tasks', 'completed_tasks', 'total_chunks', 'completed_chunks', 'task_breakdown', 
                           'current_stage', 'current_stage_description', 'stage_progress']:
                    if key in existing_data:
                        final_data[key] = existing_data[key]
            
            # บันทึก metadata อัปเดต (จะ merge กับข้อมูลเดิม)
            logger.info(f"💾 Updating final metadata: task_id={task_id}, full_text length={len(task.full_text) if task.full_text else 0}, chunks count={len(final_data['chunks'])}")
            self.json_storage.save_transcription(task_id, final_data)
            
            logger.info(f"✅ แปลงเสียงเสร็จสิ้น: {task_id}")
            
            # 🧹 ลบไฟล์ชั่วคราวหลังจากประมวลผลเสร็จแล้ว (ถ้า SAVE_TEMP_FILES=not_save)
            if not self.save_temp_files:
                if 'chunks' in locals():
                    try:
                        self.file_service.cleanup_temp_files(chunks)
                        logger.info(f"🧹 ลบ temp files สำเร็จ: {len(chunks)} files")
                    except Exception as e:
                        logger.warning(f"⚠️ ไม่สามารถลบ temp files: {e}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแปลงเสียง {task_id}: {e}")
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = utc_now()
            
            # Note: ไม่ต้องส่ง WebSocket notification จาก transcription-api แล้ว
            # เพราะ senate-backend จะส่ง SignalR notification เองหลังจากรับ webhook callback
            
            # 🧹 ลบไฟล์ชั่วคราวในกรณีเกิดข้อผิดพลาด (ถ้า SAVE_TEMP_FILES=not_save)
            if not self.save_temp_files:
                if 'chunks' in locals():
                    try:
                        self.file_service.cleanup_temp_files(chunks)
                    except Exception as e:
                        logger.warning(f"⚠️ ไม่สามารถลบ temp files: {e}")
        finally:
            # Cleanup temporary files และ folders (ถ้า SAVE_TEMP_FILES=not_save)
            context = self.task_contexts.get(task_id, {})
            if not self.save_temp_files:
                if downloaded_file_path:
                    try:
                        Path(downloaded_file_path).unlink(missing_ok=True)
                        logger.info("🧹 ลบไฟล์ที่ดาวน์โหลดสำหรับ task %s: %s", task_id, downloaded_file_path)
                    except Exception as cleanup_error:
                        logger.warning("⚠️ ไม่สามารถลบไฟล์ที่ดาวน์โหลด (%s): %s", downloaded_file_path, cleanup_error)
                download_temp_dir = context.get("download_temp_dir")
                if download_temp_dir:
                    try:
                        self.file_service.cleanup_temp_folder(download_temp_dir)
                    except Exception as cleanup_dir_error:
                        logger.warning("⚠️ ไม่สามารถลบ temp folder %s: %s", download_temp_dir, cleanup_dir_error)
                extra_download_dir = context.get("download_temp_dir")
                if extra_download_dir and extra_download_dir != download_temp_dir:
                    try:
                        self.file_service.cleanup_temp_folder(extra_download_dir)
                    except Exception as extra_cleanup_error:
                        logger.warning("⚠️ ไม่สามารถลบ temp folder ที่เก็บไว้ใน context (%s): %s", extra_download_dir, extra_cleanup_error)
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
    
    def _check_idempotency(
        self,
        idempotency_key: Optional[str] = None,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
        language: str = "th",
        model_size: str = "base"
    ) -> Optional[TranscriptionResponse]:
        """
        ตรวจสอบ idempotency: หา existing task ที่มี parameters เหมือนกัน
        
        Args:
            idempotency_key: Idempotency key จาก client (optional)
            file_path: Path ของไฟล์
            file_url: URL ของไฟล์
            language: ภาษา
            model_size: ขนาด model
            
        Returns:
            TranscriptionResponse ถ้าพบ existing task ที่ completed
            None ถ้าไม่พบหรือ task ยังไม่เสร็จ
        """
        try:
            # ถ้ามี idempotency_key ให้ค้นหาจาก metadata
            if idempotency_key:
                # ค้นหาจาก all tasks โดยใช้ idempotency_key
                all_tasks = self.json_storage.list_all_transcriptions()
                for task_data in all_tasks:
                    if task_data.get('idempotency_key') == idempotency_key:
                        task_status = task_data.get('status', '')
                        if task_status == 'completed':
                            # สร้าง TranscriptionResponse จาก existing task
                            task = self._build_task_from_storage(task_data.get('task_id'), task_data)
                            if task:
                                logger.info(f"✅ Found completed task with idempotency_key={idempotency_key}: {task.task_id}")
                                return task
                        elif task_status in ['pending', 'processing']:
                            # Return existing task ID (ไม่ต้องสร้างใหม่)
                            logger.info(f"✅ Found existing task with idempotency_key={idempotency_key}: {task_data.get('task_id')} (status: {task_status})")
                            task = self._build_task_from_storage(task_data.get('task_id'), task_data)
                            if task:
                                return task
            
            # ถ้าไม่มี idempotency_key ให้ค้นหาจาก file_path/file_url + parameters
            # ⚠️  Disable idempotency check สำหรับ pending/processing tasks (เพื่อให้สามารถ retry ได้)
            if file_path or file_url:
                all_tasks = self.json_storage.list_all_transcriptions()
                for task_data in all_tasks:
                    # ตรวจสอบว่า file_path หรือ file_url ตรงกัน
                    task_file_path = task_data.get('file_path')
                    task_file_url = task_data.get('file_url')
                    
                    # เปรียบเทียบ file_path หรือ file_url
                    file_match = False
                    if file_path and task_file_path:
                        # Normalize paths (remove trailing slashes, etc.)
                        if str(Path(file_path).resolve()) == str(Path(task_file_path).resolve()):
                            file_match = True
                    elif file_url and task_file_url:
                        if str(file_url).strip() == str(task_file_url).strip():
                            file_match = True
                    
                    if file_match:
                        # ตรวจสอบว่า parameters อื่นๆ ตรงกัน
                        task_language = task_data.get('language', 'th')
                        task_model_size = task_data.get('model_size', 'base')
                        
                        if task_language == language and task_model_size == model_size:
                            task_status = task_data.get('status', '')
                            if task_status == 'completed':
                                # สร้าง TranscriptionResponse จาก existing task
                                task = self._build_task_from_storage(task_data.get('task_id'), task_data)
                                if task:
                                    logger.info(f"✅ Found completed task with matching file: {task.task_id}")
                                    return task
                            # ⚠️  Disable idempotency check สำหรับ pending/processing tasks
                            # เพื่อให้สามารถ retry ได้ถ้า task เก่าไม่ทำงาน
                            # elif task_status in ['pending', 'processing']:
                            #     # Skip idempotency check for pending/processing tasks
                            #     logger.info(f"⚠️  Found pending/processing task with matching file: {task_data.get('task_id')} (status: {task_status}) - Skipping idempotency check to allow retry")
                            #     # Continue to create new task
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Idempotency check failed: {e}")
            return None  # Continue with new task creation
    
    def get_all_tasks(self) -> List[TranscriptionResponse]:
        """ดึงรายการ tasks ทั้งหมด"""
        responses: List[TranscriptionResponse] = []
        seen_ids = set()
        
        try:
            # โหลดจาก storage ทั้งหมดก่อน
            stored_tasks = self.json_storage.list_all_transcriptions()
            for stored in stored_tasks:
                try:
                    task_id = stored.get("task_id")
                    if not task_id:
                        continue
                    task = self._build_task_from_storage(task_id, stored, existing=self.tasks.get(task_id))
                    if task:
                        self.tasks[task_id] = task
                        responses.append(task)
                        seen_ids.add(task_id)
                except Exception as e:
                    logger.warning(f"Error processing task {stored.get('task_id', 'unknown')}: {e}")
                    continue
            
            # เติม tasks ที่อยู่ในหน่วยความจำ แต่ยังไม่อยู่ใน storage list
            for task_id, task in self.tasks.items():
                if task_id not in seen_ids:
                    responses.append(task)
        except Exception as e:
            logger.error(f"Error getting all tasks from storage: {e}", exc_info=True)
            # Return tasks from memory only if storage fails
            responses = list(self.tasks.values())
        
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
            # รองรับ status: pending, processing, transcribing, processing_chunks, waiting_for_chunks, processing_chunk_*, merging_results
            cancellable_statuses = ["pending", "processing", "transcribing", "processing_chunks", "waiting_for_chunks", "merging_results"]
            is_cancellable = (
                current_status in cancellable_statuses or 
                current_status.startswith("processing_chunk_")
            )
            
            if is_cancellable:
                # สำหรับ status "transcribing" ให้ mark เป็น "stopped" แทน "cancelled"
                # เพราะ task อาจกำลังทำงานอยู่ที่ worker ต้อง kill/stop โดยตรง
                new_status = 'stopped' if current_status == 'transcribing' else 'cancelled'
                
                # อัปเดตสถานะ
                stored_data['status'] = new_status
                stored_data['completed_at'] = utc_now().isoformat()
                stored_data['updated_at'] = utc_now().isoformat()
                self.json_storage.save_transcription(task_id, stored_data)
                
                # อัปเดตใน memory cache ด้วย
                if task_id in self.tasks:
                    self.tasks[task_id].status = new_status
                    self.tasks[task_id].completed_at = utc_now()
                
                logger.info(f"✅ Task {task_id} {'stopped' if new_status == 'stopped' else 'cancelled'} successfully")
                return True
            elif current_status in ["cancelled", "stopped"]:
                logger.info(f"⚠️  Task {task_id} is already {current_status}")
                return True  # ถ้ายกเลิกหรือหยุดแล้วก็ถือว่าสำเร็จ
            else:
                logger.warning(f"⚠️  Cannot cancel task {task_id} with status: {current_status}")
                return False
        
        # ตรวจสอบจาก memory cache
        if task_id in self.tasks:
            task = self.tasks[task_id]
            # รองรับ status: pending, processing, transcribing, processing_chunks, waiting_for_chunks, processing_chunk_*, merging_results
            cancellable_statuses = ["pending", "processing", "transcribing", "processing_chunks", "waiting_for_chunks", "merging_results"]
            is_cancellable = (
                task.status in cancellable_statuses or 
                task.status.startswith("processing_chunk_")
            )
            
            if is_cancellable:
                # สำหรับ status "transcribing" ให้ mark เป็น "stopped" แทน "cancelled"
                # เพราะ task อาจกำลังทำงานอยู่ที่ worker ต้อง kill/stop โดยตรง
                new_status = 'stopped' if task.status == 'transcribing' else 'cancelled'
                
                task.status = new_status
                task.completed_at = utc_now()
                
                # บันทึกลง storage ด้วย
                task_data = task.__dict__
                task_data['status'] = new_status
                task_data['completed_at'] = utc_now().isoformat()
                task_data['updated_at'] = utc_now().isoformat()
                self.json_storage.save_transcription(task_id, task_data)
                
                logger.info(f"✅ Task {task_id} {'stopped' if new_status == 'stopped' else 'cancelled'} successfully")
                return True
            elif task.status in ["cancelled", "stopped"]:
                logger.info(f"⚠️  Task {task_id} is already {task.status}")
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
        
        cutoff_time = utc_now().timestamp() - (max_age_hours * 3600)
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
        now = utc_now()
        
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
    
    async def _send_callback(self, task, status: str, progress: int = None):
        """ส่ง callback ไปยัง Backend เมื่อสถานะเปลี่ยน"""
        import httpx
        
        try:
            callback_url = task.callback_url
            if not callback_url:
                return
            
            # สำหรับ status "started" - ส่งข้อมูลพื้นฐาน
            if status == "started":
                payload = {
                    "jobId": getattr(task, 'job_id', None),
                    "taskId": task.task_id,
                    "status": "started",
                    "progress": 0,
                    "filePath": getattr(task, 'file_path', None) or getattr(task, 'file_name', None),
                    "language": getattr(task, 'language', 'th'),
                    "startedAt": utc_now().isoformat()
                }
                logger.info(f"📤 Sending started callback: job_id={payload['jobId']}, task_id={task.task_id}")
            
            # สำหรับ status "processing" - ส่ง progress update
            elif status == "processing":
                payload = {
                    "jobId": getattr(task, 'job_id', None),
                    "taskId": task.task_id,
                    "status": "processing",
                    "progress": progress or getattr(task, 'progress', 0),
                    "updatedAt": utc_now().isoformat()
                }
                logger.info(f"📤 Sending progress callback: job_id={payload['jobId']}, task_id={task.task_id}, progress={payload['progress']}%")
            
            # สำหรับ status "completed" - ส่งผลลัพธ์เต็ม
            elif status == "completed":
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
                    "status": "completed",
                    "text": full_text,
                    "segments": segments,
                    "audioDuration": getattr(task, 'total_duration', None),
                    "wordCount": len(full_text.split()) if full_text else 0,
                    "averageConfidence": None,  # คำนวณได้ถ้าต้องการ
                    "progress": 100,
                    "completedAt": utc_now().isoformat()
                }
                logger.info(f"📤 Sending completed callback: job_id={payload['jobId']}, task_id={task.task_id}, text_length={len(full_text)}, segments_count={len(segments)}")
            
            # สำหรับ status "failed" - ส่ง error message
            elif status == "failed":
                payload = {
                    "jobId": getattr(task, 'job_id', None),
                    "taskId": task.task_id,
                    "status": "failed",
                    "error": getattr(task, 'error_message', 'Unknown error'),
                    "failedAt": utc_now().isoformat()
                }
                logger.info(f"📤 Sending failed callback: job_id={payload['jobId']}, task_id={task.task_id}")
            
            else:
                # Unknown status - skip
                logger.warning(f"⚠️ Unknown callback status: {status}, skipping")
                return
            
            # ส่ง callback
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(
                    "ส่ง callback ไปยัง Backend: job_id=%s task_id=%s status=%s url=%s",
                    payload.get("jobId"),
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
    
    def _record_transcription_metrics(self, task_id: str, audio_path: Optional[str], 
                                     transcription_time: float, text_length: int, 
                                     chunks_count: int, success: bool, error: str = None):
        """
        บันทึก metrics สำหรับการวิเคราะห์ผล Transcription แยกจาก Audio Extraction
        
        Args:
            task_id: Task ID
            audio_path: Path ของไฟล์ audio ที่ใช้ transcription
            transcription_time: เวลาที่ใช้ในการ transcription (วินาที)
            text_length: ความยาวของข้อความที่ได้ (ตัวอักษร)
            chunks_count: จำนวน chunks/segments ที่ได้
            success: True ถ้าสำเร็จ, False ถ้าไม่สำเร็จ
            error: ข้อความ error (ถ้ามี)
        """
        try:
            metrics_dir = Path("storage/metrics")
            metrics_dir.mkdir(parents=True, exist_ok=True)
            
            metrics_file = metrics_dir / f"transcription_{task_id}.json"
            
            audio_size = Path(audio_path).stat().st_size if audio_path and Path(audio_path).exists() else None
            
            metrics = {
                "task_id": task_id,
                "type": "transcription",
                "audio_path": audio_path,
                "audio_size_bytes": audio_size,
                "transcription_time_seconds": transcription_time,
                "text_length": text_length,
                "chunks_count": chunks_count,
                "success": success,
                "error": error,
                "timestamp": utc_now().isoformat()
            }
            
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"📊 [Transcription Metrics] บันทึก metrics: {metrics_file}")
            
        except Exception as e:
            logger.warning(f"⚠️  ไม่สามารถบันทึก transcription metrics ได้: {e}") 