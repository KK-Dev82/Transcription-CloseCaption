#!/bin/bash
# Script สำหรับรัน Dashboard แบบ Daemon (Background Process)
# รองรับทั้ง nohup, systemd, และ supervisor

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Transcription Service Dashboard (Daemon Mode)${NC}"
echo "=================================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 not found. Please install Python 3.8+${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python found: $(python3 --version)${NC}"

# Check or create venv
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Get port from env or default
PORT=${DASHBOARD_PORT:-8020}

# Create logs directory
mkdir -p logs
LOG_FILE="logs/dashboard.log"
PID_FILE="logs/dashboard.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Dashboard is already running (PID: $OLD_PID)${NC}"
        echo "   Use 'bash stop-daemon.sh' to stop it first"
        exit 1
    else
        echo "🧹 Cleaning up stale PID file..."
        rm -f "$PID_FILE"
    fi
fi

# Load environment variables from parent .env.runpod if exists
if [ -f "../.env.runpod" ]; then
    echo "📋 Loading environment from ../.env.runpod..."
    set -a  # Automatically export all variables
    source ../.env.runpod 2>/dev/null || true
    set +a  # Stop automatically exporting
fi

echo ""
echo -e "${GREEN}✅ Starting Dashboard on http://0.0.0.0:${PORT}${NC}"
echo "   Log file: $LOG_FILE"
echo "   PID file: $PID_FILE"
echo ""

# Start dashboard in background with nohup
nohup python3 -m uvicorn main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    > "$LOG_FILE" 2>&1 &

# Save PID
DASHBOARD_PID=$!
echo $DASHBOARD_PID > "$PID_FILE"

# Wait a moment to check if it started successfully
sleep 2

if ps -p "$DASHBOARD_PID" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Dashboard started successfully!${NC}"
    echo "   PID: $DASHBOARD_PID"
    echo "   URL: http://localhost:${PORT}"
    echo "   Logs: tail -f $LOG_FILE"
    echo ""
    echo "📊 To stop: bash stop-daemon.sh"
    echo "📊 To view logs: tail -f $LOG_FILE"
else
    echo -e "${RED}❌ Failed to start Dashboard${NC}"
    echo "   Check logs: cat $LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
