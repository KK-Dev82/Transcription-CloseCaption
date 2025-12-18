#!/bin/bash
# Script สำหรับตรวจสอบ Worker Health
#
# วิธีใช้งาน:
#   bash scripts/pod/check-worker-health.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
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

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

cd /workspace/transcription-service || exit 1

print_header "🔍 Check Worker Health"

# Check 1: Worker Process
echo ""
print_header "1. Worker Process Status"

WORKER_PID=""
for pattern in "python3.*-m.*app.workers" "python.*-m.*app.workers" "app.workers.async.video_worker" "app.workers.video_worker"; do
    WORKER_PID=$(pgrep -f "$pattern" | head -1 || echo "")
    if [ -n "$WORKER_PID" ]; then
        break
    fi
done

if [ -n "$WORKER_PID" ]; then
    print_success "Worker process found (PID: $WORKER_PID)"
    
    # Get process info
    PROCESS_INFO=$(ps -p "$WORKER_PID" -o pid,cmd,etime,stat --no-headers 2>/dev/null || echo "")
    if [ -n "$PROCESS_INFO" ]; then
        print_info "   Process Info: $PROCESS_INFO"
        
        # Check if process is using nohup
        if ps -p "$WORKER_PID" -o cmd --no-headers 2>/dev/null | grep -q "nohup"; then
            print_success "   ✅ Process started with nohup"
        else
            print_warning "   ⚠️  Process NOT started with nohup (may die when terminal closes)"
        fi
    fi
else
    print_error "Worker process NOT found"
    print_info "   💡 Start worker: bash scripts/pod/start-service-daemon.sh 8010"
fi

# Check 2: Health Endpoint
echo ""
print_header "2. Health Endpoint (Port 8030)"

HEALTH_PORT=8030
if curl -s -f "http://localhost:${HEALTH_PORT}/health" > /dev/null 2>&1; then
    HEALTH_RESPONSE=$(curl -s "http://localhost:${HEALTH_PORT}/health" 2>/dev/null)
    print_success "Health endpoint is responding"
    print_info "   Response: $HEALTH_RESPONSE"
    
    # Parse JSON response
    if echo "$HEALTH_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('status', 'unknown'))" 2>/dev/null | grep -q "running"; then
        print_success "   ✅ Worker status: running"
    else
        print_warning "   ⚠️  Worker status may not be 'running'"
    fi
else
    print_error "Health endpoint is NOT responding"
    if [ -n "$WORKER_PID" ]; then
        print_warning "   ⚠️  Worker process exists but health endpoint not responding"
        print_info "   💡 Worker may be starting up or health server failed to start"
    else
        print_info "   💡 Worker is not running"
    fi
fi

# Check 3: Worker Logs (Heartbeat)
echo ""
print_header "3. Worker Logs (Recent Heartbeat)"

WORKER_LOG="logs/video-worker.log"
if [ -f "$WORKER_LOG" ]; then
    LAST_HEARTBEAT=$(tail -100 "$WORKER_LOG" 2>/dev/null | grep -E "Heartbeat|Worker alive" | tail -1 || echo "")
    if [ -n "$LAST_HEARTBEAT" ]; then
        print_success "Recent heartbeat found in logs"
        print_info "   $LAST_HEARTBEAT"
        
        # Extract timestamp
        TIMESTAMP=$(echo "$LAST_HEARTBEAT" | grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}" | head -1 || echo "")
        if [ -n "$TIMESTAMP" ]; then
            print_info "   Last heartbeat: $TIMESTAMP"
        fi
    else
        print_warning "No recent heartbeat found in logs"
    fi
else
    print_warning "Worker log file not found: $WORKER_LOG"
fi

# Check 4: PID File
echo ""
print_header "4. PID File Status"

WORKER_PID_FILE="/tmp/video-worker.pid"
if [ -f "$WORKER_PID_FILE" ]; then
    PID_FROM_FILE=$(cat "$WORKER_PID_FILE" 2>/dev/null || echo "")
    if [ -n "$PID_FROM_FILE" ]; then
        print_info "PID file exists: $WORKER_PID_FILE"
        print_info "   PID from file: $PID_FROM_FILE"
        
        if ps -p "$PID_FROM_FILE" > /dev/null 2>&1; then
            print_success "   ✅ PID from file is valid (process running)"
        else
            print_warning "   ⚠️  PID from file is invalid (process not found)"
            print_info "   💡 PID file may be stale"
        fi
    else
        print_warning "PID file is empty"
    fi
else
    print_warning "PID file not found: $WORKER_PID_FILE"
fi

# Summary
echo ""
print_header "📋 Summary"

if [ -n "$WORKER_PID" ] && curl -s -f "http://localhost:${HEALTH_PORT}/health" > /dev/null 2>&1; then
    print_success "✅ Worker is healthy and running"
    print_info "   PID: $WORKER_PID"
    print_info "   Health: http://localhost:${HEALTH_PORT}/health"
elif [ -n "$WORKER_PID" ]; then
    print_warning "⚠️  Worker process exists but health endpoint not responding"
    print_info "   PID: $WORKER_PID"
    print_info "   💡 Worker may be starting up or health server failed"
else
    print_error "❌ Worker is NOT running"
    print_info "   💡 Start worker: bash scripts/pod/start-service-daemon.sh 8010"
fi

echo ""

