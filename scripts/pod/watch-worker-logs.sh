#!/bin/bash
# Script สำหรับ watch worker logs แบบ multi-file (main log + error log)
# ใช้ multitail หรือ tail -f แบบ parallel

set -e

cd /workspace/transcription-service 2>/dev/null || cd /workspace/transcription-close-caption-service 2>/dev/null || {
    echo "❌ Cannot find project directory"
    exit 1
}

# Log file locations
LEGACY_LOG="/tmp/video-worker.log"
CURRENT_LOG="logs/video-worker.log"
ERROR_LOG="logs/video-worker-errors.log"

# Determine active log
ACTIVE_LOG=""
if [ -f "$CURRENT_LOG" ]; then
    ACTIVE_LOG="$CURRENT_LOG"
elif [ -f "$LEGACY_LOG" ]; then
    ACTIVE_LOG="$LEGACY_LOG"
else
    echo "❌ ไม่พบ log file"
    exit 1
fi

# Check if multitail is available
if command -v multitail > /dev/null 2>&1; then
    echo "📋 Using multitail to watch logs..."
    echo ""
    
    if [ -f "$ERROR_LOG" ]; then
        multitail -s 2 \
            -ci green "$ACTIVE_LOG" \
            -ci red "$ERROR_LOG"
    else
        multitail -s 1 \
            -ci green "$ACTIVE_LOG"
    fi
else
    # Fallback: use tail -f for both files
    echo "📋 Watching logs (Press Ctrl+C to stop)..."
    echo "   Main log: $ACTIVE_LOG"
    if [ -f "$ERROR_LOG" ]; then
        echo "   Error log: $ERROR_LOG"
    fi
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    if [ -f "$ERROR_LOG" ]; then
        # Use a simple approach: tail both files
        # Note: This will mix output, but it's better than nothing
        (
            tail -f "$ACTIVE_LOG" 2>/dev/null &
            TAIL_PID1=$!
            tail -f "$ERROR_LOG" 2>/dev/null &
            TAIL_PID2=$!
            wait $TAIL_PID1 $TAIL_PID2
        )
    else
        tail -f "$ACTIVE_LOG" 2>/dev/null
    fi
fi

