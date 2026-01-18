#!/bin/bash
# Script สำหรับดู API Logs
# วิธีใช้งาน: bash scripts/pod/view-api-logs.sh [lines]

API_LOG="/tmp/main-api.log"
LINES=${1:-50}

echo "📋 Main API Logs (last $LINES lines)"
echo "============================================"

if [ -f "$API_LOG" ]; then
    tail -n "$LINES" "$API_LOG"
else
    echo "❌ Log file not found: $API_LOG"
    echo "💡 Make sure Main API is running"
fi
