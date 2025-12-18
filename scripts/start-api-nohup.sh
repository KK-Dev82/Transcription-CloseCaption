#!/bin/bash

# Start API Server with nohup
# Usage: ./scripts/start-api-nohup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# Load environment variables
if [ -f .env.runpod ]; then
    set -a
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip empty lines and comments
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        # Export variable
        export "$line"
    done < .env.runpod
    set +a
fi

# API Configuration
# ⚠️  หมายเหตุ: Port 8001 ถูกใช้โดย RunPod Nginx/Proxy
# ใช้ port 8010 ตาม RunPod HTTP Expose
API_HOST=${API_HOST:-0.0.0.0}
API_PORT=${API_PORT:-8010}
API_WORKERS=${API_WORKERS:-1}

# Log directory
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

# Log files
API_LOG="$LOG_DIR/api.log"
API_ERROR_LOG="$LOG_DIR/api-error.log"

echo "🚀 Starting API Server..."
echo "   Host: $API_HOST"
echo "   Port: $API_PORT"
echo "   Workers: $API_WORKERS"
echo "   Log: $API_LOG"
echo "   Error Log: $API_ERROR_LOG"

# Start API with nohup
nohup python3 -m uvicorn app.main:app \
    --host "$API_HOST" \
    --port "$API_PORT" \
    --workers "$API_WORKERS" \
    --log-level info \
    > "$API_LOG" 2> "$API_ERROR_LOG" &

API_PID=$!

echo "✅ API Server started (PID: $API_PID)"
echo "   Check logs: tail -f $API_LOG"
echo "   Check errors: tail -f $API_ERROR_LOG"
echo "   Stop: kill $API_PID"

# Save PID
echo "$API_PID" > "$LOG_DIR/api.pid"

echo ""
echo "📋 Server URLs:"
echo "   API: http://$API_HOST:$API_PORT"
echo "   Health: http://$API_HOST:$API_PORT/health"
echo "   Docs: http://$API_HOST:$API_PORT/docs"

