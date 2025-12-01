import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import ffmpeg
import json
import os
import time

from .file_service import FileService
from .rabbitmq_service import RabbitMQService
from .whisper_service import WhisperService
from ..utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

class VideoService:
    def __init__(self):
        self.file_service = FileService()
        self.json_storage = JSONStorage()
        self.rabbitmq_service = RabbitMQService()
        self.whisper_service = WhisperService()
        self.tasks: Dict[str, Dict] = {}
        self.segmentation_tasks = {}  # เก็บสถานะ segmentation tasks
    
    async def trim_video(self, input_file: str, start_time: float, end_time: float,
                        output_format: str = "mp4", quality: str = "medium") -> str:
        """ตัดวิดีโอตามช่วงเวลา - ส่งไปยัง RabbitMQ queue"""
        
        # ส่งไปยัง RabbitMQ queue และรับ task_id
        try:
            task_id = self.rabbitmq_service.send_trim_task(
                input_file=input_file,
                start_time=start_time,
                end_time=end_time,
                output_format=output_format,
                quality=quality
            )
            
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
            
            logger.info(f"ส่ง trim task ไปยัง queue: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง task ไปยัง queue: {e}")
            # สร้าง task_id ใหม่สำหรับ error case
            task_id = str(uuid.uuid4())
            task = {
                "task_id": task_id,
                "type": "trim",
                "status": "failed",
                "input_file": input_file,
                "start_time": start_time,
                "end_time": end_time,
                "output_format": output_format,
                "quality": quality,
                "created_at": datetime.now().isoformat(),
                "error_message": str(e)
            }
            self.tasks[task_id] = task
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
    
    async def process_video_segmentation(
        self, 
        task_id: str, 
        file_path: str, 
        segment_duration: int = 600, 
        overlap: int = 5,
        language: str = "th",
        model_size: str = "base"
    ):
        """ประมวลผลการแบ่งตอนวิดีโอและทำ transcription แบบ batch"""
        try:
            logger.info(f"เริ่มประมวลผล video segmentation: {task_id}")
            
            # 1. ดึงข้อมูลวิดีโอ
            video_info = self.get_video_info(file_path)
            if "error" in video_info:
                self.segmentation_tasks[task_id] = {
                    "task_id": task_id,
                    "status": "failed",
                    "error": video_info["error"]
                }
                return
            
            duration = video_info.get("duration", 0)
            if duration == 0:
                self.segmentation_tasks[task_id] = {
                    "task_id": task_id,
                    "status": "failed",
                    "error": "ไม่สามารถดึงความยาววิดีโอได้"
                }
                return
            
            # 2. สร้าง segments
            segments = self._create_segments(duration, segment_duration, overlap)
            
            # 3. เริ่มต้น task
            self.segmentation_tasks[task_id] = {
                "task_id": task_id,
                "status": "processing",
                "progress": 0,
                "current_segment": 0,
                "total_segments": len(segments),
                "file_path": file_path,
                "segments": [],
                "created_at": datetime.now().isoformat(),
                "started_at": datetime.now().isoformat()
            }
            
            logger.info(f"เริ่มประมวลผล {len(segments)} segments")
            
            # 4. ประมวลผล segments แบบคิวต่อเนื่อง
            completed_segments = []
            for i, segment in enumerate(segments):
                try:
                    logger.info(f"ประมวลผล segment {i+1}/{len(segments)}")
                    
                    # อัปเดต current_segment
                    self.segmentation_tasks[task_id]["current_segment"] = i + 1
                    
                    # 1. ตัด segment
                    trim_result = await self._trim_segment_async(file_path, segment)
                    if not trim_result:
                        logger.error(f"ไม่สามารถตัด segment {i+1} ได้")
                        continue
                    
                    segment_file_path = trim_result.get('output_path')
                    
                    # 2. ทำ transcription (คิวต่อเนื่อง)
                    transcribe_result = await self._transcribe_segment_async(
                        segment_file_path, language, model_size
                    )
                    if not transcribe_result:
                        logger.error(f"ไม่สามารถทำ transcription segment {i+1} ได้")
                        continue
                    
                    # 3. สร้างผลลัพธ์
                    segment_result = {
                        'segment_number': i + 1,
                        'start_time': segment['start_time'],
                        'end_time': segment['end_time'],
                        'segment_file': segment_file_path,
                        'transcription': transcribe_result
                    }
                    
                    completed_segments.append(segment_result)
                    
                    # อัปเดต progress
                    progress = int((i + 1) / len(segments) * 100)
                    self.segmentation_tasks[task_id]["progress"] = progress
                    self.segmentation_tasks[task_id]["segments"] = completed_segments
                    
                    logger.info(f"เสร็จสิ้น segment {i+1}, progress: {progress}%")
                    
                except Exception as e:
                    logger.error(f"เกิดข้อผิดพลาดในการประมวลผล segment {i+1}: {str(e)}")
                    continue
            
            # 5. เสร็จสิ้น
            if len(completed_segments) == len(segments):
                self.segmentation_tasks[task_id]["status"] = "completed"
                self.segmentation_tasks[task_id]["completed_at"] = datetime.now().isoformat()
                logger.info(f"เสร็จสิ้น video segmentation: {task_id}")
            else:
                self.segmentation_tasks[task_id]["status"] = "completed_with_errors"
                self.segmentation_tasks[task_id]["completed_at"] = datetime.now().isoformat()
                self.segmentation_tasks[task_id]["error"] = f"เสร็จสิ้น {len(completed_segments)}/{len(segments)} segments"
                logger.warning(f"เสร็จสิ้น video segmentation ด้วยข้อผิดพลาด: {task_id}")
            
            # 6. บันทึกผลลัพธ์
            self._save_segmentation_results(task_id)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล video segmentation: {str(e)}")
            self.segmentation_tasks[task_id] = {
                "task_id": task_id,
                "status": "failed",
                "error": str(e)
            }
    
    async def _trim_segment_async(self, file_path: str, segment: Dict) -> Optional[Dict]:
        """ตัด segment แบบ async"""
        try:
            # ส่งงานไปยัง RabbitMQ
            task_id = self.rabbitmq_service.send_trim_task(
                input_file=file_path,
                start_time=segment['start_time'],
                end_time=segment['end_time'],
                output_format="mp4",
                quality="medium",
                segment_number=segment.get('segment_number', 1)
            )
            
            # รอให้เสร็จสิ้นแบบ async
            max_wait = 300  # 5 นาที
            wait_time = 0
            while wait_time < max_wait:
                await asyncio.sleep(5)
                wait_time += 5
                
                # ตรวจสอบสถานะจาก storage
                status = self.json_storage.load_video_task(task_id)
                if status and status.get('status') == 'completed':
                    return {
                        'output_path': status.get('output_file'),
                        'status': 'completed'
                    }
                elif status and status.get('status') == 'failed':
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการตัด segment: {str(e)}")
            return None
    
    async def _transcribe_segment_async(self, file_path: str, language: str, model_size: str) -> Optional[Dict]:
        """ทำ transcription แบบ async"""
        try:
            from .transcription_service import TranscriptionService
            transcription_service = TranscriptionService()
            
            # ส่งงาน transcription
            task_id = await transcription_service.start_transcription(
                file_path=file_path,
                language=language,
                model_size=model_size
            )
            
            # รอให้เสร็จสิ้นแบบ async
            max_wait = 300  # 5 นาที
            wait_time = 0
            while wait_time < max_wait:
                await asyncio.sleep(5)
                wait_time += 5
                
                # ตรวจสอบสถานะ
                status = transcription_service.get_task_status(task_id)
                if status and status.status == 'completed':
                    return {
                        'task_id': task_id,
                        'text': status.full_text,
                        'chunks': [chunk.dict() for chunk in status.chunks] if status.chunks else [],
                        'status': 'completed'
                    }
                elif status and status.status == 'failed':
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการทำ transcription: {str(e)}")
            return None
    
    def get_segmentation_status(self, task_id: str) -> Dict:
        """ตรวจสอบสถานะการแบ่งตอนวิดีโอ"""
        if task_id not in self.segmentation_tasks:
            return {
                "task_id": task_id,
                "status": "not_found",
                "message": "ไม่พบ task"
            }
        
        return self.segmentation_tasks[task_id]
    
    def _create_segments(self, duration: float, segment_duration: int, overlap: int) -> List[Dict]:
        """สร้างรายการ segments ตาม overlap"""
        segments = []
        start_time = 0
        segment_number = 1
        
        while start_time < duration:
            end_time = min(start_time + segment_duration, duration)
            
            segment = {
                'start_time': start_time,
                'end_time': end_time,
                'duration': end_time - start_time,
                'segment_number': segment_number
            }
            segments.append(segment)
            
            # เลื่อนไปยัง segment ถัดไป (ลบ overlap)
            start_time = end_time - overlap
            segment_number += 1
            
            # ถ้าเหลือน้อยกว่า segment_duration ให้หยุด
            if start_time + segment_duration >= duration:
                # สร้าง segment สุดท้าย
                final_end = min(start_time + segment_duration, duration)
                if final_end > start_time:  # ตรวจสอบว่ามีเนื้อหาเหลือ
                    final_segment = {
                        'start_time': start_time,
                        'end_time': final_end,
                        'duration': final_end - start_time,
                        'segment_number': segment_number
                    }
                    segments.append(final_segment)
                break
        
        logger.info(f"สร้าง {len(segments)} segments จากวิดีโอความยาว {duration} วินาที")
        for i, seg in enumerate(segments):
            logger.info(f"Segment {i+1}: {seg['start_time']:.1f}s - {seg['end_time']:.1f}s (ความยาว: {seg['duration']:.1f}s)")
        
        return segments
    
    def _save_segmentation_results(self, task_id: str):
        """บันทึกผลลัพธ์การแบ่งตอน"""
        try:
            if task_id not in self.segmentation_tasks:
                return
            
            task_data = self.segmentation_tasks[task_id]
            
            # สร้างไฟล์ผลลัพธ์
            output_file = f"storage/segmentation_{task_id}.json"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, indent=2, ensure_ascii=False)
            
            # สร้างไฟล์ข้อความรวม
            text_file = f"storage/transcription_{task_id}.txt"
            with open(text_file, 'w', encoding='utf-8') as f:
                for segment in task_data.get('segments', []):
                    transcription = segment.get('transcription', {})
                    text = transcription.get('text', '')
                    start_time = segment.get('start_time', 0)
                    end_time = segment.get('end_time', 0)
                    f.write(f"[{start_time:.1f}s-{end_time:.1f}s] {text}\n")
            
            logger.info(f"บันทึกผลลัพธ์ segmentation: {output_file}")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการบันทึกผลลัพธ์: {str(e)}")

    def extract_audio(self, video_path: str, output_path: str = None) -> str:
        """
        Extract audio ทั้งไฟล์จาก video (ไม่ chunk)
        
        Args:
            video_path: Path ไปยังไฟล์ video
            output_path: Path สำหรับไฟล์ audio output (ถ้าไม่ระบุจะสร้างอัตโนมัติ)
            
        Returns:
            Path ไปยังไฟล์ audio ที่ extract แล้ว
        """
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # สร้าง output path ถ้าไม่ระบุ
        if output_path is None:
            output_dir = video_path_obj.parent / "temp" / f"audio_{int(time.time())}"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / f"{video_path_obj.stem}_audio.wav")
        else:
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🎬 กำลัง extract audio จาก video: {video_path}")
        logger.info(f"   Output: {output_path}")
        
        try:
            # Extract audio ทั้งไฟล์ (16kHz mono WAV)
            (
                ffmpeg
                .input(video_path)
                .output(
                    output_path,
                    acodec='pcm_s16le',
                    ac=1,  # Mono
                    ar=16000  # 16kHz
                )
                .overwrite_output()
                .run(quiet=True, check=True)
            )
            
            logger.info(f"✅ Extract audio สำเร็จ: {output_path}")
            return output_path
            
        except ffmpeg.Error as e:
            error_message = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"❌ FFmpeg error: {error_message}")
            raise Exception(f"ไม่สามารถ extract audio ได้: {error_message}")
        except Exception as e:
            logger.error(f"❌ Error extracting audio: {e}")
            raise
    
    def extract_audio_from_video(self, video_path: str, output_path: str = None, 
                                audio_format: str = "wav", sample_rate: int = 16000) -> str:
        """แปลงวิดีโอเป็นไฟล์เสียง"""
        
        try:
            video_path = Path(video_path)
            if not video_path.exists():
                raise FileNotFoundError(f"ไม่พบไฟล์วิดีโอ: {video_path}")
            
            # สร้าง output path ถ้าไม่ระบุ
            if output_path is None:
                output_path = video_path.parent / f"{video_path.stem}_audio.{audio_format}"
            else:
                output_path = Path(output_path)
            
            # สร้างโฟลเดอร์ถ้ายังไม่มี
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"เริ่มแปลงวิดีโอเป็นเสียง: {video_path} → {output_path}")
            
            # ใช้ ffmpeg แปลงวิดีโอเป็นเสียงใน format ที่ Whisper รองรับ
            stream = ffmpeg.input(str(video_path))
            stream = ffmpeg.output(stream, str(output_path), 
                                 acodec='pcm_s16le',  # WAV PCM 16-bit (Whisper รองรับ)
                                 ar=16000,            # 16kHz sample rate (Whisper รองรับ)
                                 ac=1)                # Mono audio (Whisper รองรับ)
            
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            
            logger.info(f"แปลงวิดีโอเป็นเสียงสำเร็จ: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแปลงวิดีโอเป็นเสียง: {e}")
            raise

    def extract_audio_chunks(self, video_path: str, chunk_duration: int = 30, 
                           overlap: int = 5, audio_format: str = "wav", 
                           sample_rate: int = 16000) -> List[str]:
        """แปลงวิดีโอเป็น audio chunks"""
        
        try:
            video_path = Path(video_path)
            if not video_path.exists():
                raise FileNotFoundError(f"ไม่พบไฟล์วิดีโอ: {video_path}")
            
            # ดึงข้อมูลวิดีโอ
            probe = ffmpeg.probe(str(video_path))
            duration = float(probe['format']['duration'])
            
            logger.info(f"เริ่มแปลงวิดีโอเป็น audio chunks: {video_path} (duration: {duration}s)")
            
            chunk_paths = []
            # สร้าง temp directory แยกตาม task_id หรือใช้ timestamp
            task_folder = f"task_{int(time.time())}_{video_path.stem}"
            temp_dir = Path("temp") / task_folder
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # สร้าง chunks พร้อม overlap
            start_time = 0
            i = 0
            # Safety limit: คำนวณ max chunks ที่เป็นไปได้ (เพิ่ม buffer 10 chunks)
            max_chunks = int(duration / max(chunk_duration - overlap, 1)) + 10 if duration > 0 else 100
            previous_start_time = -1  # Track previous start_time เพื่อป้องกัน infinite loop
            
            while start_time < duration and i < max_chunks:
                # Safety check: ถ้า start_time ไม่เพิ่มขึ้น → break (ป้องกัน infinite loop)
                if start_time <= previous_start_time:
                    logger.warning(f"⚠️ start_time ไม่เพิ่มขึ้น ({start_time} <= {previous_start_time}), หยุด loop เพื่อป้องกัน infinite loop")
                    break
                
                previous_start_time = start_time
                end_time = min(start_time + chunk_duration, duration)
                
                # Safety check: ถ้า end_time <= start_time → break
                if end_time <= start_time:
                    logger.warning(f"⚠️ end_time ({end_time}) <= start_time ({start_time}), หยุด loop")
                    break
                
                # สร้างชื่อไฟล์ chunk
                chunk_filename = f"chunk_{i}_{video_path.stem}_audio.{audio_format}"
                chunk_path = temp_dir / chunk_filename
                
                logger.info(f"สร้าง audio chunk {i+1}: {start_time}s - {end_time}s")
                logger.info(f"ไฟล์ chunk path: {chunk_path}")
                
                # ใช้ ffmpeg ตัด audio chunk และแปลงเป็น format ที่ Whisper รองรับ
                stream = ffmpeg.input(str(video_path), ss=start_time, t=end_time-start_time)
                stream = ffmpeg.output(stream, str(chunk_path),
                                     acodec='pcm_s16le',  # WAV PCM 16-bit (Whisper รองรับ)
                                     ar=16000,            # 16kHz sample rate (Whisper รองรับ)
                                     ac=1)                # Mono audio (Whisper รองรับ)
                
                ffmpeg.run(stream, overwrite_output=True, quiet=True)
                
                # ตรวจสอบว่าไฟล์ถูกสร้างหรือไม่
                if chunk_path.exists():
                    logger.info(f"ไฟล์ chunk {i+1} ถูกสร้างสำเร็จ: {chunk_path} (ขนาด: {chunk_path.stat().st_size} bytes)")
                else:
                    logger.error(f"ไฟล์ chunk {i+1} ไม่ถูกสร้าง: {chunk_path}")
                
                chunk_paths.append(str(chunk_path))
                
                # เลื่อนไปยัง chunk ถัดไป (ลบ overlap)
                new_start_time = end_time - overlap
                
                # Safety check: ถ้า new_start_time <= start_time → break (ป้องกัน infinite loop)
                if new_start_time <= start_time:
                    logger.warning(f"⚠️ new_start_time ({new_start_time}) <= start_time ({start_time}), หยุด loop เพื่อป้องกัน infinite loop")
                    break
                
                start_time = new_start_time
                i += 1
                
                # หยุดถ้าเหลือน้อยกว่า chunk_duration
                if start_time + chunk_duration >= duration:
                    break
            
            # Safety check: ถ้าเกิน max_chunks → log warning
            if i >= max_chunks:
                logger.warning(f"⚠️ ถึง max_chunks limit ({max_chunks}), หยุด loop (duration: {duration}s, chunk_duration: {chunk_duration}s, overlap: {overlap}s)")
            
            logger.info(f"สร้าง audio chunks สำเร็จ: {len(chunk_paths)} chunks")
            return chunk_paths
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการสร้าง audio chunks: {e}")
            raise 