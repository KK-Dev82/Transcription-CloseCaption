#!/bin/bash
# Script สำหรับ Restart Video Worker เฉพาะ
# หยุด Video Worker แล้ว start ใหม่ (ไม่กระทบ services อื่น)

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

echo "🔄 Restarting Video Worker"
echo "📅 $(date)"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Load environment variables
if [ -f ".env.runpod" ]; then
    print_status "Loading environment variables from .env.runpod..."
    set -a
    source .env.runpod
    set +a
    print_success "✅ Environment variables loaded"
else
    print_warning "⚠️  .env.runpod not found, using system environment variables"
fi

# 1. หยุด Video Worker
print_status "Stopping Video Worker..."
if pgrep -f "python.*video_worker" > /dev/null; then
    pkill -f "python.*video_worker" 2>/dev/null || true
    sleep 2
    
    # Force kill ถ้ายังไม่หยุด
    if pgrep -f "python.*video_worker" > /dev/null; then
        print_warning "⚠️  Video Worker still running, force killing..."
        pkill -9 -f "python.*video_worker" 2>/dev/null || true
        sleep 1
    fi
    
    print_success "✅ Video Worker stopped"
else
    print_warning "⚠️  Video Worker not running"
fi

echo ""

# 2. Start Video Worker ใหม่
print_status "Starting Video Worker..."
if pgrep -f "python.*video_worker" > /dev/null; then
    print_warning "⚠️  Video Worker already running"
else
    export PYTHONPATH="$PROJECT_ROOT"
    export RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
    export RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
    export RABBITMQ_USER=${RABBITMQ_USER:-senate}
    export RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}
    export WHISPER_PROVIDER=${WHISPER_PROVIDER:-faster-whisper}
    export WHISPER_MODEL=${WHISPER_MODEL:-medium}
    export WHISPER_DEVICE=${WHISPER_DEVICE:-cuda}
    
    # Set LD_LIBRARY_PATH for CTranslate2 libraries และ cuDNN
    CTRANSLATE2_LIBS="/usr/local/lib/python3.10/dist-packages/ctranslate2.libs"
    CUDNN_LIB_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
    CUDNN_DIR="/workspace/cudnn/lib"
    
    # เพิ่ม CTranslate2 libraries
    if [ -d "$CTRANSLATE2_LIBS" ]; then
        export LD_LIBRARY_PATH="${CTRANSLATE2_LIBS}:${LD_LIBRARY_PATH:-}"
        print_status "✅ Set LD_LIBRARY_PATH for CTranslate2 libraries: $CTRANSLATE2_LIBS"
    fi
    
    # เพิ่ม cuDNN libraries จาก PyTorch (ถ้า CUDNN_DIR ไม่มี)
    if [ ! -d "$CUDNN_DIR" ] && [ -d "$CUDNN_LIB_PATH" ]; then
        if [ -z "${LD_LIBRARY_PATH:-}" ]; then
            export LD_LIBRARY_PATH="${CUDNN_LIB_PATH}"
        else
            export LD_LIBRARY_PATH="${CUDNN_LIB_PATH}:${LD_LIBRARY_PATH}"
        fi
        print_status "✅ Added cuDNN libraries from PyTorch to LD_LIBRARY_PATH: $CUDNN_LIB_PATH"
    elif [ -d "$CUDNN_DIR" ]; then
        if [ -z "${LD_LIBRARY_PATH:-}" ]; then
            export LD_LIBRARY_PATH="${CUDNN_DIR}"
        else
            export LD_LIBRARY_PATH="${CUDNN_DIR}:${LD_LIBRARY_PATH}"
        fi
        print_status "✅ Added cuDNN libraries to LD_LIBRARY_PATH: $CUDNN_DIR"
    fi
    
    nohup env RABBITMQ_HOST="${RABBITMQ_HOST}" \
             RABBITMQ_PORT="${RABBITMQ_PORT}" \
             RABBITMQ_USER="${RABBITMQ_USER}" \
             RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD}" \
             WHISPER_PROVIDER="${WHISPER_PROVIDER}" \
             WHISPER_MODEL="${WHISPER_MODEL}" \
             WHISPER_DEVICE="${WHISPER_DEVICE}" \
             LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}" \
             python3 -m app.workers.video_worker > /tmp/video-worker.log 2>&1 & disown
    sleep 3
    
    # Check if process is still running (not crashed)
    if pgrep -f "python.*video_worker" > /dev/null; then
        print_success "✅ Video Worker started successfully"
    else
        print_error "❌ Video Worker failed to start - check logs"
        print_status "💡 Check logs: tail -20 /tmp/video-worker.log"
        exit 1
    fi
fi

echo ""
print_success "🎉 Video Worker restart completed!"
echo ""
print_status "💡 View logs: tail -f /tmp/video-worker.log"
print_status "💡 Check status: ps aux | grep video_worker"
echo ""
