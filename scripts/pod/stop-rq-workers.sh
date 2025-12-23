#!/bin/bash
# Stop RQ Workers

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

print_info "Stopping RQ Workers..."

# หยุด GPU workers
pkill -f "rq worker.*transcription_gpu" 2>/dev/null || true
pkill -f "rq worker.*transcription_priority" 2>/dev/null || true

# หยุด CPU workers
pkill -f "rq worker.*transcription_cpu" 2>/dev/null || true

# หยุด preprocess workers
pkill -f "rq worker.*transcription_preprocess" 2>/dev/null || true

sleep 2

# ตรวจสอบว่า workers หยุดแล้วหรือยัง
if pgrep -f "rq worker.*transcription" > /dev/null; then
    print_warning "Some workers still running, force killing..."
    pkill -9 -f "rq worker.*transcription" 2>/dev/null || true
    sleep 1
fi

print_success "RQ Workers stopped"

