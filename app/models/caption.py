from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class CaptionRequest(BaseModel):
    file_path: str
    language: Optional[str] = "th"
    model_size: Optional[str] = "tiny"  # ใช้ tiny สำหรับ real-time
    max_delay: Optional[float] = 5.0  # ความล่าช้าสูงสุด (วินาที)
    subtitle_format: Optional[str] = "srt"  # srt, vtt, json

class CaptionSegment(BaseModel):
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None

class CaptionResponse(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    file_path: str
    segments: Optional[List[CaptionSegment]] = None
    subtitle_content: Optional[str] = None  # เนื้อหา subtitle
    subtitle_format: str
    language: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None 