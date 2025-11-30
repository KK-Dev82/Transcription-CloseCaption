#!/bin/bash
# Script สำหรับ Monitor Video Worker Activity
#
# วิธีใช้งาน:
#   bash scripts/pod/monitor-video-worker.sh [task-id]

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

TASK_ID="${1}"

echo "📊 Monitoring Video Worker Activity"
echo "📅 $(date)"
echo ""

if [ -n "$TASK_ID" ]; then
    print_status "Filtering for Task ID: $TASK_ID"
    echo ""
    tail -f /tmp/video-worker.log | grep --line-buffered -i "$TASK_ID\|transcription\|task\|processing\|error" || true
else
    print_status "Monitoring all Video Worker activity"
    echo ""
    print_status "💡 Press Ctrl+C to stop"
    echo ""
    tail -f /tmp/video-worker.log
fi

