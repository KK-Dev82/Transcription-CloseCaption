#!/bin/bash
# Init Runner: First Setup สำหรับ RunPod (หลัง clone / container ใหม่)
# รวมคำสั่งทั้งหมดจาก README Quick Start พร้อมแสดง progress
#
# วิธีใช้งาน:
#   ./scripts/pod/init-runner.sh

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_step() {
    echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_progress() {
    echo -e "${YELLOW}  ⏳ $1${NC}"
}

print_success() {
    echo -e "${GREEN}  ✅ $1${NC}"
}

print_error() {
    echo -e "${RED}  ❌ $1${NC}"
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo ""
echo -e "${GREEN}🚀 Init Runner - RunPod First Setup${NC}"
echo -e "   📅 $(date)"
echo -e "   📂 Project: $PROJECT_ROOT"
echo ""

# Step 1: apt-get update && install ffmpeg
print_step "Step 1/5: Installing FFmpeg (apt-get update + install)"
print_progress "Updating package lists..."
apt-get update -qq
print_progress "Installing ffmpeg..."
apt-get install -y ffmpeg
if command -v ffmpeg &> /dev/null; then
    print_success "FFmpeg installed: $(ffmpeg -version | head -1)"
else
    print_error "FFmpeg installation failed"
    exit 1
fi

# Step 2: pip install requirements
print_step "Step 2/5: Installing Python dependencies (requirements.txt)"
if [ ! -f "requirements.txt" ]; then
    print_error "requirements.txt not found"
    exit 1
fi
print_progress "Running pip install (อาจใช้เวลานาน)..."
pip install -r requirements.txt
print_success "Python dependencies installed"

# Step 3: setup cuDNN
print_step "Step 3/5: Setting up cuDNN environment"
print_progress "Running setup-cudnn-env.sh..."
./scripts/utility/setup-cudnn-env.sh
print_success "cuDNN environment configured"

# Step 4: start pod (Redis, Whisper API, Video Worker, Main API)
print_step "Step 4/5: Starting Pod services (start-pod.sh)"
print_progress "Starting Redis, Whisper API, Video Worker, Main API..."
./scripts/pod/start-pod.sh
print_success "Pod services started"

# Step 5: start RQ workers
print_step "Step 5/5: Starting RQ Workers"
print_progress "Starting RQ workers (GPU + Preprocess + CPU)..."
./scripts/pod/start-rq-workers.sh
print_success "RQ Workers started"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 Init Runner เสร็จสมบูรณ์!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  💡 ตรวจสอบสถานะ:  ${BLUE}./scripts/pod/check-pod.sh${NC}"
echo -e "  💡 ดู logs:       ${BLUE}./scripts/pod/logs-pod.sh${NC}"
echo ""
