#!/bin/bash

# Script: Download Whisper Models
# สำหรับโหลด ggml-base.bin มาไว้ที่ models/
# ให้ Server ที่ต่อ Internet เข้าถึงได้ Download แล้ว Copy ไฟล์ไปไว้ที่ models/ ที่ transcription server

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

# ตรวจสอบว่า curl หรือ wget มีอยู่หรือไม่
if command -v wget &> /dev/null; then
    DOWNLOAD_CMD="wget"
    DOWNLOAD_FLAGS="-O"
elif command -v curl &> /dev/null; then
    DOWNLOAD_CMD="curl"
    DOWNLOAD_FLAGS="-L -o"
else
    print_error "Neither curl nor wget is installed. Installing..."
    sudo apt update && sudo apt install -y wget curl
    DOWNLOAD_CMD="wget"
    DOWNLOAD_FLAGS="-O"
fi

# โหลด base model
print_status "Downloading ggml-base.bin using $DOWNLOAD_CMD..."

# URL ที่ถูกต้องสำหรับ Hugging Face
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"

if $DOWNLOAD_CMD $DOWNLOAD_FLAGS models/ggml-base.bin "$MODEL_URL"; then
    print_success "ggml-base.bin downloaded successfully"
else
    print_error "Failed to download ggml-base.bin"
    print_error "Trying alternative download methods..."
    
    # ลองใช้ alternative URLs
    ALTERNATIVE_URLS=(
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin?download=true"
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
        "https://huggingface.co/ggerganov/whisper.cpp/raw/main/ggml-base.bin"
        "https://huggingface.co/ggerganov/whisper.cpp/blob/main/ggml-base.bin?download=true"
    )
    
    for url in "${ALTERNATIVE_URLS[@]}"; do
        print_status "Trying: $url"
        if $DOWNLOAD_CMD $DOWNLOAD_FLAGS models/ggml-base.bin "$url"; then
            print_success "ggml-base.bin downloaded successfully using: $url"
            break
        else
            print_warning "Failed with: $url"
        fi
    done
    
    # ตรวจสอบว่า download สำเร็จหรือไม่
    if [ ! -f "models/ggml-base.bin" ] || [ $(stat -c%s "models/ggml-base.bin") -lt 100000000 ]; then
        print_error "All download methods failed"
        print_error "Please try downloading manually or check network connectivity"
        exit 1
    fi
fi

# ตรวจสอบไฟล์
print_status "Verifying downloaded files..."
if [ -f "models/ggml-base.bin" ]; then
    file_size=$(du -h models/ggml-base.bin | cut -f1)
    file_size_bytes=$(du -b models/ggml-base.bin | cut -f1)
    file_type=$(file models/ggml-base.bin)
    
    print_success "File size: $file_size ($file_size_bytes bytes)"
    print_success "File type: $file_type"
    
    # ตรวจสอบว่าไฟล์มีขนาดถูกต้อง (ควรเป็น ~148MB)
    if [ $file_size_bytes -lt 100000000 ]; then
        print_error "Model file is too small! Expected ~148MB, got $file_size"
        print_error "File might be corrupted or incomplete"
        exit 1
    fi
    
    # ตรวจสอบว่าเป็น binary file
    if [[ $file_type == *"ASCII text"* ]]; then
        print_error "Model file is ASCII text, not binary!"
        print_error "This is not a valid Whisper model file"
        exit 1
    fi
    
    print_success "Model file validation passed"
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
if docker compose restart whisper whisper-live; then
    print_success "Whisper containers restarted"
else
    print_warning "Failed to restart Whisper containers"
fi

echo ""
print_status "📊 Container status:"
docker compose ps | grep whisper

echo ""
print_success "�� Download completed!"
echo "🌐 Whisper API: http://localhost:8002/health"
echo "🌐 Whisper Live API: http://localhost:8003/health"