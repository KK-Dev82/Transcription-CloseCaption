#!/bin/bash
# Script สำหรับ Restart Video Worker เท่านั้น (ไม่ restart API Service)
# ใช้สำหรับ restart worker หลังจากแก้ไข configuration หรือเพิ่ม consumers
#
# วิธีใช้งาน:
#   bash scripts/pod/restart-worker-only.sh

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

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔄 Restarting Video Worker Only                             ║"
echo "║  เวลา: $(date '+%Y-%m-%d %H:%M:%S')                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/workspace/transcription-service"
cd "$PROJECT_DIR" 2>/dev/null || cd "/workspace/transcription-close-caption-service" 2>/dev/null || {
    echo "❌ Error: Cannot find project directory"
    exit 1
}

# Load environment variables if env.runpod exists
if [ -f "env.runpod" ]; then
    set -a
    source env.runpod
    set +a
    print_status "✅ Loaded environment from env.runpod"
elif [ -f ".env.runpod" ]; then
    set -a
    source .env.runpod
    set +a
    print_status "✅ Loaded environment from .env.runpod"
fi

# Function to check worker health before killing
check_worker_health_before_kill() {
    local pid=$1
    if [ -z "$pid" ]; then
        return 1
    fi
    
    # Check if process is still running
    if ! ps -p "$pid" > /dev/null 2>&1; then
        return 1
    fi
    
    # Check if worker is consuming messages (via RabbitMQ)
    python3 << 'EOF' 2>/dev/null
import sys
import os
import pika
from dotenv import load_dotenv

# Load environment
env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'env.runpod')
if os.path.exists(env_file):
    load_dotenv(env_file)

try:
    rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
    rabbitmq_port = int(os.getenv('RABBITMQ_PORT', '5672'))
    rabbitmq_user = os.getenv('RABBITMQ_USER', 'guest')
    rabbitmq_password = os.getenv('RABBITMQ_PASSWORD', 'guest')
    
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=rabbitmq_host,
            port=rabbitmq_port,
            credentials=pika.PlainCredentials(rabbitmq_user, rabbitmq_password),
            connection_attempts=2,
            retry_delay=1
        )
    )
    channel = connection.channel()
    
    # Check critical queues
    queues = ['transcription_request_queue', 'audio_extraction_queue']
    all_ok = True
    
    for queue_name in queues:
        try:
            method = channel.queue_declare(queue=queue_name, passive=True)
            consumer_count = method.method.consumer_count
            if consumer_count == 0:
                all_ok = False
                break
        except Exception:
            all_ok = False
            break
    
    connection.close()
    sys.exit(0 if all_ok else 1)
except Exception:
    sys.exit(1)
EOF
    
    return $?
}

# Step 1: Stop Video Worker
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛑 Step 1: Stopping Video Worker..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

WORKER_PID=$(pgrep -f "python.*video_worker" | head -1 || echo "")
if [ -n "$WORKER_PID" ]; then
    print_status "Found Video Worker (PID: $WORKER_PID)"
    
    # Check worker health before killing
    print_status "Checking worker health before stopping..."
    if check_worker_health_before_kill "$WORKER_PID"; then
        print_warning "⚠️  Worker appears healthy (consumers active)"
        print_status "   Proceeding with restart anyway (as requested)..."
    else
        print_status "   Worker appears unhealthy or not consuming messages"
    fi
    
    print_status "Stopping Video Worker (PID: $WORKER_PID)..."
    # Send SIGTERM first (graceful shutdown)
    kill -TERM $WORKER_PID 2>/dev/null || true
    sleep 3
    
    # Check if still running
    if pgrep -f "python.*video_worker" > /dev/null; then
        print_warning "Worker still running, waiting a bit more..."
        sleep 2
        
        # Force kill if still running
        if pgrep -f "python.*video_worker" > /dev/null; then
            print_warning "Force killing Video Worker..."
            pkill -9 -f "python.*video_worker" 2>/dev/null || true
            sleep 1
        fi
    fi
    
    if ! pgrep -f "python.*video_worker" > /dev/null; then
        print_success "✅ Video Worker stopped"
    else
        print_error "❌ Failed to stop Video Worker"
        exit 1
    fi
else
    print_warning "⚠️  Video Worker is not running"
fi
echo ""

# Wait a moment for process to fully stop
sleep 2

# Step 2: Start Video Worker
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Step 2: Starting Video Worker..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check FFmpeg installation (required for video-worker)
FFMPEG_INSTALL_DIR="/workspace/.local/bin"
mkdir -p "$FFMPEG_INSTALL_DIR"
export PATH="${FFMPEG_INSTALL_DIR}:$PATH"

if ! command -v ffmpeg > /dev/null 2>&1 && [ ! -f "$FFMPEG_INSTALL_DIR/ffmpeg" ]; then
    print_warning "⚠️  FFmpeg not found - video worker may not work properly"
    print_status "   💡 Run: bash scripts/pod/restart-service-daemon.sh to install FFmpeg"
fi

# Setup LD_LIBRARY_PATH for CTranslate2 and cuDNN (same as start-service-daemon.sh)
PYTHON_SITE=$(python3 -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || echo "/usr/local/lib/python3.10/dist-packages")
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.10")
WORKSPACE_LOCAL="/workspace/.local/lib/python${PYTHON_VERSION}/site-packages"

CTRANSLATE2_LIBS="${PYTHON_SITE}/ctranslate2.libs"
TORCH_LIB_DIR="${PYTHON_SITE}/torch/lib"
WORKSPACE_TORCH_LIB_DIR="${WORKSPACE_LOCAL}/torch/lib"
CUDNN_LIB_DIR="${PYTHON_SITE}/nvidia/cudnn/lib"
WORKSPACE_CUDNN_LIB_DIR="${WORKSPACE_LOCAL}/nvidia/cudnn/lib"
CUDA_LIB_DIRS="/usr/local/cuda/lib64:/usr/local/cuda-11.8/lib64"
LD_LIBRARY_PATH_VAL="${LD_LIBRARY_PATH:-}"

# Add PyTorch torch/lib (contains cuDNN v8 libraries)
if [ -d "$WORKSPACE_TORCH_LIB_DIR" ]; then
    LD_LIBRARY_PATH_VAL="${WORKSPACE_TORCH_LIB_DIR}:${LD_LIBRARY_PATH_VAL}"
fi
if [ -d "$TORCH_LIB_DIR" ]; then
    LD_LIBRARY_PATH_VAL="${TORCH_LIB_DIR}:${LD_LIBRARY_PATH_VAL}"
fi

# Add nvidia/cudnn/lib (contains cuDNN v9 libraries)
if [ -d "$WORKSPACE_CUDNN_LIB_DIR" ]; then
    LD_LIBRARY_PATH_VAL="${WORKSPACE_CUDNN_LIB_DIR}:${LD_LIBRARY_PATH_VAL}"
fi
if [ -d "$CUDNN_LIB_DIR" ]; then
    LD_LIBRARY_PATH_VAL="${CUDNN_LIB_DIR}:${LD_LIBRARY_PATH_VAL}"
fi

# Add CUDA libraries
for CUDA_DIR in $(echo "$CUDA_LIB_DIRS" | tr ':' ' '); do
    if [ -d "$CUDA_DIR" ]; then
        LD_LIBRARY_PATH_VAL="${CUDA_DIR}:${LD_LIBRARY_PATH_VAL}"
    fi
done

# Add CTranslate2 libraries (if exists)
if [ -d "$CTRANSLATE2_LIBS" ]; then
    LD_LIBRARY_PATH_VAL="${CTRANSLATE2_LIBS}:${LD_LIBRARY_PATH_VAL}"
fi

# Determine worker type
WORKER_TYPE="${VIDEO_WORKER_TYPE:-async}"
print_status "Worker Type: $WORKER_TYPE"

# Setup worker log files
WORKER_LOG_DIR="logs"
mkdir -p "$WORKER_LOG_DIR"
WORKER_LOG="$WORKER_LOG_DIR/video-worker.log"
WORKER_ERROR_LOG="$WORKER_LOG_DIR/video-worker-errors.log"
WORKER_PID_FILE="/tmp/video-worker.pid"

# Setup PYTHONPATH
PYTHON_SITE_PACKAGES=$(python3 -c "import site; print(':'.join(site.getsitepackages()))" 2>/dev/null || echo "")

# Start worker in background with proper environment
WORKER_PATH="/workspace/.local/bin:$PATH"
if [ -n "$FFMPEG_INSTALL_DIR" ] && [ -d "$FFMPEG_INSTALL_DIR" ]; then
    WORKER_PATH="${FFMPEG_INSTALL_DIR}:${WORKER_PATH}"
fi

print_status "Starting worker with environment variables from env.runpod..."
nohup env TZ="${TZ:-Asia/Bangkok}" \
         TZDIR="${TZDIR:-/usr/share/zoneinfo}" \
         PYTHONUSERBASE="/workspace/.local" \
         PATH="${WORKER_PATH}" \
         PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
         LD_LIBRARY_PATH="${LD_LIBRARY_PATH_VAL}" \
         python3 -m app.workers.video_worker \
    > "$WORKER_LOG" 2> "$WORKER_ERROR_LOG" &

WORKER_PID=$!
echo $WORKER_PID > "$WORKER_PID_FILE"

# Wait a moment for worker to start
sleep 3

# Check if worker started successfully
if ps -p $WORKER_PID > /dev/null 2>&1; then
    print_success "✅ Video Worker started (PID: $WORKER_PID)"
else
    print_error "❌ Video Worker failed to start"
    print_status "   Check logs: tail -50 /tmp/video-worker.log"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏳ Waiting for Worker to Connect..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Wait for worker to connect to RabbitMQ
MAX_WAIT=30  # Maximum wait time in seconds
WAIT_INTERVAL=2  # Check every 2 seconds
ELAPSED=0
WORKER_READY=false

print_status "Waiting for worker to connect to RabbitMQ..."
while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check if process is still running
    if ! ps -p $WORKER_PID > /dev/null 2>&1; then
        print_error "❌ Worker process died!"
        print_status "   Check logs: tail -50 /tmp/video-worker.log"
        exit 1
    fi
    
    # Check logs for connection success
    if grep -q "✅ Video Worker พร้อมรับงาน\|✅ Consumer registered for transcription_request_queue\|✅ ตั้งค่า.*consumers เสร็จสิ้น" "$WORKER_LOG" 2>/dev/null; then
        WORKER_READY=true
        print_success "✅ Worker connected and ready!"
        break
    fi
    
    print_status "   Waiting for worker to connect... (${ELAPSED}s/${MAX_WAIT}s)"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ "$WORKER_READY" = false ]; then
    print_warning "⚠️  Worker may not be fully ready (checking anyway)..."
    print_status "   Check logs: tail -50 $WORKER_LOG"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Worker Restart Complete                                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Final status check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Final Status Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if pgrep -f "python.*video_worker" > /dev/null; then
    WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
    print_success "✅ Video Worker: RUNNING (PID: $WORKER_PID)"
    
    # Check recent logs for consumer registration
    if tail -20 "$WORKER_LOG" 2>/dev/null | grep -q "transcription_request_queue"; then
        print_success "✅ Consumer registered for transcription_request_queue"
    else
        print_warning "⚠️  Consumer registration not confirmed (check logs)"
    fi
else
    print_error "❌ Video Worker: NOT RUNNING"
fi

echo ""
print_status "💡 Useful Commands:"
echo "   View Worker logs: tail -f $WORKER_LOG"
echo "   View Worker error logs: tail -f $WORKER_ERROR_LOG"
echo "   Check worker status: ps aux | grep video_worker"
echo "   Check worker PID: cat $WORKER_PID_FILE"
echo "   Check RabbitMQ consumers: (via RabbitMQ Management UI)"
echo ""

