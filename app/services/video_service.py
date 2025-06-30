import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import ffmpeg
import json

from .file_service import FileService
from .rabbitmq_service import RabbitMQService
from ..utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

class VideoService:
    def __init__(self):
        self.file_service = FileService()
        self.json_storage = JSONStorage()
        self.rabbitmq_service = RabbitMQService()
        self.tasks: Dict[str, Dict] = {}
    
    async def trim_video(self, input_file: str, start_time: float, end_time: float,
                        output_format: str = "mp4", quality: str = "medium") -> str:
        """ตัดวิดีโอตามช่วงเวลา - ส่งไปยัง RabbitMQ queue"""
        task_id = str(uuid.uuid4())
        
        task = {
            "task_id": task_id,
            "type": "trim",
            "status": "pending",
            "input_file": input_file,
            "start_time": start_time,
            "end_time": end_time,
            "output_format": output_format,
            "quality": quality,
            "created_at": datetime.now().isoformat()
        }
        
        self.tasks[task_id] = task
        
        # บันทึกลง JSON storage
        self.json_storage.save_video_task(task_id, task)
        
        # ส่งไปยัง RabbitMQ queue
        try:
            self.rabbitmq_service.send_trim_task(
                input_file=input_file,
                start_time=start_time,
                end_time=end_time,
                output_format=output_format,
                quality=quality
            )
            logger.info(f"ส่ง trim task ไปยัง queue: {task_id}")
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง task ไปยัง queue: {e}")
            task["status"] = "failed"
            task["error_message"] = str(e)
            self.json_storage.save_video_task(task_id, task)
        
        return task_id
    
    async def merge_videos(self, input_files: List[str], output_format: str = "mp4",
                          quality: str = "medium") -> str:
        """รวมวิดีโอหลายไฟล์ - ส่งไปยัง RabbitMQ queue"""
        task_id = str(uuid.uuid4())
        
        task = {
            "task_id": task_id,
            "type": "merge",
            "status": "pending",
            "input_files": input_files,
            "output_format": output_format,
            "quality": quality,
            "created_at": datetime.now().isoformat()
        }
        
        self.tasks[task_id] = task
        
        # บันทึกลง JSON storage
        self.json_storage.save_video_task(task_id, task)
        
        # ส่งไปยัง RabbitMQ queue
        try:
            self.rabbitmq_service.send_merge_task(
                input_files=input_files,
                output_format=output_format,
                quality=quality
            )
            logger.info(f"ส่ง merge task ไปยัง queue: {task_id}")
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง task ไปยัง queue: {e}")
            task["status"] = "failed"
            task["error_message"] = str(e)
            self.json_storage.save_video_task(task_id, task)
        
        return task_id
    
    async def convert_format(self, input_file: str, output_format: str,
                           quality: str = "medium") -> str:
        """แปลงรูปแบบไฟล์ - ส่งไปยัง RabbitMQ queue"""
        task_id = str(uuid.uuid4())
        
        task = {
            "task_id": task_id,
            "type": "convert",
            "status": "pending",
            "input_file": input_file,
            "output_format": output_format,
            "quality": quality,
            "created_at": datetime.now().isoformat()
        }
        
        self.tasks[task_id] = task
        
        # บันทึกลง JSON storage
        self.json_storage.save_video_task(task_id, task)
        
        # ส่งไปยัง RabbitMQ queue
        try:
            self.rabbitmq_service.send_convert_task(
                input_file=input_file,
                output_format=output_format,
                quality=quality
            )
            logger.info(f"ส่ง convert task ไปยัง queue: {task_id}")
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง task ไปยัง queue: {e}")
            task["status"] = "failed"
            task["error_message"] = str(e)
            self.json_storage.save_video_task(task_id, task)
        
        return task_id
    
    async def resize_video(self, input_file: str, width: int, height: int,
                          output_format: str = "mp4", quality: str = "medium") -> str:
        """ปรับขนาดวิดีโอ - ส่งไปยัง RabbitMQ queue"""
        task_id = str(uuid.uuid4())
        
        task = {
            "task_id": task_id,
            "type": "resize",
            "status": "pending",
            "input_file": input_file,
            "width": width,
            "height": height,
            "output_format": output_format,
            "quality": quality,
            "created_at": datetime.now().isoformat()
        }
        
        self.tasks[task_id] = task
        
        # บันทึกลง JSON storage
        self.json_storage.save_video_task(task_id, task)
        
        # ส่งไปยัง RabbitMQ queue
        try:
            self.rabbitmq_service.send_resize_task(
                input_file=input_file,
                width=width,
                height=height,
                output_format=output_format,
                quality=quality
            )
            logger.info(f"ส่ง resize task ไปยัง queue: {task_id}")
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง task ไปยัง queue: {e}")
            task["status"] = "failed"
            task["error_message"] = str(e)
            self.json_storage.save_video_task(task_id, task)
        
        return task_id
    
    async def batch_process(self, operations: List[Dict]) -> str:
        """ประมวลผลหลายไฟล์พร้อมกัน"""
        task_id = str(uuid.uuid4())
        
        task = {
            "task_id": task_id,
            "type": "batch",
            "status": "pending",
            "operations": operations,
            "results": [],
            "created_at": datetime.now().isoformat()
        }
        
        self.tasks[task_id] = task
        
        # เริ่มการประมวลผลแบบ async
        asyncio.create_task(self._process_batch(task_id))
        
        return task_id
    
    async def _process_batch(self, task_id: str):
        """ประมวลผล batch"""
        task = self.tasks[task_id]
        task["status"] = "processing"
        
        try:
            results = []
            
            for i, operation in enumerate(task["operations"]):
                op_type = operation.get("type")
                
                if op_type == "trim":
                    sub_task_id = await self.trim_video(
                        operation["input_file"],
                        operation["start_time"],
                        operation["end_time"],
                        operation.get("output_format", "mp4"),
                        operation.get("quality", "medium")
                    )
                elif op_type == "convert":
                    sub_task_id = await self.convert_format(
                        operation["input_file"],
                        operation["output_format"],
                        operation.get("quality", "medium")
                    )
                elif op_type == "resize":
                    sub_task_id = await self.resize_video(
                        operation["input_file"],
                        operation["width"],
                        operation["height"],
                        operation.get("output_format", "mp4"),
                        operation.get("quality", "medium")
                    )
                else:
                    raise ValueError(f"ไม่รองรับ operation type: {op_type}")
                
                results.append({
                    "operation_index": i,
                    "operation_type": op_type,
                    "sub_task_id": sub_task_id
                })
            
            task["results"] = results
            task["status"] = "completed"
            task["completed_at"] = datetime.now().isoformat()
            
            # บันทึกลง JSON storage
            self.json_storage.save_video_task(task_id, task)
            
            logger.info(f"Batch processing เสร็จสิ้น: {task_id}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดใน batch processing {task_id}: {e}")
            task["status"] = "failed"
            task["error_message"] = str(e)
            task["completed_at"] = datetime.now().isoformat()
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """ดึงสถานะของ task"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Dict]:
        """ดึงรายการ tasks ทั้งหมด"""
        return list(self.tasks.values())
    
    async def cancel_task(self, task_id: str) -> bool:
        """ยกเลิก task"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task["status"] in ["pending", "processing"]:
                task["status"] = "cancelled"
                task["completed_at"] = datetime.now().isoformat()
                return True
        return False
    
    def get_video_info(self, file_path: str) -> Dict:
        """ดึงข้อมูลวิดีโอ"""
        try:
            probe = ffmpeg.probe(file_path)
            
            # ดึงข้อมูลวิดีโอ
            video_info = next((stream for stream in probe['streams'] 
                             if stream['codec_type'] == 'video'), None)
            
            # ดึงข้อมูลเสียง
            audio_info = next((stream for stream in probe['streams'] 
                             if stream['codec_type'] == 'audio'), None)
            
            return {
                "file_path": file_path,
                "duration": float(probe['format']['duration']),
                "size": int(probe['format']['size']),
                "format": probe['format']['format_name'],
                "video": {
                    "codec": video_info['codec_name'] if video_info else None,
                    "width": int(video_info['width']) if video_info else None,
                    "height": int(video_info['height']) if video_info else None,
                    "fps": eval(video_info['r_frame_rate']) if video_info else None,
                    "bitrate": int(video_info['bit_rate']) if video_info else None
                } if video_info else None,
                "audio": {
                    "codec": audio_info['codec_name'] if audio_info else None,
                    "sample_rate": int(audio_info['sample_rate']) if audio_info else None,
                    "channels": int(audio_info['channels']) if audio_info else None,
                    "bitrate": int(audio_info['bit_rate']) if audio_info else None
                } if audio_info else None
            }
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลวิดีโอ: {e}")
            return {"error": str(e)} 