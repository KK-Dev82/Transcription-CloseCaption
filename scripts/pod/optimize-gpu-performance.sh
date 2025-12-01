#!/bin/bash
# Script สำหรับปรับปรุงประสิทธิภาพ GPU Utilization
# เป้าหมาย: วิดีโอ 10 นาที ใช้เวลาไม่เกิน 1-2 นาที

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SSH_HOST="${RUNPOD_HOST:-calm-pink-turtle}"
PROJECT_DIR="/workspace/transcription-service"

print_status "🚀 Optimizing GPU Performance"
print_status "Target: 10-minute video → 1-2 minutes transcription"
echo ""

# ตรวจสอบ GPU
print_status "Checking GPU..."
ssh "$SSH_HOST" "nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader"
echo ""

# ตรวจสอบ configuration ปัจจุบัน
print_status "Current configuration:"
ssh "$SSH_HOST" "cd $PROJECT_DIR && cat .env.runpod | grep -E 'TRANSCRIPTION_MAX_WORKERS|WHISPER_USE_THREAD_LOCAL|WHISPER_MODEL|TRANSCRIPTION_PREFETCH_COUNT'"
echo ""

# คำแนะนำการปรับปรุง
print_status "📊 GPU Optimization Recommendations:"
echo ""
echo "สำหรับ RTX 4080 Super (16GB):"
echo ""
echo "1. **Parallel Processing (medium model)**:"
echo "   TRANSCRIPTION_MAX_WORKERS=3-4  # medium ~2.4GB × 3-4 = 7.2-9.6GB"
echo "   WHISPER_USE_THREAD_LOCAL=true"
echo "   TRANSCRIPTION_PREFETCH_COUNT=15-20"
echo ""
echo "2. **Parallel Processing (large-v3 model)**:"
echo "   TRANSCRIPTION_MAX_WORKERS=2-3  # large-v3 ~3GB × 2-3 = 6-9GB"
echo "   WHISPER_USE_THREAD_LOCAL=true"
echo "   TRANSCRIPTION_PREFETCH_COUNT=10-15"
echo ""
echo "3. **Maximum Performance (base model)**:"
echo "   TRANSCRIPTION_MAX_WORKERS=8-10  # base ~300MB × 8-10 = 2.4-3GB"
echo "   WHISPER_USE_THREAD_LOCAL=true"
echo "   TRANSCRIPTION_PREFETCH_COUNT=30-40"
echo ""

# ถามผู้ใช้
read -p "Apply optimization? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Skipping optimization"
    exit 0
fi

# ตรวจสอบ model ที่ใช้
MODEL=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && grep WHISPER_MODEL .env.runpod | cut -d'=' -f2 | head -1")
print_status "Current model: ${MODEL:-base}"

# แนะนำ configuration ตาม model
case "$MODEL" in
    "medium")
        MAX_WORKERS=4
        PREFETCH_COUNT=20
        ;;
    "large-v3"|"large")
        MAX_WORKERS=3
        PREFETCH_COUNT=15
        ;;
    "base"|"small")
        MAX_WORKERS=8
        PREFETCH_COUNT=30
        ;;
    *)
        MAX_WORKERS=4
        PREFETCH_COUNT=20
        ;;
esac

print_status "Recommended configuration for $MODEL model:"
echo "   TRANSCRIPTION_MAX_WORKERS=$MAX_WORKERS"
echo "   TRANSCRIPTION_PREFETCH_COUNT=$PREFETCH_COUNT"
echo "   WHISPER_USE_THREAD_LOCAL=true"
echo ""

read -p "Apply this configuration? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Updating configuration..."
    ssh "$SSH_HOST" "cd $PROJECT_DIR && \
        sed -i 's/TRANSCRIPTION_MAX_WORKERS=.*/TRANSCRIPTION_MAX_WORKERS=$MAX_WORKERS/' .env.runpod && \
        sed -i 's/TRANSCRIPTION_PREFETCH_COUNT=.*/TRANSCRIPTION_PREFETCH_COUNT=$PREFETCH_COUNT/' .env.runpod && \
        sed -i 's/WHISPER_USE_THREAD_LOCAL=.*/WHISPER_USE_THREAD_LOCAL=true/' .env.runpod && \
        echo 'Updated configuration:' && \
        cat .env.runpod | grep -E 'TRANSCRIPTION_MAX_WORKERS|TRANSCRIPTION_PREFETCH_COUNT|WHISPER_USE_THREAD_LOCAL'"
    
    print_success "Configuration updated!"
    echo ""
    
    print_status "Restarting worker..."
    ssh "$SSH_HOST" "cd $PROJECT_DIR && pkill -f 'python.*video_worker' 2>/dev/null || true && sleep 2 && bash scripts/pod/start-pod.sh worker 2>&1 | tail -5"
    
    sleep 5
    
    print_status "Checking worker status..."
    ssh "$SSH_HOST" "cd $PROJECT_DIR && tail -20 /tmp/video-worker.log 2>/dev/null | grep -E 'ThreadPoolExecutor|max_workers|Initialized' | tail -3"
    
    print_success "✅ Optimization completed!"
else
    print_info "Skipping configuration update"
fi

