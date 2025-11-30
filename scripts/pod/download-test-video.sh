#!/bin/bash
# Script สำหรับ Download Test Video จาก URL
# ใช้สำหรับ download video สำหรับทดสอบ transcription
#
# วิธีใช้งาน:
# bash scripts/pod/download-test-video.sh [url] [destination-dir]
#
# ตัวอย่าง:
# bash scripts/pod/download-test-video.sh http://korrakang.com/meeting2.mp4 uploads/

set -e

VIDEO_URL="${1:-http://korrakang.com/meeting2.mp4}"
DEST_DIR="${2:-uploads}"

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

print_perf() {
    echo -e "${CYAN}[PERF]${NC} $1"
}

echo "📥 Downloading Test Video"
echo "📅 $(date)"
echo ""
echo "📋 Configuration:"
echo "   URL: $VIDEO_URL"
echo "   Destination: $DEST_DIR"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Create destination directory
mkdir -p "$DEST_DIR"
print_success "✅ Destination directory: $DEST_DIR"

# Extract filename from URL
FILENAME=$(basename "$VIDEO_URL" | sed 's/[?&].*//')
if [ -z "$FILENAME" ] || [ "$FILENAME" = "/" ] || [[ ! "$FILENAME" =~ \.(mp4|avi|mov|mkv|webm|flv)$ ]]; then
    FILENAME="meeting2-$(date +%Y%m%d-%H%M%S).mp4"
fi

DEST_PATH="$DEST_DIR/$FILENAME"

# Check if file already exists
if [ -f "$DEST_PATH" ]; then
    EXISTING_SIZE=$(stat -c%s "$DEST_PATH" 2>/dev/null || stat -f%z "$DEST_PATH" 2>/dev/null || echo "0")
    if [ "$EXISTING_SIZE" -gt 1000000 ]; then  # > 1MB
        print_warning "⚠️  File already exists: $DEST_PATH"
        print_status "   Size: $(du -h "$DEST_PATH" | cut -f1)"
        echo ""
        read -p "Overwrite? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Skipping download. Using existing file."
            exit 0
        fi
    fi
fi

# Download using wget or curl
print_status "Downloading video from: $VIDEO_URL"
print_warning "⚠️  This may take a while for large files (60+ minutes video)..."
echo ""

DOWNLOAD_START=$(date +%s)

if command -v wget &> /dev/null; then
    print_status "Using wget..."
    wget --progress=bar:force -O "$DEST_PATH" "$VIDEO_URL" 2>&1 | \
        while IFS= read -r line; do
            if [[ $line =~ ([0-9]+)% ]]; then
                PERCENT="${BASH_REMATCH[1]}"
                printf "\r   Progress: %s%%" "$PERCENT"
            fi
        done
    echo ""
    
    if [ $? -eq 0 ]; then
        DOWNLOAD_SUCCESS=true
    else
        DOWNLOAD_SUCCESS=false
    fi
elif command -v curl &> /dev/null; then
    print_status "Using curl..."
    curl -L --progress-bar -o "$DEST_PATH" "$VIDEO_URL"
    
    if [ $? -eq 0 ]; then
        DOWNLOAD_SUCCESS=true
    else
        DOWNLOAD_SUCCESS=false
    fi
else
    print_error "❌ Neither wget nor curl is available"
    exit 1
fi

DOWNLOAD_END=$(date +%s)
DOWNLOAD_TIME=$((DOWNLOAD_END - DOWNLOAD_START))

if [ "$DOWNLOAD_SUCCESS" = true ] && [ -f "$DEST_PATH" ]; then
    FILE_SIZE=$(du -h "$DEST_PATH" | cut -f1)
    FILE_SIZE_BYTES=$(stat -c%s "$DEST_PATH" 2>/dev/null || stat -f%z "$DEST_PATH" 2>/dev/null || echo "0")
    
    print_success "✅ Download completed!"
    print_perf "   File: $DEST_PATH"
    print_perf "   Size: $FILE_SIZE ($FILE_SIZE_BYTES bytes)"
    print_perf "   Download time: ${DOWNLOAD_TIME}s"
    
    # Calculate download speed
    if [ $DOWNLOAD_TIME -gt 0 ] && [ "$FILE_SIZE_BYTES" -gt 0 ]; then
        SPEED_BPS=$((FILE_SIZE_BYTES / DOWNLOAD_TIME))
        SPEED_MBPS=$(awk "BEGIN {printf \"%.2f\", $SPEED_BPS / 1024 / 1024}")
        print_perf "   Speed: ${SPEED_MBPS} MB/s"
    fi
    
    # Set permissions
    chmod 644 "$DEST_PATH" 2>/dev/null || true
    
    # Get video duration (if ffprobe is available)
    if command -v ffprobe &> /dev/null; then
        DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$DEST_PATH" 2>/dev/null || echo "0")
        if [ -n "$DURATION" ] && [ "$DURATION" != "0" ]; then
            DURATION_INT=${DURATION%.*}
            HOURS=$((DURATION_INT / 3600))
            MINUTES=$(((DURATION_INT % 3600) / 60))
            SECONDS=$((DURATION_INT % 60))
            print_perf "   Duration: ${HOURS}h ${MINUTES}m ${SECONDS}s"
        fi
    fi
    
    echo ""
    print_success "🎉 Video downloaded successfully!"
    echo ""
    print_status "💡 Next steps:"
    echo "   # Test transcription:"
    echo "   bash scripts/pod/test-transcription-performance.sh $DEST_PATH large"
    echo ""
else
    print_error "❌ Download failed!"
    if [ -f "$DEST_PATH" ]; then
        rm -f "$DEST_PATH"
    fi
    exit 1
fi

