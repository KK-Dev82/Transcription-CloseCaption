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

# โหลด environment variables จาก .env.runpod ก่อน
print_info "Loading environment variables from .env.runpod..."
if [ -f "$PROJECT_ROOT/.env.runpod" ]; then
    set -a
    source "$PROJECT_ROOT/.env.runpod"
    set +a
    print_success "✅ Environment variables loaded from .env.runpod"
else
    print_warning "⚠️  .env.runpod not found, using environment variables from shell"
fi

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

# หยุด worker เดิม (ถ้ามี) - kill ครบทุก queue (รวม multi-worker pattern)
print_info "Stopping existing RQ workers..."
pkill -f "rq worker.*transcription_gpu" 2>/dev/null || true
pkill -f "rq worker.*transcription_priority" 2>/dev/null || true
pkill -f "rq worker.*transcription_cpu" 2>/dev/null || true
pkill -f "rq worker.*transcription_preprocess" 2>/dev/null || true
pkill -f "rq.*worker-gpu.*-w" 2>/dev/null || true  # Kill multi-worker pattern
sleep 2

# ตั้งค่า LD_LIBRARY_PATH สำหรับ CUDA, cuDNN และ CTranslate2
# ⚠️ สำคัญ: ต้องมี cuDNN libraries ก่อน CUDA เพื่อให้ CTranslate2 พบ cuDNN ได้
# Order: cuDNN → CUDA → CTranslate2
CUDNN_LIB_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
CUDA_LIB_PATH="/usr/local/cuda-12.1/lib64"
CTRANSLATE2_LIB_PATH="/usr/local/lib/python3.10/dist-packages/ctranslate2.libs"

# สร้าง LD_LIBRARY_PATH ใหม่ (cuDNN ก่อน, แล้ว CUDA, แล้ว CTranslate2)
NEW_LD_LIBRARY_PATH=""
if [ -d "$CUDNN_LIB_PATH" ]; then
    NEW_LD_LIBRARY_PATH="$CUDNN_LIB_PATH"
    print_success "✅ Added cuDNN libraries to LD_LIBRARY_PATH"
fi
if [ -d "$CUDA_LIB_PATH" ]; then
    if [ -n "$NEW_LD_LIBRARY_PATH" ]; then
        NEW_LD_LIBRARY_PATH="$NEW_LD_LIBRARY_PATH:$CUDA_LIB_PATH"
    else
        NEW_LD_LIBRARY_PATH="$CUDA_LIB_PATH"
    fi
    print_success "✅ Added CUDA libraries to LD_LIBRARY_PATH"
fi
if [ -d "$CTRANSLATE2_LIB_PATH" ]; then
    if [ -n "$NEW_LD_LIBRARY_PATH" ]; then
        NEW_LD_LIBRARY_PATH="$NEW_LD_LIBRARY_PATH:$CTRANSLATE2_LIB_PATH"
    else
        NEW_LD_LIBRARY_PATH="$CTRANSLATE2_LIB_PATH"
    fi
    print_success "✅ Added CTranslate2 libraries to LD_LIBRARY_PATH"
fi

# รวมกับ LD_LIBRARY_PATH เดิม (ถ้ามี)
if [ -n "$NEW_LD_LIBRARY_PATH" ]; then
    export LD_LIBRARY_PATH="$NEW_LD_LIBRARY_PATH:${LD_LIBRARY_PATH:-}"
    print_info "Final LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
    
    # ตรวจสอบว่า cuDNN libraries พบจริงหรือไม่
    if [ -d "$CUDNN_LIB_PATH" ]; then
        cudnn_libs=$(find "$CUDNN_LIB_PATH" -name "libcudnn*.so*" 2>/dev/null | wc -l)
        if [ "$cudnn_libs" -gt 0 ]; then
            print_success "✅ Found $cudnn_libs cuDNN libraries"
        else
            print_warning "⚠️  cuDNN path exists but no libraries found"
        fi
    fi
else
    print_warning "⚠️  No CUDA/cuDNN libraries found in standard paths"
    print_warning "⚠️  GPU workers may fallback to CPU mode (high RAM usage!)"
    # ตั้งค่า LD_LIBRARY_PATH เป็น empty string เพื่อป้องกันปัญหา
    export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
fi

# FIX: ตรวจสอบและยืนยันว่า LD_LIBRARY_PATH ถูกตั้งค่าอย่างถูกต้อง
# เพื่อป้องกันปัญหา "LD_LIBRARY_PATH ไม่ถูกส่งต่อให้ worker"
if [ -z "${LD_LIBRARY_PATH:-}" ]; then
    print_error "❌ LD_LIBRARY_PATH is empty! GPU workers will not work correctly."
    print_error "   Please check CUDA/cuDNN installation."
    exit 1
fi

# FIX: ตรวจสอบว่า cuDNN library สามารถ load ได้จริงหรือไม่
print_info "Verifying cuDNN library can be loaded..."
if python3 -c "import ctypes; ctypes.CDLL('libcudnn_ops_infer.so.8')" 2>/dev/null; then
    print_success "✅ cuDNN library verification passed"
else
    print_warning "⚠️  cuDNN library verification failed (may still work if libraries are in system paths)"
fi

# ตั้งค่า PATH สำหรับ FFmpeg
export PATH="/usr/bin:/usr/local/bin:${PATH:-}"
if command -v ffmpeg &> /dev/null; then
    print_success "✅ FFmpeg found in PATH"
else
    print_warning "⚠️  FFmpeg not found in PATH (may cause chunking to fail)"
fi

# ตรวจสอบจำนวน GPU (ตรวจจริง)
if command -v nvidia-smi &> /dev/null; then
    DETECTED_GPUS=$(nvidia-smi -L | wc -l)
    NUM_GPUS=${NUM_GPUS:-$DETECTED_GPUS}
    print_info "Detected $DETECTED_GPUS GPUs (using $NUM_GPUS)"
else
    NUM_GPUS=${NUM_GPUS:-1}
    print_warning "nvidia-smi not found, using NUM_GPUS=$NUM_GPUS (default)"
fi

# จำนวน workers ต่อ 1 GPU (เพื่อให้ GPU utilization สูงขึ้น)
# 4 workers = optimal สำหรับ RTX 4000 Ada (20GB VRAM) + small model
# แต่ Pod มี 6 vCPU → ใช้ 3 workers เพื่อไม่ให้ CPU bottleneck
GPU_WORKERS_PER_GPU=${GPU_WORKERS_PER_GPU:-4}  # เพิ่มจาก 3 เป็น 4 เพื่อความเร็ว
print_info "GPU Workers per GPU: $GPU_WORKERS_PER_GPU"

# Set PYTHONPATH เพื่อให้ import app.* ได้
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"

# เริ่ม RQ Workers สำหรับแต่ละ GPU (multiple workers per GPU)
# แต่ละ worker ฟัง priority queue ก่อน แล้วค่อย gpu queue ของตัวเอง
# เพื่อให้ priority jobs ได้ GPU ทันทีโดยไม่แย่ง GPU0
# 🚀 OPTIMIZATION: Multiple workers per GPU = concurrent GPU utilization
WORKER_PIDS=()
for i in $(seq 0 $((NUM_GPUS - 1))); do
    print_info "Starting $GPU_WORKERS_PER_GPU RQ Workers for GPU $i..."
    
    # Start multiple workers for this GPU (each in separate process)
    for w in $(seq 0 $((GPU_WORKERS_PER_GPU - 1))); do
        worker_name="worker-gpu${i}-w${w}"
        print_info "   Starting ${worker_name} (listening to priority + gpu$i)..."
        
        # ⚠️ สำคัญ: ส่งต่อ environment variables ทั้งหมดที่จำเป็นสำหรับ GPU
        # - LD_LIBRARY_PATH: สำหรับ CUDA/cuDNN libraries
        # - CUDNN_DISABLE: ตั้งเป็น 0 เพื่อใช้ cuDNN (ถ้าไม่ตั้งจะใช้ default จาก .env.runpod)
        # - WHISPER_DEVICE: ต้องเป็น 'cuda'
        # - WHISPER_COMPUTE_TYPE: ควรเป็น 'float16' สำหรับ GPU
        # ⚠️ สำคัญ: ต้องส่งต่อ LD_LIBRARY_PATH ให้ worker process
        # ถ้าไม่ส่งต่อ CTranslate2 จะไม่พบ cuDNN → fallback เป็น CPU → ใช้ RAM มาก
        # FIX: ใช้ env command เพื่อให้แน่ใจว่า environment variables ถูกส่งต่ออย่างถูกต้อง
        # และใช้ explicit LD_LIBRARY_PATH แทน ${LD_LIBRARY_PATH:-} เพื่อป้องกัน empty value
        env CUDA_VISIBLE_DEVICES=$i \
            LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
            REDIS_URL="$REDIS_URL" \
            PYTHONPATH="$PYTHONPATH" \
            WHISPER_DEVICE="${WHISPER_DEVICE:-cuda}" \
            WHISPER_COMPUTE_TYPE="${WHISPER_COMPUTE_TYPE:-float16}" \
            WHISPER_MODEL="${WHISPER_MODEL:-base}" \
            WHISPER_USE_BATCHED="${WHISPER_USE_BATCHED:-true}" \
            WHISPER_BATCH_SIZE="${WHISPER_BATCH_SIZE:-16}" \
            CUDNN_DISABLE="${CUDNN_DISABLE:-0}" \
            VIDEO_WORKER_TYPE=pika \
            RQ_PRELOAD_MODEL=true \
            RQ_DEFAULT_RESULT_TTL="${RQ_DEFAULT_RESULT_TTL:-43200}" \
            rq worker \
            --url "$REDIS_URL" \
            transcription_priority \
            transcription_gpu$i \
            --name $worker_name \
            --pid /tmp/rq-${worker_name}.pid \
            > /tmp/rq-${worker_name}.log 2>&1 &
        
        WORKER_PID=$!
        WORKER_PIDS+=($WORKER_PID)
        print_success "✅ ${worker_name} started (PID: $WORKER_PID)"
    done
    
    print_success "✅ GPU $i: $GPU_WORKERS_PER_GPU workers started"
done

# เริ่ม Preprocess Workers (1 worker สำหรับ extract + chunking - ลดเพื่อลด setup complexity)
# ใช้ CPU workers หลายตัวเพื่อรองรับ 25 concurrent requests
NUM_PREPROCESS_WORKERS=${NUM_PREPROCESS_WORKERS:-1}
print_info "Starting RQ Preprocess Workers (${NUM_PREPROCESS_WORKERS} workers for extract + chunking)..."
PREPROCESS_PIDS=()
for i in $(seq 0 $((NUM_PREPROCESS_WORKERS - 1))); do
    REDIS_URL="$REDIS_URL" \
        PYTHONPATH="$PYTHONPATH" \
        VIDEO_WORKER_TYPE=pika \
        RQ_PRELOAD_MODEL=false \
        rq worker \
        --url "$REDIS_URL" \
        transcription_preprocess \
        --name worker-preprocess-$i \
        --pid /tmp/rq-worker-preprocess-$i.pid \
        > /tmp/rq-worker-preprocess-$i.log 2>&1 &
    
    PREPROCESS_PID=$!
    PREPROCESS_PIDS+=($PREPROCESS_PID)
    print_success "RQ Preprocess Worker $i started (PID: $PREPROCESS_PID)"
done

# เริ่ม CPU Workers สำหรับ aggregator jobs (1 worker - ลดเพื่อลด setup complexity)
NUM_CPU_WORKERS=${NUM_CPU_WORKERS:-1}
print_info "Starting RQ CPU Workers (${NUM_CPU_WORKERS} workers for aggregator jobs)..."
CPU_PIDS=()
for i in $(seq 0 $((NUM_CPU_WORKERS - 1))); do
    REDIS_URL="$REDIS_URL" \
        PYTHONPATH="$PYTHONPATH" \
        VIDEO_WORKER_TYPE=pika \
        RQ_PRELOAD_MODEL=false \
        rq worker \
        --url "$REDIS_URL" \
        transcription_cpu \
        --name worker-cpu-$i \
        --pid /tmp/rq-worker-cpu-$i.pid \
        > /tmp/rq-worker-cpu-$i.log 2>&1 &
    
    CPU_PID=$!
    CPU_PIDS+=($CPU_PID)
    print_success "RQ CPU Worker $i started (PID: $CPU_PID)"
done

print_success "✅ RQ Workers started successfully!"
print_info "Workers:"
for i in $(seq 0 $((NUM_GPUS - 1))); do
    print_info "  - GPU $i: transcription_priority + transcription_gpu$i (priority first)"
done
print_info "  - Preprocess: ${NUM_PREPROCESS_WORKERS} workers (transcription_preprocess)"
print_info "  - CPU: ${NUM_CPU_WORKERS} workers (transcription_cpu for aggregator)"
print_info ""
print_info "Logs:"
for i in $(seq 0 $((NUM_GPUS - 1))); do
    print_info "  - GPU $i: tail -f /tmp/rq-worker-gpu$i.log"
done
for i in $(seq 0 $((NUM_PREPROCESS_WORKERS - 1))); do
    print_info "  - Preprocess $i: tail -f /tmp/rq-worker-preprocess-$i.log"
done
for i in $(seq 0 $((NUM_CPU_WORKERS - 1))); do
    print_info "  - CPU $i: tail -f /tmp/rq-worker-cpu-$i.log"
done
print_info ""
print_info "Monitor queues:"
print_info "  rq info --url $REDIS_URL"

