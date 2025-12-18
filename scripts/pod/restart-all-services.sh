#!/bin/bash
# Script สำหรับ Restart Services ทั้งหมด (MainAPI, Video-Worker, Dashboard)
# รอทุก service ให้ครบ และทำ health check หลัง 10 วินาที
#
# วิธีใช้งาน:
#   bash scripts/pod/restart-all-services.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_status() {
    echo -e "${BLUE}📋 $1${NC}"
}

cd /workspace/transcription-service || exit 1

API_PORT=8010
DASHBOARD_PORT=8020

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔄 Restarting All Services                                   ║"
echo "║  เวลา: $(date '+%Y-%m-%d %H:%M:%S')                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ============================================
# Step 1: Stop All Services
# ============================================
print_header "Step 1: Stopping All Services"

# Stop MainAPI
API_PID=$(pgrep -f "uvicorn.*app.main.*${API_PORT}" | head -1 || echo "")
if [ -n "$API_PID" ]; then
    print_status "Stopping MainAPI (PID: $API_PID)..."
    kill $API_PID 2>/dev/null || true
    sleep 2
    if pgrep -f "uvicorn.*app.main.*${API_PORT}" > /dev/null; then
        pkill -9 -f "uvicorn.*app.main.*${API_PORT}" 2>/dev/null || true
        sleep 1
    fi
    print_success "✅ MainAPI stopped"
else
    print_warning "⚠️  MainAPI is not running"
fi

# Stop Video-Worker
WORKER_PID=""
for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker"; do
    WORKER_PID=$(pgrep -f "$pattern" | head -1 || echo "")
    if [ -n "$WORKER_PID" ]; then
        break
    fi
done

if [ -n "$WORKER_PID" ]; then
    print_status "Stopping Video-Worker (PID: $WORKER_PID)..."
    kill -TERM $WORKER_PID 2>/dev/null || true
    sleep 3
    if pgrep -f "app.workers.video_worker\|python3.*video_worker\|python.*video_worker" > /dev/null; then
        for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker"; do
            pkill -9 -f "$pattern" 2>/dev/null || true
        done
        sleep 1
    fi
    print_success "✅ Video-Worker stopped"
else
    print_warning "⚠️  Video-Worker is not running"
fi

# Stop Dashboard
DASHBOARD_PID=$(pgrep -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|uvicorn.*main:app.*${DASHBOARD_PORT}" | head -1 || echo "")
if [ -n "$DASHBOARD_PID" ]; then
    print_status "Stopping Dashboard (PID: $DASHBOARD_PID)..."
    kill $DASHBOARD_PID 2>/dev/null || true
    sleep 2
    if pgrep -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|uvicorn.*main:app.*${DASHBOARD_PORT}" > /dev/null; then
        pkill -9 -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|uvicorn.*main:app.*${DASHBOARD_PORT}" 2>/dev/null || true
        sleep 1
    fi
    print_success "✅ Dashboard stopped"
else
    print_warning "⚠️  Dashboard is not running"
fi

echo ""
sleep 2

# ============================================
# Step 2: Start All Services
# ============================================
print_header "Step 2: Starting All Services"

bash scripts/pod/start-all-services.sh

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ All Services Restart Complete                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

