#!/bin/bash
# Script สำหรับ Start Transcription Service แบบ Daemon (ทำงานต่อได้แม้ออกจาก Terminal)
#
# วิธีใช้งาน:
#   ssh pytorch-pod "bash -s" < scripts/pod/start-service-daemon.sh
#   หรือ
#   bash scripts/pod/start-service-daemon.sh (บน Pod)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/workspace/transcription-service"

echo "🚀 Starting Transcription Service (Daemon Mode)"
echo "================================================"
echo ""

# Check if running on Pod
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Error: Project directory not found: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

# Check if service is already running
if pgrep -f "uvicorn.*app.main:app.*8010" > /dev/null; then
    echo "⚠️  Transcription Service is already running"
    PID=$(pgrep -f "uvicorn.*app.main:app.*8010" | head -1)
    echo "   PID: $PID"
    echo ""
    read -p "Do you want to stop and restart? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping existing service..."
        kill $PID 2>/dev/null || true
        sleep 2
    else
        echo "Keeping existing service running"
        exit 0
    fi
fi

# Setup GPU environment
if [ -f "scripts/pod/setup-gpu-env.sh" ]; then
    echo "📋 Setting up GPU environment..."
    source scripts/pod/setup-gpu-env.sh
    echo "✅ GPU environment ready"
    echo ""
fi

# Prepare directories
echo "📁 Preparing directories..."
mkdir -p uploads storage temp models test-files
echo "✅ Directories ready"
echo ""

# Start Redis (if not running)
if ! pgrep -x "redis-server" > /dev/null; then
    echo "📦 Starting Redis..."
    redis-server --daemonize yes --port 6379 --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru || {
        echo "⚠️  Redis may already be running"
    }
    sleep 2
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis started"
    else
        echo "⚠️  Redis not responding (may continue anyway)"
    fi
    echo ""
fi

# Install/check timezone data (required for pythainlp)
echo "📋 Checking timezone data..."
if [ ! -d "/usr/share/zoneinfo" ] || [ ! -f "/usr/share/zoneinfo/Asia/Bangkok" ]; then
    echo "📦 Installing tzdata..."
    apt-get update -qq && apt-get install -y -qq tzdata > /dev/null 2>&1 || {
        echo "⚠️  Failed to install tzdata (may continue anyway)"
    }
fi
if [ -d "/usr/share/zoneinfo" ]; then
    export TZDIR=/usr/share/zoneinfo
    echo "✅ Timezone data available"
else
    echo "⚠️  Timezone data not found"
fi
export TZ=Asia/Bangkok
echo "   TZ=$TZ"
echo ""

# Load environment variables
if [ -f ".env.runpod" ]; then
    echo "📋 Loading .env.runpod..."
    set -a
    source .env.runpod
    set +a
    echo "✅ Environment loaded"
    echo ""
fi

# Check if dependencies are installed
echo "🔍 Checking dependencies..."
if ! python3 -c "import uvicorn" 2>/dev/null; then
    echo "❌ Error: uvicorn is not installed"
    echo ""
    echo "💡 Installing dependencies..."
    echo "   Run: bash scripts/pod/install-dependencies.sh"
    echo ""
    read -p "Do you want to install dependencies now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        bash scripts/pod/install-dependencies.sh || {
            echo "❌ Failed to install dependencies"
            exit 1
        }
    else
        echo "❌ Cannot start service without dependencies"
        exit 1
    fi
else
    echo "✅ Dependencies OK"
    echo ""
fi

# Log file location
LOG_FILE="/tmp/transcription-service.log"
PID_FILE="/tmp/transcription-service.pid"

# Start service with nohup (ทำงานต่อได้แม้ออกจาก terminal)
echo "🚀 Starting Transcription Service (with nohup)..."
echo "   Host: 0.0.0.0"
echo "   Port: 8010"
echo "   Log: $LOG_FILE"
echo "   PID: $PID_FILE"
echo ""
echo "   ⚠️  Service will continue running after you exit terminal"
echo ""

# Start with nohup - redirect all output to log file
# Set timezone environment variables for pythainlp
# เพิ่ม PYTHONPATH และ PATH สำหรับ packages ใน /workspace/.local
export PYTHONUSERBASE="/workspace/.local"
export PATH="/workspace/.local/bin:$PATH"
export PYTHONPATH="/workspace/.local/lib/python3.10/site-packages:$PYTHONPATH"
nohup env TZ="${TZ:-Asia/Bangkok}" \
         TZDIR="${TZDIR:-/usr/share/zoneinfo}" \
         PYTHONUSERBASE="/workspace/.local" \
         PATH="/workspace/.local/bin:$PATH" \
         PYTHONPATH="/workspace/.local/lib/python3.10/site-packages:$PYTHONPATH" \
         python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8010 \
    --workers 1 \
    > "$LOG_FILE" 2>&1 &

SERVICE_PID=$!
echo $SERVICE_PID > "$PID_FILE"

# Wait a moment for service to start
sleep 3

# Check if service started successfully
if ps -p $SERVICE_PID > /dev/null; then
    echo "✅ Transcription Service started successfully"
    echo "   PID: $SERVICE_PID"
    echo "   PID File: $PID_FILE"
    echo ""
    
    # Wait a bit and test
    sleep 2
    if curl -s -f http://localhost:8010/health > /dev/null 2>&1; then
        echo "✅ Service is responding"
        echo ""
        echo "📊 Service Information:"
        echo "   URL: http://0.0.0.0:8010"
        echo "   Health: http://localhost:8010/health"
        echo "   Docs: http://localhost:8010/docs"
        echo "   Log: tail -f $LOG_FILE"
        echo "   PID: cat $PID_FILE"
        echo ""
        echo "🌐 External Access:"
        echo "   URL: http://80.15.7.37:8010"
        echo "   Health: http://80.15.7.37:8010/health"
        echo ""
        echo "💡 Useful Commands:"
        echo "   Stop: kill \$(cat $PID_FILE)"
        echo "   Logs: tail -f $LOG_FILE"
        echo "   Status: ps aux | grep uvicorn"
    else
        echo "⚠️  Service started but not responding yet (check log: $LOG_FILE)"
        echo "   Wait a few seconds and check: curl http://localhost:8010/health"
    fi
else
    echo "❌ Failed to start service"
    echo "   Check log: $LOG_FILE"
    tail -20 "$LOG_FILE"
    exit 1
fi

echo "=============================="
echo "✅ Setup Complete"
echo ""
echo "⚠️  Service is running in background (nohup)"
echo "   You can safely exit this terminal"
echo ""

