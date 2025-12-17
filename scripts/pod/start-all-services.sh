#!/bin/bash
# Script สำหรับ Start Services ทั้งหมด (MainAPI, Video-Worker, Dashboard)
#
# วิธีใช้งาน:
#   bash scripts/pod/start-all-services.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

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

print_header "🚀 Starting All Transcription Services"

# ============================================
# Part 1: Start MainAPI
# ============================================
print_header "1. Starting MainAPI (Port $API_PORT)"

if pgrep -f "uvicorn.*app.main.*${API_PORT}" > /dev/null; then
    print_warning "MainAPI is already running"
    PID=$(pgrep -f "uvicorn.*app.main.*${API_PORT}" | head -1)
    echo "   PID: $PID"
else
    print_status "Starting MainAPI..."
    if [ -f "scripts/pod/start-service-daemon.sh" ]; then
        bash scripts/pod/start-service-daemon.sh "$API_PORT" > /tmp/mainapi-start.log 2>&1 &
        START_PID=$!
        echo "   Start script PID: $START_PID"
        
        # Wait a bit for service to start
        sleep 5
        
        # Check if service started
        if pgrep -f "uvicorn.*app.main.*${API_PORT}" > /dev/null; then
            print_success "MainAPI started successfully"
        else
            print_warning "MainAPI may not have started. Check logs: /tmp/mainapi-start.log"
        fi
    else
        print_error "start-service-daemon.sh not found"
    fi
fi
echo ""

# ============================================
# Part 2: Start Video-Worker
# ============================================
print_header "2. Starting Video-Worker"

if pgrep -f "python.*video_worker" > /dev/null; then
    print_warning "Video-Worker is already running"
    PID=$(pgrep -f "python.*video_worker" | head -1)
    echo "   PID: $PID"
else
    print_status "Starting Video-Worker..."
    if [ -f "scripts/pod/start-pod.sh" ]; then
        bash scripts/pod/start-pod.sh > /tmp/worker-start.log 2>&1 &
        START_PID=$!
        echo "   Start script PID: $START_PID"
        
        # Wait a bit for worker to start
        sleep 5
        
        # Check if worker started
        if pgrep -f "python.*video_worker" > /dev/null; then
            print_success "Video-Worker started successfully"
        else
            print_warning "Video-Worker may not have started. Check logs: /tmp/worker-start.log"
        fi
    else
        print_warning "start-pod.sh not found. You may need to start worker manually"
    fi
fi
echo ""

# ============================================
# Part 3: Start Dashboard
# ============================================
print_header "3. Starting Dashboard (Port $DASHBOARD_PORT)"

if pgrep -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|python.*dashboard.*main" > /dev/null; then
    print_warning "Dashboard is already running"
    PID=$(pgrep -f "uvicorn.*dashboard.*${DASHBOARD_PORT}\|python.*dashboard.*main" | head -1)
    echo "   PID: $PID"
else
    print_status "Starting Dashboard..."
    cd dashboard || {
        print_error "Dashboard directory not found"
        exit 1
    }
    
    # Check if dependencies are installed
    if ! python3 -c "import fastapi" 2>/dev/null; then
        print_status "Installing dashboard dependencies..."
        pip install -q -r requirements.txt
    fi
    
    # Start dashboard in background
    export DASHBOARD_PORT=$DASHBOARD_PORT
    nohup python3 -m uvicorn main:app --host 0.0.0.0 --port "$DASHBOARD_PORT" > /tmp/dashboard.log 2>&1 &
    DASHBOARD_PID=$!
    echo "   Dashboard PID: $DASHBOARD_PID"
    
    # Wait a bit for dashboard to start
    sleep 3
    
    # Check if dashboard started
    if pgrep -f "uvicorn.*main:app.*${DASHBOARD_PORT}" > /dev/null; then
        print_success "Dashboard started successfully"
    else
        print_warning "Dashboard may not have started. Check logs: /tmp/dashboard.log"
    fi
    
    cd ..
fi
echo ""

# ============================================
# Part 4: Verify Services
# ============================================
print_header "4. Verifying Services"

sleep 2

# Check MainAPI
if pgrep -f "uvicorn.*app.main.*${API_PORT}" > /dev/null; then
    print_success "MainAPI is running"
    API_RESPONSE=$(curl -s -m 3 "http://localhost:${API_PORT}/health" 2>&1 || echo "ERROR")
    if echo "$API_RESPONSE" | grep -q "healthy\|status"; then
        print_success "MainAPI health check: OK"
    else
        print_warning "MainAPI health check: Not ready yet"
    fi
else
    print_error "MainAPI is NOT running"
fi

# Check Video-Worker
if pgrep -f "python.*video_worker" > /dev/null; then
    print_success "Video-Worker is running"
else
    print_error "Video-Worker is NOT running"
fi

# Check Dashboard
if pgrep -f "uvicorn.*main:app.*${DASHBOARD_PORT}" > /dev/null; then
    print_success "Dashboard is running"
    DASHBOARD_RESPONSE=$(curl -s -m 3 "http://localhost:${DASHBOARD_PORT}/" 2>&1 || echo "ERROR")
    if echo "$DASHBOARD_RESPONSE" | grep -q "Transcription\|dashboard\|html"; then
        print_success "Dashboard is responding"
    else
        print_warning "Dashboard may not be ready yet"
    fi
else
    print_error "Dashboard is NOT running"
fi
echo ""

# ============================================
# Summary
# ============================================
print_header "📋 Summary"

echo "Services Status:"
if pgrep -f "uvicorn.*app.main.*${API_PORT}" > /dev/null; then
    echo -e "   ${GREEN}✅ MainAPI: RUNNING${NC} (http://localhost:${API_PORT})"
else
    echo -e "   ${RED}❌ MainAPI: NOT RUNNING${NC}"
fi

if pgrep -f "python.*video_worker" > /dev/null; then
    echo -e "   ${GREEN}✅ Video-Worker: RUNNING${NC}"
else
    echo -e "   ${RED}❌ Video-Worker: NOT RUNNING${NC}"
fi

if pgrep -f "uvicorn.*main:app.*${DASHBOARD_PORT}" > /dev/null; then
    echo -e "   ${GREEN}✅ Dashboard: RUNNING${NC} (http://localhost:${DASHBOARD_PORT})"
else
    echo -e "   ${RED}❌ Dashboard: NOT RUNNING${NC}"
fi

echo ""
echo "💡 Useful Commands:"
echo "   Check all services: bash scripts/pod/check-logs-and-webhook.sh"
echo "   View logs:         bash scripts/pod/tail-all-logs.sh"
echo "   Check API status:  bash scripts/pod/check-service-status.sh"
echo "   Check worker:      bash scripts/pod/check-worker-activity.sh"
echo ""

