"""
Video Service - จัดการวิดีโอและแยกเสียง
OPTIMIZATION: Decode audio ครั้งเดียวแล้ว slice เป็น chunks ใน RAM
เพื่อลด I/O และ CPU overhead (GPU จะทำงานต่อเนื่องขึ้น)
"""
import logging
import ffmpeg
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import tempfile
import os
import subprocess
import numpy as np

logger = logging.getLogger(__name__)

# Import faster-whisper decode_audio (ถ้ามี)
try:
    from faster_whisper import decode_audio as faster_whisper_decode_audio
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning("faster-whisper not available for optimized decoding. Using ffmpeg fallback.")


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
            
            # ใช้ subprocess ตรงๆ (เร็วและคุม args ชัดเจนกว่า)
            cmd = [
                "ffmpeg", "-y",  # -y = overwrite output
                "-i", str(video_file),
                "-vn",  # no video
                "-ac", "1",  # mono
                "-ar", "16000",  # 16kHz
                "-c:a", "pcm_s16le",  # WAV format
                str(output_path)
            ]
            
            p = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if p.returncode != 0:
                error_msg = p.stderr[-2000:] if len(p.stderr) > 2000 else p.stderr
                logger.error(f"❌ FFmpeg extract_audio failed: {error_msg}")
                raise RuntimeError(f"FFmpeg extract_audio failed: {error_msg[:500]}")
            
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
    
    def decode_audio_once(self, audio_path: str, sampling_rate: int = 16000) -> np.ndarray:
        """
        OPTIMIZATION: Decode audio ครั้งเดียวเป็น numpy array
        เพื่อลด I/O และ CPU overhead (GPU จะทำงานต่อเนื่องขึ้น)
        
        Args:
            audio_path: Path ไปยังไฟล์ audio
            sampling_rate: Sample rate (default: 16000 Hz)
            
        Returns:
            np.ndarray: Audio array (float32, mono, sampling_rate Hz)
        """
        try:
            if FASTER_WHISPER_AVAILABLE:
                # ใช้ faster-whisper decode_audio (เร็วกว่า, ไม่ต้องใช้ ffmpeg)
                logger.info(f"📦 Decoding audio once: {audio_path} (using faster-whisper)")
                audio_array = faster_whisper_decode_audio(audio_path, sampling_rate=sampling_rate)
                logger.info(f"✅ Decoded audio: shape={audio_array.shape}, dtype={audio_array.dtype}, duration={len(audio_array)/sampling_rate:.2f}s")
                return audio_array
            else:
                # Fallback: ใช้ ffmpeg + numpy (ช้ากว่า)
                logger.warning(f"⚠️  faster-whisper not available, using ffmpeg fallback for decoding")
                # TODO: Implement ffmpeg fallback if needed
                raise NotImplementedError("ffmpeg fallback not implemented. Please install faster-whisper.")
        except Exception as e:
            logger.error(f"❌ Error decoding audio: {e}", exc_info=True)
            raise
    
    def create_chunks(
        self, 
        audio_path: str, 
        chunk_duration: int = 30, 
        task_id: Optional[str] = None,
        use_numpy_chunks: bool = True  # OPTIMIZATION: ใช้ numpy chunks (.npy) แทน WAV files
    ) -> List[str]:
        """
        แบ่งไฟล์ audio เป็น chunks
        
        OPTIMIZATION: Decode audio ครั้งเดียวแล้ว slice เป็น chunks ใน RAM
        เพื่อลด I/O และ CPU overhead (GPU จะทำงานต่อเนื่องขึ้น)
        
        Args:
            audio_path: Path ไปยังไฟล์ audio
            chunk_duration: ความยาวของแต่ละ chunk (วินาที)
            task_id: Task ID (optional, สำหรับแยกโฟลเดอร์กันชน)
            use_numpy_chunks: ใช้ numpy chunks (.npy) แทน WAV files (เร็วกว่า)
            
        Returns:
            List[str]: List ของ chunk paths (.npy หรือ .wav)
        """
        try:
            audio_file = Path(audio_path)
            if not audio_file.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            # แยกโฟลเดอร์ตาม task_id เพื่อกันชนกันระหว่าง tasks
            if task_id:
                base_dir = Path("temp") / "chunks" / task_id
            else:
                base_dir = Path("temp") / "chunks" / audio_file.stem
            base_dir.mkdir(parents=True, exist_ok=True)
            
            sampling_rate = 16000
            
            if use_numpy_chunks and FASTER_WHISPER_AVAILABLE:
                # OPTIMIZATION: Decode ครั้งเดียวแล้ว slice เป็น chunks ใน RAM
                logger.info(f"📦 Creating numpy chunks (optimized): {audio_path} -> {base_dir} (chunk={chunk_duration}s)")
                
                # Decode audio ครั้งเดียว
                audio_array = self.decode_audio_once(audio_path, sampling_rate=sampling_rate)
                
                # Slice เป็น chunks ใน RAM
                chunk_samples = chunk_duration * sampling_rate
                total_chunks = int(np.ceil(len(audio_array) / chunk_samples))
                
                chunk_paths = []
                for i in range(total_chunks):
                    start_idx = i * chunk_samples
                    end_idx = min((i + 1) * chunk_samples, len(audio_array))
                    chunk_array = audio_array[start_idx:end_idx]
                    
                    # เก็บ chunk เป็น .npy file (เร็วกว่า decode WAV ทุกครั้ง)
                    chunk_path = base_dir / f"{audio_file.stem}_chunk_{i:04d}.npy"
                    np.save(str(chunk_path), chunk_array)
                    chunk_paths.append(str(chunk_path))
                    
                    logger.debug(f"   Chunk {i+1}/{total_chunks}: shape={chunk_array.shape}, duration={len(chunk_array)/sampling_rate:.2f}s")
                
                logger.info(f"✅ Created {len(chunk_paths)} numpy chunks in {base_dir} (optimized)")
                return chunk_paths
            else:
                # Fallback: ใช้ ffmpeg segment แบบเดิม (สร้าง WAV files)
                logger.info(f"📦 Creating WAV chunks (fallback): {audio_path} -> {base_dir} (chunk={chunk_duration}s)")
                
                # Pattern สำหรับ output files
                out_pattern = base_dir / f"{audio_file.stem}_chunk_%04d.wav"
                
                # ใช้ ffmpeg segment ในคำสั่งเดียว (เร็วกว่ามาก - ไม่ต้อง spawn process ซ้ำ)
                cmd = [
                    "ffmpeg", "-y",  # -y = overwrite output
                    "-i", str(audio_file),
                    "-f", "segment",  # segment muxer
                    "-segment_time", str(chunk_duration),
                    "-reset_timestamps", "1",  # reset timestamps ต่อ chunk
                    "-ac", "1",  # mono
                    "-ar", "16000",  # 16kHz
                    "-c:a", "pcm_s16le",  # WAV format
                    str(out_pattern)
                ]
                
                p = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if p.returncode != 0:
                    error_msg = p.stderr[-2000:] if len(p.stderr) > 2000 else p.stderr
                    logger.error(f"❌ FFmpeg create_chunks failed: {error_msg}")
                    raise RuntimeError(f"FFmpeg create_chunks failed: {error_msg[:500]}")
                
                # รวบรวม chunk files ที่สร้างขึ้น (เรียงตามชื่อ)
                chunks = sorted([str(p) for p in base_dir.glob(f"{audio_file.stem}_chunk_*.wav")])
                
                logger.info(f"✅ Created {len(chunks)} WAV chunks in {base_dir}")
                return chunks
            
        except Exception as e:
            logger.error(f"❌ Error creating chunks: {e}", exc_info=True)
            raise

