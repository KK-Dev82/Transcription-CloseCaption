#!/bin/bash
# Script สำหรับ Restart Main API เฉพาะ
# หยุด Main API แล้ว start ใหม่ (ไม่กระทบ services อื่น)

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

echo "🔄 Restarting Main API"
echo "📅 $(date)"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# 1. หยุด Main API
print_status "Stopping Main API..."
if pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
    pkill -f "python.*uvicorn.*app.main" 2>/dev/null || true
    sleep 2
    
    # Force kill ถ้ายังไม่หยุด
    if pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
        print_warning "⚠️  Main API still running, force killing..."
        pkill -9 -f "python.*uvicorn.*app.main" 2>/dev/null || true
        sleep 1
    fi
    
    print_success "✅ Main API stopped"
else
    print_warning "⚠️  Main API not running"
fi

echo ""

# 2. Start Main API ใหม่
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
            print_success "✅ Main API started successfully"
            print_status "📍 API URL: http://localhost:8010"
            print_status "📚 Docs: http://localhost:8010/docs"
        else
            print_warning "⚠️  Main API started but health check failed - check logs"
            print_status "💡 Check logs: tail -f /tmp/main-api.log"
        fi
    else
        print_error "❌ Main API failed to start - check logs"
        print_status "💡 Check logs: tail -20 /tmp/main-api.log"
        exit 1
    fi
fi

echo ""
print_success "🎉 Main API restart completed!"
echo ""
print_status "💡 View logs: tail -f /tmp/main-api.log"
print_status "💡 Check status: curl http://localhost:8010/health"
echo ""

