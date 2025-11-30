#!/bin/bash
# Script สำหรับ Restart Services หลัง Start Pod ใหม่
#
# วิธีใช้งาน:
# bash scripts/pod/restart-pod-services.sh
#
# ใช้เมื่อ:
# - Pod ถูก Stop แล้ว Start ใหม่
# - Services หยุดทำงาน
# - ต้องการ Restart Services

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "🔄 Restarting Transcription Services after Pod Restart"
echo "📅 $(date)"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

print_status "Project Root: $PROJECT_ROOT"
echo ""

# Check GPU
print_status "Checking GPU..."
if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
    if [ -n "$GPU_INFO" ]; then
        print_success "✅ GPU detected: $GPU_INFO"
    else
        print_warning "⚠️  GPU not detected or not available"
    fi
else
    print_warning "⚠️  nvidia-smi not found"
fi
echo ""

# Check if services are running
print_status "Checking existing services..."
RUNNING_SERVICES=0

if pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
    print_warning "⚠️  Main API is already running"
    RUNNING_SERVICES=$((RUNNING_SERVICES + 1))
fi

if pgrep -f "python.*whisper_api" > /dev/null; then
    print_warning "⚠️  Whisper API is already running"
    RUNNING_SERVICES=$((RUNNING_SERVICES + 1))
fi

if pgrep -f "python.*video_worker" > /dev/null; then
    print_warning "⚠️  Video Worker is already running"
    RUNNING_SERVICES=$((RUNNING_SERVICES + 1))
fi

if pgrep -f "redis-server" > /dev/null; then
    print_warning "⚠️  Redis is already running"
    RUNNING_SERVICES=$((RUNNING_SERVICES + 1))
fi

if [ $RUNNING_SERVICES -gt 0 ]; then
    echo ""
    read -p "Some services are already running. Stop and restart? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Cancelled. Services will continue running."
        exit 0
    fi
    echo ""
    print_status "Stopping existing services..."
    bash scripts/pod/stop-services.sh
    sleep 2
fi

echo ""

# Check project structure
print_status "Checking project structure..."
if [ ! -f "app/main.py" ]; then
    print_error "❌ app/main.py not found"
    print_error "Project structure may be incorrect"
    exit 1
fi

if [ ! -d "whisper-service" ]; then
    print_warning "⚠️  whisper-service directory not found"
fi

print_success "✅ Project structure OK"
echo ""

# Check .env.runpod
print_status "Checking .env.runpod..."
if [ -f ".env.runpod" ]; then
    print_success "✅ .env.runpod found"
    
    # Check if it's from backup
    if [ -f "/workspace/.env.runpod.backup" ]; then
        print_status "Found backup .env.runpod. Restore? (y/N)"
        read -p "" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cp /workspace/.env.runpod.backup .env.runpod
            print_success "✅ Restored .env.runpod from backup"
        fi
    fi
else
    print_warning "⚠️  .env.runpod not found"
    
    # Check for backup
    if [ -f "/workspace/.env.runpod.backup" ]; then
        print_status "Found backup .env.runpod. Restore? (y/N)"
        read -p "" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cp /workspace/.env.runpod.backup .env.runpod
            print_success "✅ Restored .env.runpod from backup"
        else
            print_warning "⚠️  .env.runpod will be created by start-services-direct.sh"
        fi
    else
        print_warning "⚠️  .env.runpod will be created by start-services-direct.sh"
    fi
fi
echo ""

# Check models
print_status "Checking Whisper models..."
if [ -d "models" ] && [ "$(ls -A models/*.bin 2>/dev/null)" ]; then
    MODEL_COUNT=$(ls -1 models/*.bin 2>/dev/null | wc -l)
    print_success "✅ Found $MODEL_COUNT model(s) in models/"
    
    # Check for models in volume
    if [ -d "/workspace/models" ] && [ "$(ls -A /workspace/models/*.bin 2>/dev/null)" ]; then
        VOLUME_MODEL_COUNT=$(ls -1 /workspace/models/*.bin 2>/dev/null | wc -l)
        print_status "Found $VOLUME_MODEL_COUNT model(s) in /workspace/models (Volume)"
    fi
else
    print_warning "⚠️  No models found in models/"
    print_status "💡 Models will be downloaded if needed"
fi
echo ""

# Start services
print_status "Starting services..."
bash scripts/pod/start-services-direct.sh

echo ""
print_success "✅ Services restart completed!"
echo ""
print_status "📋 Next steps:"
echo "   1. Check services: bash scripts/pod/check-services.sh"
echo "   2. Check logs: tail -f /tmp/main-api.log /tmp/whisper.log /tmp/video-worker.log"
echo "   3. Test health: curl http://localhost:8001/health"

