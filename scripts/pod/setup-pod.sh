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
WHISPER_PROVIDER=builtin
WHISPER_API_URL=http://localhost:8002
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1
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
if [ -f "requirements.txt" ]; then
    if [ ! -f ".deps_installed" ]; then
        print_warning "⚠️  Dependencies not installed"
        read -p "Install Python dependencies? (Y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            pip3 install --no-cache-dir -r requirements.txt || {
                print_warning "⚠️  Some packages failed, installing essentials..."
                pip3 install --no-cache-dir fastapi uvicorn pydantic requests aiohttp aiofiles redis pika python-dotenv tzdata || true
            }
            touch .deps_installed
            print_success "✅ Dependencies installed"
        fi
    else
        print_success "✅ Dependencies installed"
    fi
else
    print_warning "⚠️  requirements.txt not found"
fi
echo ""

# Check Whisper models
print_status "Checking Whisper models..."
MODEL_FOUND=""
for variant in "ggml-large-v3.bin" "ggml-large-v2.bin" "ggml-large.bin" "ggml-medium.bin" "ggml-small.bin" "ggml-base.bin"; do
    if [ -f "models/$variant" ]; then
        FILE_SIZE=$(stat -c%s "models/$variant" 2>/dev/null || stat -f%z "models/$variant" 2>/dev/null || echo "0")
        if [ "$FILE_SIZE" -gt 100000000 ]; then  # > 100MB
            MODEL_FOUND="$variant"
            print_success "✅ Found model: $variant ($(du -h "models/$variant" | cut -f1))"
            break
        fi
    fi
done

if [ -z "$MODEL_FOUND" ]; then
    print_warning "⚠️  No Whisper model found"
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

