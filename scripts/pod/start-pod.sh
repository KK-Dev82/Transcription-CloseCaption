#!/bin/bash
# Script สำหรับ Start Services ทั้งหมด (Redis, Whisper API, Video Worker, Main API)
# สร้าง folders ที่จำเป็นอัตโนมัติ
#
# วิธีใช้งาน:
#   bash scripts/pod/start-pod.sh

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

echo "🚀 Starting Transcription Services"
echo "📅 $(date)"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# แก้ไข cuDNN version mismatch สำหรับ faster-whisper
# ใช้ cuDNN 9.1.0 จาก CTranslate2 package แทน cuDNN 8.7.0 จาก PyTorch
CUDNN_LIB="/usr/local/lib/python3.10/dist-packages/ctranslate2.libs/libcudnn-74a4c495.so.9.1.0"
if [ -f "$CUDNN_LIB" ]; then
    export LD_PRELOAD="$CUDNN_LIB"
    print_success "✅ Using cuDNN 9.1.0 from CTranslate2 package (LD_PRELOAD)"
else
    print_warning "⚠️  cuDNN library not found, faster-whisper may have issues"
fi
echo ""

# Check GPU
print_status "Checking GPU..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
    GPU_COUNT=$(nvidia-smi --list-gpus | wc -l)
    print_success "✅ Found $GPU_COUNT GPU(s)"
else
    print_warning "⚠️  nvidia-smi not found. GPU may not be available."
fi
echo ""

# Create necessary directories
print_status "Creating directories..."
mkdir -p uploads storage/transcriptions storage/metadata storage/captions temp models test-files
print_success "✅ Directories created"
echo ""

# Load environment variables
if [ -f ".env.runpod" ]; then
    print_status "Loading .env.runpod..."
    set -a
    source .env.runpod
    set +a
    print_success "✅ Environment variables loaded"
else
    print_warning "⚠️  .env.runpod not found, creating default..."
    cat > .env.runpod << EOF
ENVIRONMENT=runpod
STORAGE_TYPE=json
JSON_STORAGE_DIR=$PROJECT_ROOT/storage
# RabbitMQ - สำหรับ Local Testing ใช้ host.docker.internal (ถ้าไม่มี .env.runpod)
# สำหรับ Production ใช้ 178.128.105.100 (จาก .env.runpod)
RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
RABBITMQ_USER=${RABBITMQ_USER:-senate}
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT
REDIS_URL=redis://default:Guls3SwcxCfzYNoigtrlNq7bKZWklCCf@redis-12598.c252.ap-southeast-1-1.ec2.cloud.redislabs.com:12598
WHISPER_PROVIDER=${WHISPER_PROVIDER:-openai-whisper}
WHISPER_API_URL=http://localhost:8002
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1
EOF
    set -a
    source .env.runpod
    set +a
    print_success "✅ Created .env.runpod"
fi
echo ""

# Note: tzdata removed - using UTC timezone (datetime.now(timezone.utc))
# Frontend/Dashboard handles timezone conversion to UTC+7

# Install Python dependencies if needed
print_status "Checking Python dependencies..."
MISSING_DEPS=()

# Check critical dependencies
for dep in aiofiles fastapi uvicorn pydantic requests aiohttp redis pika; do
    if ! python3 -c "import ${dep//-/_}" 2>/dev/null; then
        MISSING_DEPS+=("$dep")
    fi
done

# Check python-dotenv separately (import name is 'dotenv')
if ! python3 -c "import dotenv" 2>/dev/null; then
    MISSING_DEPS+=("python-dotenv")
fi

if [ ${#MISSING_DEPS[@]} -gt 0 ] || [ ! -f ".deps_installed" ]; then
    print_status "Installing Python dependencies..."
    if [ -f "requirements.txt" ]; then
        pip3 install --no-cache-dir -r requirements.txt 2>&1 | tail -5 || {
            print_warning "⚠️  Failed to install from requirements.txt, installing core dependencies..."
            pip3 install --no-cache-dir fastapi uvicorn pydantic requests aiohttp aiofiles redis pika python-dotenv || true
        }
    else
        print_warning "⚠️  requirements.txt not found, installing core dependencies..."
        pip3 install --no-cache-dir fastapi uvicorn pydantic requests aiohttp aiofiles redis pika python-dotenv || true
    fi
    
    # Verify critical dependencies
    print_status "Verifying dependencies..."
    for dep in aiofiles fastapi uvicorn; do
        if python3 -c "import ${dep//-/_}" 2>/dev/null; then
            print_success "   ✅ $dep"
        else
            print_error "   ❌ $dep (missing)"
        fi
    done
    
    touch .deps_installed
    print_success "✅ Dependencies installed"
    echo ""
else
    print_success "✅ All dependencies are installed"
    echo ""
fi

# Redis: Using Redis Cloud (external)
# REDIS_URL configured in .env.runpod (redis://default:...@redis-12598.c252.ap-southeast-1-1.ec2.cloud.redislabs.com:12598)
# No need to start local Redis server
print_status "Using Redis Cloud (external) - no local Redis server needed"
echo ""

# Start Whisper API
print_status "Starting Whisper API..."
if pgrep -f "python.*whisper_api" > /dev/null; then
    print_warning "⚠️  Whisper API already running"
else
    cd whisper-service
    if [ -f "whisper_api.py" ]; then
        export WHISPER_MODEL_PATH="$PROJECT_ROOT/models"
        export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
        export WHISPER_CUBLAS=1
        nohup python3 whisper_api.py > /tmp/whisper.log 2>&1 & disown
        sleep 3
        if curl -f http://localhost:8002/health > /dev/null 2>&1; then
            print_success "✅ Whisper API started"
        else
            print_warning "⚠️  Whisper API may not be ready yet"
        fi
    else
        print_error "❌ whisper_api.py not found"
    fi
    cd ..
fi
echo ""

# Start Video Worker
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
    CUDNN_DIR="/workspace/cudnn/lib"
    
    # เพิ่ม CTranslate2 libraries
    if [ -d "$CTRANSLATE2_LIBS" ]; then
        export LD_LIBRARY_PATH="${CTRANSLATE2_LIBS}:${LD_LIBRARY_PATH:-}"
        print_status "✅ Set LD_LIBRARY_PATH for CTranslate2 libraries: $CTRANSLATE2_LIBS"
    fi
    
    # เพิ่ม cuDNN libraries (persistent)
    if [ -d "$CUDNN_DIR" ]; then
        export LD_LIBRARY_PATH="${CUDNN_DIR}:${LD_LIBRARY_PATH:-}"
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
    sleep 2
    if pgrep -f "python.*video_worker" > /dev/null; then
        print_success "✅ Video Worker started"
    else
        print_error "❌ Video Worker failed to start"
    fi
fi
echo ""

# Start Main API
print_status "Starting Main API..."
if pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
    print_warning "⚠️  Main API already running"
else
    export PYTHONPATH="$PROJECT_ROOT"
    export RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
    export RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
    export RABBITMQ_USER=${RABBITMQ_USER:-senate}
    export RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}
    export WHISPER_PROVIDER=${WHISPER_PROVIDER:-openai-whisper}
    export WHISPER_MODEL=${WHISPER_MODEL:-large-v3}
    export WHISPER_DEVICE=${WHISPER_DEVICE:-auto}
    # Note: Using UTC timezone (datetime.now(timezone.utc)) - frontend handles conversion
    nohup env RABBITMQ_HOST="${RABBITMQ_HOST}" \
             RABBITMQ_PORT="${RABBITMQ_PORT}" \
             RABBITMQ_USER="${RABBITMQ_USER}" \
             RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD}" \
             WHISPER_PROVIDER="${WHISPER_PROVIDER}" \
             WHISPER_MODEL="${WHISPER_MODEL}" \
             WHISPER_DEVICE="${WHISPER_DEVICE}" \
             python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8010 > /tmp/main-api.log 2>&1 & disown
    sleep 5
    # Check if process is still running (not crashed)
    if pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
        if curl -f http://localhost:8010/health > /dev/null 2>&1; then
            print_success "✅ Main API started"
        else
            print_warning "⚠️  Main API started but health check failed - check logs"
            print_status "💡 Check logs: tail -f /tmp/main-api.log"
        fi
    else
        print_error "❌ Main API failed to start - check logs"
        print_status "💡 Check logs: tail -20 /tmp/main-api.log"
    fi
fi
echo ""

print_success "🎉 All services started!"
echo ""
print_status "💡 Check status: bash scripts/pod/check-pod.sh"
print_status "💡 View logs: bash scripts/pod/logs-pod.sh"
echo ""

