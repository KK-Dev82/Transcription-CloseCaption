#!/bin/bash
# Script สำหรับ Start Transcription Service แบบ Daemon (ทำงานต่อได้แม้ออกจาก Terminal)
#
# วิธีใช้งาน:
#   ssh pytorch-pod "bash -s" < scripts/pod/start-service-daemon.sh
#   หรือ
#   bash scripts/pod/start-service-daemon.sh [INTERNAL_PORT]
#
# Parameters:
#   INTERNAL_PORT  - Internal port (optional, default: 8010)

set -e

# Parse optional internal port parameter
INTERNAL_PORT="${1:-8010}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/workspace/transcription-service"

echo "🚀 Starting Transcription Service (Daemon Mode)"
echo "================================================"
echo ""

# Check if running on Pod
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Error: Project directory not found: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

# Check if service is already running
if pgrep -f "uvicorn.*app.main:app.*${INTERNAL_PORT}" > /dev/null; then
    echo "⚠️  Transcription Service is already running"
    PID=$(pgrep -f "uvicorn.*app.main:app.*${INTERNAL_PORT}" | head -1)
    echo "   PID: $PID"
    echo ""
    read -p "Do you want to stop and restart? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping existing service..."
        kill $PID 2>/dev/null || true
        sleep 2
    else
        echo "Keeping existing service running"
        exit 0
    fi
fi

# Setup GPU environment
if [ -f "scripts/pod/setup-gpu-env.sh" ]; then
    echo "📋 Setting up GPU environment..."
    source scripts/pod/setup-gpu-env.sh
    echo "✅ GPU environment ready"
    echo ""
fi

# Prepare directories
echo "📁 Preparing directories..."
mkdir -p uploads storage temp models test-files
echo "✅ Directories ready"
echo ""

# Start Redis (if not running)
if ! pgrep -x "redis-server" > /dev/null; then
    echo "📦 Starting Redis..."
    redis-server --daemonize yes --port 6379 --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru || {
        echo "⚠️  Redis may already be running"
    }
    sleep 2
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis started"
    else
        echo "⚠️  Redis not responding (may continue anyway)"
    fi
    echo ""
fi

# Install/check timezone data (required for pythainlp)
echo "📋 Checking timezone data..."
if [ ! -d "/usr/share/zoneinfo" ] || [ ! -f "/usr/share/zoneinfo/Asia/Bangkok" ]; then
    echo "📦 Installing tzdata..."
    apt-get update -qq && apt-get install -y -qq tzdata > /dev/null 2>&1 || {
        echo "⚠️  Failed to install tzdata (may continue anyway)"
    }
fi
if [ -d "/usr/share/zoneinfo" ]; then
    export TZDIR=/usr/share/zoneinfo
    echo "✅ Timezone data available"
else
    echo "⚠️  Timezone data not found"
fi
export TZ=Asia/Bangkok
echo "   TZ=$TZ"
echo ""

# Load environment variables
if [ -f ".env.runpod" ]; then
    echo "📋 Loading .env.runpod..."
    set -a
    source .env.runpod
    set +a
    echo "✅ Environment loaded"
    echo ""
fi

# Setup Python user base for persistent storage (สำคัญ! ต้องทำก่อน check dependencies)
# Detect Python version dynamically
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.10")
PYTHON_SITE_PACKAGES="/workspace/.local/lib/python${PYTHON_VERSION}/site-packages"

export PYTHONUSERBASE="/workspace/.local"
export PATH="/workspace/.local/bin:$PATH"
export PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH"

# Create persistent directory if not exists
mkdir -p "$PYTHON_SITE_PACKAGES"
mkdir -p "/workspace/.local/bin"

# Check if dependencies are installed (ใช้ PYTHONPATH ที่ถูกต้อง)
echo "🔍 Checking dependencies..."
echo "   Python version: ${PYTHON_VERSION}"
echo "   Installation path: ${PYTHON_SITE_PACKAGES}"
if ! env PYTHONUSERBASE="/workspace/.local" \
        PATH="/workspace/.local/bin:$PATH" \
        PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
        python3 -c "import uvicorn" 2>/dev/null; then
    echo "❌ Error: uvicorn is not installed"
    echo ""
    echo "💡 Installing dependencies..."
    echo "   Run: bash scripts/pod/install-dependencies.sh"
    echo ""
    read -p "Do you want to install dependencies now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        bash scripts/pod/install-dependencies.sh || {
            echo "❌ Failed to install dependencies"
            exit 1
        }
    else
        echo "❌ Cannot start service without dependencies"
        exit 1
    fi
else
    echo "✅ Dependencies OK"
    echo ""
fi

# Log file location
LOG_FILE="/tmp/transcription-service.log"
PID_FILE="/tmp/transcription-service.pid"

# Start service with nohup (ทำงานต่อได้แม้ออกจาก terminal)
echo "🚀 Starting Transcription Service (with nohup)..."
echo "   Host: 0.0.0.0"
echo "   Port: ${INTERNAL_PORT}"
echo "   Log: $LOG_FILE"
echo "   PID: $PID_FILE"
echo ""
echo "   ⚠️  Service will continue running after you exit terminal"
echo ""

# Start with nohup - redirect all output to log file
# Set timezone environment variables for pythainlp
# PYTHONUSERBASE และ PATH ได้ถูก set แล้วข้างบน
nohup env TZ="${TZ:-Asia/Bangkok}" \
         TZDIR="${TZDIR:-/usr/share/zoneinfo}" \
         PYTHONUSERBASE="/workspace/.local" \
         PATH="/workspace/.local/bin:$PATH" \
         PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
         python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${INTERNAL_PORT} \
    --workers 1 \
    > "$LOG_FILE" 2>&1 &

SERVICE_PID=$!
echo $SERVICE_PID > "$PID_FILE"

# Wait a moment for service to start
sleep 3

# Check if service started successfully
if ps -p $SERVICE_PID > /dev/null; then
    echo "✅ Transcription Service started successfully"
    echo "   PID: $SERVICE_PID"
    echo "   PID File: $PID_FILE"
    echo ""
    
    # Wait a bit and test
    sleep 2
    if curl -s -f http://localhost:${INTERNAL_PORT}/health > /dev/null 2>&1; then
        echo "✅ Service is responding"
        echo ""
        echo "📊 Service Information:"
        echo "   URL: http://0.0.0.0:${INTERNAL_PORT}"
        echo "   Health: http://localhost:${INTERNAL_PORT}/health"
        echo "   Docs: http://localhost:${INTERNAL_PORT}/docs"
        echo "   Log: tail -f $LOG_FILE"
        echo "   PID: cat $PID_FILE"
        echo ""
        EXTERNAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "80.15.7.37")
        echo "🌐 External Access:"
        echo "   IP: ${EXTERNAL_IP}"
        echo "   💡 Use RunPod port mapping to access externally"
        echo ""
        echo "💡 Useful Commands:"
        echo "   Stop: kill \$(cat $PID_FILE)"
        echo "   Logs: tail -f $LOG_FILE"
        echo "   Status: ps aux | grep uvicorn"
    else
        echo "⚠️  Service started but not responding yet (check log: $LOG_FILE)"
        echo "   Wait a few seconds and check: curl http://localhost:${INTERNAL_PORT}/health"
    fi
else
    echo "❌ Failed to start service"
    echo "   Check log: $LOG_FILE"
    tail -20 "$LOG_FILE"
    exit 1
fi

# Start Video Worker
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎬 Starting Video Worker..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

WORKER_LOG="/tmp/video-worker.log"
WORKER_PID_FILE="/tmp/video-worker.pid"

# Check if worker is already running
if pgrep -f "python.*video_worker" > /dev/null; then
    WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
    echo "⚠️  Video Worker is already running (PID: $WORKER_PID)"
    echo "   Keeping existing worker running"
else
    echo "🚀 Starting Video Worker..."
    
    # Setup LD_LIBRARY_PATH for CTranslate2 and cuDNN
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
    
    # Priority 1: Add PyTorch torch/lib (contains cuDNN v8 libraries - most important!)
    if [ -d "$WORKSPACE_TORCH_LIB_DIR" ]; then
        LD_LIBRARY_PATH_VAL="${WORKSPACE_TORCH_LIB_DIR}:${LD_LIBRARY_PATH_VAL}"
        echo "   ✅ Added PyTorch cuDNN libraries (persistent) to LD_LIBRARY_PATH: $WORKSPACE_TORCH_LIB_DIR"
    fi
    if [ -d "$TORCH_LIB_DIR" ]; then
        LD_LIBRARY_PATH_VAL="${TORCH_LIB_DIR}:${LD_LIBRARY_PATH_VAL}"
        echo "   ✅ Added PyTorch cuDNN libraries (system) to LD_LIBRARY_PATH: $TORCH_LIB_DIR"
    fi
    
    # Priority 2: Add nvidia/cudnn/lib (contains cuDNN v9 libraries)
    if [ -d "$WORKSPACE_CUDNN_LIB_DIR" ]; then
        LD_LIBRARY_PATH_VAL="${WORKSPACE_CUDNN_LIB_DIR}:${LD_LIBRARY_PATH_VAL}"
        echo "   ✅ Added nvidia cuDNN libraries (persistent) to LD_LIBRARY_PATH: $WORKSPACE_CUDNN_LIB_DIR"
    fi
    if [ -d "$CUDNN_LIB_DIR" ]; then
        LD_LIBRARY_PATH_VAL="${CUDNN_LIB_DIR}:${LD_LIBRARY_PATH_VAL}"
        echo "   ✅ Added nvidia cuDNN libraries (system) to LD_LIBRARY_PATH: $CUDNN_LIB_DIR"
    fi
    
    # Add CUDA libraries
    for CUDA_DIR in $(echo "$CUDA_LIB_DIRS" | tr ':' ' '); do
        if [ -d "$CUDA_DIR" ]; then
            LD_LIBRARY_PATH_VAL="${CUDA_DIR}:${LD_LIBRARY_PATH_VAL}"
            echo "   ✅ Added CUDA libraries to LD_LIBRARY_PATH: $CUDA_DIR"
        fi
    done
    
    # Add CTranslate2 libraries (if exists)
    if [ -d "$CTRANSLATE2_LIBS" ]; then
        LD_LIBRARY_PATH_VAL="${CTRANSLATE2_LIBS}:${LD_LIBRARY_PATH_VAL}"
        echo "   ✅ Added CTranslate2 libraries to LD_LIBRARY_PATH"
    fi
    
    echo "   📁 Final LD_LIBRARY_PATH: $LD_LIBRARY_PATH_VAL"
    
    # Start worker with nohup
    nohup env TZ="${TZ:-Asia/Bangkok}" \
             TZDIR="${TZDIR:-/usr/share/zoneinfo}" \
             PYTHONUSERBASE="/workspace/.local" \
             PATH="/workspace/.local/bin:$PATH" \
             PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
             RABBITMQ_HOST="${RABBITMQ_HOST:-178.128.105.100}" \
             RABBITMQ_PORT="${RABBITMQ_PORT:-5672}" \
             RABBITMQ_USER="${RABBITMQ_USER:-senate}" \
             RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}" \
             WHISPER_PROVIDER="${WHISPER_PROVIDER:-faster-whisper}" \
             WHISPER_MODEL="${WHISPER_MODEL:-medium}" \
             WHISPER_DEVICE="${WHISPER_DEVICE:-cuda}" \
             GPU_CONCURRENCY="${GPU_CONCURRENCY:-10}" \
             LD_LIBRARY_PATH="${LD_LIBRARY_PATH_VAL}" \
             python3 -m app.workers.video_worker \
        > "$WORKER_LOG" 2>&1 &
    
    WORKER_PID=$!
    echo $WORKER_PID > "$WORKER_PID_FILE"
    
    # Wait a moment for worker to start
    sleep 3
    
    # Check if worker started successfully
    if ps -p $WORKER_PID > /dev/null; then
        echo "✅ Video Worker started successfully"
        echo "   PID: $WORKER_PID"
        echo "   PID File: $WORKER_PID_FILE"
        echo "   Log: $WORKER_LOG"
        echo ""
        
        # Wait a bit and check connection
        sleep 2
        if grep -q "Connected to RabbitMQ\|Starting consumer" "$WORKER_LOG" 2>/dev/null; then
            echo "✅ Worker connected to RabbitMQ"
        else
            echo "⚠️  Worker started but connection status unknown (check log: $WORKER_LOG)"
        fi
    else
        echo "❌ Failed to start Video Worker"
        echo "   Check log: $WORKER_LOG"
        tail -20 "$WORKER_LOG" 2>/dev/null || echo "   (Log file not found)"
    fi
fi
echo ""

echo "=============================="
echo "✅ Setup Complete"
echo ""
echo "📊 Running Services:"
echo "   • Transcription Service (API): PID $(cat $PID_FILE 2>/dev/null || echo 'N/A')"
echo "   • Video Worker: PID $(cat $WORKER_PID_FILE 2>/dev/null || echo 'N/A')"
echo ""
echo "⚠️  Services are running in background (nohup)"
echo "   You can safely exit this terminal"
echo ""
echo "💡 Useful Commands:"
echo "   Stop API: kill \$(cat $PID_FILE)"
echo "   Stop Worker: kill \$(cat $WORKER_PID_FILE)"
echo "   View API Logs: tail -f $LOG_FILE"
echo "   View Worker Logs: tail -f $WORKER_LOG"
echo ""

