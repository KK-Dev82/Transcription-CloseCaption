#!/bin/bash
# Script สำหรับ Stop Services ทั้งหมด
#
# วิธีใช้งาน:
# bash scripts/pod/stop-services.sh

set -e

echo "🛑 Stopping Transcription Services..."
echo ""

# Stop Main API
echo "🛑 Stopping Main API..."
pkill -f "python.*uvicorn.*app.main" && echo "✅ Main API stopped" || echo "⚠️  Main API not running"

# Stop Whisper API
echo "🛑 Stopping Whisper API..."
pkill -f "python.*whisper_api" && echo "✅ Whisper API stopped" || echo "⚠️  Whisper API not running"

# Stop Video Worker
echo "🛑 Stopping Video Worker..."
pkill -f "python.*video_worker" && echo "✅ Video Worker stopped" || echo "⚠️  Video Worker not running"

# Stop Redis
echo "🛑 Stopping Redis..."
pkill -f redis-server && echo "✅ Redis stopped" || echo "⚠️  Redis not running"

# Wait a bit
sleep 2

# Check if processes are still running
echo ""
echo "🔍 Checking for remaining processes..."
REMAINING=$(ps aux | grep -E "(python.*uvicorn|python.*whisper|python.*video_worker|redis-server)" | grep -v grep || true)
if [ -n "$REMAINING" ]; then
    echo "⚠️  Some processes are still running:"
    echo "$REMAINING"
    echo ""
    echo "💡 Force kill:"
    echo "   pkill -9 -f 'python.*uvicorn'"
    echo "   pkill -9 -f 'python.*whisper'"
    echo "   pkill -9 -f 'python.*video_worker'"
    echo "   pkill -9 -f redis-server"
else
    echo "✅ All services stopped"
fi

echo ""
echo "✅ Stop completed!"

