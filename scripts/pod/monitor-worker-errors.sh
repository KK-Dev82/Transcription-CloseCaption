#!/bin/bash
# Worker Error Monitoring Script
# ติดตาม error logs และแจ้งเตือนเมื่อพบปัญหา

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Log files
WORKER_LOG="logs/video-worker.log"
WORKER_ERROR_LOG="logs/video-worker-errors.log"
MONITOR_LOG="logs/worker-monitor.log"
ALERT_LOG="logs/worker-alerts.log"

mkdir -p logs

# Function to analyze errors
analyze_errors() {
    local log_file=$1
    local lines=${2:-100}
    
    if [ ! -f "$log_file" ]; then
        echo "0"
        return
    fi
    
    # Count different error types (ensure single number output)
    local count=$(tail -$lines "$log_file" 2>/dev/null | grep -cE "ERROR|CRITICAL|Fatal|Exception|Traceback" 2>/dev/null || echo "0")
    # Remove any newlines and ensure it's a number
    count=$(echo "$count" | tr -d '\n' | head -1)
    [ -z "$count" ] && count=0
    echo "$count"
}

# Function to check for specific error patterns
check_error_patterns() {
    local log_file=$1
    local lines=${2:-100}
    
    if [ ! -f "$log_file" ]; then
        return 1
    fi
    
    # Check for critical error patterns
    local patterns=(
        "RabbitMQ.*connection.*lost"
        "Channel.*closed"
        "Out of memory"
        "CUDA.*error"
        "GPU.*error"
        "Signal.*15"
        "Worker.*crash"
        "Fatal.*error"
    )
    
    for pattern in "${patterns[@]}"; do
        if tail -$lines "$log_file" 2>/dev/null | grep -qiE "$pattern"; then
            echo "$pattern"
            return 0
        fi
    done
    
    return 1
}

# Main monitoring
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  📊 Worker Error Monitoring                                  ║"
echo "║  เวลา: $(date '+%Y-%m-%d %H:%M:%S')                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check worker process (use same logic as worker-health-check.sh)
WORKER_PID=""
for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker" "video_worker"; do
    WORKER_PID=$(pgrep -f "$pattern" 2>/dev/null | head -1)
    if [ -n "$WORKER_PID" ]; then
        break
    fi
done

# If still not found, try checking PID file
if [ -z "$WORKER_PID" ] && [ -f "/tmp/video-worker.pid" ]; then
    PID_FROM_FILE=$(cat /tmp/video-worker.pid 2>/dev/null | tr -d '[:space:]')
    if [ -n "$PID_FROM_FILE" ] && ps -p "$PID_FROM_FILE" > /dev/null 2>&1; then
        WORKER_PID="$PID_FROM_FILE"
    fi
fi

if [ -z "$WORKER_PID" ]; then
    print_error "Worker process not running"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ALERT: Worker process not running" >> "$ALERT_LOG"
    exit 1
else
    print_success "Worker process running (PID: $WORKER_PID)"
fi

# Analyze error logs
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Error Analysis (Last 100 lines)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ERROR_COUNT=0
CRITICAL_PATTERN=""

if [ -f "$WORKER_ERROR_LOG" ]; then
    ERROR_COUNT=$(analyze_errors "$WORKER_ERROR_LOG" 100)
    # Ensure ERROR_COUNT is a number
    ERROR_COUNT=$(echo "$ERROR_COUNT" | tr -d '\n' | head -1)
    [ -z "$ERROR_COUNT" ] && ERROR_COUNT=0
    ERROR_COUNT=$((ERROR_COUNT + 0))
    
    CRITICAL_PATTERN=$(check_error_patterns "$WORKER_ERROR_LOG" 100 || echo "")
    
    print_info "Error log: $WORKER_ERROR_LOG"
    print_info "Errors in last 100 lines: $ERROR_COUNT"
    
    if [ -n "$CRITICAL_PATTERN" ]; then
        print_error "Critical pattern detected: $CRITICAL_PATTERN"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - CRITICAL: $CRITICAL_PATTERN" >> "$ALERT_LOG"
    fi
else
    print_warning "Error log file not found: $WORKER_ERROR_LOG"
    ERROR_COUNT=0
fi

# Check main log for errors too
if [ -f "$WORKER_LOG" ]; then
    MAIN_ERROR_COUNT=$(analyze_errors "$WORKER_LOG" 100)
    # Ensure MAIN_ERROR_COUNT is a number
    MAIN_ERROR_COUNT=$(echo "$MAIN_ERROR_COUNT" | tr -d '\n' | head -1)
    [ -z "$MAIN_ERROR_COUNT" ] && MAIN_ERROR_COUNT=0
    MAIN_ERROR_COUNT=$((MAIN_ERROR_COUNT + 0))
    
    print_info "Main log: $WORKER_LOG"
    print_info "Errors in last 100 lines: $MAIN_ERROR_COUNT"
    ERROR_COUNT=$((ERROR_COUNT + MAIN_ERROR_COUNT))
    
    MAIN_CRITICAL_PATTERN=$(check_error_patterns "$WORKER_LOG" 100 || echo "")
    if [ -n "$MAIN_CRITICAL_PATTERN" ]; then
        print_error "Critical pattern in main log: $MAIN_CRITICAL_PATTERN"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - CRITICAL: $MAIN_CRITICAL_PATTERN (main log)" >> "$ALERT_LOG"
    fi
else
    # If main log doesn't exist, ensure ERROR_COUNT is set
    [ -z "$ERROR_COUNT" ] && ERROR_COUNT=0
fi

# Check for recent crashes
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Crash Detection"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CRASH_INDICATORS=0

# Check for signal 15 (SIGTERM) in logs
if [ -f "$WORKER_LOG" ]; then
    SIGTERM_COUNT=$(tail -200 "$WORKER_LOG" 2>/dev/null | grep -cE "signal.*15|SIGTERM" 2>/dev/null || echo "0")
    SIGTERM_COUNT=$(echo "$SIGTERM_COUNT" | tr -d '\n' | head -1)
    [ -z "$SIGTERM_COUNT" ] && SIGTERM_COUNT=0
    SIGTERM_COUNT=$((SIGTERM_COUNT + 0))
    if [ "$SIGTERM_COUNT" -gt 0 ]; then
        print_warning "Found $SIGTERM_COUNT SIGTERM signal(s) in last 200 lines"
        CRASH_INDICATORS=$((CRASH_INDICATORS + SIGTERM_COUNT))
    fi
fi

# Check for "Worker.*crash" or "Fatal.*error"
if [ -f "$WORKER_ERROR_LOG" ]; then
    FATAL_COUNT=$(tail -200 "$WORKER_ERROR_LOG" 2>/dev/null | grep -cE "Worker.*crash|Fatal.*error" 2>/dev/null || echo "0")
    FATAL_COUNT=$(echo "$FATAL_COUNT" | tr -d '\n' | head -1)
    [ -z "$FATAL_COUNT" ] && FATAL_COUNT=0
    FATAL_COUNT=$((FATAL_COUNT + 0))
    if [ "$FATAL_COUNT" -gt 0 ]; then
        print_warning "Found $FATAL_COUNT fatal error(s) in last 200 lines"
        CRASH_INDICATORS=$((CRASH_INDICATORS + FATAL_COUNT))
    fi
fi

# Check worker uptime
if [ -n "$WORKER_PID" ]; then
    UPTIME=$(ps -o etime= -p "$WORKER_PID" 2>/dev/null | tr -d ' ' || echo "unknown")
    print_info "Worker uptime: $UPTIME"
    
    # Parse uptime to minutes
    # Format can be: "MM:SS" or "HH:MM:SS" or "DD-HH:MM:SS"
    UPTIME_MINUTES=999
    if echo "$UPTIME" | grep -qE "^[0-9]+:[0-9]+:[0-9]+$"; then
        # HH:MM:SS format
        HOURS=$(echo "$UPTIME" | cut -d: -f1)
        MINUTES=$(echo "$UPTIME" | cut -d: -f2)
        UPTIME_MINUTES=$((HOURS * 60 + MINUTES))
    elif echo "$UPTIME" | grep -qE "^[0-9]+:[0-9]+$"; then
        # MM:SS format
        UPTIME_MINUTES=$(echo "$UPTIME" | cut -d: -f1)
    elif echo "$UPTIME" | grep -qE "^[0-9]+-[0-9]+:[0-9]+:[0-9]+$"; then
        # DD-HH:MM:SS format
        DAYS=$(echo "$UPTIME" | cut -d- -f1)
        HOURS=$(echo "$UPTIME" | cut -d: -f1 | cut -d- -f2)
        MINUTES=$(echo "$UPTIME" | cut -d: -f2)
        UPTIME_MINUTES=$((DAYS * 24 * 60 + HOURS * 60 + MINUTES))
    fi
    
    # Only count as crash indicator if uptime is less than 2 minutes AND there are actual errors
    # (Restart from script is normal, but crash + auto-restart within 2 min is suspicious)
    if [ "$UPTIME_MINUTES" -lt 2 ] && [ "$UPTIME_MINUTES" != "999" ] && [ "$ERROR_COUNT" -gt 0 ]; then
        print_warning "Worker restarted recently (uptime: $UPTIME) with errors - possible crash"
        CRASH_INDICATORS=$((CRASH_INDICATORS + 1))
    elif [ "$UPTIME_MINUTES" -lt 2 ] && [ "$UPTIME_MINUTES" != "999" ]; then
        print_info "Worker restarted recently (uptime: $UPTIME) - likely normal restart"
        # Don't count as crash indicator if no errors
    fi
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Ensure ERROR_COUNT and CRASH_INDICATORS are numbers
ERROR_COUNT=$(echo "$ERROR_COUNT" | tr -d '\n' | head -1)
[ -z "$ERROR_COUNT" ] && ERROR_COUNT=0
ERROR_COUNT=$((ERROR_COUNT + 0))

CRASH_INDICATORS=$(echo "$CRASH_INDICATORS" | tr -d '\n' | head -1)
[ -z "$CRASH_INDICATORS" ] && CRASH_INDICATORS=0
CRASH_INDICATORS=$((CRASH_INDICATORS + 0))

# Log monitoring results
MONITOR_ENTRY="$(date '+%Y-%m-%d %H:%M:%S') - Errors: $ERROR_COUNT, Crash indicators: $CRASH_INDICATORS"
echo "$MONITOR_ENTRY" >> "$MONITOR_LOG"

# Determine status based on errors and crash indicators
if [ "$ERROR_COUNT" -eq 0 ] && [ "$CRASH_INDICATORS" -eq 0 ]; then
    print_success "No issues detected"
    echo "$MONITOR_ENTRY - Status: OK" >> "$MONITOR_LOG"
    exit 0
elif [ "$ERROR_COUNT" -eq 0 ] && [ "$CRASH_INDICATORS" -gt 0 ]; then
    # If no errors but has crash indicators (like recent restart), it's likely normal
    print_success "No issues detected (recent restart is normal)"
    echo "$MONITOR_ENTRY - Status: OK (normal restart)" >> "$MONITOR_LOG"
    exit 0
elif [ "$ERROR_COUNT" -lt 5 ] && [ "$CRASH_INDICATORS" -eq 0 ]; then
    print_warning "Minor issues detected (Errors: $ERROR_COUNT)"
    echo "$MONITOR_ENTRY - Status: WARNING" >> "$MONITOR_LOG"
    exit 0
else
    print_error "Issues detected (Errors: $ERROR_COUNT, Crash indicators: $CRASH_INDICATORS)"
    echo "$MONITOR_ENTRY - Status: ALERT" >> "$MONITOR_LOG"
    
    # Show recent errors
    if [ -f "$WORKER_ERROR_LOG" ]; then
        echo ""
        print_info "Recent errors:"
        tail -10 "$WORKER_ERROR_LOG" 2>/dev/null | grep -E "ERROR|CRITICAL|Fatal" | tail -5 || true
    fi
    
    exit 1
fi

