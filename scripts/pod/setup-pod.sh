#!/bin/bash
# Script สำหรับ Setup Pod ครั้งแรก หรือตรวจสอบและจัดการส่วนที่ขาด
#
# วิธีใช้งาน:
#   bash scripts/pod/setup-pod.sh

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

echo "🔧 Setting Up Pod"
echo "📅 $(date)"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Check if services are already running
print_status "Checking for running services..."
SERVICES_RUNNING=false

if pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
    print_warning "⚠️  Main API is already running (port 8001)"
    SERVICES_RUNNING=true
fi

if pgrep -f "python.*video_worker" > /dev/null; then
    print_warning "⚠️  Video Worker is already running"
    SERVICES_RUNNING=true
fi

if pgrep -x "redis-server" > /dev/null; then
    print_warning "⚠️  Redis is already running"
    SERVICES_RUNNING=true
fi

if [ "$SERVICES_RUNNING" = true ]; then
    echo ""
    print_warning "⚠️  Some services are already running"
    print_status "💡 If you encounter 'address already in use' error, stop services first:"
    echo "   bash scripts/pod/stop-pod.sh"
    echo ""
    read -p "Continue with setup anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Setup cancelled. Please stop services first if needed."
        exit 0
    fi
    echo ""
fi

# Create directories
print_status "Creating directories..."
mkdir -p uploads storage/transcriptions storage/metadata storage/captions temp models test-files
print_success "✅ Directories created"
echo ""

# Check/Setup .env.runpod
print_status "Checking .env.runpod..."
if [ -f ".env.runpod" ]; then
    print_success "✅ .env.runpod exists"
    # Check RabbitMQ config
    if grep -q "RABBITMQ_HOST=localhost" .env.runpod; then
        print_warning "⚠️  RABBITMQ_HOST is set to localhost"
        echo ""
        read -p "Update RabbitMQ to Backend Server (178.128.105.100)? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sed -i 's/RABBITMQ_HOST=localhost/RABBITMQ_HOST=178.128.105.100/g' .env.runpod
            print_success "✅ Updated RABBITMQ_HOST"
        fi
    fi
else
    print_warning "⚠️  .env.runpod not found, creating..."
    cat > .env.runpod << EOF
ENVIRONMENT=runpod
STORAGE_TYPE=json
JSON_STORAGE_DIR=$PROJECT_ROOT/storage
RABBITMQ_HOST=178.128.105.100
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT
REDIS_URL=redis://localhost:6379
WHISPER_PROVIDER=${WHISPER_PROVIDER:-faster-whisper}
WHISPER_MODEL=${WHISPER_MODEL:-medium}
WHISPER_DEVICE=${WHISPER_DEVICE:-auto}
WHISPER_COMPUTE_TYPE=float16
WHISPER_BATCH_SIZE=16
# Note: WHISPER_API_URL ไม่จำเป็นสำหรับ faster-whisper และ openai-whisper provider
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1
# Parallel Processing Configuration
WHISPER_USE_THREAD_LOCAL=false
TRANSCRIPTION_MAX_WORKERS=1
TRANSCRIPTION_CHUNK_DURATION=90
TRANSCRIPTION_PREFETCH_COUNT=100
# Simplified Flow (ไม่ chunk โดย default)
USE_CHUNKING=false
EOF
    print_success "✅ Created .env.runpod"
fi
echo ""

# Install system timezone data (required for pythainlp)
print_status "Installing system timezone data..."
if [ ! -d "/usr/share/zoneinfo" ] || [ ! -f "/usr/share/zoneinfo/Asia/Bangkok" ]; then
    print_status "Installing tzdata..."
    apt-get update -qq && apt-get install -y -qq tzdata > /dev/null 2>&1 && {
        print_success "✅ System tzdata installed"
    } || {
        print_warning "⚠️  Failed to install system tzdata (may need sudo)"
    }
else
    print_success "✅ System timezone data available"
fi
echo ""

# Check Python dependencies
print_status "Checking Python dependencies..."

# Check critical dependencies
MISSING_DEPS=()
for dep in aiofiles fastapi uvicorn pydantic requests aiohttp redis pika; do
    if ! python3 -c "import ${dep//-/_}" 2>/dev/null; then
        MISSING_DEPS+=("$dep")
    fi
done

# Check faster-whisper separately (import name is 'faster_whisper')
if ! python3 -c "import faster_whisper" 2>/dev/null; then
    MISSING_DEPS+=("faster-whisper")
fi

# Check python-dotenv separately (import name is 'dotenv')
if ! python3 -c "import dotenv" 2>/dev/null; then
    MISSING_DEPS+=("python-dotenv")
fi

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    print_warning "⚠️  Missing dependencies: ${MISSING_DEPS[*]}"
    if [ -f "requirements.txt" ]; then
        print_status "Installing from requirements.txt..."
        pip3 install --no-cache-dir -r requirements.txt || {
            print_warning "⚠️  Some packages failed, installing essentials..."
            pip3 install --no-cache-dir fastapi uvicorn pydantic requests aiohttp aiofiles redis pika python-dotenv tzdata || true
        }
    else
        print_warning "⚠️  requirements.txt not found, installing essentials..."
        pip3 install --no-cache-dir fastapi uvicorn pydantic requests aiohttp aiofiles redis pika python-dotenv tzdata || true
    fi
    
    # Verify critical dependencies
    print_status "Verifying dependencies..."
    for dep in aiofiles fastapi uvicorn pydantic requests aiohttp redis pika; do
        if python3 -c "import ${dep//-/_}" 2>/dev/null; then
            print_success "   ✅ $dep"
        else
            print_error "   ❌ $dep (missing)"
        fi
    done
    # Check python-dotenv separately
    if python3 -c "import dotenv" 2>/dev/null; then
        print_success "   ✅ python-dotenv"
    else
        print_error "   ❌ python-dotenv (missing)"
    fi
    # Check faster-whisper separately
    if python3 -c "import faster_whisper" 2>/dev/null; then
        print_success "   ✅ faster-whisper"
    else
        print_error "   ❌ faster-whisper (missing)"
    fi
    
    touch .deps_installed
    print_success "✅ Dependencies installed"
elif [ -f ".deps_installed" ]; then
    print_success "✅ All dependencies are installed"
else
    # Install even if .deps_installed doesn't exist but dependencies are present
    touch .deps_installed
    print_success "✅ All dependencies are installed"
fi
echo ""

# Check Whisper models
print_status "Checking Whisper models..."

# Check WHISPER_PROVIDER from .env.runpod
if [ -f ".env.runpod" ]; then
    set -a
    source .env.runpod
    set +a
fi

WHISPER_PROVIDER=${WHISPER_PROVIDER:-faster-whisper}

if [ "$WHISPER_PROVIDER" = "faster-whisper" ]; then
    # Check faster-whisper models (stored in ~/.cache/huggingface/hub/ by default)
    print_status "Checking faster-whisper models..."
    WHISPER_CACHE_DIR=${WHISPER_DOWNLOAD_ROOT:-~/.cache/huggingface/hub}
    MODEL_FOUND=""
    
    # Check for common model directories
    for model_name in "medium" "large-v3" "large-v2" "large" "small" "base" "tiny"; do
        # faster-whisper models are stored in directories like:
        # ~/.cache/huggingface/hub/models--guillaumekln--faster-whisper-{model_name}/
        MODEL_PATTERN="*faster-whisper-${model_name}*"
        MODEL_PATH=$(find "$WHISPER_CACHE_DIR" -type d -name "$MODEL_PATTERN" 2>/dev/null | head -1)
        
        if [ -n "$MODEL_PATH" ] && [ -d "$MODEL_PATH" ]; then
            MODEL_SIZE=$(du -sh "$MODEL_PATH" 2>/dev/null | cut -f1)
            MODEL_FOUND="$model_name"
            print_success "✅ Found faster-whisper model: $model_name ($MODEL_SIZE)"
            break
        fi
    done
    
    if [ -z "$MODEL_FOUND" ]; then
        print_warning "⚠️  No faster-whisper model found in $WHISPER_CACHE_DIR"
        print_status "💡 Models will be downloaded automatically on first use"
        echo ""
        echo "Available models (will be auto-downloaded):"
        echo "  - tiny: Fastest, lowest accuracy (~39M parameters)"
        echo "  - base: Fast, medium accuracy (~74M parameters)"
        echo "  - small: Balanced (~244M parameters)"
        echo "  - medium: Better accuracy (~769M parameters) ⭐ แนะนำสำหรับ RTX 4080"
        echo "  - large-v3: Best accuracy, slowest (~1550M parameters)"
        echo ""
        print_status "💡 To pre-download a model, run:"
        echo "   python3 -c 'from faster_whisper import WhisperModel; WhisperModel(\"medium\")'"
    fi
    
elif [ "$WHISPER_PROVIDER" = "openai-whisper" ]; then
    # Check openai-whisper models (stored in ~/.cache/whisper/ by default)
    print_status "Checking openai-whisper models..."
    WHISPER_CACHE_DIR=${WHISPER_DOWNLOAD_ROOT:-~/.cache/whisper}
    MODEL_FOUND=""
    
    # Check for common model files
    for model_name in "large-v3.pt" "large-v2.pt" "large.pt" "medium.pt" "small.pt" "base.pt" "tiny.pt"; do
        MODEL_PATH="$WHISPER_CACHE_DIR/$model_name"
        if [ -f "$MODEL_PATH" ]; then
            FILE_SIZE=$(stat -c%s "$MODEL_PATH" 2>/dev/null || stat -f%z "$MODEL_PATH" 2>/dev/null || echo "0")
            if [ "$FILE_SIZE" -gt 1000000 ]; then  # > 1MB
                MODEL_FOUND="$model_name"
                print_success "✅ Found openai-whisper model: $model_name ($(du -h "$MODEL_PATH" | cut -f1))"
                break
            fi
        fi
    done
    
    if [ -z "$MODEL_FOUND" ]; then
        print_warning "⚠️  No openai-whisper model found in $WHISPER_CACHE_DIR"
        print_status "💡 Models will be downloaded automatically on first use"
        echo ""
        echo "Available models (will be auto-downloaded):"
        echo "  - tiny: Fastest, lowest accuracy (~39M parameters)"
        echo "  - base: Fast, medium accuracy (~74M parameters)"
        echo "  - small: Balanced (~244M parameters)"
        echo "  - medium: Better accuracy (~769M parameters) (แนะนำสำหรับ RTX 4080)"
        echo "  - large-v3: Best accuracy, slowest (~1550M parameters) (แนะนำสำหรับ RTX 4080)"
        echo ""
        print_status "💡 To pre-download a model, run:"
        echo "   python3 -c 'import whisper; whisper.load_model(\"large-v3\")'"
    fi
    
    # Check for old whisper.cpp models in models/ directory
    print_status "Checking for old whisper.cpp models in models/ directory..."
    OLD_MODELS=$(find models/ -name "ggml-*.bin" 2>/dev/null | wc -l || echo "0")
    if [ "$OLD_MODELS" -gt 0 ]; then
        print_warning "⚠️  Found $OLD_MODELS old whisper.cpp model file(s) in models/ directory"
        print_status "💡 These are not needed for openai-whisper provider"
        echo ""
        read -p "Delete old whisper.cpp models? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f models/ggml-*.bin && print_success "✅ Old whisper.cpp models removed"
        else
            print_status "💡 Old models kept (can be deleted later: rm -f models/ggml-*.bin)"
        fi
    fi
else
    # Check whisper.cpp models (ggml-*.bin files)
    print_status "Checking whisper.cpp models (ggml-*.bin)..."
    MODEL_FOUND=""
    for variant in "ggml-large-v3.bin" "ggml-large-v2.bin" "ggml-large.bin" "ggml-medium.bin" "ggml-small.bin" "ggml-base.bin"; do
        if [ -f "models/$variant" ]; then
            FILE_SIZE=$(stat -c%s "models/$variant" 2>/dev/null || stat -f%z "models/$variant" 2>/dev/null || echo "0")
            if [ "$FILE_SIZE" -gt 100000000 ]; then  # > 100MB
                MODEL_FOUND="$variant"
                print_success "✅ Found whisper.cpp model: $variant ($(du -h "models/$variant" | cut -f1))"
                break
            fi
        fi
    done
    
    if [ -z "$MODEL_FOUND" ]; then
        print_warning "⚠️  No whisper.cpp model found"
        echo ""
        echo "Available models:"
        echo "  - base: Fastest, lowest accuracy"
        echo "  - small: Balanced"
        echo "  - medium: Better accuracy (แนะนำสำหรับ RTX 4080)"
        echo "  - large-v3: Best accuracy, slowest (แนะนำสำหรับ RTX 4080)"
        echo ""
        read -p "Download model? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo ""
            read -p "Model size (medium/large-v3): " MODEL_SIZE
            MODEL_SIZE=${MODEL_SIZE:-medium}
            if [ -f "scripts/utility/download-models.sh" ]; then
                bash scripts/utility/download-models.sh "$MODEL_SIZE" --skip-restart
            else
                print_error "❌ download-models.sh not found"
            fi
        fi
    fi
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

# Summary
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Setup Summary"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

print_success "✅ Setup completed!"
echo ""
print_status "💡 Next steps:"
echo "   1. Start services: bash scripts/pod/start-pod.sh"
echo "   2. Check status: bash scripts/pod/check-pod.sh"
echo "   3. Test transcription: bash scripts/pod/test-transcription.sh"
echo ""

