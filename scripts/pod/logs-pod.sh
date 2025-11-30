#!/bin/bash
# Script สำหรับดู Logs ของ Services
#
# วิธีใช้งาน:
#   bash scripts/pod/logs-pod.sh                    # ดู logs ทั้งหมด
#   bash scripts/pod/logs-pod.sh api               # ดู Main API logs
#   bash scripts/pod/logs-pod.sh whisper           # ดู Whisper API logs
#   bash scripts/pod/logs-pod.sh worker            # ดู Video Worker logs
#   bash scripts/pod/logs-pod.sh all 100           # ดู logs ทั้งหมด (100 บรรทัด)

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

SERVICE="${1:-all}"
LINES="${2:-50}"

MAIN_API_LOG="/tmp/main-api.log"
WHISPER_LOG="/tmp/whisper.log"
VIDEO_WORKER_LOG="/tmp/video-worker.log"

case "$SERVICE" in
    api|main|main-api)
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "Main API Logs (Last $LINES lines)"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        if [ -f "$MAIN_API_LOG" ]; then
            tail -n "$LINES" "$MAIN_API_LOG"
        else
            print_error "❌ Log file not found: $MAIN_API_LOG"
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
        fi
        ;;
    
    all|*)
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "All Service Logs (Last $LINES lines each)"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        print_header "📡 Main API:"
        [ -f "$MAIN_API_LOG" ] && tail -n "$LINES" "$MAIN_API_LOG" || print_error "   ❌ Log file not found"
        echo ""
        echo ""
        
        print_header "🎤 Whisper API:"
        [ -f "$WHISPER_LOG" ] && tail -n "$LINES" "$WHISPER_LOG" || print_error "   ❌ Log file not found"
        echo ""
        echo ""
        
        print_header "🎬 Video Worker:"
        [ -f "$VIDEO_WORKER_LOG" ] && tail -n "$LINES" "$VIDEO_WORKER_LOG" || print_error "   ❌ Log file not found"
        echo ""
        ;;
esac

echo ""
print_status "💡 Follow logs in real-time:"
echo "   tail -f $MAIN_API_LOG"
echo "   tail -f $WHISPER_LOG"
echo "   tail -f $VIDEO_WORKER_LOG"
echo ""

