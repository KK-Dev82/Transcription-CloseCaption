#!/bin/bash
# Script สำหรับ Start Transcription Service บน Pod สำหรับ Backend Integration
#
# วิธีใช้งาน:
#   ssh pytorch-pod "bash -s" < scripts/pod/start-service-for-backend.sh
#   หรือ
#   bash scripts/pod/start-service-for-backend.sh (บน Pod)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/workspace/transcription-service"

echo "🚀 Starting Transcription Service for Backend Integration"
echo "=========================================================="
echo ""

# Check if running on Pod
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Error: Project directory not found: $PROJECT_DIR"
    echo "   Please make sure you're running on the Pod and project is cloned"
    exit 1
fi

cd "$PROJECT_DIR"

# Check if service is already running
if pgrep -f "uvicorn.*app.main:app" > /dev/null; then
    echo "⚠️  Transcription Service is already running"
    PID=$(pgrep -f "uvicorn.*app.main:app" | head -1)
    echo "   PID: $PID"
    echo ""
    read -p "Do you want to stop and restart? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping existing service..."
        kill $PID
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

# Load environment variables
if [ -f ".env.runpod" ]; then
    echo "📋 Loading .env.runpod..."
    set -a
    source .env.runpod
    set +a
    echo "✅ Environment loaded"
    echo ""
fi

# Start service in background
LOG_FILE="/tmp/transcription-service.log"
echo "🚀 Starting Transcription Service..."
echo "   Host: 0.0.0.0"
echo "   Port: 8001"
echo "   Log: $LOG_FILE"
echo ""

nohup python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8001 \
    --workers 1 \
    > "$LOG_FILE" 2>&1 &

SERVICE_PID=$!
sleep 3

# Check if service started successfully
if ps -p $SERVICE_PID > /dev/null; then
    echo "✅ Transcription Service started successfully"
    echo "   PID: $SERVICE_PID"
    echo ""
    
    # Wait a bit and test
    sleep 2
    if curl -s -f http://localhost:8001/health > /dev/null 2>&1; then
        echo "✅ Service is responding"
        echo ""
        echo "📊 Service Information:"
        echo "   URL: http://0.0.0.0:8001"
        echo "   Health: http://localhost:8001/health"
        echo "   Docs: http://localhost:8001/docs"
        echo "   Log: tail -f $LOG_FILE"
        echo ""
        echo "🌐 External Access:"
        echo "   URL: http://80.15.7.37:8001"
        echo "   Health: http://80.15.7.37:8001/health"
        echo ""
    else
        echo "⚠️  Service started but not responding yet (check log: $LOG_FILE)"
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
echo "💡 Next Steps:"
echo "   1. Test service: curl http://80.15.7.37:8001/health"
echo "   2. Configure Backend: Update appsettings.Development.json"
echo "   3. Start testing integration"
echo ""

