#!/bin/bash
# Script สำหรับ Download หลาย Video จาก URL Pattern
#
# วิธีใช้งาน:
#   bash scripts/pod/download-multiple-videos.sh <base-url> <start> <end> [suffix]
#
# ตัวอย่าง:
#   bash scripts/pod/download-multiple-videos.sh https://korrakang.com/video/v10- 1 10 .mp4
#   (จะ download v10-1.mp4 ถึง v10-10.mp4)

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

# Parse arguments
BASE_URL="${1:-}"
START="${2:-1}"
END="${3:-10}"
SUFFIX="${4:-.mp4}"

if [ -z "$BASE_URL" ]; then
    print_error "❌ Error: Base URL is required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/download-multiple-videos.sh <base-url> <start> <end> [suffix]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pod/download-multiple-videos.sh https://korrakang.com/video/v10- 1 10 .mp4"
    echo "  (will download v10-1.mp4 to v10-10.mp4)"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
UPLOADS_DIR="$PROJECT_ROOT/uploads"
mkdir -p "$UPLOADS_DIR"

print_status "Downloading videos from $START to $END"
print_status "Base URL: $BASE_URL"
print_status "Suffix: $SUFFIX"
echo ""

SUCCESS_COUNT=0
FAILED_COUNT=0
SKIPPED_COUNT=0

for i in $(seq $START $END); do
    VIDEO_URL="${BASE_URL}${i}${SUFFIX}"
    OUTPUT_FILENAME="v10-${i}${SUFFIX}"
    OUTPUT_PATH="$UPLOADS_DIR/$OUTPUT_FILENAME"
    
    # Check if file already exists
    if [ -f "$OUTPUT_PATH" ]; then
        print_warning "⚠️  Skipping $OUTPUT_FILENAME (already exists)"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi
    
    print_status "[$i/$END] Downloading $OUTPUT_FILENAME..."
    
    # Download using wget or curl
    if command -v wget > /dev/null 2>&1; then
        if wget -O "$OUTPUT_PATH" "$VIDEO_URL" --quiet --show-progress 2>&1 | grep -q "saved"; then
            FILE_SIZE=$(du -h "$OUTPUT_PATH" | cut -f1)
            print_success "   ✅ $OUTPUT_FILENAME ($FILE_SIZE)"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            print_error "   ❌ Failed: $OUTPUT_FILENAME"
            rm -f "$OUTPUT_PATH"
            FAILED_COUNT=$((FAILED_COUNT + 1))
        fi
    elif command -v curl > /dev/null 2>&1; then
        if curl -L -o "$OUTPUT_PATH" --silent --show-error --fail "$VIDEO_URL" 2>/dev/null; then
            FILE_SIZE=$(du -h "$OUTPUT_PATH" | cut -f1)
            print_success "   ✅ $OUTPUT_FILENAME ($FILE_SIZE)"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            print_error "   ❌ Failed: $OUTPUT_FILENAME"
            rm -f "$OUTPUT_PATH"
            FAILED_COUNT=$((FAILED_COUNT + 1))
        fi
    else
        print_error "❌ Neither wget nor curl found"
        exit 1
    fi
done

echo ""
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Download Summary"
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_success "✅ Success: $SUCCESS_COUNT"
print_warning "⚠️  Skipped: $SKIPPED_COUNT"
if [ $FAILED_COUNT -gt 0 ]; then
    print_error "❌ Failed: $FAILED_COUNT"
fi
print_status "Total: $((SUCCESS_COUNT + SKIPPED_COUNT + FAILED_COUNT))"
echo ""

