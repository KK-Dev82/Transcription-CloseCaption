#!/bin/bash
# Script สำหรับตรวจสอบสถานะ Services
#
# วิธีใช้งาน:
# bash scripts/pod/check-services-status.sh

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

echo "🔍 Checking Services Status"
echo "📅 $(date)"
echo ""

# Check Redis
print_status "Checking Redis..."
if pgrep -x "redis-server" > /dev/null; then
    REDIS_PID=$(pgrep -x "redis-server")
    print_success "✅ Redis is running (PID: $REDIS_PID)"
    if redis-cli ping > /dev/null 2>&1; then
        print_success "   Redis is responding"
    else
        print_warning "   Redis is not responding"
    fi
else
    print_error "❌ Redis is not running"
fi
echo ""

# Check Whisper API
print_status "Checking Whisper API..."
if pgrep -f "python.*whisper_api" > /dev/null; then
    WHISPER_PID=$(pgrep -f "python.*whisper_api")
    print_success "✅ Whisper API is running (PID: $WHISPER_PID)"
    if curl -f http://localhost:8002/health > /dev/null 2>&1; then
        print_success "   Whisper API is responding"
    else
        print_warning "   Whisper API is not responding"
    fi
else
    print_error "❌ Whisper API is not running"
fi
echo ""

# Check Video Worker
print_status "Checking Video Worker..."
if pgrep -f "python.*video_worker" > /dev/null; then
    VIDEO_WORKER_PID=$(pgrep -f "python.*video_worker")
    print_success "✅ Video Worker is running (PID: $VIDEO_WORKER_PID)"
else
    print_error "❌ Video Worker is not running"
fi
echo ""

# Check Main API
print_status "Checking Main API..."
if pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
    MAIN_API_PID=$(pgrep -f "python.*uvicorn.*app.main")
    print_success "✅ Main API is running (PID: $MAIN_API_PID)"
    if curl -f http://localhost:8001/health > /dev/null 2>&1; then
        print_success "   Main API is responding"
    else
        print_warning "   Main API is not responding"
    fi
else
    print_error "❌ Main API is not running"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ALL_RUNNING=true

if ! pgrep -x "redis-server" > /dev/null; then
    ALL_RUNNING=false
fi

if ! pgrep -f "python.*whisper_api" > /dev/null; then
    ALL_RUNNING=false
fi

if ! pgrep -f "python.*video_worker" > /dev/null; then
    ALL_RUNNING=false
fi

if ! pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
    ALL_RUNNING=false
fi

if [ "$ALL_RUNNING" = true ]; then
    print_success "✅ All services are running"
    echo ""
    print_status "💡 To restart services:"
    echo "   bash scripts/pod/stop-services.sh"
    echo "   bash scripts/pod/start-services-direct.sh"
else
    print_warning "⚠️  Some services are not running"
    echo ""
    print_status "💡 To start services:"
    echo "   bash scripts/pod/start-services-direct.sh"
    echo ""
    print_status "💡 To restart all services:"
    echo "   bash scripts/pod/restart-pod-services.sh"
fi

