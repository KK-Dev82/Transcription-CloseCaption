from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UploadResponse(BaseModel):
    file_id: str
    filename: str
    file_path: str
    file_size: int
    file_type: str
    duration: Optional[float] = None  # สำหรับ video/audio files
    uploaded_at: datetime
    status: str  # uploaded, processing, ready 