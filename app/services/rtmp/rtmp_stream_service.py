"""
RTMP Stream Service
สำหรับจัดการ RTMP streams และทำ transcription แบบ real-time
"""

import asyncio
import logging
import subprocess
import json
import time
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import tempfile
import os
import aiofiles

from ...services.whisper_service import WhisperService
from ...services.caption_service import CaptionService
from ...utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

class RTMPStreamService:
    """Service สำหรับจัดการ RTMP streams และ transcription"""
    
    def __init__(self):
        self.whisper_service = WhisperService()
        self.caption_service = CaptionService()
        self.json_storage = JSONStorage()
        
        # เก็บข้อมูล streams
        self.active_streams: Dict[str, Dict] = {}
        
        # เก็บ transcription results
        self.transcriptions: Dict[str, List[Dict]] = {}
        
        # Settings
        self.chunk_duration = 3  # วินาที (สำหรับ realtime)
        self.hls_base_path = Path("/tmp/hls")
        
    async def start_stream(self, stream_key: str, stream_name: str = None, 
                          language: str = "th", model_size: str = "base") -> Dict:
        """
        เริ่ม stream session
        
        Args:
            stream_key: RTMP stream key
            stream_name: ชื่อ stream (ถ้าไม่ระบุจะใช้ stream_key)
            language: ภาษา (default: th)
            model_size: ขนาด model (default: base)
        """
        stream_id = stream_name or stream_key
        
        if stream_id in self.active_streams:
            logger.warning(f"Stream {stream_id} already exists")
            return self.active_streams[stream_id]
        
        stream_info = {
            "stream_id": stream_id,
            "stream_key": stream_key,
            "status": "active",
            "started_at": datetime.now().isoformat(),
            "hls_clean_url": f"/hls/clean/{stream_id}.m3u8",
            "hls_cc_url": f"/hls/cc/{stream_id}.m3u8",
            "transcription_count": 0,
            "last_transcription": None,
            "language": language,
            "model_size": model_size
        }
        
        self.active_streams[stream_id] = stream_info
        self.transcriptions[stream_id] = []
        
        # เริ่ม transcription worker
        asyncio.create_task(self._transcription_worker(stream_id))
        
        logger.info(f"✅ Started RTMP stream: {stream_id}")
        return stream_info
    
    async def stop_stream(self, stream_id: str) -> Dict:
        """หยุด stream session"""
        if stream_id not in self.active_streams:
            return {"error": "Stream not found"}
        
        stream_info = self.active_streams[stream_id]
        stream_info["status"] = "stopped"
        stream_info["stopped_at"] = datetime.now().isoformat()
        
        # บันทึก transcription ทั้งหมด
        await self._save_transcriptions(stream_id)
        
        logger.info(f"⏹️ Stopped RTMP stream: {stream_id}")
        return stream_info
    
    async def _transcription_worker(self, stream_id: str):
        """Worker สำหรับทำ transcription จาก HLS stream"""
        logger.info(f"🎤 Starting transcription worker for stream: {stream_id}")
        
        hls_path = self.hls_base_path / "clean" / f"{stream_id}.m3u8"
        last_segment_time = 0
        
        while stream_id in self.active_streams:
            try:
                # ตรวจสอบว่า stream ยัง active อยู่หรือไม่
                if self.active_streams[stream_id]["status"] != "active":
                    break
                
                # ตรวจสอบ HLS playlist
                if not hls_path.exists():
                    await asyncio.sleep(1)
                    continue
                
                # อ่าน playlist เพื่อหา segments ใหม่
                async with aiofiles.open(hls_path, 'r') as f:
                    playlist = await f.read()
                
                # แยก segments จาก playlist
                segments = [line.strip() for line in playlist.split('\n') 
                           if line.strip() and not line.startswith('#') and line.endswith('.ts')]
                
                if not segments:
                    await asyncio.sleep(1)
                    continue
                
                # หา segment ใหม่ที่ยังไม่ได้ process
                for segment_name in segments:
                    segment_path = hls_path.parent / segment_name
                    
                    if not segment_path.exists():
                        continue
                    
                    # ตรวจสอบว่าเป็น segment ใหม่หรือไม่
                    segment_mtime = segment_path.stat().st_mtime
                    if segment_mtime <= last_segment_time:
                        continue
                    
                    last_segment_time = segment_mtime
                    
                    # แยกเสียงจาก segment
                    audio_path = await self._extract_audio_from_segment(segment_path)
                    
                    if audio_path and os.path.exists(audio_path):
                        # ทำ transcription
                        try:
                            result = await self._transcribe_segment(stream_id, audio_path, segment_mtime)
                            
                            if result:
                                # อัปเดต stream info
                                self.active_streams[stream_id]["transcription_count"] += 1
                                self.active_streams[stream_id]["last_transcription"] = result
                                
                                # เก็บ transcription
                                self.transcriptions[stream_id].append(result)
                                
                                logger.info(f"📝 Transcribed segment: {result.get('text', '')[:50]}...")
                        except Exception as e:
                            logger.error(f"❌ Transcription error: {e}")
                        finally:
                            # ลบไฟล์ชั่วคราว
                            try:
                                if os.path.exists(audio_path):
                                    os.unlink(audio_path)
                            except:
                                pass
                
                await asyncio.sleep(self.chunk_duration)
                
            except Exception as e:
                logger.error(f"❌ Error in transcription worker: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"🛑 Transcription worker stopped for stream: {stream_id}")
    
    async def _extract_audio_from_segment(self, segment_path: Path) -> Optional[str]:
        """แยกเสียงจาก HLS segment"""
        try:
            # สร้าง temporary audio file
            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio.close()
            
            # ใช้ ffmpeg แยกเสียง
            cmd = [
                'ffmpeg', '-y',
                '-i', str(segment_path),
                '-ac', '1',  # mono
                '-ar', '16000',  # 16kHz
                '-acodec', 'pcm_s16le',
                temp_audio.name
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return temp_audio.name
            else:
                logger.error(f"FFmpeg error: {stderr.decode()}")
                if os.path.exists(temp_audio.name):
                    os.unlink(temp_audio.name)
                return None
                
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            return None
    
    async def _transcribe_segment(self, stream_id: str, audio_path: str, timestamp: float) -> Optional[Dict]:
        """ทำ transcription จาก audio segment"""
        try:
            stream_info = self.active_streams.get(stream_id, {})
            language = stream_info.get("language", "th")
            model_size = stream_info.get("model_size", "base")
            
            # ทำ transcription
            result = self.whisper_service.transcribe_file(
                audio_path=audio_path,
                model_size=model_size,
                language=language
            )
            
            if result and "text" in result:
                # คำนวณเวลาเริ่มต้นของ segment (relative to stream start)
                stream_start = datetime.fromisoformat(stream_info["started_at"]).timestamp()
                segment_start_time = timestamp - stream_start
                
                # สร้าง transcription result
                transcription_result = {
                    "stream_id": stream_id,
                    "timestamp": timestamp,
                    "segment_start_time": segment_start_time,
                    "text": result.get("text", ""),
                    "segments": result.get("segments", []),
                    "language": language,
                    "model_size": model_size,
                    "created_at": datetime.now().isoformat()
                }
                
                return transcription_result
            
            return None
            
        except Exception as e:
            logger.error(f"Error in transcription: {e}")
            return None
    
    async def _save_transcriptions(self, stream_id: str):
        """บันทึก transcriptions ทั้งหมดลง storage"""
        if stream_id not in self.transcriptions:
            return
        
        try:
            transcriptions = self.transcriptions[stream_id]
            
            if not transcriptions:
                return
            
            # รวม segments ทั้งหมด
            all_segments = []
            for trans in transcriptions:
                for seg in trans.get("segments", []):
                    # ปรับเวลาให้เป็น absolute time
                    base_time = trans.get("segment_start_time", 0)
                    all_segments.append({
                        "start": base_time + seg.get("start", 0),
                        "end": base_time + seg.get("end", 0),
                        "text": seg.get("text", "")
                    })
            
            # สร้าง caption data
            caption_data = {
                "task_id": stream_id,
                "status": "completed",
                "file_path": f"rtmp://stream/{stream_id}",
                "language": transcriptions[0].get("language", "th") if transcriptions else "th",
                "subtitle_format": "srt",
                "subtitle_content": self._create_srt_from_segments(all_segments),
                "segments": all_segments,
                "created_at": self.active_streams[stream_id]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            
            # บันทึก
            self.json_storage.save_caption(stream_id, caption_data)
            
            logger.info(f"💾 Saved {len(transcriptions)} transcriptions for stream: {stream_id}")
            
        except Exception as e:
            logger.error(f"Error saving transcriptions: {e}")
    
    def _create_srt_from_segments(self, segments: List[Dict]) -> str:
        """สร้าง SRT subtitle จาก segments"""
        srt_content = ""
        
        for i, segment in enumerate(segments, 1):
            start_time = self._format_srt_timestamp(segment.get("start", 0))
            end_time = self._format_srt_timestamp(segment.get("end", 0))
            text = segment.get("text", "").strip()
            
            srt_content += f"{i}\n"
            srt_content += f"{start_time} --> {end_time}\n"
            srt_content += f"{text}\n\n"
        
        return srt_content
    
    def _format_srt_timestamp(self, seconds: float) -> str:
        """แปลงวินาทีเป็นรูปแบบ SRT timestamp"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def get_stream_status(self, stream_id: str) -> Optional[Dict]:
        """ดึงสถานะ stream"""
        return self.active_streams.get(stream_id)
    
    def get_all_streams(self) -> List[Dict]:
        """ดึงรายการ streams ทั้งหมด"""
        return list(self.active_streams.values())
    
    def get_transcriptions(self, stream_id: str) -> List[Dict]:
        """ดึง transcriptions ของ stream"""
        return self.transcriptions.get(stream_id, [])

