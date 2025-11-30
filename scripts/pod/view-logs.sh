#!/bin/bash
# Script สำหรับดู Logs ของ Services บน RunPod/Z2
#
# วิธีใช้งาน:
#   bash scripts/pod/view-logs.sh [service] [lines]
#
# ตัวอย่าง:
#   bash scripts/pod/view-logs.sh                    # ดู logs ทั้งหมด
#   bash scripts/pod/view-logs.sh api               # ดู Main API logs
#   bash scripts/pod/view-logs.sh whisper           # ดู Whisper API logs
#   bash scripts/pod/view-logs.sh worker           # ดู Video Worker logs
#   bash scripts/pod/view-logs.sh all 100           # ดู logs ทั้งหมด (100 บรรทัดล่าสุด)

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

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${CYAN}$1${NC}"
}

SERVICE="${1:-all}"
LINES="${2:-50}"

echo "📋 Viewing Service Logs"
echo "📅 $(date)"
echo ""

# Log file paths
MAIN_API_LOG="/tmp/main-api.log"
WHISPER_LOG="/tmp/whisper.log"
VIDEO_WORKER_LOG="/tmp/video-worker.log"
REDIS_LOG="/tmp/redis.log"

case "$SERVICE" in
    api|main|main-api)
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "Main API Logs (Last $LINES lines)"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        if [ -f "$MAIN_API_LOG" ]; then
            tail -n "$LINES" "$MAIN_API_LOG"
        else
            print_error "❌ Log file not found: $MAIN_API_LOG"
            print_status "💡 Main API may not be running"
        fi
        ;;
    
    whisper|whisper-api)
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "Whisper API Logs (Last $LINES lines)"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        if [ -f "$WHISPER_LOG" ]; then
            tail -n "$LINES" "$WHISPER_LOG"
        else
            print_error "❌ Log file not found: $WHISPER_LOG"
            print_status "💡 Whisper API may not be running"
        fi
        ;;
    
    worker|video-worker|video_worker)
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "Video Worker Logs (Last $LINES lines)"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        if [ -f "$VIDEO_WORKER_LOG" ]; then
            tail -n "$LINES" "$VIDEO_WORKER_LOG"
        else
            print_error "❌ Log file not found: $VIDEO_WORKER_LOG"
            print_status "💡 Video Worker may not be running"
        fi
        ;;
    
    redis)
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "Redis Logs (Last $LINES lines)"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        if [ -f "$REDIS_LOG" ]; then
            tail -n "$LINES" "$REDIS_LOG"
        else
            print_warning "⚠️  Redis logs may not be available (Redis runs in background)"
            print_status "💡 Check Redis status: redis-cli ping"
        fi
        ;;
    
    all|*)
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "All Service Logs (Last $LINES lines each)"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        # Main API
        print_header "📡 Main API:"
        if [ -f "$MAIN_API_LOG" ]; then
            tail -n "$LINES" "$MAIN_API_LOG"
        else
            print_error "   ❌ Log file not found: $MAIN_API_LOG"
        fi
        echo ""
        echo ""
        
        # Whisper API
        print_header "🎤 Whisper API:"
        if [ -f "$WHISPER_LOG" ]; then
            tail -n "$LINES" "$WHISPER_LOG"
        else
            print_error "   ❌ Log file not found: $WHISPER_LOG"
        fi
        echo ""
        echo ""
        
        # Video Worker
        print_header "🎬 Video Worker:"
        if [ -f "$VIDEO_WORKER_LOG" ]; then
            tail -n "$LINES" "$VIDEO_WORKER_LOG"
        else
            print_error "   ❌ Log file not found: $VIDEO_WORKER_LOG"
        fi
        echo ""
        ;;
esac

echo ""
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "💡 Useful Commands:"
echo ""
echo "   # Follow logs in real-time:"
echo "   tail -f $MAIN_API_LOG"
echo "   tail -f $WHISPER_LOG"
echo "   tail -f $VIDEO_WORKER_LOG"
echo ""
echo "   # View specific service:"
echo "   bash scripts/pod/view-logs.sh api 100"
echo "   bash scripts/pod/view-logs.sh whisper 100"
echo "   bash scripts/pod/view-logs.sh worker 100"
echo ""
echo "   # Check service status:"
echo "   bash scripts/pod/check-services-status.sh"
echo ""

