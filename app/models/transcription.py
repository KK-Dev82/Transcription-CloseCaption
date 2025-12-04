from pydantic import BaseModel, AnyHttpUrl, root_validator
from typing import Optional, List, Dict
from datetime import datetime

class TranscriptionRequest(BaseModel):
    file_path: Optional[str] = None
    file_url: Optional[AnyHttpUrl] = None
    file_name: Optional[str] = None
    language: Optional[str] = "th"  # ภาษาไทยเป็น default
    model_size: Optional[str] = "base"  # tiny, base, small, medium, large
    chunk_duration: Optional[int] = 30  # ความยาวของ chunk (วินาที) - ใช้เมื่อ use_chunking=true
    use_chunking: Optional[bool] = False  # ใช้ chunking หรือไม่ (default: false - transcribe ทั้งไฟล์เลย)
    enable_timestamps: Optional[bool] = True
    display_mode: Optional[str] = "full_text"  # "full_text" หรือ "realtime_chunks" - วิธีแสดงผลลัพธ์ (full_text = แสดง Full Text ทีเดียว, realtime_chunks = แสดงทีละ Chunk แบบ realtime)
    callback_url: Optional[str] = None  # URL สำหรับ callback เมื่อเสร็จ (จาก Backend)
    job_id: Optional[int] = None  # Job ID จาก Backend (ถ้ามี)
    user_id: Optional[str] = None  # User ID (ถ้ามี)
    idempotency_key: Optional[str] = None  # Idempotency key สำหรับป้องกัน duplicate requests

    @root_validator(skip_on_failure=True)
    def validate_source(cls, values):
        file_path = values.get("file_path")
        file_url = values.get("file_url")
        if not file_path and not file_url:
            raise ValueError("ต้องระบุอย่างน้อยหนึ่งค่าระหว่าง file_path หรือ file_url")
        return values

class TranscriptionChunk(BaseModel):
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None

class TranscriptionResponse(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    file_path: str
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    job_id: Optional[int] = None
    user_id: Optional[str] = None
    callback_url: Optional[str] = None
    total_duration: Optional[float] = None
    chunks: Optional[List[TranscriptionChunk]] = None
    full_text: Optional[str] = None
    original_text: Optional[str] = None  # Raw text ก่อน correction (จาก Whisper โดยตรง)
    corrected_text: Optional[str] = None  # Text หลัง correction (ผ่าน Thai Text Processor)
    partial_text: Optional[str] = None  # ข้อความที่แปลงได้ระหว่างประมวลผล
    language: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress: Optional[int] = 0  # Progress percentage (0-100)
    updated_at: Optional[datetime] = None
    time_used: Optional[float] = None  # เวลาที่ใช้ในการประมวลผล (วินาที)
    
    # Progress tracking แบบ x/total
    total_chunks: Optional[int] = None  # จำนวน chunks ทั้งหมด (ถ้าใช้ chunking)
    completed_chunks: Optional[int] = None  # จำนวน chunks ที่เสร็จแล้ว
    total_tasks: Optional[int] = None  # จำนวน tasks ทั้งหมด (1 audio extraction + N transcription chunks)
    completed_tasks: Optional[int] = None  # จำนวน tasks ที่เสร็จแล้ว
    
    # Time tracking แยกตาม phase
    audio_extraction_time: Optional[float] = None  # เวลาที่ใช้ extract audio (วินาที) - จะเป็น None ถ้าเป็น audio file โดยตรง (ไม่ต้อง extract)
    transcription_time: Optional[float] = None  # เวลาที่ใช้ transcription (วินาที, ไม่รวม correction)
    text_correction_time: Optional[float] = None  # เวลาที่ใช้ text correction (วินาที)
    
    # Task breakdown สำหรับแสดงรายละเอียด
    task_breakdown: Optional[List[Dict]] = None  # รายละเอียดของ tasks: [{"type": "audio_extraction", "status": "completed", "time": 0.92}, ...] 