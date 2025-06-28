import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import ffmpeg
import json

from .file_service import FileService
from ..utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

class VideoService:
    def __init__(self):
        self.file_service = FileService()
        self.json_storage = JSONStorage()
        self.tasks: Dict[str, Dict] = {}
    
    async def trim_video(self, input_file: str, start_time: float, end_time: float,
                        output_format: str = "mp4", quality: str = "medium") -> str:
        """ตัดวิดีโอตามช่วงเวลา"""
        task_id = str(uuid.uuid4())
        
        task = {
            "task_id": task_id,
            "type": "trim",
            "status": "pending",
            "input_file": input_file,
            "start_time": start_time,
            "end_time": end_time,
            "output_format": output_format,
            "created_at": datetime.now().isoformat()
        }
        
        self.tasks[task_id] = task
        
        # เริ่มการประมวลผลแบบ async
        asyncio.create_task(self._process_trim_video(task_id))
        
        return task_id
    
    async def _process_trim_video(self, task_id: str):
        """ประมวลผลการตัดวิดีโอ"""
        task = self.tasks[task_id]
        task["status"] = "processing"
        
        try:
            input_path = Path(task["input_file"])
            if not input_path.exists():
                raise FileNotFoundError(f"ไม่พบไฟล์: {task['input_file']}")
            
            # สร้างชื่อไฟล์ output
            output_filename = f"trimmed_{task_id}.{task['output_format']}"
            output_path = self.file_service.upload_dir / output_filename
            
            # ตั้งค่า FFmpeg parameters
            duration = task["end_time"] - task["start_time"]
            
            # ใช้ FFmpeg ตัดวิดีโอ
            stream = ffmpeg.input(
                str(input_path), 
                ss=task["start_time"], 
                t=duration
            )
            
            # ตั้งค่า quality
            if task["output_format"] == "mp4":
                if task["quality"] == "high":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=18, preset='slow')
                elif task["quality"] == "medium":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=23, preset='medium')
                else:  # low
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=28, preset='fast')
            else:
                stream = ffmpeg.output(stream, str(output_path))
            
            # รัน FFmpeg
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            # อัปเดต task
            task["status"] = "completed"
            task["output_file"] = str(output_path)
            task["completed_at"] = datetime.now().isoformat()
            
            # บันทึกลง JSON storage
            self.json_storage.save_video_task(task_id, task)
            
            logger.info(f"ตัดวิดีโอเสร็จสิ้น: {task_id}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการตัดวิดีโอ {task_id}: {e}")
            task["status"] = "failed"
            task["error_message"] = str(e)
            task["completed_at"] = datetime.now().isoformat()
    
    async def merge_videos(self, input_files: List[str], output_format: str = "mp4",
                          quality: str = "medium") -> str:
        """รวมวิดีโอหลายไฟล์"""
        task_id = str(uuid.uuid4())
        
        task = {
            "task_id": task_id,
            "type": "merge",
            "status": "pending",
            "input_files": input_files,
            "output_format": output_format,
            "created_at": datetime.now().isoformat()
        }
        
        self.tasks[task_id] = task
        
        # เริ่มการประมวลผลแบบ async
        asyncio.create_task(self._process_merge_videos(task_id))
        
        return task_id
    
    async def _process_merge_videos(self, task_id: str):
        """ประมวลผลการรวมวิดีโอ"""
        task = self.tasks[task_id]
        task["status"] = "processing"
        
        try:
            # ตรวจสอบไฟล์ input
            for input_file in task["input_files"]:
                if not Path(input_file).exists():
                    raise FileNotFoundError(f"ไม่พบไฟล์: {input_file}")
            
            # สร้างไฟล์ list สำหรับ FFmpeg
            list_file = self.file_service.temp_dir / f"merge_list_{task_id}.txt"
            with open(list_file, 'w', encoding='utf-8') as f:
                for input_file in task["input_files"]:
                    f.write(f"file '{input_file}'\n")
            
            # สร้างชื่อไฟล์ output
            output_filename = f"merged_{task_id}.{task['output_format']}"
            output_path = self.file_service.upload_dir / output_filename
            
            # ใช้ FFmpeg รวมวิดีโอ
            stream = ffmpeg.input(str(list_file), f='concat', safe=0)
            
            # ตั้งค่า quality
            if task["output_format"] == "mp4":
                if task["quality"] == "high":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=18, preset='slow')
                elif task["quality"] == "medium":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=23, preset='medium')
                else:  # low
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=28, preset='fast')
            else:
                stream = ffmpeg.output(stream, str(output_path))
            
            # รัน FFmpeg
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            # ลบไฟล์ list
            list_file.unlink(missing_ok=True)
            
            # อัปเดต task
            task["status"] = "completed"
            task["output_file"] = str(output_path)
            task["completed_at"] = datetime.now().isoformat()
            
            # บันทึกลง JSON storage
            self.json_storage.save_video_task(task_id, task)
            
            logger.info(f"รวมวิดีโอเสร็จสิ้น: {task_id}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการรวมวิดีโอ {task_id}: {e}")
            task["status"] = "failed"
            task["error_message"] = str(e)
            task["completed_at"] = datetime.now().isoformat()
    
    async def convert_format(self, input_file: str, output_format: str,
                           quality: str = "medium") -> str:
        """แปลงรูปแบบไฟล์"""
        task_id = str(uuid.uuid4())
        
        task = {
            "task_id": task_id,
            "type": "convert",
            "status": "pending",
            "input_file": input_file,
            "output_format": output_format,
            "created_at": datetime.now().isoformat()
        }
        
        self.tasks[task_id] = task
        
        # เริ่มการประมวลผลแบบ async
        asyncio.create_task(self._process_convert_format(task_id))
        
        return task_id
    
    async def _process_convert_format(self, task_id: str):
        """ประมวลผลการแปลงรูปแบบ"""
        task = self.tasks[task_id]
        task["status"] = "processing"
        
        try:
            input_path = Path(task["input_file"])
            if not input_path.exists():
                raise FileNotFoundError(f"ไม่พบไฟล์: {task['input_file']}")
            
            # สร้างชื่อไฟล์ output
            output_filename = f"converted_{task_id}.{task['output_format']}"
            output_path = self.file_service.upload_dir / output_filename
            
            # ใช้ FFmpeg แปลงรูปแบบ
            stream = ffmpeg.input(str(input_path))
            
            # ตั้งค่า quality ตาม output format
            if task["output_format"] == "mp4":
                if task["quality"] == "high":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=18, preset='slow')
                elif task["quality"] == "medium":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=23, preset='medium')
                else:  # low
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=28, preset='fast')
            elif task["output_format"] == "avi":
                stream = ffmpeg.output(stream, str(output_path), 
                                     vcodec='libx264', acodec='mp3')
            elif task["output_format"] == "mov":
                stream = ffmpeg.output(stream, str(output_path), 
                                     vcodec='libx264', acodec='aac')
            else:
                stream = ffmpeg.output(stream, str(output_path))
            
            # รัน FFmpeg
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            # อัปเดต task
            task["status"] = "completed"
            task["output_file"] = str(output_path)
            task["completed_at"] = datetime.now().isoformat()
            
            # บันทึกลง JSON storage
            self.json_storage.save_video_task(task_id, task)
            
            logger.info(f"แปลงรูปแบบเสร็จสิ้น: {task_id}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแปลงรูปแบบ {task_id}: {e}")
            task["status"] = "failed"
            task["error_message"] = str(e)
            task["completed_at"] = datetime.now().isoformat()
    
    async def resize_video(self, input_file: str, width: int, height: int,
                          output_format: str = "mp4", quality: str = "medium") -> str:
        """ปรับขนาดวิดีโอ"""
        task_id = str(uuid.uuid4())
        
        task = {
            "task_id": task_id,
            "type": "resize",
            "status": "pending",
            "input_file": input_file,
            "width": width,
            "height": height,
            "output_format": output_format,
            "created_at": datetime.now().isoformat()
        }
        
        self.tasks[task_id] = task
        
        # เริ่มการประมวลผลแบบ async
        asyncio.create_task(self._process_resize_video(task_id))
        
        return task_id
    
    async def _process_resize_video(self, task_id: str):
        """ประมวลผลการปรับขนาดวิดีโอ"""
        task = self.tasks[task_id]
        task["status"] = "processing"
        
        try:
            input_path = Path(task["input_file"])
            if not input_path.exists():
                raise FileNotFoundError(f"ไม่พบไฟล์: {task['input_file']}")
            
            # สร้างชื่อไฟล์ output
            output_filename = f"resized_{task_id}.{task['output_format']}"
            output_path = self.file_service.upload_dir / output_filename
            
            # ใช้ FFmpeg ปรับขนาดวิดีโอ
            stream = ffmpeg.input(str(input_path))
            stream = ffmpeg.filter(stream, 'scale', 
                                 task["width"], task["height"])
            
            # ตั้งค่า quality
            if task["output_format"] == "mp4":
                if task["quality"] == "high":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=18, preset='slow')
                elif task["quality"] == "medium":
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=23, preset='medium')
                else:  # low
                    stream = ffmpeg.output(stream, str(output_path), 
                                         vcodec='libx264', acodec='aac',
                                         crf=28, preset='fast')
            else:
                stream = ffmpeg.output(stream, str(output_path))
            
            # รัน FFmpeg
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            # อัปเดต task
            task["status"] = "completed"
            task["output_file"] = str(output_path)
            task["completed_at"] = datetime.now().isoformat()
            
            # บันทึกลง JSON storage
            self.json_storage.save_video_task(task_id, task)
            
            logger.info(f"ปรับขนาดวิดีโอเสร็จสิ้น: {task_id}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการปรับขนาดวิดีโอ {task_id}: {e}")
            task["status"] = "failed"
            task["error_message"] = str(e)
            task["completed_at"] = datetime.now().isoformat()
    
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