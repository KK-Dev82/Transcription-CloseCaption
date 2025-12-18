#!/bin/bash
# Script สำหรับ Restart Dashboard Service
#
# วิธีใช้งาน:
#   bash scripts/pod/restart-dashboard.sh

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

DASHBOARD_PORT=8020

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔄 Restarting Dashboard Service                             ║"
echo "║  เวลา: $(date '+%Y-%m-%d %H:%M:%S')                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

cd /workspace/transcription-service || exit 1

# Step 1: Stop Dashboard
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛑 Step 1: Stopping Dashboard (Port: ${DASHBOARD_PORT})..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

DASHBOARD_PID=$(pgrep -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|uvicorn.*main:app.*${DASHBOARD_PORT}" | head -1 || echo "")
if [ -n "$DASHBOARD_PID" ]; then
    print_status "Stopping Dashboard (PID: $DASHBOARD_PID)..."
    kill $DASHBOARD_PID 2>/dev/null || true
    sleep 2
    
    # Force kill if still running
    if pgrep -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|uvicorn.*main:app.*${DASHBOARD_PORT}" > /dev/null; then
        print_warning "Force killing Dashboard..."
        pkill -9 -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|uvicorn.*main:app.*${DASHBOARD_PORT}" 2>/dev/null || true
        sleep 1
    fi
    
    if ! pgrep -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|uvicorn.*main:app.*${DASHBOARD_PORT}" > /dev/null; then
        print_success "✅ Dashboard stopped"
    else
        print_error "❌ Failed to stop Dashboard"
    fi
else
    print_warning "⚠️  Dashboard is not running"
fi
echo ""

# Wait a moment
sleep 2

# Step 2: Start Dashboard
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Step 2: Starting Dashboard..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

bash scripts/pod/start-dashboard.sh

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Dashboard Restart Complete                               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

