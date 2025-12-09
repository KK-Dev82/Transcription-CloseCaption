#!/bin/bash
# Script สำหรับรัน Benchmark บน RTX 4000 Ada ผ่าน SSH
# ตรวจสอบและแก้ไขปัญหาก่อนรัน benchmark
#
# วิธีใช้งาน:
#   bash scripts/pod/run-benchmark-4000ada-remote.sh

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

SSH_HOST="${SSH_4000ADA_HOST:-4000-ada}"
PROJECT_DIR="/workspace/transcription-service"

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "RTX 4000 Ada - Remote Benchmark Setup & Test"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. ตรวจสอบ SSH Connection
print_status "1. Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 "$SSH_HOST" "echo 'Connection OK'" > /dev/null 2>&1; then
    print_error "❌ Cannot connect to $SSH_HOST"
    print_status "💡 Check SSH config: ~/.ssh/config"
    print_status "💡 Or set SSH_4000ADA_HOST environment variable"
    exit 1
fi
print_success "✅ SSH connection OK"
echo ""

# 2. Git Pull
print_status "2. Pulling latest code..."
if ssh "$SSH_HOST" "[ -d '$PROJECT_DIR' ]"; then
    ssh "$SSH_HOST" "cd $PROJECT_DIR && git pull" || {
        print_warning "⚠️  Git pull failed (may have local changes)"
    }
    print_success "✅ Code updated"
else
    print_error "❌ Project directory not found: $PROJECT_DIR"
    exit 1
fi
echo ""

# 3. ตรวจสอบ Services
print_status "3. Checking services..."
ssh "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/check-pod.sh" || {
    print_warning "⚠️  Some services may not be running"
}
echo ""

# 4. ตรวจสอบ Video
print_status "4. Checking test video..."
if ssh "$SSH_HOST" "[ -f '$PROJECT_DIR/uploads/v10-1.mp4' ]"; then
    FILE_SIZE=$(ssh "$SSH_HOST" "du -h $PROJECT_DIR/uploads/v10-1.mp4 | cut -f1")
    print_success "✅ Video found: uploads/v10-1.mp4 ($FILE_SIZE)"
else
    print_warning "⚠️  Video not found"
    print_status "💡 Downloading video..."
    ssh "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/download-video.sh https://korrakang.com/video/v10-1.mp4" || {
        print_error "❌ Failed to download video"
        exit 1
    }
fi
echo ""

# 5. Run Test Script
print_status "5. Running test script on server..."
ssh "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/test-benchmark-4000ada.sh" || {
    print_error "❌ Test script failed"
    exit 1
}

print_success "✅ Setup and test completed!"
echo ""
print_status "💡 To SSH and run benchmark manually:"
echo "   ssh $SSH_HOST"
echo "   cd $PROJECT_DIR"
echo "   bash scripts/pod/run-benchmark-concurrent.sh uploads/v10-1.mp4 10 medium rtx4000"

