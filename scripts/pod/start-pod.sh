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
RABBITMQ_HOST=178.128.105.100
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT
REDIS_URL=redis://localhost:6379
WHISPER_PROVIDER=builtin
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

# Install system timezone data (required for pythainlp)
print_status "Checking system timezone data..."
if [ ! -d "/usr/share/zoneinfo" ] || [ ! -f "/usr/share/zoneinfo/Asia/Bangkok" ]; then
    print_warning "⚠️  System timezone data not found, installing..."
    apt-get update -qq && apt-get install -y -qq tzdata > /dev/null 2>&1 || {
        print_warning "⚠️  Failed to install system tzdata, trying alternative..."
        # Try to set TZDIR if available
        if [ -d "/usr/share/zoneinfo" ]; then
            export TZDIR=/usr/share/zoneinfo
        fi
    }
fi

# Install Python dependencies if needed
print_status "Checking Python dependencies..."
MISSING_DEPS=()

# Check critical dependencies
for dep in aiofiles fastapi uvicorn pydantic requests aiohttp redis pika python-dotenv; do
    if ! python3 -c "import ${dep//-/_}" 2>/dev/null; then
        MISSING_DEPS+=("$dep")
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ] || [ ! -f ".deps_installed" ]; then
    print_status "Installing Python dependencies..."
    if [ -f "requirements.txt" ]; then
        pip3 install --no-cache-dir -r requirements.txt 2>&1 | tail -5 || {
            print_warning "⚠️  Failed to install from requirements.txt, installing core dependencies..."
            pip3 install --no-cache-dir fastapi uvicorn pydantic requests aiohttp aiofiles redis pika python-dotenv tzdata || true
        }
    else
        print_warning "⚠️  requirements.txt not found, installing core dependencies..."
        pip3 install --no-cache-dir fastapi uvicorn pydantic requests aiohttp aiofiles redis pika python-dotenv tzdata || true
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

# Start Redis
print_status "Starting Redis..."
if pgrep -x "redis-server" > /dev/null; then
    print_warning "⚠️  Redis already running"
else
    redis-server --daemonize yes --port 6379 --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru || true
    sleep 2
    if redis-cli ping > /dev/null 2>&1; then
        print_success "✅ Redis started"
    else
        print_error "❌ Redis failed to start"
    fi
fi
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
    nohup env RABBITMQ_HOST="${RABBITMQ_HOST}" \
             RABBITMQ_PORT="${RABBITMQ_PORT}" \
             RABBITMQ_USER="${RABBITMQ_USER}" \
             RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD}" \
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
    # Set timezone environment variables for pythainlp
    export TZ=Asia/Bangkok
    [ -d "/usr/share/zoneinfo" ] && export TZDIR=/usr/share/zoneinfo || true
    nohup env RABBITMQ_HOST="${RABBITMQ_HOST}" \
             RABBITMQ_PORT="${RABBITMQ_PORT}" \
             RABBITMQ_USER="${RABBITMQ_USER}" \
             RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD}" \
             TZ="${TZ}" \
             TZDIR="${TZDIR:-/usr/share/zoneinfo}" \
             python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/main-api.log 2>&1 & disown
    sleep 5
    # Check if process is still running (not crashed)
    if pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
        if curl -f http://localhost:8001/health > /dev/null 2>&1; then
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

