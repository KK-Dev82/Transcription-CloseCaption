#!/bin/bash
# Script สำหรับ Monitor SIGTERM และ Tracking ทั้ง Main API และ Video Worker
# ใช้สำหรับหาต้นเหตุ SIGTERM

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

cd /workspace/transcription-service || exit 1

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔍 SIGTERM Monitor & Tracking System                       ║"
echo "║  เวลา: $(date '+%Y-%m-%d %H:%M:%S')                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Create monitoring log file
MONITOR_LOG="logs/sigterm-monitor.log"
mkdir -p logs
touch "$MONITOR_LOG"

# Function to log with timestamp
log_event() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$MONITOR_LOG"
}

print_info "Starting SIGTERM monitoring..."
log_event "SIGTERM Monitor started"

# Check Main API
print_info "Checking Main API..."
MAIN_API_PID=$(pgrep -f "uvicorn.*app.main" | head -1)
if [ -n "$MAIN_API_PID" ]; then
    MAIN_API_UPTIME=$(ps -o etime= -p "$MAIN_API_PID" 2>/dev/null | tr -d ' ' || echo "unknown")
    print_success "Main API running (PID: $MAIN_API_PID, Uptime: $MAIN_API_UPTIME)"
    log_event "Main API: PID=$MAIN_API_PID, Uptime=$MAIN_API_UPTIME"
else
    print_warning "Main API not running"
    log_event "Main API: NOT RUNNING"
fi

# Check Video Worker
print_info "Checking Video Worker..."
WORKER_PID=$(pgrep -f "app.workers.*video_worker" | head -1)
if [ -n "$WORKER_PID" ]; then
    WORKER_UPTIME=$(ps -o etime= -p "$WORKER_PID" 2>/dev/null | tr -d ' ' || echo "unknown")
    print_success "Video Worker running (PID: $WORKER_PID, Uptime: $WORKER_UPTIME)"
    log_event "Video Worker: PID=$WORKER_PID, Uptime=$WORKER_UPTIME"
else
    print_warning "Video Worker not running"
    log_event "Video Worker: NOT RUNNING"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Recent SIGTERM Events (from logs):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check worker logs for SIGTERM
if [ -f "logs/video-worker-errors.log" ]; then
    SIGTERM_COUNT=$(grep -cE "SIGTERM|signal.*15" logs/video-worker-errors.log 2>/dev/null || echo "0")
    if [ "$SIGTERM_COUNT" -gt 0 ]; then
        print_warning "Found $SIGTERM_COUNT SIGTERM event(s) in worker logs"
        echo ""
        echo "Recent SIGTERM events:"
        grep -E "SIGTERM|signal.*15" logs/video-worker-errors.log | tail -5 | while read -r line; do
            echo "   $line"
        done
    else
        print_success "No SIGTERM events found in worker logs"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Process Uptime Analysis:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Analyze uptime patterns
if [ -f "logs/video-worker-errors.log" ]; then
    # Extract start times and SIGTERM times
    START_TIMES=$(grep -E "Starting Video Worker|Video Worker พร้อมรับงาน" logs/video-worker-errors.log | tail -10)
    SIGTERM_TIMES=$(grep -E "SIGTERM|signal.*15" logs/video-worker-errors.log | tail -10)
    
    if [ -n "$SIGTERM_TIMES" ]; then
        print_warning "SIGTERM Pattern Analysis:"
        echo "$SIGTERM_TIMES" | while read -r line; do
            echo "   $line"
        done
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Container/Platform Check:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if running in container
if [ -f /.dockerenv ]; then
    print_info "Running in container (Pod Container)"
    log_event "Environment: Container detected"
    
    # Check container resource limits
    if [ -f /sys/fs/cgroup/memory/memory.limit_in_bytes ]; then
        MEMORY_LIMIT=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes)
        MEMORY_USAGE=$(cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null || echo "0")
        print_info "Memory Limit: $((MEMORY_LIMIT / 1024 / 1024))MB"
        print_info "Memory Usage: $((MEMORY_USAGE / 1024 / 1024))MB"
        log_event "Memory: Limit=$((MEMORY_LIMIT / 1024 / 1024))MB, Usage=$((MEMORY_USAGE / 1024 / 1024))MB"
    fi
else
    print_info "Running on host (not in container)"
    log_event "Environment: Host detected"
fi

# Check for RunPod-specific indicators
if [ -n "$RUNPOD_POD_ID" ] || [ -n "$RUNPOD_CPU_COUNT" ]; then
    print_info "RunPod environment detected"
    log_event "Platform: RunPod detected"
    
    if [ -n "$RUNPOD_POD_ID" ]; then
        print_info "Pod ID: $RUNPOD_POD_ID"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💡 Recommendations:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Check container exit codes:"
echo "   bash scripts/pod/check-container-exit-codes.sh"
echo ""
echo "2. Monitor heartbeat logs (should appear every 25 seconds):"
echo "   tail -f logs/video-worker-errors.log | grep Heartbeat"
echo ""
echo "3. Check RunPod settings:"
echo "   - Idle timeout / scale-to-zero"
echo "   - Health check policy"
echo "   - Max execution time"
echo "   - Spot / interruptible settings"
echo ""
echo "4. Monitor log file:"
echo "   tail -f $MONITOR_LOG"
echo ""

log_event "SIGTERM Monitor check completed"
print_success "Monitoring completed - log saved to $MONITOR_LOG"

