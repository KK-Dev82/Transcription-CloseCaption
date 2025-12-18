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

# Check worker with multiple patterns
WORKER_RUNNING=false
WORKER_PID=""
for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker"; do
    if pgrep -f "$pattern" > /dev/null; then
        WORKER_RUNNING=true
        WORKER_PID=$(pgrep -f "$pattern" | head -1)
        break
    fi
done

if [ "$WORKER_RUNNING" = true ]; then
    print_warning "Video-Worker is already running"
    PID="$WORKER_PID"
    echo "   PID: $PID"
else
    print_status "Starting Video-Worker..."
    if [ -f "scripts/pod/start-pod.sh" ]; then
        bash scripts/pod/start-pod.sh > /tmp/worker-start.log 2>&1 &
        START_PID=$!
        echo "   Start script PID: $START_PID"
        
        # Wait a bit for worker to start
        sleep 5
        
        # Check if worker started (try multiple patterns)
        WORKER_STARTED=false
        for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker"; do
            if pgrep -f "$pattern" > /dev/null; then
                WORKER_STARTED=true
                break
            fi
        done
        
        if [ "$WORKER_STARTED" = true ]; then
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
# Part 4: Wait for All Services to be Ready
# ============================================
print_header "4. Waiting for All Services to be Ready"

MAX_WAIT=60  # Maximum wait time in seconds
WAIT_INTERVAL=2  # Check every 2 seconds
ELAPSED=0

print_status "Waiting for services to start (max ${MAX_WAIT}s)..."
echo ""

# Wait for MainAPI
API_READY=false
while [ $ELAPSED -lt $MAX_WAIT ] && [ "$API_READY" = false ]; do
    if pgrep -f "uvicorn.*app.main.*${API_PORT}" > /dev/null; then
        if curl -s -f "http://localhost:${API_PORT}/health" > /dev/null 2>&1; then
            API_READY=true
            print_success "✅ MainAPI is ready (${ELAPSED}s)"
            break
        fi
    fi
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
    if [ $((ELAPSED % 10)) -eq 0 ]; then
        print_status "   Waiting for MainAPI... (${ELAPSED}s/${MAX_WAIT}s)"
    fi
done

if [ "$API_READY" = false ]; then
    print_warning "⚠️  MainAPI did not become ready within ${MAX_WAIT}s"
fi

# Wait for Video-Worker
WORKER_READY=false
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ] && [ "$WORKER_READY" = false ]; do
    for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker"; do
        if pgrep -f "$pattern" > /dev/null; then
            WORKER_READY=true
            print_success "✅ Video-Worker is ready (${ELAPSED}s)"
            break
        fi
    done
    if [ "$WORKER_READY" = true ]; then
        break
    fi
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
    if [ $((ELAPSED % 10)) -eq 0 ]; then
        print_status "   Waiting for Video-Worker... (${ELAPSED}s/${MAX_WAIT}s)"
    fi
done

if [ "$WORKER_READY" = false ]; then
    print_warning "⚠️  Video-Worker did not become ready within ${MAX_WAIT}s"
fi

# Wait for Dashboard
DASHBOARD_READY=false
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ] && [ "$DASHBOARD_READY" = false ]; do
    if pgrep -f "uvicorn.*main:app.*${DASHBOARD_PORT}" > /dev/null; then
        if curl -s -f "http://localhost:${DASHBOARD_PORT}/" > /dev/null 2>&1; then
            DASHBOARD_READY=true
            print_success "✅ Dashboard is ready (${ELAPSED}s)"
            break
        fi
    fi
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
    if [ $((ELAPSED % 10)) -eq 0 ]; then
        print_status "   Waiting for Dashboard... (${ELAPSED}s/${MAX_WAIT}s)"
    fi
done

if [ "$DASHBOARD_READY" = false ]; then
    print_warning "⚠️  Dashboard did not become ready within ${MAX_WAIT}s"
fi

echo ""

# ============================================
# Part 5: Initial Health Check
# ============================================
print_header "5. Initial Health Check (Immediate)"

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

# Check Video-Worker (try multiple patterns)
WORKER_RUNNING=false
for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker"; do
    if pgrep -f "$pattern" > /dev/null; then
        WORKER_RUNNING=true
        break
    fi
done

if [ "$WORKER_RUNNING" = true ]; then
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
# Part 6: Delayed Health Check (10 seconds)
# ============================================
print_header "6. Delayed Health Check (After 10 seconds)"

print_status "Waiting 10 seconds before final health check..."
sleep 10
echo ""

# Check MainAPI again
API_STILL_RUNNING=false
if pgrep -f "uvicorn.*app.main.*${API_PORT}" > /dev/null; then
    API_STILL_RUNNING=true
    API_RESPONSE=$(curl -s -m 3 "http://localhost:${API_PORT}/health" 2>&1 || echo "ERROR")
    if echo "$API_RESPONSE" | grep -q "healthy\|status"; then
        print_success "✅ MainAPI: Still running and healthy"
    else
        print_warning "⚠️  MainAPI: Running but health check failed"
    fi
else
    print_error "❌ MainAPI: DIED after start!"
fi

# Check Video-Worker again
WORKER_STILL_RUNNING=false
for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker"; do
    if pgrep -f "$pattern" > /dev/null; then
        WORKER_STILL_RUNNING=true
        break
    fi
done

if [ "$WORKER_STILL_RUNNING" = true ]; then
    print_success "✅ Video-Worker: Still running"
else
    print_error "❌ Video-Worker: DIED after start!"
fi

# Check Dashboard again
DASHBOARD_STILL_RUNNING=false
if pgrep -f "uvicorn.*main:app.*${DASHBOARD_PORT}" > /dev/null; then
    DASHBOARD_STILL_RUNNING=true
    DASHBOARD_RESPONSE=$(curl -s -m 3 "http://localhost:${DASHBOARD_PORT}/" 2>&1 || echo "ERROR")
    if echo "$DASHBOARD_RESPONSE" | grep -q "Transcription\|dashboard\|html"; then
        print_success "✅ Dashboard: Still running and responding"
    else
        print_warning "⚠️  Dashboard: Running but not responding"
    fi
else
    print_error "❌ Dashboard: DIED after start!"
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

# Check Video-Worker (try multiple patterns)
WORKER_RUNNING=false
for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker"; do
    if pgrep -f "$pattern" > /dev/null; then
        WORKER_RUNNING=true
        break
    fi
done

if [ "$WORKER_RUNNING" = true ]; then
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

