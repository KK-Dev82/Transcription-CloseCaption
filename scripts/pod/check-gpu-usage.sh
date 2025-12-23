#!/bin/bash
# ตรวจสอบว่า Workers ใช้ GPU หรือ CPU

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Load .env.runpod
if [ -f "$PROJECT_ROOT/.env.runpod" ]; then
    set -a
    source "$PROJECT_ROOT/.env.runpod"
    set +a
fi

print_info "Checking GPU usage by workers..."
echo ""

# ตรวจสอบ GPU utilization
if command -v nvidia-smi &> /dev/null; then
    print_info "GPU Status:"
    nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader
    echo ""
fi

# ตรวจสอบ worker logs
print_info "Checking worker logs for GPU/CPU usage..."
echo ""

num_gpus=${NUM_GPUS:-2}
for i in $(seq 0 $((num_gpus - 1))); do
    log_file="/tmp/rq-worker-gpu$i.log"
    if [ -f "$log_file" ]; then
        print_info "GPU Worker $i:"
        # ตรวจสอบว่าใช้ GPU หรือ CPU
        if grep -q "device.*cuda" "$log_file" 2>/dev/null; then
            print_success "   ✅ Using GPU (CUDA)"
        elif grep -q "device.*cpu" "$log_file" 2>/dev/null; then
            print_warning "   ⚠️  Using CPU (fallback - high RAM usage!)"
        else
            print_warning "   ⚠️  Cannot determine device from logs"
        fi
        
        # ตรวจสอบ cuDNN
        if grep -q "cudnn\|cuDNN" "$log_file" 2>/dev/null; then
            if grep -q "cudnn.*error\|cuDNN.*error\|Could not load.*cudnn" "$log_file" 2>/dev/null; then
                print_error "   ❌ cuDNN error detected!"
            else
                print_success "   ✅ cuDNN mentioned in logs (likely working)"
            fi
        else
            print_warning "   ⚠️  No cuDNN mention in logs"
        fi
        
        # ตรวจสอบ LD_LIBRARY_PATH
        if grep -q "LD_LIBRARY_PATH" "$log_file" 2>/dev/null; then
            print_success "   ✅ LD_LIBRARY_PATH set"
        else
            print_warning "   ⚠️  LD_LIBRARY_PATH not mentioned in logs"
        fi
        
        echo ""
    else
        print_warning "   ⚠️  Log file not found: $log_file"
    fi
done

# ตรวจสอบ Python processes
print_info "Checking Python processes:"
ps aux | grep -E "rq worker|python.*transcription" | grep -v grep | head -5
echo ""

# ตรวจสอบ environment variables ของ worker processes
print_info "Checking worker environment variables:"
for pid in $(pgrep -f "rq worker.*transcription_gpu" 2>/dev/null | head -1); do
    if [ -n "$pid" ]; then
        print_info "   Worker PID: $pid"
        if [ -f "/proc/$pid/environ" ]; then
            env_vars=$(cat "/proc/$pid/environ" 2>/dev/null | tr '\0' '\n' | grep -E "LD_LIBRARY_PATH|CUDA_VISIBLE_DEVICES|WHISPER_DEVICE" || true)
            if [ -n "$env_vars" ]; then
                echo "$env_vars" | while read line; do
                    echo "      $line"
                done
            else
                print_warning "      No relevant env vars found"
            fi
        fi
        break
    fi
done
echo ""

# ตรวจสอบ CUDA_VISIBLE_DEVICES ของแต่ละ worker process
print_info "Checking CUDA_VISIBLE_DEVICES for each worker:"
num_gpus=${NUM_GPUS:-2}
for i in $(seq 0 $((num_gpus - 1))); do
    worker_pids=$(pgrep -f "rq worker.*worker-gpu$i" 2>/dev/null || true)
    if [ -n "$worker_pids" ]; then
        for pid in $worker_pids; do
            if [ -f "/proc/$pid/environ" ]; then
                cuda_dev=$(cat "/proc/$pid/environ" 2>/dev/null | tr '\0' '\n' | grep "^CUDA_VISIBLE_DEVICES=" || true)
                if [ -n "$cuda_dev" ]; then
                    print_success "   Worker GPU $i (PID $pid): $cuda_dev"
                else
                    print_warning "   Worker GPU $i (PID $pid): CUDA_VISIBLE_DEVICES not set!"
                fi
            fi
        done
    else
        print_warning "   Worker GPU $i: Not running"
    fi
done
echo ""

# ตรวจสอบ GPU utilization แบบ real-time (ถ้ามี transcription กำลังทำงาน)
print_info "Real-time GPU Utilization (30 seconds):"
if command -v nvidia-smi &> /dev/null; then
    timeout 30 watch -n 1 -d 'nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader' 2>/dev/null || \
    nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader --loop=30 2>/dev/null || \
    nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader
    echo ""
fi

print_info "💡 Tips:"
echo "   - ถ้าเห็น 'Using CPU' → CTranslate2 ไม่พบ cuDNN → ใช้ RAM มาก!"
echo "   - ตรวจสอบ LD_LIBRARY_PATH ใน worker logs"
echo "   - GPU utilization ควรสูง (>80%) ระหว่าง transcription"
echo "   - ถ้า GPU0 และ GPU1 ทำงานพร้อมกัน → ระบบใช้ 2 GPU ถูกต้อง"

