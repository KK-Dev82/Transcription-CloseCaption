#!/bin/bash
# Script สำหรับ Restart API Service และ Video Worker เท่านั้น
# ใช้สำหรับ restart หลังจากเพิ่ม consumers ใหม่
#
# วิธีใช้งาน:
#   bash scripts/pod/restart-service-daemon.sh

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
echo "║  🔄 Restarting API Service & Video Worker                    ║"
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

# Step 1: Stop API Service
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛑 Step 1: Stopping API Service..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

API_PID=$(pgrep -f "uvicorn.*app.main.*8010" | head -1 || echo "")
if [ -n "$API_PID" ]; then
    print_status "Stopping API Service (PID: $API_PID)..."
    kill $API_PID 2>/dev/null || true
    sleep 2
    
    # Force kill if still running
    if pgrep -f "uvicorn.*app.main.*8010" > /dev/null; then
        print_warning "Force killing API Service..."
        pkill -9 -f "uvicorn.*app.main.*8010" 2>/dev/null || true
        sleep 1
    fi
    
    if ! pgrep -f "uvicorn.*app.main.*8010" > /dev/null; then
        print_success "✅ API Service stopped"
    else
        print_error "❌ Failed to stop API Service"
    fi
else
    print_warning "⚠️  API Service is not running"
fi
echo ""

# Step 2: Stop Video Worker
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛑 Step 2: Stopping Video Worker..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

WORKER_PID=$(pgrep -f "python.*video_worker" | head -1 || echo "")
if [ -n "$WORKER_PID" ]; then
    print_status "Stopping Video Worker (PID: $WORKER_PID)..."
    kill $WORKER_PID 2>/dev/null || true
    sleep 2
    
    # Force kill if still running
    if pgrep -f "python.*video_worker" > /dev/null; then
        print_warning "Force killing Video Worker..."
        pkill -9 -f "python.*video_worker" 2>/dev/null || true
        sleep 1
    fi
    
    if ! pgrep -f "python.*video_worker" > /dev/null; then
        print_success "✅ Video Worker stopped"
    else
        print_error "❌ Failed to stop Video Worker"
    fi
else
    print_warning "⚠️  Video Worker is not running"
fi
echo ""

# Wait a moment for processes to fully stop
sleep 2

# Step 3: Start Services using start-service-daemon.sh
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Step 3: Starting Services..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if start-service-daemon.sh exists
if [ ! -f "scripts/pod/start-service-daemon.sh" ]; then
    print_error "❌ start-service-daemon.sh not found"
    exit 1
fi

# Start services
bash scripts/pod/start-service-daemon.sh

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Restart Complete                                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Final status check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Final Status Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if pgrep -f "uvicorn.*app.main.*8010" > /dev/null; then
    API_PID=$(pgrep -f "uvicorn.*app.main.*8010" | head -1)
    print_success "✅ API Service: RUNNING (PID: $API_PID)"
else
    print_error "❌ API Service: NOT RUNNING"
fi

if pgrep -f "python.*video_worker" > /dev/null; then
    WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
    print_success "✅ Video Worker: RUNNING (PID: $WORKER_PID)"
else
    print_error "❌ Video Worker: NOT RUNNING"
fi

echo ""
print_status "💡 Useful Commands:"
echo "   Check status: bash scripts/pod/check-logs-diagnosis.sh"
echo "   View API logs: tail -f /tmp/transcription-service.log"
echo "   View Worker logs: tail -f /tmp/video-worker.log"
echo ""

