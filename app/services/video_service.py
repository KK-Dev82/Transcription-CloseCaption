"""
Video Service - จัดการวิดีโอและแยกเสียง
"""
import logging
import ffmpeg
from pathlib import Path
from typing import Dict, Optional
import tempfile
import os

logger = logging.getLogger(__name__)


class VideoService:
    """Service สำหรับจัดการวิดีโอและแยกเสียง"""
    
    def __init__(self):
        logger.info("✅ VideoService initialized")
    
    def extract_audio(self, video_path: str, task_id: Optional[str] = None) -> str:
        """
        แยกเสียงจากวิดีโอ
        
        Args:
            video_path: Path ไปยังไฟล์วิดีโอ
            task_id: Task ID (optional, สำหรับ naming output file)
            
        Returns:
            str: Path ไปยังไฟล์ audio ที่แยกแล้ว (WAV format)
        """
        try:
            video_file = Path(video_path)
            if not video_file.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # สร้างชื่อไฟล์ output
            if task_id:
                output_filename = f"audio_{task_id}.wav"
            else:
                output_filename = f"{video_file.stem}.wav"
            
            # ใช้ temp directory หรือ uploads directory
            output_dir = Path("uploads")
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / output_filename
            
            logger.info(f"🎬 Extracting audio from: {video_path}")
            logger.info(f"   Output: {output_path}")
            
            # ใช้ FFmpeg แยกเสียง
            stream = ffmpeg.input(str(video_file))
            audio = ffmpeg.output(
                stream,
                str(output_path),
                acodec='pcm_s16le',  # WAV format
                ac=1,  # Mono
                ar='16000'  # 16kHz sample rate (เหมาะสำหรับ Whisper)
            )
            
            ffmpeg.run(audio, overwrite_output=True, quiet=True)
            
            logger.info(f"✅ Audio extracted: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"❌ Error extracting audio: {e}", exc_info=True)
            raise
    
    def get_video_info(self, video_path: str) -> Dict:
        """
        ดึงข้อมูลวิดีโอ
        
        Args:
            video_path: Path ไปยังไฟล์วิดีโอ
            
        Returns:
            Dict: ข้อมูลวิดีโอ (duration, width, height, etc.)
        """
        try:
            video_file = Path(video_path)
            if not video_file.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # ใช้ FFprobe ดึงข้อมูล
            probe = ffmpeg.probe(str(video_file))
            
            # หา video stream
            video_stream = next(
                (stream for stream in probe['streams'] if stream['codec_type'] == 'video'),
                None
            )
            
            # หา audio stream
            audio_stream = next(
                (stream for stream in probe['streams'] if stream['codec_type'] == 'audio'),
                None
            )
            
            # ดึงข้อมูล
            info = {
                "duration": float(probe['format'].get('duration', 0)),
                "size": int(probe['format'].get('size', 0)),
                "bitrate": int(probe['format'].get('bit_rate', 0)),
                "format": probe['format'].get('format_name', 'unknown')
            }
            
            if video_stream:
                info.update({
                    "width": int(video_stream.get('width', 0)),
                    "height": int(video_stream.get('height', 0)),
                    "video_codec": video_stream.get('codec_name', 'unknown'),
                    "fps": eval(video_stream.get('r_frame_rate', '0/1'))
                })
            
            if audio_stream:
                info.update({
                    "audio_codec": audio_stream.get('codec_name', 'unknown'),
                    "sample_rate": int(audio_stream.get('sample_rate', 0)),
                    "channels": int(audio_stream.get('channels', 0))
                })
            
            return info
            
        except Exception as e:
            logger.error(f"❌ Error getting video info: {e}", exc_info=True)
            return {
                "error": str(e),
                "duration": 0,
                "size": 0
            }
    
    def create_chunks(self, audio_path: str, chunk_duration: int = 30) -> list:
        """
        แบ่งไฟล์ audio เป็น chunks
        
        Args:
            audio_path: Path ไปยังไฟล์ audio
            chunk_duration: ความยาวของแต่ละ chunk (วินาที)
            
        Returns:
            list: List ของ chunk paths
        """
        try:
            audio_file = Path(audio_path)
            if not audio_file.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            # ดึงข้อมูล audio เพื่อหาความยาว
            probe = ffmpeg.probe(str(audio_file))
            duration = float(probe['format'].get('duration', 0))
            
            # คำนวณจำนวน chunks
            num_chunks = int(duration / chunk_duration) + (1 if duration % chunk_duration > 0 else 0)
            
            logger.info(f"📦 Creating {num_chunks} chunks from {audio_path} (duration: {duration:.2f}s, chunk_duration: {chunk_duration}s)")
            
            chunks = []
            output_dir = Path("temp") / "chunks"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for i in range(num_chunks):
                start_time = i * chunk_duration
                chunk_path = output_dir / f"{audio_file.stem}_chunk_{i:04d}.wav"
                
                # ใช้ FFmpeg ตัด chunk
                stream = ffmpeg.input(
                    str(audio_file),
                    ss=start_time,
                    t=chunk_duration
                )
                audio = ffmpeg.output(
                    stream,
                    str(chunk_path),
                    acodec='pcm_s16le',
                    ac=1,
                    ar='16000'
                )
                
                ffmpeg.run(audio, overwrite_output=True, quiet=True)
                chunks.append(str(chunk_path))
            
            logger.info(f"✅ Created {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"❌ Error creating chunks: {e}", exc_info=True)
            raise

