#!/bin/bash

# Stop All Services
# Usage: ./scripts/stop-all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

LOG_DIR="$PROJECT_DIR/logs"

echo "🛑 Stopping All Services..."

# Stop API
if [ -f "$LOG_DIR/api.pid" ]; then
    API_PID=$(cat "$LOG_DIR/api.pid")
    if ps -p "$API_PID" > /dev/null 2>&1; then
        echo "   Stopping API (PID: $API_PID)..."
        kill "$API_PID"
        rm "$LOG_DIR/api.pid"
    else
        echo "   API not running"
    fi
fi

# Stop Worker
if [ -f "$LOG_DIR/worker.pid" ]; then
    WORKER_PID=$(cat "$LOG_DIR/worker.pid")
    if ps -p "$WORKER_PID" > /dev/null 2>&1; then
        echo "   Stopping Worker (PID: $WORKER_PID)..."
        kill "$WORKER_PID"
        rm "$LOG_DIR/worker.pid"
    else
        echo "   Worker not running"
    fi
fi

echo "✅ All services stopped!"

