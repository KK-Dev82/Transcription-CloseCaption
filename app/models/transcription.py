from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class TranscriptionRequest(BaseModel):
    file_path: str
    language: Optional[str] = "th"  # ภาษาไทยเป็น default
    model_size: Optional[str] = "base"  # tiny, base, small, medium, large
    chunk_duration: Optional[int] = 30  # ความยาวของ chunk (วินาที)
    enable_timestamps: Optional[bool] = True

class TranscriptionChunk(BaseModel):
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None

class TranscriptionResponse(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    file_path: str
    total_duration: Optional[float] = None
    chunks: Optional[List[TranscriptionChunk]] = None
    full_text: Optional[str] = None
    language: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress: Optional[int] = 0  # Progress percentage (0-100)
    updated_at: Optional[datetime] = None 