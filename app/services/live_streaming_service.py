"""
Live Streaming Service สำหรับ Real-time Transcription
รองรับการทำ transcription แบบ real-time เหมือน YouTube
"""

import asyncio
import logging
import json
import time
from typing import Dict, List, Optional, Callable
from datetime import datetime
import websockets
from pathlib import Path
import tempfile
import os

from .whisper_service import WhisperService
from .caption_service import CaptionService

logger = logging.getLogger(__name__)

class LiveStreamingService:
    def __init__(self):
        self.whisper_service = WhisperService()
        self.caption_service = CaptionService()
        self.active_streams: Dict[str, Dict] = {}
        self.audio_buffers: Dict[str, List[bytes]] = {}
        self.callback_handlers: Dict[str, List[Callable]] = {}
        
        # Real-time settings
        self.buffer_duration = 10  # วินาที
        self.sample_rate = 16000
        self.chunk_size = 1024 * 4  # 4KB chunks
        
    async def start_live_stream(self, stream_id: str, language: str = "th", 
                              model_size: str = "base") -> bool:
        """เริ่ม live streaming session"""
        try:
            self.active_streams[stream_id] = {
                "stream_id": stream_id,
                "status": "active",
                "language": language,
                "model_size": model_size,
                "started_at": datetime.now(),
                "total_audio_duration": 0,
                "transcription_count": 0,
                "last_transcription": None
            }
            
            self.audio_buffers[stream_id] = []
            self.callback_handlers[stream_id] = []
            
            logger.info(f"เริ่ม live stream: {stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการเริ่ม live stream: {e}")
            return False
    
    async def process_audio_chunk(self, stream_id: str, audio_chunk: bytes) -> bool:
        """ประมวลผล audio chunk แบบ real-time"""
        if stream_id not in self.active_streams:
            return False
        
        try:
            # เพิ่ม audio chunk เข้า buffer
            self.audio_buffers[stream_id].append(audio_chunk)
            
            # ตรวจสอบว่า buffer เต็มหรือยัง
            buffer_duration = self._calculate_buffer_duration(stream_id)
            
            if buffer_duration >= self.buffer_duration:
                # ประมวลผล buffer
                await self._process_audio_buffer(stream_id)
                
            return True
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล audio chunk: {e}")
            return False
    
    async def _process_audio_buffer(self, stream_id: str):
        """ประมวลผล audio buffer และทำ transcription"""
        try:
            # รวม audio chunks
            combined_audio = b''.join(self.audio_buffers[stream_id])
            
            # สร้าง temporary audio file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_audio_path = temp_file.name
                temp_file.write(combined_audio)
            
            # ทำ transcription
            stream_info = self.active_streams[stream_id]
            transcription_result = self.whisper_service.transcribe_file(
                audio_path=temp_audio_path,
                model_size=stream_info["model_size"],
                language=stream_info["language"]
            )
            
            if transcription_result and "text" in transcription_result:
                # อัปเดตข้อมูล stream
                stream_info["transcription_count"] += 1
                stream_info["last_transcription"] = {
                    "text": transcription_result["text"],
                    "segments": transcription_result.get("segments", []),
                    "timestamp": datetime.now(),
                    "audio_duration": self.buffer_duration
                }
                
                # สร้าง captions
                captions = self.caption_service.create_srt_subtitles(transcription_result)
                
                # ส่งผลลัพธ์ไปยัง callbacks
                await self._notify_callbacks(stream_id, {
                    "type": "transcription",
                    "text": transcription_result["text"],
                    "segments": transcription_result.get("segments", []),
                    "captions": captions,
                    "timestamp": datetime.now().isoformat()
                })
                
                logger.info(f"Real-time transcription: {transcription_result['text'][:50]}...")
            
            # ล้าง buffer
            self.audio_buffers[stream_id] = []
            
            # ลบ temporary file
            try:
                os.unlink(temp_audio_path)
            except:
                pass
                
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผล audio buffer: {e}")
    
    def _calculate_buffer_duration(self, stream_id: str) -> float:
        """คำนวณความยาวของ audio buffer"""
        total_bytes = sum(len(chunk) for chunk in self.audio_buffers[stream_id])
        # ประมาณการ: 2 bytes per sample, stereo = 4 bytes per sample
        total_samples = total_bytes / 4
        return total_samples / self.sample_rate
    
    async def add_callback_handler(self, stream_id: str, callback: Callable):
        """เพิ่ม callback handler สำหรับ real-time updates"""
        if stream_id not in self.callback_handlers:
            self.callback_handlers[stream_id] = []
        self.callback_handlers[stream_id].append(callback)
    
    async def _notify_callbacks(self, stream_id: str, data: Dict):
        """แจ้งเตือน callbacks"""
        if stream_id in self.callback_handlers:
            for callback in self.callback_handlers[stream_id]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"เกิดข้อผิดพลาดใน callback: {e}")
    
    async def stop_live_stream(self, stream_id: str) -> Dict:
        """หยุด live streaming session"""
        if stream_id not in self.active_streams:
            return {"error": "Stream not found"}
        
        try:
            # ประมวลผล buffer ที่เหลือ
            if self.audio_buffers[stream_id]:
                await self._process_audio_buffer(stream_id)
            
            # สร้างสรุป
            stream_info = self.active_streams[stream_id]
            summary = {
                "stream_id": stream_id,
                "status": "completed",
                "started_at": stream_info["started_at"],
                "ended_at": datetime.now(),
                "total_transcriptions": stream_info["transcription_count"],
                "total_duration": stream_info["total_audio_duration"]
            }
            
            # ล้างข้อมูล
            del self.active_streams[stream_id]
            if stream_id in self.audio_buffers:
                del self.audio_buffers[stream_id]
            if stream_id in self.callback_handlers:
                del self.callback_handlers[stream_id]
            
            logger.info(f"หยุด live stream: {stream_id}")
            return summary
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการหยุด live stream: {e}")
            return {"error": str(e)}
    
    def get_stream_status(self, stream_id: str) -> Optional[Dict]:
        """ดึงสถานะของ stream"""
        return self.active_streams.get(stream_id)
    
    def get_all_active_streams(self) -> List[Dict]:
        """ดึงรายการ active streams ทั้งหมด"""
        return list(self.active_streams.values()) 