#!/bin/bash
# Script สำหรับ View Logs ของ Local Docker Services
# Usage: bash scripts/local/logs-local.sh [service] [lines]
# service: api, whisper, worker, redis, or all (default: all)
# lines: number of lines to show (default: 50)

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

SERVICE=${1:-all}
LINES=${2:-50}

# Check if container exists
if ! docker ps | grep -q transcription-local-base; then
    print_error "❌ Container is not running"
    echo ""
    echo "Start container with:"
    echo "   bash scripts/local/start-local.sh"
    exit 1
fi

print_header "📋 Viewing Logs: $SERVICE (last $LINES lines)"
echo ""

case $SERVICE in
    api|main)
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "Main API Logs"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        docker exec transcription-local-base bash -c "tail -n $LINES /tmp/main-api.log 2>/dev/null || echo 'No logs found'"
        ;;
    whisper)
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "Whisper API Logs"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        docker exec transcription-local-base bash -c "tail -n $LINES /tmp/whisper.log 2>/dev/null || echo 'No logs found'"
        ;;
    worker|video-worker)
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "Video Worker Logs"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        docker exec transcription-local-base bash -c "tail -n $LINES /tmp/video-worker.log 2>/dev/null || echo 'No logs found'"
        ;;
    redis)
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "Redis Logs"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        docker exec transcription-local-base bash -c "tail -n $LINES /tmp/redis.log 2>/dev/null || echo 'No logs found'"
        ;;
    all|*)
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "All Services Logs (last $LINES lines each)"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        print_header "Main API:"
        docker exec transcription-local-base bash -c "tail -n $LINES /tmp/main-api.log 2>/dev/null || echo 'No logs found'"
        echo ""
        
        print_header "Whisper API:"
        docker exec transcription-local-base bash -c "tail -n $LINES /tmp/whisper.log 2>/dev/null || echo 'No logs found'"
        echo ""
        
        print_header "Video Worker:"
        docker exec transcription-local-base bash -c "tail -n $LINES /tmp/video-worker.log 2>/dev/null || echo 'No logs found'"
        echo ""
        
        print_header "Redis:"
        docker exec transcription-local-base bash -c "tail -n $LINES /tmp/redis.log 2>/dev/null || echo 'No logs found'"
        ;;
esac

echo ""
print_status "💡 Tip: Use 'tail -f' for real-time logs:"
echo "   docker exec -it transcription-local-base bash -c 'tail -f /tmp/video-worker.log'"

