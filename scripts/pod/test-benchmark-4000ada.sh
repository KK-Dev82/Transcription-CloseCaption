#!/bin/bash
# Script สำหรับทดสอบ Benchmark บน RTX 4000 Ada
# ตรวจสอบและแก้ไขปัญหาก่อนรัน benchmark
#
# วิธีใช้งาน:
#   bash scripts/pod/test-benchmark-4000ada.sh

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "RTX 4000 Ada - Benchmark Test & Setup"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. ตรวจสอบ GPU
print_status "1. Checking GPU..."
if command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1)
    print_success "✅ GPU: $GPU_NAME"
    
    if echo "$GPU_NAME" | grep -qi "4000"; then
        print_success "✅ RTX 4000 Ada detected"
    else
        print_warning "⚠️  GPU may not be RTX 4000 Ada"
    fi
else
    print_error "❌ nvidia-smi not found"
    exit 1
fi
echo ""

# 2. ตรวจสอบ Services
print_status "2. Checking Services..."
SERVICES_OK=true

# Check Redis
if pgrep -x "redis-server" > /dev/null; then
    print_success "✅ Redis is running"
else
    print_warning "⚠️  Redis is not running"
    SERVICES_OK=false
fi

# Check API (port 8001 or 8010)
API_PORT=""
if curl -s -f http://localhost:8001/health > /dev/null 2>&1; then
    API_PORT=8001
    print_success "✅ API is running on port 8001"
elif curl -s -f http://localhost:8010/health > /dev/null 2>&1; then
    API_PORT=8010
    print_success "✅ API is running on port 8010"
else
    print_error "❌ API is not running"
    print_status "💡 Start API: bash scripts/pod/start-pod.sh"
    SERVICES_OK=false
fi

# Check Video Worker
if pgrep -f "python.*video_worker" > /dev/null; then
    print_success "✅ Video Worker is running"
else
    print_warning "⚠️  Video Worker is not running"
    SERVICES_OK=false
fi
echo ""

if [ "$SERVICES_OK" = false ]; then
    print_warning "⚠️  Some services are not running"
    read -p "Start services now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Starting services..."
        bash scripts/pod/start-pod.sh
        sleep 5
        
        # Re-check API port
        if curl -s -f http://localhost:8001/health > /dev/null 2>&1; then
            API_PORT=8001
        elif curl -s -f http://localhost:8010/health > /dev/null 2>&1; then
            API_PORT=8010
        fi
    else
        print_error "❌ Cannot proceed without services"
        exit 1
    fi
    echo ""
fi

# 3. ตรวจสอบ Video
print_status "3. Checking test video..."
VIDEO_PATH="uploads/v10-1.mp4"
if [ -f "$VIDEO_PATH" ]; then
    FILE_SIZE=$(du -h "$VIDEO_PATH" | cut -f1)
    print_success "✅ Video found: $VIDEO_PATH ($FILE_SIZE)"
else
    print_warning "⚠️  Video not found: $VIDEO_PATH"
    print_status "💡 Download video: bash scripts/pod/download-video.sh https://korrakang.com/video/v10-1.mp4"
    read -p "Download video now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        bash scripts/pod/download-video.sh https://korrakang.com/video/v10-1.mp4
    else
        print_error "❌ Cannot proceed without video"
        exit 1
    fi
fi
echo ""

# 4. ตรวจสอบ Model
print_status "4. Checking Whisper model (medium)..."
if python3 -c "from faster_whisper import WhisperModel" 2>/dev/null; then
    print_success "✅ faster-whisper is available"
    # Try to load model (will download if not exists)
    print_status "   Checking if model 'medium' is available..."
    if python3 -c "from faster_whisper import WhisperModel; m = WhisperModel('medium'); print('✅ Model loaded')" 2>&1 | grep -q "✅ Model loaded"; then
        print_success "✅ Model 'medium' is ready"
    else
        print_warning "⚠️  Model will be downloaded on first use"
    fi
else
    print_error "❌ faster-whisper not found"
    print_status "💡 Install: bash scripts/pod/install-dependencies.sh"
    exit 1
fi
echo ""

# 5. Test API Endpoint
print_status "5. Testing API endpoint..."
if [ -n "$API_PORT" ]; then
    TEST_RESPONSE=$(curl -s -X POST "http://localhost:${API_PORT}/transcribe/" \
        -H "Content-Type: application/json" \
        -d '{
            "file_path": "/workspace/transcription-service/uploads/v10-1.mp4",
            "file_name": "v10-1.mp4",
            "language": "th",
            "model_size": "medium"
        }' 2>&1)
    
    if echo "$TEST_RESPONSE" | grep -q "task_id"; then
        TEST_TASK_ID=$(echo "$TEST_RESPONSE" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4)
        print_success "✅ API endpoint working (test task: $TEST_TASK_ID)"
        
        # Cancel test task
        print_status "   Cancelling test task..."
        sleep 1
    elif echo "$TEST_RESPONSE" | grep -q "405\|Not Allowed\|nginx"; then
        print_error "❌ API endpoint error (405 Not Allowed)"
        print_status "   Response: $(echo "$TEST_RESPONSE" | head -c 200)"
        print_status "💡 This usually means API is not running correctly"
        print_status "💡 Try: bash scripts/pod/restart-pod.sh"
        exit 1
    else
        print_error "❌ API endpoint not working"
        print_status "   Response: $(echo "$TEST_RESPONSE" | head -c 200)"
        exit 1
    fi
else
    print_error "❌ API port not detected"
    exit 1
fi
echo ""

# 6. Summary and Run Benchmark
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Ready for Benchmark"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

print_success "✅ All checks passed!"
echo ""
print_status "Configuration:"
echo "  GPU: RTX 4000 Ada"
echo "  API Port: $API_PORT"
echo "  Video: $VIDEO_PATH"
echo "  Model: medium"
echo ""

read -p "Run concurrent benchmark (10 tasks)? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Starting benchmark..."
    echo ""
    bash scripts/pod/run-benchmark-concurrent.sh "$VIDEO_PATH" 10 medium rtx4000
else
    print_status "Benchmark cancelled"
    echo ""
    print_status "💡 To run benchmark manually:"
    echo "   bash scripts/pod/run-benchmark-concurrent.sh uploads/v10-1.mp4 10 medium rtx4000"
fi

