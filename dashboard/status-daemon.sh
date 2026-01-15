#!/bin/bash
# Script สำหรับตรวจสอบสถานะ Dashboard

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PID_FILE="logs/dashboard.pid"
PORT=${DASHBOARD_PORT:-8020}

echo -e "${BLUE}📊 Dashboard Status${NC}"
echo "=================="
echo ""

if [ ! -f "$PID_FILE" ]; then
    echo -e "${RED}❌ Dashboard is not running${NC}"
    echo "   PID file not found: $PID_FILE"
    exit 1
fi

PID=$(cat "$PID_FILE")

if ! ps -p "$PID" > /dev/null 2>&1; then
    echo -e "${RED}❌ Dashboard is not running${NC}"
    echo "   Process not found (PID: $PID)"
    echo "   Cleaning up stale PID file..."
    rm -f "$PID_FILE"
    exit 1
fi

# Get process info
PROCESS_INFO=$(ps -p "$PID" -o pid,user,etime,cmd --no-headers 2>/dev/null || echo "")

if [ -z "$PROCESS_INFO" ]; then
    echo -e "${RED}❌ Cannot get process information${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Dashboard is running${NC}"
echo ""
echo "   PID: $PID"
echo "   Process: $PROCESS_INFO"
echo ""

# Check if port is listening
if command -v lsof &> /dev/null; then
    PORT_INFO=$(lsof -i :$PORT 2>/dev/null | grep LISTEN || echo "")
    if [ -n "$PORT_INFO" ]; then
        echo -e "${GREEN}✅ Port $PORT is listening${NC}"
    else
        echo -e "${YELLOW}⚠️  Port $PORT is not listening${NC}"
    fi
fi

# Check log file
LOG_FILE="logs/dashboard.log"
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(du -h "$LOG_FILE" | cut -f1)
    echo ""
    echo "   Log file: $LOG_FILE ($LOG_SIZE)"
    echo "   Last 5 lines:"
    tail -n 5 "$LOG_FILE" | sed 's/^/      /'
fi

echo ""
echo "   URL: http://localhost:$PORT"
echo ""
