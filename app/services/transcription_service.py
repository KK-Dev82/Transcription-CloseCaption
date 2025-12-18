"""
Transcription Service - จัดการ transcription tasks
"""
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timezone
from pathlib import Path
import aiohttp
import json

from .whisper_service import WhisperService
from .file_service import FileService
from ..utils.json_storage import JSONStorage
from ..models.transcription import TranscriptionResponse

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service สำหรับจัดการ transcription tasks"""
    
    def __init__(self):
        self.whisper_service = WhisperService()
        self.file_service = FileService()
        self.json_storage = JSONStorage()
        self.tasks: Dict[str, TranscriptionResponse] = {}
        logger.info("✅ TranscriptionService initialized")
    
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
        
        # ใช้ WhisperService โดยตรง
        result = self.whisper_service.transcribe_file(
            file_path,
            model_size=model_size,
            language=language,
            use_thai_processor=True
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
        """ประมวลผลด้วย chunking"""
        logger.info(f"🔄 Processing with chunking (chunk_duration={chunk_duration}s)...")
        
        # TODO: Implement chunking logic
        # สำหรับตอนนี้ ใช้ full file processing
        logger.warning("⚠️  Chunking not fully implemented, using full file processing")
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
            self.json_storage.save_transcription(task.task_id, task_dict)
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

