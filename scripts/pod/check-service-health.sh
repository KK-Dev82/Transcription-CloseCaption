#!/bin/bash
# Script สำหรับตรวจสอบ Service Health
PROJECT_DIR="/workspace/transcription-service"
cd "$PROJECT_DIR" 2>/dev/null || exit 1
INTERNAL_PORT="${1:-8010}"
echo "🔍 Checking Service Health..."
if pgrep -f "uvicorn.*app.main:app.*${INTERNAL_PORT}" > /dev/null; then
    echo "✅ Service running"
else
    echo "❌ Service NOT running"
    echo "💡 Check logs: tail -f /tmp/transcription-service.log"
fi
if curl -s -f "http://localhost:${INTERNAL_PORT}/health" > /dev/null 2>&1; then
    echo "✅ Health OK"
else
    echo "❌ Health failed"
fi
