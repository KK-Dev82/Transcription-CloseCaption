import asyncio
import uuid
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import aiohttp
import json

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
        
        # API server URL สำหรับ notifications
        # ใช้ environment variable หรือ default ตาม environment
        environment = os.getenv('ENVIRONMENT', 'development')
        if environment == 'development':
            self.api_server_url = "http://transcription-api-dev:8001"
        elif environment == 'staging':
            self.api_server_url = "http://transcription-api-staging:8001"
        elif environment == 'local':
            self.api_server_url = "http://api:8001"
        else:  # production
            self.api_server_url = "http://transcription-api:8001"
    
    async def start_transcription(self, file_path: str, language: str = "th",
                                model_size: str = "base", chunk_duration: int = 30) -> str:
        """เริ่มการแปลงเสียงเป็นข้อความ - ส่งไปยัง RabbitMQ queue"""
        
        # ส่งไปยัง RabbitMQ queue และรับ task_id
        try:
            task_id = self.rabbitmq_service.send_transcription_task(
                file_path=file_path,
                language=language,
                model_size=model_size,
                chunk_duration=chunk_duration
            )
            
            # สร้าง task response
            task = TranscriptionResponse(
                task_id=task_id,
                status="pending",
                file_path=file_path,
                language=language,
                created_at=datetime.now()
            )
            
            self.tasks[task_id] = task
            
            logger.info(f"ส่ง transcription task ไปยัง queue: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง task ไปยัง queue: {e}")
            # สร้าง task_id ใหม่สำหรับ error case
            task_id = str(uuid.uuid4())
            task = TranscriptionResponse(
                task_id=task_id,
                status="failed",
                file_path=file_path,
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
                    "language": language,
                    "status": "failed",
                    "error_message": str(e),
                    "created_at": datetime.now().timestamp()
                }
                self.json_storage.save_transcription(task_id, task_data)
            except Exception as storage_error:
                logger.error(f"ไม่สามารถบันทึก task ลง storage: {storage_error}")
            
            return task_id
    
    async def _process_transcription(self, task_id: str, file_path: str,
                                   language: str, model_size: str, chunk_duration: int):
        """ประมวลผลการแปลงเสียง"""
        task = self.tasks[task_id]
        task.status = "processing"
        
        # 🌐 WebSocket: แจ้งเตือนเริ่มต้น (HTTP call to API server)
        try:
            await self._notify_api_server("started", task_id, {
                "file_path": file_path,
                "language": language,
                "status": "started"
            })
        except Exception as e:
            logger.warning(f"WebSocket notification failed (started): {e}")
        
        try:
            # ตรวจสอบไฟล์
            if not Path(file_path).exists():
                raise FileNotFoundError(f"ไฟล์ไม่พบ: {file_path}")
            
            # สร้าง audio chunks
            logger.info("กำลังแบ่งไฟล์เป็น audio chunks...")
            chunks = self.video_service.extract_audio_chunks(file_path, chunk_duration)
            
            # ดึงข้อมูลไฟล์
            file_info = self.file_service.get_file_info(file_path)
            task.total_duration = file_info.get("duration")
            
            # แปลงเสียงแต่ละ chunk พร้อม progress tracking
            logger.info(f"กำลังแปลงเสียง {len(chunks)} chunks...")
            task.status = "processing"
            task.progress = 10  # เริ่มต้น
            self.json_storage.save_transcription(task_id, task.__dict__)
            
            chunk_results = []
            total_chunks = len(chunks)
            
            for i, chunk_path in enumerate(chunks):
                try:
                    logger.info(f"กำลังแปลง chunk {i+1}/{total_chunks}")
                    result = self.whisper_service.transcribe_file(
                        chunk_path, model_size, language, use_thai_processor=True
                    )
                    chunk_results.append(result)
                    
                    # อัปเดต progress
                    progress = 10 + int((i + 1) / total_chunks * 80)  # 10-90%
                    task.progress = progress
                    task.status = f"processing_chunk_{i+1}_of_{total_chunks}"
                    self.json_storage.save_transcription(task_id, task.__dict__)
                    
                    # 🌐 WebSocket: แจ้งเตือน progress (ทุก 25% หรือ chunk สุดท้าย)
                    if progress % 25 == 0 or i == total_chunks - 1:
                        try:
                            await self._notify_api_server("progress", task_id, {
                                "progress": progress,
                                "status": task.status,
                                "stage": f"processing_chunk_{i+1}_of_{total_chunks}"
                            })
                        except Exception as e:
                            logger.warning(f"WebSocket notification failed (progress): {e}")
                    
                    logger.info(f"เสร็จ chunk {i+1}/{total_chunks} - Progress: {progress}%")
                    
                except Exception as e:
                    logger.error(f"เกิดข้อผิดพลาดในการแปลง chunk {i}: {e}")
                    chunk_results.append({"error": str(e)})
            
            # รวมผลลัพธ์
            logger.info("กำลังรวมผลลัพธ์...")
            task.progress = 90
            task.status = "merging_results"
            self.json_storage.save_transcription(task_id, task.__dict__)
            
            merged_result = self.whisper_service.merge_transcriptions(
                chunk_results, chunk_duration
            )
            
            logger.info(f"Merged result: {merged_result}")
            
            # แปลงเป็น TranscriptionChunk objects
            task.chunks = []
            if "segments" in merged_result and merged_result["segments"]:
                for segment in merged_result["segments"]:
                    chunk = TranscriptionChunk(
                        start_time=segment["start"],
                        end_time=segment["end"],
                        text=segment.get("text", ""),
                        confidence=segment.get("avg_logprob", None)
                    )
                    task.chunks.append(chunk)
            else:
                logger.warning("No segments found in merged result")
            
            task.full_text = merged_result.get("text", "")
            task.progress = 95
            task.status = "finalizing"
            task.updated_at = datetime.now()
            
            logger.info(f"Final task data - full_text: '{task.full_text}', chunks: {len(task.chunks)}")
            
            # แปลง task เป็น dict ที่ JSON serializable ได้
            task_data = {
                "task_id": task.task_id,
                "status": task.status,
                "file_path": task.file_path,
                "total_duration": task.total_duration,
                "chunks": [chunk.dict() for chunk in task.chunks] if task.chunks else [],
                "full_text": task.full_text,
                "language": task.language,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "error_message": task.error_message,
                "progress": task.progress
            }
            self.json_storage.save_transcription(task_id, task_data)
            
            task.status = "completed"
            task.progress = 100
            task.completed_at = datetime.now()
            
            # 🧹 ลบ temp files หลังเสร็จสิ้น
            try:
                self.file_service.cleanup_temp_files(chunks)
                logger.info(f"ลบ temp files สำเร็จ: {len(chunks)} files")
            except Exception as e:
                logger.warning(f"ไม่สามารถลบ temp files: {e}")
            
            # 🌐 WebSocket: แจ้งเตือนเสร็จสิ้น (HTTP call to API server)
            try:
                await self._notify_api_server("completed", task_id, {
                    "status": "completed",
                    "progress": 100,
                    "results_summary": {
                        "text": task.full_text,
                        "chunks_count": len(task.chunks) if task.chunks else 0,
                        "duration": task.total_duration
                    }
                })
            except Exception as e:
                logger.warning(f"WebSocket notification failed (completed): {e}")
            
            # บันทึกข้อมูลสุดท้าย - ครั้งเดียวเท่านั้น
            logger.info("กำลังบันทึกผลลัพธ์สุดท้าย...")
            final_data = {
                "task_id": task.task_id,
                "status": task.status,
                "file_path": task.file_path,
                "total_duration": task.total_duration,
                "chunks": [chunk.dict() for chunk in task.chunks] if task.chunks else [],
                "full_text": task.full_text,
                "language": task.language,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "error_message": task.error_message,
                "progress": task.progress
            }
            self.json_storage.save_transcription(task_id, final_data)
            
            logger.info(f"แปลงเสียงเสร็จสิ้น: {task_id}")
            
            # ลบไฟล์ชั่วคราวหลังจากประมวลผลเสร็จแล้ว (ปิดไว้เพื่อ debug)
            # if 'chunks' in locals():
            #     self.file_service.cleanup_temp_files(chunks)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแปลงเสียง {task_id}: {e}")
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            
            # 🌐 WebSocket: แจ้งเตือนเมื่อล้มเหลว (HTTP call to API server)
            try:
                await self._notify_api_server("failed", task_id, {
                    "status": "failed",
                    "error": str(e)
                })
            except Exception as websocket_error:
                logger.warning(f"WebSocket notification failed (error): {websocket_error}")
            
            # ลบไฟล์ชั่วคราวในกรณีเกิดข้อผิดพลาด (ปิดไว้เพื่อ debug)
            # if 'chunks' in locals():
            #     self.file_service.cleanup_temp_files(chunks)
    
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
    
    async def _notify_api_server(self, event_type: str, task_id: str, data: dict):
        """ส่ง notification ไปยัง API server เพื่อ broadcast ผ่าน WebSocket"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "type": f"transcription.{event_type}",
                    "task_id": task_id,
                    "timestamp": datetime.now().isoformat(),
                    **data
                }
                
                async with session.post(
                    f"{self.api_server_url}/internal/websocket-broadcast",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ WebSocket notification sent: {event_type} for task {task_id}")
                    else:
                        logger.warning(f"⚠️ WebSocket notification failed: {response.status}")
                        
        except Exception as e:
            logger.error(f"❌ Failed to send WebSocket notification: {e}") 