import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from .file_service import FileService
from .whisper_service import WhisperService
from ..models.transcription import TranscriptionChunk, TranscriptionResponse
from ..utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(self):
        self.file_service = FileService()
        self.whisper_service = WhisperService()
        self.json_storage = JSONStorage()
        self.tasks: Dict[str, TranscriptionResponse] = {}
    
    async def start_transcription(self, file_path: str, language: str = "th",
                                model_size: str = "base", chunk_duration: int = 30) -> str:
        """เริ่มการแปลงเสียงเป็นข้อความ"""
        task_id = str(uuid.uuid4())
        
        # สร้าง task response
        task = TranscriptionResponse(
            task_id=task_id,
            status="pending",
            file_path=file_path,
            language=language,
            created_at=datetime.now()
        )
        
        self.tasks[task_id] = task
        
        # เริ่มการประมวลผลแบบ async
        asyncio.create_task(self._process_transcription(
            task_id, file_path, language, model_size, chunk_duration
        ))
        
        return task_id
    
    async def _process_transcription(self, task_id: str, file_path: str,
                                   language: str, model_size: str, chunk_duration: int):
        """ประมวลผลการแปลงเสียง"""
        task = self.tasks[task_id]
        task.status = "processing"
        
        try:
            # ตรวจสอบไฟล์
            if not Path(file_path).exists():
                raise FileNotFoundError(f"ไฟล์ไม่พบ: {file_path}")
            
            # แยกเสียงจากวิดีโอ (ถ้าจำเป็น)
            audio_path = file_path
            if self.file_service.is_video_file(file_path):
                logger.info("กำลังแยกเสียงจากวิดีโอ...")
                audio_path = self.file_service.extract_audio(file_path)
            
            # สร้าง chunks
            logger.info("กำลังแบ่งไฟล์เป็น chunks...")
            chunks = self.file_service.create_chunks(audio_path, chunk_duration)
            
            # ดึงข้อมูลไฟล์
            file_info = self.file_service.get_file_info(file_path)
            task.total_duration = file_info.get("duration")
            
            # แปลงเสียงแต่ละ chunk
            logger.info(f"กำลังแปลงเสียง {len(chunks)} chunks...")
            chunk_results = self.whisper_service.transcribe_chunks(
                chunks, model_size, language
            )
            
            # รวมผลลัพธ์
            logger.info("กำลังรวมผลลัพธ์...")
            merged_result = self.whisper_service.merge_transcriptions(
                chunk_results, chunk_duration
            )
            
            # แปลงเป็น TranscriptionChunk objects
            task.chunks = []
            if "segments" in merged_result:
                for segment in merged_result["segments"]:
                    chunk = TranscriptionChunk(
                        start_time=segment["start"],
                        end_time=segment["end"],
                        text=segment.get("text", ""),
                        confidence=segment.get("avg_logprob", None)
                    )
                    task.chunks.append(chunk)
            
            task.full_text = merged_result.get("text", "")
            task.status = "completed"
            task.completed_at = datetime.now()
            
            # บันทึกลง JSON storage
            logger.info("กำลังบันทึกข้อมูลลง JSON...")
            transcription_data = {
                "file_path": task.file_path,
                "language": task.language,
                "total_duration": task.total_duration,
                "chunks": [chunk.dict() for chunk in task.chunks],
                "full_text": task.full_text,
                "status": task.status
            }
            self.json_storage.save_transcription(task_id, transcription_data)
            
            logger.info(f"แปลงเสียงเสร็จสิ้น: {task_id}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแปลงเสียง {task_id}: {e}")
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
        
        finally:
            # ลบไฟล์ชั่วคราว
            if 'audio_path' in locals() and audio_path != file_path:
                self.file_service.cleanup_temp_files([audio_path])
            if 'chunks' in locals():
                self.file_service.cleanup_temp_files(chunks)
    
    def get_task_status(self, task_id: str) -> Optional[TranscriptionResponse]:
        """ดึงสถานะของ task"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[TranscriptionResponse]:
        """ดึงรายการ tasks ทั้งหมด"""
        return list(self.tasks.values())
    
    async def cancel_task(self, task_id: str) -> bool:
        """ยกเลิก task"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status == "pending" or task.status == "processing":
                task.status = "cancelled"
                task.completed_at = datetime.now()
                return True
        return False
    
    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """ลบ tasks ที่เสร็จสิ้นแล้ว"""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        tasks_to_remove = []
        for task_id, task in self.tasks.items():
            if (task.status in ["completed", "failed", "cancelled"] and 
                task.created_at.timestamp() < cutoff_time):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
        
        logger.info(f"ลบ tasks เก่า {len(tasks_to_remove)} รายการ")
    
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