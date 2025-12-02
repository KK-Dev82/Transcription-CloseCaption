#!/bin/bash
# Script สำหรับ Stop Transcription Service

set -e

PID_FILE="/tmp/transcription-service.pid"

echo "🛑 Stopping Transcription Service"
echo "=================================="
echo ""

# Method 1: Use PID file
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "Stopping service (PID: $PID)..."
        kill $PID
        sleep 2
        
        if ps -p $PID > /dev/null 2>&1; then
            echo "Force killing..."
            kill -9 $PID
        fi
        
        rm -f "$PID_FILE"
        echo "✅ Service stopped"
    else
        echo "⚠️  PID file exists but process not running"
        rm -f "$PID_FILE"
    fi
fi

# Method 2: Find by process name
PID=$(pgrep -f "uvicorn.*app.main:app.*8001" | head -1)
if [ ! -z "$PID" ]; then
    echo "Found running service (PID: $PID)..."
    kill $PID 2>/dev/null || kill -9 $PID
    echo "✅ Service stopped"
else
    echo "✅ No service running"
fi

echo ""
echo "Done"

