#!/bin/bash

# Script: Fix Missing App Models
# สำหรับสร้างไฟล์ app/models/ ที่ขาดหายไป

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "🔧 Fixing Missing App Models..."

# สร้าง directory
print_status "Creating app/models directory..."
mkdir -p app/models/
print_success "Directory created"

# สร้างไฟล์ upload.py
print_status "Creating upload.py..."
echo 'from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UploadResponse(BaseModel):
    task_id: str
    filename: str
    status: str
    created_at: datetime
    file_path: Optional[str] = None
    error_message: Optional[str] = None' > app/models/upload.py
print_success "upload.py created"

# สร้างไฟล์ transcription.py
print_status "Creating transcription.py..."
echo 'from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class TranscriptionResponse(BaseModel):
    task_id: str
    status: str
    file_path: str
    language: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    transcription_text: Optional[str] = None
    error_message: Optional[str] = None

class TranscriptionChunk(BaseModel):
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None
    language: Optional[str] = None' > app/models/transcription.py
print_success "transcription.py created"

# สร้างไฟล์ caption.py
print_status "Creating caption.py..."
echo 'from pydantic import BaseModel
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
print_success "caption.py created"

# สร้างไฟล์ __init__.py
print_status "Creating __init__.py..."
echo '' > app/models/__init__.py
print_success "__init__.py created"

# ตรวจสอบไฟล์
print_status "Verifying created files..."
echo "📁 Directory structure:"
ls -la app/models/

echo ""
print_status "📄 File contents verification:"
echo "upload.py:"
head -5 app/models/upload.py
echo ""
echo "transcription.py:"
head -15 app/models/transcription.py
echo ""
echo "caption.py:"
head -5 app/models/caption.py

echo ""
print_status "🔄 Restarting containers..."
if docker-compose -f docker-compose.yml restart api video-worker-1 video-worker-2 video-worker-3; then
    print_success "Containers restarted successfully"
else
    print_warning "Failed to restart some containers"
fi

echo ""
print_status "📊 Container status:"
docker-compose -f docker-compose.yml ps

echo ""
print_status " Recent logs (API):"
docker logs transcription-api-staging --tail=10

echo ""
print_success "🎉 Fix completed!"
echo " API Health: http://localhost:8001/health"
echo "🌐 API Docs: http://localhost:8001/docs"