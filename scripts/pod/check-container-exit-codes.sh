#!/bin/bash
# Script สำหรับตรวจสอบ Container Exit Codes และ OOM
# ใช้สำหรับหาต้นเหตุ SIGTERM/SIGKILL

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

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔍 Container Exit Code & OOM Checker                       ║"
echo "║  เวลา: $(date '+%Y-%m-%d %H:%M:%S')                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if running in container
if [ -f /.dockerenv ] || [ -n "$CONTAINER_ID" ]; then
    print_info "Running inside container"
    CONTAINER_ID=$(hostname)
else
    print_info "Running on host - checking for containers..."
    
    # Try to find video-worker container
    CONTAINER_ID=$(docker ps -a --filter "name=video-worker" --format "{{.ID}}" | head -1)
    if [ -z "$CONTAINER_ID" ]; then
        # Try to find any transcription-service container
        CONTAINER_ID=$(docker ps -a --filter "name=transcription" --format "{{.ID}}" | head -1)
    fi
fi

if [ -z "$CONTAINER_ID" ]; then
    print_warning "No container found - checking current process..."
    
    # Check current process exit status
    if [ -n "$PPID" ]; then
        print_info "Parent process ID: $PPID"
    fi
    
    # Check if we can access docker
    if command -v docker > /dev/null 2>&1; then
        print_info "Checking all containers..."
        docker ps -a --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.ExitCode}}" | head -20
    else
        print_warning "Docker not available - cannot check container exit codes"
    fi
    exit 0
fi

print_info "Container ID: $CONTAINER_ID"

# Check container status
if command -v docker > /dev/null 2>&1; then
    print_info "Checking container exit codes..."
    echo ""
    
    # Get container info
    EXIT_CODE=$(docker inspect "$CONTAINER_ID" --format '{{.State.ExitCode}}' 2>/dev/null || echo "N/A")
    FINISHED_AT=$(docker inspect "$CONTAINER_ID" --format '{{.State.FinishedAt}}' 2>/dev/null || echo "N/A")
    OOM_KILLED=$(docker inspect "$CONTAINER_ID" --format '{{.State.OOMKilled}}' 2>/dev/null || echo "N/A")
    ERROR=$(docker inspect "$CONTAINER_ID" --format '{{.State.Error}}' 2>/dev/null || echo "N/A")
    STATUS=$(docker inspect "$CONTAINER_ID" --format '{{.State.Status}}' 2>/dev/null || echo "N/A")
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 Container Status:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "   Status: $STATUS"
    echo "   Exit Code: $EXIT_CODE"
    echo "   OOM Killed: $OOM_KILLED"
    echo "   Finished At: $FINISHED_AT"
    echo "   Error: $ERROR"
    echo ""
    
    # Interpret exit codes
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔍 Exit Code Interpretation:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    case "$EXIT_CODE" in
        0)
            print_success "Exit Code 0: Normal exit (no error)"
            ;;
        143)
            print_warning "Exit Code 143: SIGTERM (15) - Process was terminated gracefully"
            echo "   → Likely causes:"
            echo "     - Platform idle timeout (RunPod scale-to-zero)"
            echo "     - Health check failure"
            echo "     - Manual restart/stop"
            echo "     - Resource limits"
            ;;
        137)
            print_error "Exit Code 137: SIGKILL (9) - Process was killed forcefully"
            echo "   → Likely causes:"
            echo "     - OOM (Out of Memory)"
            echo "     - Platform forced termination"
            echo "     - System resource exhaustion"
            ;;
        130)
            print_info "Exit Code 130: SIGINT (2) - Process was interrupted (Ctrl+C)"
            ;;
        *)
            if [ "$EXIT_CODE" != "N/A" ]; then
                print_warning "Exit Code $EXIT_CODE: Unknown exit code"
            fi
            ;;
    esac
    
    echo ""
    
    # Check OOM
    if [ "$OOM_KILLED" = "true" ]; then
        print_error "⚠️  OOM Killed: Container was killed due to Out of Memory!"
        echo "   → Solution: Reduce memory usage or increase container memory limit"
    else
        print_success "OOM Killed: false (no memory issues)"
    fi
    
    echo ""
    
    # Check recent container logs for SIGTERM
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📋 Recent Container Logs (SIGTERM/SIGKILL):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    docker logs "$CONTAINER_ID" --tail 50 2>&1 | grep -iE "SIGTERM|SIGKILL|signal.*15|signal.*9|terminated|killed" || echo "   No SIGTERM/SIGKILL found in recent logs"
    
    echo ""
    
    # Check system logs
    if [ -f /var/log/syslog ] || [ -f /var/log/messages ]; then
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📋 System Logs (OOM Killer):"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        if [ -f /var/log/syslog ]; then
            grep -i "oom\|killed process" /var/log/syslog | tail -5 || echo "   No OOM events found"
        elif [ -f /var/log/messages ]; then
            grep -i "oom\|killed process" /var/log/messages | tail -5 || echo "   No OOM events found"
        fi
    fi
    
else
    print_warning "Docker not available - cannot check container exit codes"
    print_info "Running process check instead..."
    
    # Check current process
    if [ -n "$$" ]; then
        print_info "Current PID: $$"
        if ps -p $$ > /dev/null 2>&1; then
            print_success "Process is running"
        else
            print_error "Process is not running"
        fi
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Check completed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

