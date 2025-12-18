#!/bin/bash

# Start All Services with nohup
# Usage: ./scripts/start-all-nohup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "🚀 Starting All Services..."

# Start API
bash "$SCRIPT_DIR/start-api-nohup.sh"
sleep 2

# Start Worker
bash "$SCRIPT_DIR/start-worker-nohup.sh"
sleep 2

echo ""
echo "✅ All services started!"
echo ""
echo "📋 Check Status:"
echo "   API Logs: tail -f logs/api.log"
echo "   Worker Logs: tail -f logs/worker.log"
echo ""
echo "🛑 Stop All:"
echo "   bash scripts/stop-all.sh"

