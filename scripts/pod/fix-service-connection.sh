#!/bin/bash
# Script สำหรับแก้ไขปัญหา Service Connection
PROJECT_DIR="/workspace/transcription-service"
cd "$PROJECT_DIR" 2>/dev/null || exit 1
INTERNAL_PORT="${1:-8010}"
echo "🔧 Fixing Service Connection..."
pkill -f "uvicorn.*app.main:app.*${INTERNAL_PORT}" 2>/dev/null || true
sleep 2
bash scripts/pod/start-service-daemon.sh "$INTERNAL_PORT"
sleep 5
if pgrep -f "uvicorn.*app.main:app.*${INTERNAL_PORT}" > /dev/null; then
    echo "✅ Service started"
else
    echo "❌ Service failed to start"
    echo "💡 Check logs: tail -f /tmp/transcription-service.log"
    exit 1
fi
