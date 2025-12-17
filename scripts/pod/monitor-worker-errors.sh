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

# Check worker process
WORKER_PID=$(pgrep -f "python.*video_worker" | head -1 || echo "")
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
    
    # If uptime is less than 5 minutes, might be a recent restart
    UPTIME_MINUTES=$(echo "$UPTIME" | grep -oE "[0-9]+:[0-9]+" | head -1 | cut -d: -f1 || echo "999")
    if [ "$UPTIME_MINUTES" -lt 5 ] && [ "$UPTIME_MINUTES" != "999" ]; then
        print_warning "Worker restarted recently (uptime: $UPTIME)"
        CRASH_INDICATORS=$((CRASH_INDICATORS + 1))
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

if [ "$ERROR_COUNT" -eq 0 ] && [ "$CRASH_INDICATORS" -eq 0 ]; then
    print_success "No issues detected"
    echo "$MONITOR_ENTRY - Status: OK" >> "$MONITOR_LOG"
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

