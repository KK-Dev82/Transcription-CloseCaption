"""
Overlap Buffer Manager
สำหรับจัดการ audio buffer ที่มี overlap สำหรับ CloseCaption
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import wave
import struct

logger = logging.getLogger(__name__)


class OverlapBuffer:
    """
    Buffer สำหรับเก็บ audio tail (overlap) จาก chunk ก่อนหน้า
    """
    
    def __init__(self, overlap_seconds: float = 0.6, sample_rate: int = 16000):
        """
        Args:
            overlap_seconds: ระยะเวลา overlap (วินาที)
            sample_rate: Sample rate ของ audio (Hz)
        """
        self.overlap_seconds = overlap_seconds
        self.sample_rate = sample_rate
        self.overlap_samples = int(overlap_seconds * sample_rate)
        self.tail_buffer: Optional[np.ndarray] = None
    
    def add_chunk(self, audio_data: bytes) -> bytes:
        """
        เพิ่ม audio chunk และ prepend tail จาก chunk ก่อนหน้า
        
        Args:
            audio_data: Audio data (PCM16 bytes)
        
        Returns:
            Audio data ที่ prepend tail แล้ว (พร้อมสำหรับ transcription)
        """
        # แปลง bytes เป็น numpy array (PCM16)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # ถ้ามี tail buffer → prepend
        if self.tail_buffer is not None:
            # รวม tail + new chunk
            combined = np.concatenate([self.tail_buffer, audio_array])
            logger.debug(f"🔗 Overlap: prepended {len(self.tail_buffer)} samples (tail) + {len(audio_array)} samples (new) = {len(combined)} samples")
        else:
            combined = audio_array
            logger.debug(f"🔗 Overlap: first chunk, no tail ({len(combined)} samples)")
        
        # เก็บ tail สำหรับ chunk ถัดไป (overlap_samples สุดท้าย)
        if len(combined) >= self.overlap_samples:
            self.tail_buffer = combined[-self.overlap_samples:].copy()
            logger.debug(f"💾 Saved tail: {len(self.tail_buffer)} samples ({self.overlap_seconds}s)")
        else:
            # ถ้า chunk สั้นกว่า overlap → เก็บทั้งหมด
            self.tail_buffer = combined.copy()
            logger.debug(f"💾 Saved tail (short chunk): {len(self.tail_buffer)} samples")
        
        # แปลงกลับเป็น bytes
        return combined.astype(np.int16).tobytes()
    
    def add_chunk_from_file(self, audio_file_path: str) -> str:
        """
        เพิ่ม audio chunk จากไฟล์ WAV และ prepend tail
        
        Args:
            audio_file_path: Path ไปยังไฟล์ WAV
        
        Returns:
            Path ไปยังไฟล์ WAV ใหม่ที่ prepend tail แล้ว
        """
        # อ่านไฟล์ WAV
        with wave.open(audio_file_path, 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frames = wav_file.readframes(wav_file.getnframes())
        
        # แปลงเป็น numpy array
        if sample_width == 2:  # PCM16
            audio_array = np.frombuffer(frames, dtype=np.int16)
        else:
            raise ValueError(f"Unsupported sample width: {sample_width}")
        
        # ถ้าเป็น stereo → แปลงเป็น mono
        if channels == 2:
            audio_array = audio_array.reshape(-1, 2).mean(axis=1).astype(np.int16)
        
        # เพิ่ม chunk (prepend tail)
        combined_bytes = self.add_chunk(audio_array.tobytes())
        combined_array = np.frombuffer(combined_bytes, dtype=np.int16)
        
        # สร้างไฟล์ WAV ใหม่
        output_path = audio_file_path.replace('.wav', '_overlap.wav')
        with wave.open(output_path, 'wb') as wav_out:
            wav_out.setnchannels(1)  # Mono
            wav_out.setsampwidth(2)  # PCM16
            wav_out.setframerate(self.sample_rate)
            wav_out.writeframes(combined_array.tobytes())
        
        logger.debug(f"💾 Created overlap WAV: {output_path} ({len(combined_array)} samples)")
        return output_path
    
    def reset(self):
        """Reset buffer (ลบ tail)"""
        self.tail_buffer = None
        logger.debug("🔄 Overlap buffer reset")
    
    def clear(self):
        """Clear buffer (alias for reset)"""
        self.reset()
