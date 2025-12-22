#!/bin/bash
# Start Multi-GPU Workers
# รัน 2 worker process แต่ละตัว fix GPU ด้วย CUDA_VISIBLE_DEVICES

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# ตรวจสอบว่า ffmpeg อยู่ใน PATH
if ! command -v ffmpeg &> /dev/null; then
    print_warning "ffmpeg not found in PATH, adding /usr/bin to PATH"
    export PATH="/usr/bin:$PATH"
fi

# ตั้งค่า LD_LIBRARY_PATH สำหรับ cuDNN
CUDNN_LIB_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
if [ -d "$CUDNN_LIB_PATH" ]; then
    export LD_LIBRARY_PATH="$CUDNN_LIB_PATH:${LD_LIBRARY_PATH:-}"
    print_success "✅ Set LD_LIBRARY_PATH for cuDNN libraries"
fi

# หยุด worker เดิม (ถ้ามี)
print_info "Stopping existing workers..."
pkill -f "uvicorn.*app.main.*--port 8010" 2>/dev/null || true
pkill -f "uvicorn.*app.main.*--port 8011" 2>/dev/null || true
sleep 2

# เริ่ม Worker GPU 0 (port 8010)
print_info "Starting Worker GPU 0 (port 8010)..."
CUDA_VISIBLE_DEVICES=0 \
    LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
    python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8010 \
    --workers 1 \
    > /tmp/worker-gpu0.log 2>&1 &

WORKER_0_PID=$!
print_success "Worker GPU 0 started (PID: $WORKER_0_PID, port: 8010)"

# เริ่ม Worker GPU 1 (port 8011)
print_info "Starting Worker GPU 1 (port 8011)..."
CUDA_VISIBLE_DEVICES=1 \
    LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
    python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8011 \
    --workers 1 \
    > /tmp/worker-gpu1.log 2>&1 &

WORKER_1_PID=$!
print_success "Worker GPU 1 started (PID: $WORKER_1_PID, port: 8011)"

# รอให้ workers เริ่ม
print_info "Waiting for workers to start..."
sleep 10

# ตรวจสอบว่า workers ทำงานได้
if curl -s http://localhost:8010/health > /dev/null 2>&1; then
    print_success "✅ Worker GPU 0 is healthy"
else
    print_error "❌ Worker GPU 0 is not responding"
    print_error "Check logs: tail -f /tmp/worker-gpu0.log"
fi

if curl -s http://localhost:8011/health > /dev/null 2>&1; then
    print_success "✅ Worker GPU 1 is healthy"
else
    print_error "❌ Worker GPU 1 is not responding"
    print_error "Check logs: tail -f /tmp/worker-gpu1.log"
fi

print_success "✅ Multi-GPU workers started successfully!"
print_info "Worker URLs:"
print_info "  - GPU 0: http://127.0.0.1:8010"
print_info "  - GPU 1: http://127.0.0.1:8011"
print_info ""
print_info "Set environment variable:"
print_info "  export WHISPER_WORKER_URLS='http://127.0.0.1:8010,http://127.0.0.1:8011'"
print_info ""
print_info "Logs:"
print_info "  - GPU 0: tail -f /tmp/worker-gpu0.log"
print_info "  - GPU 1: tail -f /tmp/worker-gpu1.log"


