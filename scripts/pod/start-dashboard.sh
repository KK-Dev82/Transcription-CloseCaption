#!/bin/bash
# Script สำหรับ Start Dashboard Service
#
# วิธีใช้งาน:
#   bash scripts/pod/start-dashboard.sh

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

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

cd /workspace/transcription-service || exit 1

DASHBOARD_PORT=8020
DASHBOARD_DIR="dashboard"
DASHBOARD_LOG="/tmp/dashboard.log"
DASHBOARD_PID_FILE="/tmp/dashboard.pid"

print_header "🚀 Starting Dashboard Service"

# Check if dashboard is already running
if pgrep -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|uvicorn.*main:app.*${DASHBOARD_PORT}" > /dev/null; then
    print_warning "Dashboard is already running"
    PID=$(pgrep -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|uvicorn.*main:app.*${DASHBOARD_PORT}" | head -1)
    echo "   PID: $PID"
    echo ""
    read -p "Do you want to stop and restart? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Stopping existing dashboard..."
        kill $PID 2>/dev/null || true
        sleep 2
        if pgrep -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|uvicorn.*main:app.*${DASHBOARD_PORT}" > /dev/null; then
            pkill -9 -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|uvicorn.*main:app.*${DASHBOARD_PORT}" 2>/dev/null || true
            sleep 1
        fi
    else
        echo "Keeping existing dashboard running"
        exit 0
    fi
fi

# Check dashboard directory
if [ ! -d "$DASHBOARD_DIR" ]; then
    print_error "Dashboard directory not found: $DASHBOARD_DIR"
    exit 1
fi

cd "$DASHBOARD_DIR" || exit 1

# Load environment variables from parent .env.runpod
if [ -f "../env.runpod" ]; then
    print_status "Loading environment from ../env.runpod..."
    set -a
    source ../env.runpod
    set +a
    print_success "Environment loaded"
fi

# Check if dependencies are installed
print_status "Checking dependencies..."
if ! python3 -c "import fastapi" 2>/dev/null; then
    print_warning "Dependencies not installed, installing..."
    pip install -q -r requirements.txt || {
        print_error "Failed to install dependencies"
        exit 1
    }
    print_success "Dependencies installed"
else
    print_success "Dependencies OK"
fi

# Start dashboard in background
print_status "Starting Dashboard..."
print_info "   Port: $DASHBOARD_PORT"
print_info "   Log: $DASHBOARD_LOG"
print_info "   PID: $DASHBOARD_PID_FILE"
echo ""

# Start with nohup
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port "$DASHBOARD_PORT" > "$DASHBOARD_LOG" 2>&1 &

DASHBOARD_PID=$!
echo $DASHBOARD_PID > "$DASHBOARD_PID_FILE"

# Wait a moment for dashboard to start
sleep 3

# Check if dashboard started successfully
if ps -p $DASHBOARD_PID > /dev/null; then
    print_success "Dashboard started successfully"
    echo "   PID: $DASHBOARD_PID"
    echo "   PID File: $DASHBOARD_PID_FILE"
    echo ""
    
    # Wait a bit and test
    sleep 2
    if curl -s -f "http://localhost:${DASHBOARD_PORT}/" > /dev/null 2>&1; then
        print_success "Dashboard is responding"
        echo ""
        print_info "📊 Dashboard Information:"
        echo "   URL: http://0.0.0.0:${DASHBOARD_PORT}"
        echo "   Log: tail -f $DASHBOARD_LOG"
        echo "   PID: cat $DASHBOARD_PID_FILE"
        echo ""
        
        # Check webhook endpoint
        if curl -s -f "http://localhost:${DASHBOARD_PORT}/api/webhook/events" > /dev/null 2>&1; then
            print_success "Webhook endpoint is accessible"
        else
            print_warning "Webhook endpoint may not be ready yet"
        fi
    else
        print_warning "Dashboard started but not responding yet (check log: $DASHBOARD_LOG)"
        echo "   Wait a few seconds and check: curl http://localhost:${DASHBOARD_PORT}/"
    fi
else
    print_error "Failed to start dashboard"
    echo "   Check log: $DASHBOARD_LOG"
    tail -20 "$DASHBOARD_LOG" 2>/dev/null || echo "   (Log file not found)"
    exit 1
fi

cd ..

