#!/bin/bash
# Script สำหรับดู Logs ทั้งหมดพร้อมกัน (tail multiple files)
#
# วิธีใช้งาน:
#   bash scripts/pod/tail-all-logs.sh [OPTIONS]
#
# Options:
#   -f, --follow    Follow log output (default)
#   -n, --lines N   Show last N lines (default: 50)
#   -a, --api-only  Show API logs only
#   -w, --worker-only  Show worker logs only
#   -q, --quiet     Suppress file headers

set -e

# Default values
FOLLOW=true
LINES=50
SHOW_API=true
SHOW_WORKER=true
QUIET=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -n|--lines)
            LINES="$2"
            shift 2
            ;;
        -a|--api-only)
            SHOW_WORKER=false
            shift
            ;;
        -w|--worker-only)
            SHOW_API=false
            shift
            ;;
        -q|--quiet)
            QUIET=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -f, --follow         Follow log output (default)"
            echo "  -n, --lines N        Show last N lines (default: 50)"
            echo "  -a, --api-only       Show API logs only"
            echo "  -w, --worker-only    Show worker logs only"
            echo "  -q, --quiet          Suppress file headers"
            echo ""
            echo "Examples:"
            echo "  $0                   # Show all logs, follow mode"
            echo "  $0 -n 100            # Show last 100 lines"
            echo "  $0 --api-only        # Show API logs only"
            echo "  $0 --worker-only -n 200  # Show worker logs, 200 lines"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Log files
API_LOG="/tmp/transcription-service.log"
WORKER_LOG="/tmp/video-worker.log"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  📋 Tail All Logs - Transcription Service                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Function to tail with color
tail_log() {
    local file=$1
    local name=$2
    local color=$3
    
    if [ ! -f "$file" ]; then
        echo -e "${YELLOW}⚠️  File not found: $file${NC}"
        return
    fi
    
    if [ "$QUIET" = false ]; then
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${color}📄 $name${NC} ($file)"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    fi
    
    if [ "$FOLLOW" = true ]; then
        tail -f -n "$LINES" "$file" | sed "s/^/$color[$name]$NC /"
    else
        tail -n "$LINES" "$file" | sed "s/^/$color[$name]$NC /"
    fi
}

# Check if any log files exist
if [ "$SHOW_API" = true ] && [ ! -f "$API_LOG" ]; then
    echo -e "${YELLOW}⚠️  API log not found: $API_LOG${NC}"
    SHOW_API=false
fi

if [ "$SHOW_WORKER" = true ] && [ ! -f "$WORKER_LOG" ]; then
    echo -e "${YELLOW}⚠️  Worker log not found: $WORKER_LOG${NC}"
    SHOW_WORKER=false
fi

if [ "$SHOW_API" = false ] && [ "$SHOW_WORKER" = false ]; then
    echo -e "${YELLOW}⚠️  No log files found${NC}"
    exit 1
fi

# If following, use multitail if available, otherwise run tails in parallel
if [ "$FOLLOW" = true ]; then
    # Check if multitail is available
    if command -v multitail > /dev/null 2>&1; then
        if [ "$SHOW_API" = true ] && [ "$SHOW_WORKER" = true ]; then
            multitail -s 2 \
                -cT ansi "$API_LOG" \
                -cT ansi "$WORKER_LOG"
        elif [ "$SHOW_API" = true ]; then
            tail -f -n "$LINES" "$API_LOG"
        elif [ "$SHOW_WORKER" = true ]; then
            tail -f -n "$LINES" "$WORKER_LOG"
        fi
    else
        # Fallback: run multiple tails in parallel
        if [ "$SHOW_API" = true ] && [ "$SHOW_WORKER" = true ]; then
            (
                tail_log "$API_LOG" "API" "$GREEN" &
                tail_log "$WORKER_LOG" "WORKER" "$BLUE" &
                wait
            )
        elif [ "$SHOW_API" = true ]; then
            tail_log "$API_LOG" "API" "$GREEN"
        elif [ "$SHOW_WORKER" = true ]; then
            tail_log "$WORKER_LOG" "WORKER" "$BLUE"
        fi
    fi
else
    # Not following, show both sequentially
    if [ "$SHOW_API" = true ]; then
        tail_log "$API_LOG" "API" "$GREEN"
        echo ""
    fi
    
    if [ "$SHOW_WORKER" = true ]; then
        tail_log "$WORKER_LOG" "WORKER" "$BLUE"
    fi
fi

