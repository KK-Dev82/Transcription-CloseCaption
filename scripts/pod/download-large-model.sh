#!/bin/bash
# Script สำหรับ Download Large Model โดยเฉพาะ
# ใช้เมื่อ download ผ่าน start-services-direct.sh ไม่สำเร็จ
#
# วิธีใช้งาน:
# bash scripts/pod/download-large-model.sh

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

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

echo "📥 Downloading Large Whisper Model"
echo "📅 $(date)"
echo ""
print_warning "⚠️  Large model is ~3GB, this may take a while..."
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Create models directory
mkdir -p models
print_success "✅ Models directory: models/"

MODEL_FILE="models/ggml-large.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large.bin"
EXPECTED_SIZE=3100000000  # ~3GB

# Check if model already exists
if [ -f "$MODEL_FILE" ]; then
    EXISTING_SIZE=$(stat -c%s "$MODEL_FILE" 2>/dev/null || stat -f%z "$MODEL_FILE" 2>/dev/null || echo "0")
    EXISTING_SIZE_MB=$((EXISTING_SIZE / 1024 / 1024))
    
    if [ "$EXISTING_SIZE" -ge $((EXPECTED_SIZE * 8 / 10)) ]; then
        print_success "✅ Large model already exists: $MODEL_FILE"
        print_status "   Size: ${EXISTING_SIZE_MB}MB ($(du -h "$MODEL_FILE" | cut -f1))"
        echo ""
        read -p "Re-download? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Skipping download. Using existing model."
            exit 0
        fi
        rm -f "$MODEL_FILE"
    else
        print_warning "⚠️  Existing model file is too small (${EXISTING_SIZE_MB}MB). Re-downloading..."
        rm -f "$MODEL_FILE"
    fi
fi

# Try using utility script first
if [ -f "scripts/utility/download-models.sh" ]; then
    print_status "Trying utility download script..."
    bash scripts/utility/download-models.sh large --skip-restart && {
        if [ -f "$MODEL_FILE" ]; then
            print_success "✅ Large model downloaded successfully!"
            exit 0
        fi
    }
fi

# Try whisper.cpp script
if [ -d "whisper-service" ] && [ -f "whisper-service/models/download-ggml-model.sh" ]; then
    print_status "Trying whisper.cpp download script..."
    cd whisper-service
    bash models/download-ggml-model.sh large && {
        if [ -f "models/ggml-large.bin" ]; then
            cp models/ggml-large.bin ../models/ 2>/dev/null || true
            cd ..
            if [ -f "$MODEL_FILE" ]; then
                print_success "✅ Large model downloaded successfully!"
                exit 0
            fi
        fi
    }
    cd ..
fi

# Direct download using wget or curl
print_status "Downloading directly from Hugging Face..."
DOWNLOAD_START=$(date +%s)

if command -v wget &> /dev/null; then
    print_status "Using wget..."
    wget --progress=bar:force -O "$MODEL_FILE" "$MODEL_URL" 2>&1 | \
        while IFS= read -r line; do
            if [[ $line =~ ([0-9]+)% ]]; then
                PERCENT="${BASH_REMATCH[1]}"
                printf "\r   Progress: %s%%" "$PERCENT"
            fi
        done
    echo ""
elif command -v curl &> /dev/null; then
    print_status "Using curl..."
    curl -L --progress-bar -o "$MODEL_FILE" "$MODEL_URL"
else
    print_error "❌ Neither wget nor curl is available"
    exit 1
fi

DOWNLOAD_END=$(date +%s)
DOWNLOAD_TIME=$((DOWNLOAD_END - DOWNLOAD_START))

# Verify download
if [ -f "$MODEL_FILE" ]; then
    FILE_SIZE=$(stat -c%s "$MODEL_FILE" 2>/dev/null || stat -f%z "$MODEL_FILE" 2>/dev/null || echo "0")
    FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))
    
    if [ "$FILE_SIZE" -ge $((EXPECTED_SIZE * 8 / 10)) ]; then
        print_success "✅ Large model downloaded successfully!"
        print_status "   File: $MODEL_FILE"
        print_status "   Size: ${FILE_SIZE_MB}MB ($(du -h "$MODEL_FILE" | cut -f1))"
        print_status "   Download time: ${DOWNLOAD_TIME}s"
        
        # Verify file type
        FILE_TYPE=$(file "$MODEL_FILE" 2>/dev/null || echo "unknown")
        if [[ $FILE_TYPE == *"ASCII text"* ]]; then
            print_error "❌ Downloaded file is text, not binary! Download may have failed."
            rm -f "$MODEL_FILE"
            exit 1
        fi
        
        echo ""
        print_success "🎉 Large model is ready to use!"
        echo ""
        print_status "💡 Next steps:"
        echo "   # Restart services to use large model:"
        echo "   bash scripts/pod/stop-services.sh"
        echo "   bash scripts/pod/start-services-direct.sh"
        echo ""
    else
        print_error "❌ Downloaded file is too small (${FILE_SIZE_MB}MB). Expected ~3000MB."
        print_error "   File may be corrupted or incomplete."
        rm -f "$MODEL_FILE"
        exit 1
    fi
else
    print_error "❌ Download failed!"
    exit 1
fi

