#!/bin/bash
# Script สำหรับตรวจสอบ Live-Chunk Logs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

echo "================================================================================"
echo "🔍 ตรวจสอบ Live-Chunk Logs"
echo "================================================================================"
echo ""

# 1. ตรวจสอบ Workers Processes
print_info "1. ตรวจสอบ Worker Processes:"
worker_count=$(ps aux | grep "rq worker.*transcription_priority" | grep -v grep | wc -l)
if [ "$worker_count" -gt 0 ]; then
    print_success "พบ $worker_count worker processes"
    ps aux | grep "rq worker.*transcription_priority" | grep -v grep | head -3 | awk '{print "   PID:", $2, "|", $NF}'
else
    print_error "ไม่พบ worker processes"
fi
echo ""

# 2. ตรวจสอบ Worker Logs
print_info "2. ตรวจสอบ Worker Logs:"

# Check log files
LOG_FOUND=0
for i in 0 1 2; do
    log_file="/tmp/rq-worker-gpu0-w${i}.log"
    if [ -f "$log_file" ]; then
        LOG_FOUND=1
        print_success "พบ log file: $log_file"
        
        # Check for live-chunk related logs
        live_chunk_count=$(grep -c "live chunk\|process_live_chunk" "$log_file" 2>/dev/null || echo "0")
        ws_event_count=$(grep -c "WS event\|Sent.*HTTP" "$log_file" 2>/dev/null || echo "0")
        
        if [ "$live_chunk_count" -gt 0 ] || [ "$ws_event_count" -gt 0 ]; then
            print_success "   พบ live-chunk logs: $live_chunk_count, WS events: $ws_event_count"
            echo ""
            print_info "   📋 Last 10 relevant lines:"
            grep -E "(live chunk|process_live_chunk|WS event|Sent.*HTTP|Starting live chunk job)" "$log_file" 2>/dev/null | tail -10 | sed 's/^/      /' || echo "      (no matches)"
        else
            print_warning "   ไม่พบ live-chunk logs ใน file นี้"
            print_info "   📋 Last 5 lines:"
            tail -5 "$log_file" 2>/dev/null | sed 's/^/      /' || echo "      (empty file)"
        fi
        echo ""
    fi
done

if [ "$LOG_FOUND" -eq 0 ]; then
    print_warning "ไม่พบ log files ที่ /tmp/rq-worker-gpu0-w*.log"
    print_info "  อาจจะใช้ Docker หรือ logs อยู่ใน container"
    print_info "  ลองใช้: docker logs <worker-container>"
fi

# 3. ตรวจสอบ Main API
print_info "3. ตรวจสอบ Main API Process:"
main_api_count=$(ps aux | grep "uvicorn.*app.main" | grep -v grep | wc -l)
if [ "$main_api_count" -gt 0 ]; then
    print_success "พบ Main API process"
    ps aux | grep "uvicorn.*app.main" | grep -v grep | head -1 | awk '{print "   PID:", $2}'
else
    print_error "ไม่พบ Main API process"
fi
echo ""

# 4. ตรวจสอบ Main API Logs
print_info "4. ตรวจสอบ Main API Logs:"

# Check if using Docker
if command -v docker &> /dev/null; then
    # Try to find main-api container
    MAIN_API_CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "main|api" | head -1)
    if [ -n "$MAIN_API_CONTAINER" ]; then
        print_info "  พบ Docker container: $MAIN_API_CONTAINER"
        ws_event_count=$(docker logs "$MAIN_API_CONTAINER" 2>&1 | grep -c "ws-event\|Broadcasted\|Received.*ws-event" || echo "0")
        if [ "$ws_event_count" -gt 0 ]; then
            print_success "  พบ ws-event logs: $ws_event_count"
            echo ""
            print_info "  📋 Last 10 relevant lines:"
            docker logs "$MAIN_API_CONTAINER" 2>&1 | grep -E "(ws-event|Broadcasted|Received.*ws-event|send_to_user|meeting_id)" | tail -10 | sed 's/^/      /' || echo "      (no matches)"
        else
            print_warning "  ไม่พบ ws-event logs"
            print_info "  📋 Last 10 lines:"
            docker logs "$MAIN_API_CONTAINER" 2>&1 | tail -10 | sed 's/^/      /'
        fi
    else
        print_warning "  ไม่พบ Docker container"
    fi
else
    print_info "  Docker ไม่พร้อมใช้งาน"
fi

# Check log file
if [ -f "/tmp/main-api.log" ]; then
    print_success "  พบ log file: /tmp/main-api.log"
    ws_event_count=$(grep -c "ws-event\|Broadcasted\|Received.*ws-event" "/tmp/main-api.log" 2>/dev/null || echo "0")
    if [ "$ws_event_count" -gt 0 ]; then
        print_success "    พบ ws-event logs: $ws_event_count"
        echo ""
        print_info "    📋 Last 10 relevant lines:"
        grep -E "(ws-event|Broadcasted|Received.*ws-event|send_to_user|meeting_id)" "/tmp/main-api.log" 2>/dev/null | tail -10 | sed 's/^/      /' || echo "      (no matches)"
    else
        print_warning "    ไม่พบ ws-event logs"
    fi
elif [ -f "/var/log/main-api.log" ]; then
    print_success "  พบ log file: /var/log/main-api.log"
    ws_event_count=$(grep -c "ws-event\|Broadcasted\|Received.*ws-event" "/var/log/main-api.log" 2>/dev/null || echo "0")
    if [ "$ws_event_count" -gt 0 ]; then
        print_success "    พบ ws-event logs: $ws_event_count"
    else
        print_warning "    ไม่พบ ws-event logs"
    fi
else
    print_warning "  ไม่พบ log files: /tmp/main-api.log หรือ /var/log/main-api.log"
fi
echo ""

# 5. คำแนะนำ
print_info "5. คำแนะนำการตรวจสอบ Logs:"
echo ""
echo "  📋 Workers Logs:"
echo "    tail -f /tmp/rq-worker-gpu0-w0.log | grep -E '(live chunk|WS event|Sent.*HTTP)'"
echo "    tail -f /tmp/rq-worker-gpu0-w1.log | grep -E '(live chunk|WS event|Sent.*HTTP)'"
echo "    tail -f /tmp/rq-worker-gpu0-w2.log | grep -E '(live chunk|WS event|Sent.*HTTP)'"
echo ""
echo "  📋 Main API Logs (Docker):"
echo "    docker logs <container-name> | grep -E '(ws-event|Broadcasted|Received|send_to_user)'"
echo ""
echo "  📋 Main API Logs (Scripts):"
echo "    tail -f /tmp/main-api.log | grep -E '(ws-event|Broadcasted|Received)'"
echo ""
echo "  📋 Key Logs ที่ควรเห็น:"
echo "    Workers:"
echo "      - '🚀 RQ Worker: Starting live chunk job'"
echo "      - '📤 Sent V3 final caption event via HTTP'"
echo "      - '✅ WS event sent via HTTP'"
echo ""
echo "    Main API:"
echo "      - '📥 Received ws-event callback'"
echo "      - '✅ Broadcasted meeting update'"
echo "      - '📤 Sending message to user_id=...'"
echo ""

echo "================================================================================"
