#!/bin/bash

# Script: Download Whisper Models
# สำหรับโหลด ggml-base.bin มาไว้ที่ models/

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

echo "📥 Starting Whisper Models Download..."

# สร้าง directory
print_status "Creating models directory..."
mkdir -p models
print_success "Models directory created"

# ตรวจสอบว่า curl มีอยู่หรือไม่
if ! command -v curl &> /dev/null; then
    print_error "curl is not installed. Installing..."
    sudo apt update && sudo apt install -y curl
fi

# โหลด base model
print_status "Downloading ggml-base.bin..."
if curl -L -o models/ggml-base.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/models/ggml-base.bin; then
    print_success "ggml-base.bin downloaded successfully"
else
    print_error "Failed to download ggml-base.bin"
    exit 1
fi

# ตรวจสอบไฟล์
print_status "Verifying downloaded files..."
if [ -f "models/ggml-base.bin" ]; then
    file_size=$(du -h models/ggml-base.bin | cut -f1)
    print_success "File size: $file_size"
    print_success "File type: $(file models/ggml-base.bin)"
else
    print_error "ggml-base.bin not found"
    exit 1
fi

# แสดงผลลัพธ์
echo ""
print_success "✅ Models downloaded successfully!"
echo "�� Directory structure:"
ls -la models/

echo ""
print_status "🔄 Restarting Whisper containers..."
if docker-compose -f docker-compose.staging.yml restart whisper whisper-live; then
    print_success "Whisper containers restarted"
else
    print_warning "Failed to restart Whisper containers"
fi

echo ""
print_status "📊 Container status:"
docker-compose -f docker-compose.staging.yml ps | grep whisper

echo ""
print_success "�� Download completed!"
echo "🌐 Whisper API: http://localhost:8002/health"
echo "🌐 Whisper Live API: http://localhost:8003/health"