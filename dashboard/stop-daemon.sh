#!/bin/bash
# Script สำหรับหยุด Dashboard ที่รันแบบ Daemon

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PID_FILE="logs/dashboard.pid"

if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}⚠️  Dashboard is not running (PID file not found)${NC}"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ! ps -p "$PID" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Dashboard process not found (PID: $PID)${NC}"
    echo "   Cleaning up stale PID file..."
    rm -f "$PID_FILE"
    exit 0
fi

echo -e "${GREEN}🛑 Stopping Dashboard (PID: $PID)...${NC}"

# Try graceful shutdown first
kill "$PID" 2>/dev/null || true

# Wait for process to stop
for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Dashboard stopped successfully${NC}"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

# Force kill if still running
if ps -p "$PID" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Force killing Dashboard...${NC}"
    kill -9 "$PID" 2>/dev/null || true
    sleep 1
fi

# Clean up
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Dashboard stopped${NC}"
    rm -f "$PID_FILE"
else
    echo -e "${RED}❌ Failed to stop Dashboard${NC}"
    exit 1
fi
