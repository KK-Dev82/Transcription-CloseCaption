"""
FFmpeg Burn-in Service
สำหรับ overlay Close Caption บนวิดีโอ stream ด้วย FFmpeg
"""

import asyncio
import logging
import subprocess
from typing import Dict, List, Optional
from pathlib import Path
import tempfile
import os
import json

logger = logging.getLogger(__name__)

class FFmpegBurninService:
    """Service สำหรับ burn-in Close Caption ด้วย FFmpeg"""
    
    def __init__(self):
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self.caption_cache: Dict[str, List[Dict]] = {}
        
    async def start_burnin_stream(self, stream_id: str, 
                                  input_url: str,
                                  output_rtmp: str,
                                  caption_segments: List[Dict]) -> bool:
        """
        เริ่ม burn-in stream
        
        Args:
            stream_id: ID ของ stream
            input_url: Input URL (RTMP หรือ HLS)
            output_rtmp: RTMP output URL (CC stream)
            caption_segments: รายการ caption segments
        """
        try:
            # ตรวจสอบว่า stream นี้มี process อยู่แล้วหรือไม่
            if stream_id in self.active_processes:
                logger.warning(f"Stream {stream_id} already has burn-in process")
                return False
            
            # เก็บ caption segments
            self.caption_cache[stream_id] = caption_segments
            
            # สร้าง filter complex สำหรับ burn-in
            filter_complex = self._create_burnin_filter(stream_id, caption_segments)
            
            # ตรวจสอบว่าเป็น HLS หรือ RTMP
            is_hls = input_url.startswith('http://') or input_url.startswith('https://')
            
            # เริ่ม FFmpeg process
            cmd = [
                'ffmpeg',
                '-i', input_url,  # Input (RTMP หรือ HLS)
            ]
            
            # เพิ่ม options สำหรับ HLS
            if is_hls:
                cmd.extend([
                    '-c:v', 'libx264',  # Video codec
                    '-preset', 'veryfast',  # Encoding preset
                    '-tune', 'zerolatency',  # Low latency
                    '-c:a', 'aac',  # Audio codec (HLS ต้องใช้ AAC)
                    '-b:a', '128k',  # Audio bitrate
                ])
            else:
                cmd.extend([
                    '-c:v', 'libx264',  # Video codec
                    '-preset', 'veryfast',  # Encoding preset
                    '-tune', 'zerolatency',  # Low latency
                    '-c:a', 'copy',  # Copy audio (RTMP)
                ])
            
            cmd.extend([
                '-vf', filter_complex,  # Video filter (burn-in)
                '-f', 'flv',  # Output format
                '-y',  # Overwrite output
                output_rtmp  # Output RTMP URL
            ])
            
            # เริ่ม process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL
            )
            
            self.active_processes[stream_id] = process
            
            # ตรวจสอบว่า process ยังทำงานอยู่หรือไม่
            asyncio.create_task(self._monitor_process(stream_id, process))
            
            logger.info(f"✅ Started burn-in stream: {stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting burn-in stream: {e}")
            return False
    
    def _create_burnin_filter(self, stream_id: str, caption_segments: List[Dict]) -> str:
        """
        สร้าง FFmpeg filter complex สำหรับ burn-in
        
        ใช้ drawtext filter เพื่อแสดงข้อความบนวิดีโอ
        Note: ใช้วิธีสร้าง subtitle file แล้ว overlay แทน
        """
        if not caption_segments:
            return "null"
        
        # สร้าง subtitle file (SRT format)
        subtitle_file = f"/tmp/captions_{stream_id}.srt"
        self._create_srt_file(subtitle_file, caption_segments)
        
        # ใช้ subtitles filter สำหรับ burn-in
        # ต้อง escape path และใช้ fontconfig
        filter_complex = (
            f"subtitles={subtitle_file}"
            f":force_style='FontName=DejaVu Sans Bold,FontSize=24,"
            f"PrimaryColour=&Hffffff,OutlineColour=&H000000,"
            f"Outline=2,Alignment=2,MarginV=50'"
        )
        
        return filter_complex
    
    def _create_srt_file(self, filepath: str, segments: List[Dict]):
        """สร้างไฟล์ SRT สำหรับ subtitles filter"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments, 1):
                    start_time = segment.get("start", 0)
                    end_time = segment.get("end", 0)
                    text = segment.get("text", "").strip()
                    
                    # Format SRT timestamp
                    start_str = self._format_srt_time(start_time)
                    end_str = self._format_srt_time(end_time)
                    
                    f.write(f"{i}\n")
                    f.write(f"{start_str} --> {end_str}\n")
                    f.write(f"{text}\n\n")
        except Exception as e:
            logger.error(f"Error creating SRT file: {e}")
    
    def _format_srt_time(self, seconds: float) -> str:
        """แปลงวินาทีเป็นรูปแบบ SRT timestamp"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    async def update_captions(self, stream_id: str, caption_segments: List[Dict]):
        """อัปเดต caption segments สำหรับ stream"""
        self.caption_cache[stream_id] = caption_segments
        logger.info(f"📝 Updated captions for stream: {stream_id} ({len(caption_segments)} segments)")
    
    async def _monitor_process(self, stream_id: str, process: subprocess.Popen):
        """Monitor FFmpeg process"""
        try:
            # รอ process จบ
            return_code = await asyncio.to_thread(process.wait)
            
            if return_code != 0:
                # อ่าน error output
                stderr = process.stderr.read().decode() if process.stderr else ""
                logger.error(f"❌ FFmpeg process exited with code {return_code}: {stderr}")
            else:
                logger.info(f"✅ FFmpeg process completed: {stream_id}")
            
        except Exception as e:
            logger.error(f"❌ Error monitoring process: {e}")
        finally:
            # ลบ process จาก active_processes
            if stream_id in self.active_processes:
                del self.active_processes[stream_id]
            if stream_id in self.caption_cache:
                del self.caption_cache[stream_id]
    
    async def stop_burnin_stream(self, stream_id: str) -> bool:
        """หยุด burn-in stream"""
        if stream_id not in self.active_processes:
            return False
        
        try:
            process = self.active_processes[stream_id]
            
            # ส่ง SIGTERM
            process.terminate()
            
            # รอให้ process จบ (timeout 5 วินาที)
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(process.wait),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                # ถ้ายังไม่จบ ให้ kill
                process.kill()
                await asyncio.to_thread(process.wait)
            
            # ลบจาก active_processes
            del self.active_processes[stream_id]
            
            if stream_id in self.caption_cache:
                del self.caption_cache[stream_id]
            
            logger.info(f"⏹️ Stopped burn-in stream: {stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping burn-in stream: {e}")
            return False
    
    def get_active_streams(self) -> List[str]:
        """ดึงรายการ active burn-in streams"""
        return list(self.active_processes.keys())
    
    def get_stream_status(self, stream_id: str) -> Dict:
        """ดึงสถานะ burn-in stream"""
        if stream_id not in self.active_processes:
            return {"status": "not_found"}
        
        process = self.active_processes[stream_id]
        
        return {
            "status": "active" if process.poll() is None else "stopped",
            "return_code": process.returncode,
            "caption_segments_count": len(self.caption_cache.get(stream_id, []))
        }

