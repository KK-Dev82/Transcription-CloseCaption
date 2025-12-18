#!/bin/bash

# Start Worker with nohup
# Usage: ./scripts/start-worker-nohup.sh

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

# Log directory
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

# Log files
WORKER_LOG="$LOG_DIR/worker.log"
WORKER_ERROR_LOG="$LOG_DIR/worker-error.log"

echo "🚀 Starting Worker..."
echo "   Log: $WORKER_LOG"
echo "   Error Log: $WORKER_ERROR_LOG"

# Start Worker with nohup
nohup python3 -m app.workers.sync.video_worker \
    > "$WORKER_LOG" 2> "$WORKER_ERROR_LOG" &

WORKER_PID=$!

echo "✅ Worker started (PID: $WORKER_PID)"
echo "   Check logs: tail -f $WORKER_LOG"
echo "   Check errors: tail -f $WORKER_ERROR_LOG"
echo "   Stop: kill $WORKER_PID"

# Save PID
echo "$WORKER_PID" > "$LOG_DIR/worker.pid"

