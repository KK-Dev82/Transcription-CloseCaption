#!/bin/bash
# Script สำหรับ Download Video จาก URL ไปไว้ที่ uploads/
#
# วิธีใช้งาน:
#   bash scripts/pod/download-video.sh <url> [output-filename]
#
# ตัวอย่าง:
#   bash scripts/pod/download-video.sh https://korrakang.com/video/v10-1.mp4
#   bash scripts/pod/download-video.sh https://korrakang.com/video/v10-1.mp4 v10-1.mp4

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
UPLOADS_DIR="$PROJECT_ROOT/uploads"
mkdir -p "$UPLOADS_DIR"

# Parse arguments
VIDEO_URL="${1:-}"
OUTPUT_FILENAME="${2:-}"

if [ -z "$VIDEO_URL" ]; then
    print_error "❌ Error: Video URL is required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/download-video.sh <url> [output-filename]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pod/download-video.sh https://korrakang.com/video/v10-1.mp4"
    echo "  bash scripts/pod/download-video.sh https://korrakang.com/video/v10-1.mp4 v10-1.mp4"
    exit 1
fi

# Extract filename from URL if not provided
if [ -z "$OUTPUT_FILENAME" ]; then
    OUTPUT_FILENAME=$(basename "$VIDEO_URL" | cut -d'?' -f1)
    if [ -z "$OUTPUT_FILENAME" ] || [ "$OUTPUT_FILENAME" = "/" ]; then
        OUTPUT_FILENAME="video-$(date +%s).mp4"
    fi
fi

OUTPUT_PATH="$UPLOADS_DIR/$OUTPUT_FILENAME"

# Check if file already exists
if [ -f "$OUTPUT_PATH" ]; then
    print_warning "⚠️  File already exists: $OUTPUT_PATH"
    read -p "Overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Skipping download"
        exit 0
    fi
    rm -f "$OUTPUT_PATH"
fi

print_status "Downloading video..."
print_status "URL: $VIDEO_URL"
print_status "Output: $OUTPUT_PATH"
echo ""

# Download using wget or curl
if command -v wget > /dev/null 2>&1; then
    wget -O "$OUTPUT_PATH" "$VIDEO_URL" --progress=bar:force 2>&1 | grep -E "([0-9]+%)|saved" || true
elif command -v curl > /dev/null 2>&1; then
    curl -L -o "$OUTPUT_PATH" --progress-bar "$VIDEO_URL"
else
    print_error "❌ Neither wget nor curl found"
    exit 1
fi

# Check if download was successful
if [ -f "$OUTPUT_PATH" ] && [ -s "$OUTPUT_PATH" ]; then
    FILE_SIZE=$(du -h "$OUTPUT_PATH" | cut -f1)
    print_success "✅ Download completed: $OUTPUT_FILENAME ($FILE_SIZE)"
    print_status "Location: $OUTPUT_PATH"
else
    print_error "❌ Download failed"
    exit 1
fi

