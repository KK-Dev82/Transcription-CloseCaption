#!/bin/bash
# Script สำหรับ Download วิดีโอทดสอบทั้ง 3 ตัว
#
# วิธีใช้งาน:
#   bash scripts/pod/download-test-videos.sh

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
print_header() { echo -e "${CYAN}$1${NC}"; }

SSH_HOST="${RUNPOD_HOST:-calm-pink-turtle}"
PROJECT_DIR="/workspace/transcription-service"

# วิดีโอที่จะ download
declare -A VIDEOS=(
    ["v05-1.mp4"]="https://korrakang.com/video/v05-1.mp4"
    ["v10-1.mp4"]="https://korrakang.com/video/v10-1.mp4"
    ["v60-1.mp4"]="https://korrakang.com/video/v60-1.mp4"
)

echo "📥 Downloading Test Videos"
echo "📅 $(date)"
echo ""

# ตรวจสอบ SSH connection
print_status "Checking SSH connection..."
if ! ssh -o ConnectTimeout=5 "$SSH_HOST" "echo 'Connection OK'" > /dev/null 2>&1; then
    print_error "Cannot connect to $SSH_HOST"
    exit 1
fi
print_success "✅ SSH connection OK"
echo ""

# Download แต่ละวิดีโอ
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Downloading Videos"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for filename in "${!VIDEOS[@]}"; do
    url="${VIDEOS[$filename]}"
    print_status "Downloading: $filename"
    print_status "   URL: $url"
    
    # ตรวจสอบว่ามีไฟล์อยู่แล้วหรือไม่
    if ssh "$SSH_HOST" "[ -f '$PROJECT_DIR/uploads/$filename' ]"; then
        FILE_SIZE=$(ssh "$SSH_HOST" "stat -c%s '$PROJECT_DIR/uploads/$filename' 2>/dev/null || stat -f%z '$PROJECT_DIR/uploads/$filename' 2>/dev/null || echo '0'")
        if [ "$FILE_SIZE" -gt 1000 ]; then
            print_warning "   ⚠️  File already exists ($(ssh "$SSH_HOST" "du -h '$PROJECT_DIR/uploads/$filename' | cut -f1"))"
            read -p "   Re-download? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_success "   ✅ Skipped (using existing file)"
                echo ""
                continue
            fi
        fi
    fi
    
    # Download
    ssh "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/download-video.sh '$url' uploads/" || {
        print_error "   ❌ Failed to download $filename"
        continue
    }
    
    # ตรวจสอบไฟล์
    if ssh "$SSH_HOST" "[ -f '$PROJECT_DIR/uploads/$filename' ]"; then
        FILE_SIZE=$(ssh "$SSH_HOST" "stat -c%s '$PROJECT_DIR/uploads/$filename' 2>/dev/null || stat -f%z '$PROJECT_DIR/uploads/$filename' 2>/dev/null || echo '0'")
        FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))
        print_success "   ✅ Downloaded: $filename ($FILE_SIZE_MB MB)"
        
        # ตรวจสอบ duration (ถ้ามี ffprobe)
        if ssh "$SSH_HOST" "command -v ffprobe > /dev/null 2>&1"; then
            DURATION=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 'uploads/$filename' 2>/dev/null | cut -d'.' -f1" || echo "0")
            if [ -n "$DURATION" ] && [ "$DURATION" != "0" ]; then
                MINUTES=$((DURATION / 60))
                SECONDS=$((DURATION % 60))
                print_status "   Duration: ${MINUTES}m ${SECONDS}s"
            fi
        fi
    else
        print_error "   ❌ File not found after download"
    fi
    echo ""
done

# Summary
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Download Summary"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

print_status "Checking downloaded files..."
for filename in "${!VIDEOS[@]}"; do
    if ssh "$SSH_HOST" "[ -f '$PROJECT_DIR/uploads/$filename' ]"; then
        FILE_SIZE=$(ssh "$SSH_HOST" "du -h '$PROJECT_DIR/uploads/$filename' | cut -f1")
        print_success "   ✅ $filename ($FILE_SIZE)"
    else
        print_error "   ❌ $filename (missing)"
    fi
done
echo ""

print_success "✅ Download completed!"
echo ""
print_status "💡 Next steps:"
echo "   1. Start services: bash scripts/pod/start-pod.sh"
echo "   2. Test transcription: bash scripts/pod/test-all-videos.sh"
echo ""

