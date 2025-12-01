#!/bin/bash
# Script สำหรับทดสอบ Transcription บน RunPod GPU Server
# Usage: bash scripts/pod/test-runpod.sh [video_file] [model]

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# SSH Host (จาก ~/.ssh/config)
SSH_HOST="${RUNPOD_HOST:-calm-pink-turtle}"
PROJECT_DIR="/workspace/transcription-service"
POD_NAME="calm_pink_turtle"
VIDEO_FILE="${1:-uploads/v10-1.mp4}"
MODEL="${2:-medium}"

print_status "🧪 Testing Transcription on RunPod GPU Server"
print_status "Pod Name: $POD_NAME"
print_status "SSH Host: $SSH_HOST"
print_status "Video File: $VIDEO_FILE"
print_status "Model: $MODEL"
echo ""

# ตรวจสอบ SSH connection
if ! ssh -o ConnectTimeout=5 "$SSH_HOST" "echo 'Connection OK'" > /dev/null 2>&1; then
    print_error "Cannot connect to $SSH_HOST"
    exit 1
fi

# ตรวจสอบว่าไฟล์วิดีโอมีอยู่บน server
print_status "Checking video file..."
if ! ssh "$SSH_HOST" "[ -f '$PROJECT_DIR/$VIDEO_FILE' ]"; then
    print_error "Video file not found: $VIDEO_FILE"
    print_info "Available files:"
    ssh "$SSH_HOST" "cd $PROJECT_DIR && ls -lh uploads/*.mp4 2>/dev/null | head -5"
    exit 1
fi
print_success "Video file found"
echo ""

# ตรวจสอบ GPU
print_status "Checking GPU..."
ssh "$SSH_HOST" "nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader"
echo ""

# ตรวจสอบ services
print_status "Checking services..."
ssh "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/check-pod.sh"
echo ""

# Run test
print_status "Running transcription test..."
ssh "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/test-transcription.sh $VIDEO_FILE $MODEL"
echo ""

print_success "✅ Test completed!"
print_info "View results: ssh $SSH_HOST 'cd $PROJECT_DIR && bash scripts/pod/result-view.sh -detail 5'"

