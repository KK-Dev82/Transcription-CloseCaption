# ใช้ Python 3.11 slim image
FROM python:3.11-slim

# ตั้งค่า environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# อัปเดต package manager และติดตั้ง dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic1 \
    libsndfile1 \
    libportaudio2 \
    libasound2-dev \
    portaudio19-dev \
    python3-dev \
    gcc \
    g++ \
    make \
    curl \
    git \
    cmake \
    wget \
    && rm -rf /var/lib/apt/lists/*



# สร้าง working directory
WORKDIR /app

# คัดลอก requirements และติดตั้ง Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอก source code
COPY . .

# สร้างโฟลเดอร์ที่จำเป็น
RUN mkdir -p uploads temp storage models

# สร้าง app/models directory และไฟล์ที่จำเป็น
RUN mkdir -p app/models

# สร้างไฟล์ models ที่จำเป็น
RUN echo 'from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UploadResponse(BaseModel):
    task_id: str
    filename: str
    status: str
    created_at: datetime
    file_path: Optional[str] = None
    error_message: Optional[str] = None' > app/models/upload.py

RUN echo 'from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TranscriptionResponse(BaseModel):
    task_id: str
    status: str
    file_path: str
    language: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    transcription_text: Optional[str] = None
    error_message: Optional[str] = None' > app/models/transcription.py

RUN echo 'from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class CaptionResponse(BaseModel):
    task_id: str
    status: str
    file_path: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    captions: Optional[List[dict]] = None
    error_message: Optional[str] = None' > app/models/caption.py

RUN echo '' > app/models/__init__.py

# ตั้งค่า permissions
RUN chmod +x main.py

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# รัน application
CMD ["sh", "-c", "if [ \"$ENVIRONMENT\" = \"development\" ]; then uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload --log-level info; else uvicorn app.main:app --host 0.0.0.0 --port 8001 --log-level info; fi"] 