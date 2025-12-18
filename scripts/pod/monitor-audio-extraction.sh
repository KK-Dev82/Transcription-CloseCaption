#!/bin/bash
# Script สำหรับ Monitor Audio Extraction Activity แบบ Real-time
#
# วิธีใช้งาน:
#   bash scripts/pod/monitor-audio-extraction.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
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

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

cd /workspace/transcription-service || exit 1

# Load environment variables
if [ -f "env.runpod" ]; then
    set -a
    source env.runpod
    set +a
fi

RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
RABBITMQ_USER=${RABBITMQ_USER:-senate}
RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}
RABBITMQ_MGMT_PORT=${RABBITMQ_MGMT_PORT:-15672}

print_header "🔍 Monitor Audio Extraction Activity (Real-time)"

echo ""
print_info "Monitoring queues and logs for audio extraction activity..."
print_info "Press Ctrl+C to stop"
echo ""

LAST_LOG_LINE=0
MONITOR_INTERVAL=5

while true; do
    clear
    print_header "📊 Audio Extraction Monitor - $(date '+%Y-%m-%d %H:%M:%S')"
    
    # Check Queue Status
    echo ""
    print_header "1. Queue Status"
    
    # Transcription Request Queue
    REQ_QUEUE_INFO=$(curl -s -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
        "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues/%2F/transcription_request_queue" 2>/dev/null)
    
    if [ -n "$REQ_QUEUE_INFO" ] && ! echo "$REQ_QUEUE_INFO" | grep -q "Not Found\|404"; then
        REQ_MESSAGES=$(echo "$REQ_QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages', 0))" 2>/dev/null || echo "0")
        REQ_CONSUMERS=$(echo "$REQ_QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('consumers', 0))" 2>/dev/null || echo "0")
        
        print_info "transcription_request_queue:"
        print_info "   Messages: $REQ_MESSAGES"
        print_info "   Consumers: $REQ_CONSUMERS"
        
        if [ "$REQ_MESSAGES" -gt 0 ]; then
            print_warning "   ⚠️  $REQ_MESSAGES messages waiting"
        fi
    fi
    
    # Audio Extraction Queue
    EXT_QUEUE_INFO=$(curl -s -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
        "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues/%2F/audio_extraction_queue" 2>/dev/null)
    
    if [ -n "$EXT_QUEUE_INFO" ] && ! echo "$EXT_QUEUE_INFO" | grep -q "Not Found\|404"; then
        EXT_MESSAGES=$(echo "$EXT_QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages', 0))" 2>/dev/null || echo "0")
        EXT_UNACKED=$(echo "$EXT_QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages_unacknowledged', 0))" 2>/dev/null || echo "0")
        EXT_CONSUMERS=$(echo "$EXT_QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('consumers', 0))" 2>/dev/null || echo "0")
        
        print_info "audio_extraction_queue:"
        print_info "   Messages: $EXT_MESSAGES"
        print_info "   Unacked: $EXT_UNACKED"
        print_info "   Consumers: $EXT_CONSUMERS"
        
        if [ "$EXT_MESSAGES" -gt 0 ] || [ "$EXT_UNACKED" -gt 0 ]; then
            print_warning "   ⚠️  Activity detected: $EXT_MESSAGES ready, $EXT_UNACKED processing"
        else
            print_success "   ✅ Queue empty (no pending tasks)"
        fi
    fi
    
    # Recent Logs
    echo ""
    print_header "2. Recent Activity (Last 30 seconds)"
    
    RECENT_LOGS=$(tail -100 logs/video-worker.log 2>/dev/null | grep -E "RECEIVED MESSAGE|handle_|Audio Extraction|extracting_audio|Sending to" | tail -10 || echo "")
    
    if [ -n "$RECENT_LOGS" ]; then
        echo "$RECENT_LOGS" | while IFS= read -r line; do
            if echo "$line" | grep -q "RECEIVED MESSAGE\|Audio Extraction\|extracting_audio"; then
                print_success "   $line"
            elif echo "$line" | grep -q "Sending to\|Sent to"; then
                print_info "   $line"
            else
                print_info "   $line"
            fi
        done
    else
        print_warning "   No recent activity"
    fi
    
    # Worker Status
    echo ""
    print_header "3. Worker Status"
    
    WORKER_PID=$(pgrep -f "python.*-m.*app\.workers" | head -1 || echo "")
    if [ -n "$WORKER_PID" ]; then
        print_success "Worker running (PID: $WORKER_PID)"
        
        if curl -s -f "http://localhost:8030/health" > /dev/null 2>&1; then
            print_success "   Health endpoint: OK"
        else
            print_warning "   Health endpoint: Not responding"
        fi
    else
        print_error "Worker NOT running"
    fi
    
    echo ""
    print_info "Refreshing in ${MONITOR_INTERVAL} seconds... (Ctrl+C to stop)"
    sleep $MONITOR_INTERVAL
done

