#!/bin/bash
# Start RQ Workers สำหรับ Multi-GPU Transcription
# แต่ละ worker fix GPU ด้วย CUDA_VISIBLE_DEVICES

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
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

# ตรวจสอบ Redis connection
print_info "Checking Redis connection..."
if [ -z "${REDIS_URL:-}" ]; then
    print_error "REDIS_URL is not set! Please set it in .env.runpod or export it."
    exit 1
fi
print_info "Using REDIS_URL: ${REDIS_URL:0:40}..."
if python3 -c "import redis; r=redis.from_url('$REDIS_URL'); r.ping(); print('OK')" 2>/dev/null; then
    print_success "Redis connection OK"
else
    print_error "Cannot connect to Redis: ${REDIS_URL:0:40}..."
    exit 1
fi

# หยุด worker เดิม (ถ้ามี)
print_info "Stopping existing RQ workers..."
pkill -f "rq worker.*transcription_gpu" 2>/dev/null || true
sleep 2

# ตั้งค่า LD_LIBRARY_PATH สำหรับ cuDNN
CUDNN_LIB_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
if [ -d "$CUDNN_LIB_PATH" ]; then
    export LD_LIBRARY_PATH="$CUDNN_LIB_PATH:${LD_LIBRARY_PATH:-}"
    print_success "✅ Set LD_LIBRARY_PATH for cuDNN libraries"
fi

# ตั้งค่า PATH สำหรับ FFmpeg
export PATH="/usr/bin:/usr/local/bin:${PATH:-}"
if command -v ffmpeg &> /dev/null; then
    print_success "✅ FFmpeg found in PATH"
else
    print_warning "⚠️  FFmpeg not found in PATH (may cause chunking to fail)"
fi

# ตรวจสอบจำนวน GPU
NUM_GPUS=${NUM_GPUS:-4}
print_info "Detected $NUM_GPUS GPUs"

# เริ่ม RQ Workers สำหรับแต่ละ GPU
WORKER_PIDS=()
for i in $(seq 0 $((NUM_GPUS - 1))); do
    print_info "Starting RQ Worker GPU $i..."
    CUDA_VISIBLE_DEVICES=$i \
        LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
        REDIS_URL="$REDIS_URL" \
        RQ_PRELOAD_MODEL=true \
        rq worker \
        --url "$REDIS_URL" \
        transcription_gpu$i \
        transcription_default \
        --name worker-gpu$i \
        --pid /tmp/rq-worker-gpu$i.pid \
        > /tmp/rq-worker-gpu$i.log 2>&1 &
    
    WORKER_PID=$!
    WORKER_PIDS+=($WORKER_PID)
    print_success "RQ Worker GPU $i started (PID: $WORKER_PID)"
done

# เริ่ม Priority Worker (ใช้ GPU 0 สำหรับ priority tasks)
print_info "Starting RQ Priority Worker..."
CUDA_VISIBLE_DEVICES=0 \
    LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
    REDIS_URL="$REDIS_URL" \
    RQ_PRELOAD_MODEL=true \
    rq worker \
    --url "$REDIS_URL" \
    transcription_priority \
    --name worker-priority \
    --pid /tmp/rq-worker-priority.pid \
    > /tmp/rq-worker-priority.log 2>&1 &

PRIORITY_PID=$!
print_success "RQ Priority Worker started (PID: $PRIORITY_PID)"

print_success "✅ RQ Workers started successfully!"
print_info "Workers:"
for i in $(seq 0 $((NUM_GPUS - 1))); do
    print_info "  - GPU $i: transcription_gpu$i, transcription_default"
done
print_info "  - Priority: transcription_priority (GPU 0)"
print_info ""
print_info "Logs:"
for i in $(seq 0 $((NUM_GPUS - 1))); do
    print_info "  - GPU $i: tail -f /tmp/rq-worker-gpu$i.log"
done
print_info "  - Priority: tail -f /tmp/rq-worker-priority.log"
print_info ""
print_info "Monitor queues:"
print_info "  rq info --url $REDIS_URL"

