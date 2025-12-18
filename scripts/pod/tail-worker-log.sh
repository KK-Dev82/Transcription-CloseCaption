#!/bin/bash
# Script สำหรับติดตาม Video Worker Logs แบบ real-time
# ตรวจสอบ log file ทั้ง 2 ที่ (legacy และ current) และแสดง log ที่ active

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

cd /workspace/transcription-service 2>/dev/null || cd /workspace/transcription-close-caption-service 2>/dev/null || {
    echo "❌ Cannot find project directory"
    exit 1
}

# Log file locations
LEGACY_LOG="/tmp/video-worker.log"
CURRENT_LOG="logs/video-worker.log"
ERROR_LOG="logs/video-worker-errors.log"

# Check which log file exists and is active
ACTIVE_LOG=""
LOG_TYPE=""

if [ -f "$CURRENT_LOG" ]; then
    # Check if current log is recent (modified in last 5 minutes)
    if [ -n "$(find "$(dirname "$CURRENT_LOG")" -name "$(basename "$CURRENT_LOG")" -mmin -5 2>/dev/null)" ]; then
        ACTIVE_LOG="$CURRENT_LOG"
        LOG_TYPE="current"
    elif [ -f "$LEGACY_LOG" ]; then
        # Check if legacy log is recent
        if [ -n "$(find "$(dirname "$LEGACY_LOG")" -name "$(basename "$LEGACY_LOG")" -mmin -5 2>/dev/null)" ]; then
            ACTIVE_LOG="$LEGACY_LOG"
            LOG_TYPE="legacy"
        else
            # Use current log even if not recent
            ACTIVE_LOG="$CURRENT_LOG"
            LOG_TYPE="current (stale)"
        fi
    else
        ACTIVE_LOG="$CURRENT_LOG"
        LOG_TYPE="current"
    fi
elif [ -f "$LEGACY_LOG" ]; then
    ACTIVE_LOG="$LEGACY_LOG"
    LOG_TYPE="legacy"
else
    print_warning "ไม่พบ log file ทั้ง 2 ที่"
    echo "   Expected locations:"
    echo "   - $CURRENT_LOG"
    echo "   - $LEGACY_LOG"
    exit 1
fi

# Check if worker is running
WORKER_RUNNING=false
for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker"; do
    if pgrep -f "$pattern" > /dev/null; then
        WORKER_RUNNING=true
        break
    fi
done

if [ "$WORKER_RUNNING" = false ]; then
    print_warning "Worker ไม่ได้ทำงานอยู่"
    echo ""
    echo "💡 แนะนำ:"
    echo "   bash scripts/pod/start-service-daemon.sh"
    echo ""
fi

# Show log info
print_info "Using log file: $ACTIVE_LOG (type: $LOG_TYPE)"
if [ -f "$ERROR_LOG" ]; then
    print_info "Error log: $ERROR_LOG"
fi
echo ""

# Show last few lines before tailing
if [ -f "$ACTIVE_LOG" ]; then
    LOG_SIZE=$(wc -l < "$ACTIVE_LOG" 2>/dev/null || echo "0")
    print_info "Log file size: $LOG_SIZE lines"
    echo ""
    print_info "Last 10 lines before tailing:"
    tail -10 "$ACTIVE_LOG" 2>/dev/null | sed 's/^/   | /'
    echo ""
    print_info "Starting tail -f (Press Ctrl+C to stop)..."
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Tail the log file
    tail -f "$ACTIVE_LOG" 2>/dev/null || {
        print_warning "Cannot tail log file. Trying to read it..."
        tail -50 "$ACTIVE_LOG" 2>/dev/null || echo "Cannot read log file"
    }
else
    print_warning "Log file not found: $ACTIVE_LOG"
    echo ""
    echo "💡 Check if worker is running:"
    echo "   ps aux | grep video_worker"
    echo ""
    echo "💡 Start worker:"
    echo "   bash scripts/pod/start-service-daemon.sh"
fi

