import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from .file_service import FileService
from .whisper_service import WhisperService
from ..models.caption import CaptionSegment, CaptionResponse
from ..utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

class CaptionService:
    def __init__(self):
        self.file_service = FileService()
        self.whisper_service = WhisperService()
        self.json_storage = JSONStorage()
        self.tasks: Dict[str, CaptionResponse] = {}
    
    async def start_caption_generation(self, file_path: str, language: str = "th",
                                     model_size: str = "tiny", subtitle_format: str = "srt") -> str:
        """เริ่มการสร้าง close caption"""
        task_id = str(uuid.uuid4())
        
        # สร้าง task response
        task = CaptionResponse(
            task_id=task_id,
            status="pending",
            file_path=file_path,
            subtitle_format=subtitle_format,
            language=language,
            created_at=datetime.now()
        )
        
        self.tasks[task_id] = task
        
        # เริ่มการประมวลผลแบบ async
        asyncio.create_task(self._process_caption(
            task_id, file_path, language, model_size, subtitle_format
        ))
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[CaptionResponse]:
        """ดึงสถานะ task"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[CaptionResponse]:
        """ดึง tasks ทั้งหมด"""
        return list(self.tasks.values())
    
    async def _process_caption(self, task_id: str, file_path: str,
                             language: str, model_size: str, subtitle_format: str):
        """ประมวลผลการสร้าง close caption"""
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
            
            # สำหรับ close caption ใช้ chunk เล็กกว่า (5-10 วินาที)
            chunk_duration = 5 if model_size == "tiny" else 10
            
            # สร้าง chunks
            logger.info("กำลังแบ่งไฟล์เป็น chunks...")
            chunks = self.file_service.create_chunks(audio_path, chunk_duration)
            
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
            
            # แปลงเป็น CaptionSegment objects
            task.segments = []
            if "segments" in merged_result:
                for segment in merged_result["segments"]:
                    caption_segment = CaptionSegment(
                        start_time=segment["start"],
                        end_time=segment["end"],
                        text=segment.get("text", ""),
                        confidence=segment.get("avg_logprob", None)
                    )
                    task.segments.append(caption_segment)
            
            # สร้าง subtitle content
            if subtitle_format == "srt":
                task.subtitle_content = self.whisper_service.create_srt_subtitles(merged_result)
            elif subtitle_format == "vtt":
                task.subtitle_content = self._create_vtt_subtitles(merged_result)
            elif subtitle_format == "json":
                import json
                task.subtitle_content = json.dumps(merged_result, ensure_ascii=False, indent=2)
            
            task.status = "completed"
            task.completed_at = datetime.now()
            
            # บันทึกผลลัพธ์ลง storage
            caption_data = {
                "task_id": task.task_id,
                "status": task.status,
                "file_path": task.file_path,
                "language": task.language,
                "subtitle_format": task.subtitle_format,
                "subtitle_content": task.subtitle_content,
                "segments": [segment.dict() for segment in task.segments] if task.segments else [],
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "error_message": task.error_message
            }
            self.json_storage.save_caption(task_id, caption_data)
            
            logger.info(f"สร้าง close caption เสร็จสิ้น: {task_id}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการสร้าง close caption {task_id}: {e}")
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
        
        finally:
            # ลบไฟล์ชั่วคราว
            if 'audio_path' in locals() and audio_path != file_path:
                self.file_service.cleanup_temp_files([audio_path])
            if 'chunks' in locals():
                self.file_service.cleanup_temp_files(chunks)
    
    def _create_vtt_subtitles(self, transcription: Dict) -> str:
        """สร้างไฟล์ VTT subtitle"""
        vtt_content = "WEBVTT\n\n"
        
        if "segments" not in transcription:
            return vtt_content
        
        for i, segment in enumerate(transcription["segments"], 1):
            start_time = self._format_vtt_timestamp(segment["start"])
            end_time = self._format_vtt_timestamp(segment["end"])
            text = segment.get("text", "").strip()
            
            vtt_content += f"{start_time} --> {end_time}\n"
            vtt_content += f"{text}\n\n"
        
        return vtt_content
    
    def _format_vtt_timestamp(self, seconds: float) -> str:
        """แปลงวินาทีเป็นรูปแบบ VTT timestamp"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millisecs:03d}"
    
    def get_task_status(self, task_id: str) -> Optional[CaptionResponse]:
        """ดึงสถานะของ task"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[CaptionResponse]:
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
        
        logger.info(f"ลบ caption tasks เก่า {len(tasks_to_remove)} รายการ") 