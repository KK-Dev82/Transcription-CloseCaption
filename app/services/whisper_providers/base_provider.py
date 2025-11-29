"""
Base Provider Abstract Class
กำหนด interface มาตรฐานสำหรับทุก Whisper Provider
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """ผลลัพธ์การ transcription มาตรฐาน"""
    text: str
    segments: List[Dict] = field(default_factory=list)
    language: str = "th"
    provider: str = "unknown"
    model: str = "unknown"
    duration: Optional[float] = None  # ระยะเวลาของ audio (วินาที)
    processing_time: Optional[float] = None  # เวลาที่ใช้ในการประมวลผล (วินาที)
    
    def to_dict(self) -> Dict:
        """แปลงเป็น dictionary"""
        return {
            "text": self.text,
            "segments": self.segments,
            "language": self.language,
            "provider": self.provider,
            "model": self.model,
            "duration": self.duration,
            "processing_time": self.processing_time
        }


class WhisperProvider(ABC):
    """
    Abstract Base Class สำหรับ Whisper Providers
    
    ทุก Provider ต้อง implement:
    - transcribe(): แปลงเสียงเป็นข้อความ
    - health_check(): ตรวจสอบสถานะ
    
    Features:
    - รองรับ Model: large-v3-turbo (Groq), base/small/medium/large (On-Premise)
    - รองรับภาษาไทย + อังกฤษ
    - ใช้ flow เดิม (ส่ง audio path, ลบ tmp หลังเสร็จ)
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.provider_name = "base"
        self.supported_languages = ["th", "en", "auto"]
        self.default_model = "base"
    
    @abstractmethod
    async def transcribe(
        self, 
        audio_path: str, 
        language: str = "th",
        model_size: str = None
    ) -> TranscriptionResult:
        """
        แปลงเสียงเป็นข้อความ
        
        Args:
            audio_path: Path ไปยังไฟล์ audio (WAV, MP3, etc.)
            language: ภาษา ("th", "en", "auto")
            model_size: ขนาด model (ถ้าไม่ระบุใช้ default)
            
        Returns:
            TranscriptionResult: ผลลัพธ์การ transcription
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """
        ตรวจสอบสถานะของ Provider
        
        Returns:
            bool: True ถ้า Provider พร้อมใช้งาน
        """
        pass
    
    def get_provider_info(self) -> Dict:
        """คืนค่าข้อมูลของ Provider สำหรับ monitoring"""
        return {
            "provider": self.provider_name,
            "supported_languages": self.supported_languages,
            "default_model": self.default_model,
            "config": {k: v for k, v in self.config.items() if 'key' not in k.lower() and 'secret' not in k.lower()}
        }
    
    def normalize_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        ปรับ format ของ segments ให้เป็นมาตรฐานเดียวกัน
        
        Standard format:
        {
            "start": "HH:MM:SS,mmm" หรือ float (seconds),
            "end": "HH:MM:SS,mmm" หรือ float (seconds),
            "text": "ข้อความ"
        }
        """
        normalized = []
        for seg in segments:
            normalized.append({
                "start": self._normalize_timestamp(seg.get("start", 0)),
                "end": self._normalize_timestamp(seg.get("end", 0)),
                "text": str(seg.get("text", "")).strip()
            })
        return normalized
    
    def _normalize_timestamp(self, value) -> str:
        """แปลง timestamp เป็น format HH:MM:SS,mmm"""
        if isinstance(value, str):
            # ถ้าเป็น string แล้ว return เลย
            if ":" in value:
                return value
            # ถ้าเป็นตัวเลข string ให้แปลงเป็น float
            try:
                value = float(value)
            except ValueError:
                return "00:00:00,000"
        
        if isinstance(value, (int, float)):
            # แปลง seconds เป็น HH:MM:SS,mmm
            total_seconds = float(value)
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            milliseconds = int((total_seconds % 1) * 1000)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
        
        return "00:00:00,000"
    
    def _timestamp_to_seconds(self, timestamp: str) -> float:
        """แปลง HH:MM:SS,mmm เป็น seconds"""
        try:
            if isinstance(timestamp, (int, float)):
                return float(timestamp)
            
            if "," in timestamp:
                time_part, ms_part = timestamp.split(",")
            else:
                time_part = timestamp
                ms_part = "000"
            
            parts = time_part.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds + int(ms_part) / 1000
            elif len(parts) == 2:
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds + int(ms_part) / 1000
            else:
                return float(parts[0]) + int(ms_part) / 1000
        except (ValueError, AttributeError):
            return 0.0


