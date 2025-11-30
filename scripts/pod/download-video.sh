#!/bin/bash
# Script สำหรับ Download Video และเก็บไว้ใน Pod
# รองรับทั้ง URL และ Local File (ผ่าน SCP)
#
# วิธีใช้งาน:
# bash scripts/pod/download-video.sh <source> [destination]
#
# ตัวอย่าง:
# bash scripts/pod/download-video.sh https://example.com/video.mp4
# bash scripts/pod/download-video.sh /local/path/video.mp4 uploads/test-video.mp4
# bash scripts/pod/download-video.sh /local/path/video.mp4 test-files/video.mp4

set -e

SOURCE="${1}"
DEST_DIR="${2:-uploads}"

if [ -z "$SOURCE" ]; then
    echo "❌ Error: Source is required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/download-video.sh <source> [destination-dir]"
    echo ""
    echo "Examples:"
    echo "  # Download from URL"
    echo "  bash scripts/pod/download-video.sh https://example.com/video.mp4"
    echo ""
    echo "  # Copy from local file (if running from Pod)"
    echo "  bash scripts/pod/download-video.sh /tmp/video.mp4 uploads/"
    echo ""
    echo "  # Copy to test-files directory"
    echo "  bash scripts/pod/download-video.sh /tmp/video.mp4 test-files/"
    echo ""
    exit 1
fi

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Create destination directory
mkdir -p "$DEST_DIR"
print_success "✅ Destination directory: $DEST_DIR"

# Determine if source is URL or local file
if [[ "$SOURCE" =~ ^https?:// ]]; then
    # Download from URL
    print_status "Downloading from URL: $SOURCE"
    
    # Extract filename from URL
    FILENAME=$(basename "$SOURCE" | sed 's/[?&].*//')
    if [ -z "$FILENAME" ] || [ "$FILENAME" = "/" ]; then
        FILENAME="video-$(date +%Y%m%d-%H%M%S).mp4"
    fi
    
    DEST_PATH="$DEST_DIR/$FILENAME"
    
    # Download using wget or curl
    if command -v wget &> /dev/null; then
        wget -O "$DEST_PATH" "$SOURCE" || {
            print_error "❌ Download failed with wget"
            exit 1
        }
    elif command -v curl &> /dev/null; then
        curl -L -o "$DEST_PATH" "$SOURCE" || {
            print_error "❌ Download failed with curl"
            exit 1
        }
    else
        print_error "❌ Neither wget nor curl is available"
        exit 1
    fi
    
    print_success "✅ Downloaded: $DEST_PATH"
    
elif [ -f "$SOURCE" ]; then
    # Copy from local file
    print_status "Copying from local file: $SOURCE"
    
    FILENAME=$(basename "$SOURCE")
    DEST_PATH="$DEST_DIR/$FILENAME"
    
    # If destination is a directory, append filename
    if [ -d "$DEST_DIR" ]; then
        DEST_PATH="$DEST_DIR/$FILENAME"
    fi
    
    cp "$SOURCE" "$DEST_PATH" || {
        print_error "❌ Copy failed"
        exit 1
    }
    
    print_success "✅ Copied: $SOURCE -> $DEST_PATH"
    
else
    print_error "❌ Source not found: $SOURCE"
    echo ""
    print_status "💡 Tips:"
    echo "   - For URL: Use http:// or https://"
    echo "   - For local file: Use absolute or relative path"
    exit 1
fi

# Set permissions
chmod 644 "$DEST_PATH" 2>/dev/null || true

# Get file info
FILE_SIZE=$(du -h "$DEST_PATH" | cut -f1)
FILE_SIZE_BYTES=$(stat -c%s "$DEST_PATH" 2>/dev/null || stat -f%z "$DEST_PATH" 2>/dev/null || echo "0")

print_success "✅ File saved: $DEST_PATH"
print_status "   Size: $FILE_SIZE ($FILE_SIZE_BYTES bytes)"

# Get video duration (if ffprobe is available)
if command -v ffprobe &> /dev/null; then
    DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$DEST_PATH" 2>/dev/null || echo "0")
    if [ -n "$DURATION" ] && [ "$DURATION" != "0" ]; then
        DURATION_INT=${DURATION%.*}
        MINUTES=$((DURATION_INT / 60))
        SECONDS=$((DURATION_INT % 60))
        print_status "   Duration: ${MINUTES}m ${SECONDS}s"
    fi
fi

echo ""
print_status "💡 Next steps:"
echo "   # Test transcription:"
echo "   bash scripts/pod/test-transcription-performance.sh $DEST_PATH medium"
echo ""

