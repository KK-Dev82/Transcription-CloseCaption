#!/bin/bash
# Script สำหรับตรวจสอบ Concurrency Settings
#
# วิธีใช้งาน:
#   bash scripts/pod/check-concurrency-settings.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
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

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

cd /workspace/transcription-service || exit 1

# Load environment variables
if [ -f "env.runpod" ]; then
    set -a
    source env.runpod
    set +a
fi

print_header "🔍 Concurrency Settings Check"

echo ""
print_header "1. Environment Variables"

GPU_CONCURRENCY=${GPU_CONCURRENCY:-1}
AUDIO_EXTRACTION_MAX_WORKERS=${AUDIO_EXTRACTION_MAX_WORKERS:-3}
FFMPEG_PROC_SEM=${FFMPEG_PROC_SEM:-3}
AUDIO_EXTRACTION_PREFETCH_COUNT=${AUDIO_EXTRACTION_PREFETCH_COUNT:-1}
TRANSCRIPTION_REQUEST_PREFETCH_COUNT=${TRANSCRIPTION_REQUEST_PREFETCH_COUNT:-1}
TRANSCRIPTION_PREFETCH_COUNT=${TRANSCRIPTION_PREFETCH_COUNT:-1}

print_info "GPU_CONCURRENCY: $GPU_CONCURRENCY"
if [ "$GPU_CONCURRENCY" -gt 5 ]; then
    print_warning "   ⚠️  GPU_CONCURRENCY สูงเกินไป (แนะนำ: 1-3)"
else
    print_success "   ✅ GPU_CONCURRENCY อยู่ในระดับที่เหมาะสม"
fi

print_info "AUDIO_EXTRACTION_MAX_WORKERS: $AUDIO_EXTRACTION_MAX_WORKERS"
if [ "$AUDIO_EXTRACTION_MAX_WORKERS" -gt 5 ]; then
    print_warning "   ⚠️  AUDIO_EXTRACTION_MAX_WORKERS สูงเกินไป (แนะนำ: 3-5)"
else
    print_success "   ✅ AUDIO_EXTRACTION_MAX_WORKERS อยู่ในระดับที่เหมาะสม"
fi

print_info "FFMPEG_PROC_SEM: $FFMPEG_PROC_SEM"
if [ "$FFMPEG_PROC_SEM" -gt 5 ]; then
    print_warning "   ⚠️  FFMPEG_PROC_SEM สูงเกินไป (แนะนำ: 3-5)"
else
    print_success "   ✅ FFMPEG_PROC_SEM อยู่ในระดับที่เหมาะสม"
fi

print_info "AUDIO_EXTRACTION_PREFETCH_COUNT: $AUDIO_EXTRACTION_PREFETCH_COUNT"
if [ "$AUDIO_EXTRACTION_PREFETCH_COUNT" -gt 3 ]; then
    print_warning "   ⚠️  AUDIO_EXTRACTION_PREFETCH_COUNT สูงเกินไป (แนะนำ: 1-3)"
else
    print_success "   ✅ AUDIO_EXTRACTION_PREFETCH_COUNT อยู่ในระดับที่เหมาะสม"
fi

print_info "TRANSCRIPTION_REQUEST_PREFETCH_COUNT: $TRANSCRIPTION_REQUEST_PREFETCH_COUNT"
print_info "TRANSCRIPTION_PREFETCH_COUNT: $TRANSCRIPTION_PREFETCH_COUNT"

echo ""
print_header "2. Running Process Status"

WORKER_PID=$(pgrep -f "python.*-m.*app\.workers" | head -1 || echo "")
if [ -n "$WORKER_PID" ]; then
    print_success "Worker running (PID: $WORKER_PID)"
    
    # Check memory usage
    MEM_USAGE=$(ps -p "$WORKER_PID" -o rss= 2>/dev/null | awk '{printf "%.1f", $1/1024/1024}' || echo "N/A")
    print_info "   Memory usage: ${MEM_USAGE} MB"
    
    if [ "$MEM_USAGE" != "N/A" ] && (( $(echo "$MEM_USAGE > 2000" | bc -l) )); then
        print_warning "   ⚠️  Memory usage สูง (${MEM_USAGE} MB) - อาจต้องลด concurrency"
    fi
else
    print_error "Worker NOT running"
fi

echo ""
print_header "3. Recommendations"

echo ""
print_info "💡 Recommendations:"
echo ""
print_info "   - GPU_CONCURRENCY: 1-3 (สำหรับ GPU transcription)"
print_info "   - AUDIO_EXTRACTION_MAX_WORKERS: 3-5 (CPU-bound, ไม่ใช้ GPU)"
print_info "   - FFMPEG_PROC_SEM: 3-5 (CPU-bound, ไม่ใช้ GPU)"
print_info "   - AUDIO_EXTRACTION_PREFETCH_COUNT: 1-3 (process one at a time)"
echo ""
print_info "   ⚠️  การตั้งค่า concurrency สูงเกินไปอาจทำให้:"
print_info "      - Memory exhaustion"
print_info "      - CPU overload"
print_info "      - Service crash/restart"
print_info "      - Resource contention"
echo ""

