#!/bin/bash
# Script สำหรับตรวจสอบสถานะ Audio Extraction
#
# วิธีใช้งาน:
#   bash scripts/pod/check-audio-extraction-status.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
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

print_header "🔍 Check Audio Extraction Status"

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

# Check 1: FFmpeg
echo ""
print_header "1. FFmpeg Status"

FFMPEG_PATH=$(which ffmpeg 2>/dev/null || echo "")
if [ -n "$FFMPEG_PATH" ]; then
    print_success "FFmpeg found: $FFMPEG_PATH"
    
    # Check FFmpeg version
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1 || echo "")
    if [ -n "$FFMPEG_VERSION" ]; then
        print_info "   $FFMPEG_VERSION"
    fi
    
    # Check if FFmpeg can load libraries
    if ldd "$FFMPEG_PATH" 2>&1 | grep -q "not found"; then
        print_error "FFmpeg has missing libraries:"
        ldd "$FFMPEG_PATH" 2>&1 | grep "not found" | head -5
    else
        print_success "   FFmpeg libraries OK"
    fi
else
    print_error "FFmpeg not found"
fi

# Check 2: Worker Process
echo ""
print_header "2. Worker Process Status"

WORKER_PID=""
for pattern in "python3.*-m.*app.workers" "python.*-m.*app.workers" "app.workers.async.video_worker"; do
    WORKER_PID=$(pgrep -f "$pattern" | head -1 || echo "")
    if [ -n "$WORKER_PID" ]; then
        break
    fi
done

if [ -n "$WORKER_PID" ]; then
    print_success "Worker process found (PID: $WORKER_PID)"
    
    PROCESS_INFO=$(ps -p "$WORKER_PID" -o pid,etime,stat,cmd --no-headers 2>/dev/null || echo "")
    if [ -n "$PROCESS_INFO" ]; then
        print_info "   $PROCESS_INFO"
    fi
else
    print_error "Worker process NOT found"
fi

# Check 3: Queue Status
echo ""
print_header "3. Queue Status"

QUEUE_INFO=$(curl -s -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
    "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues/%2F/audio_extraction_queue" 2>/dev/null)

if [ -n "$QUEUE_INFO" ] && ! echo "$QUEUE_INFO" | grep -q "Not Found\|404"; then
    MESSAGES=$(echo "$QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages', 0))" 2>/dev/null || echo "0")
    UNACKED=$(echo "$QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages_unacknowledged', 0))" 2>/dev/null || echo "0")
    CONSUMERS=$(echo "$QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('consumers', 0))" 2>/dev/null || echo "0")
    
    print_info "audio_extraction_queue:"
    print_info "   Messages ready: $MESSAGES"
    print_info "   Messages unacked: $UNACKED"
    print_info "   Consumers: $CONSUMERS"
    
    if [ "$CONSUMERS" -eq 0 ]; then
        print_warning "   ⚠️  No consumers registered (worker may have disconnected)"
    else
        print_success "   ✅ Consumers registered"
    fi
else
    print_warning "Cannot get queue info"
fi

# Check 4: Recent Audio Extraction Logs
echo ""
print_header "4. Recent Audio Extraction Activity"

RECENT_EXTRACTIONS=$(grep -E "Audio Extraction.*Processing|Audio extracted|extracting_audio" logs/video-worker.log 2>/dev/null | tail -5 || echo "")

if [ -n "$RECENT_EXTRACTIONS" ]; then
    print_success "Recent audio extraction activity found:"
    echo "$RECENT_EXTRACTIONS" | while IFS= read -r line; do
        print_info "   $line"
    done
else
    print_warning "No recent audio extraction activity found"
fi

# Check 5: DLQ Status
echo ""
print_header "5. DLQ Status"

DLQ_INFO=$(curl -s -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
    "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues/%2F/audio_extraction_queue.dlq" 2>/dev/null)

if [ -n "$DLQ_INFO" ] && ! echo "$DLQ_INFO" | grep -q "Not Found\|404"; then
    DLQ_MESSAGES=$(echo "$DLQ_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages', 0))" 2>/dev/null || echo "0")
    
    if [ "$DLQ_MESSAGES" -gt 0 ]; then
        print_warning "DLQ has $DLQ_MESSAGES messages"
        print_info "   💡 Republish: bash scripts/pod/republish-dlq-messages.sh audio_extraction_queue"
    else
        print_success "DLQ is empty"
    fi
else
    print_success "DLQ not found or empty"
fi

# Check 6: FFmpeg Errors in Logs
echo ""
print_header "6. FFmpeg Errors in Logs"

FFMPEG_ERRORS=$(grep -E "FFmpeg.*error|libavdevice.*not found|FFmpeg failed" logs/video-worker.log logs/video-worker-errors.log 2>/dev/null | tail -5 || echo "")

if [ -n "$FFMPEG_ERRORS" ]; then
    print_warning "Recent FFmpeg errors found:"
    echo "$FFMPEG_ERRORS" | while IFS= read -r line; do
        print_warning "   $line"
    done
else
    print_success "No recent FFmpeg errors"
fi

# Summary
echo ""
print_header "📋 Summary"

if [ -n "$WORKER_PID" ] && [ "$CONSUMERS" -gt 0 ] 2>/dev/null; then
    print_success "✅ Audio extraction is ready"
    print_info "   Worker: Running (PID: $WORKER_PID)"
    print_info "   FFmpeg: $FFMPEG_PATH"
    print_info "   Consumers: $CONSUMERS"
elif [ -n "$WORKER_PID" ]; then
    print_warning "⚠️  Worker running but no consumers registered"
    print_info "   💡 Worker may need to reconnect to RabbitMQ"
else
    print_error "❌ Worker is not running"
    print_info "   💡 Start worker: bash scripts/pod/start-service-daemon.sh 8010"
fi

echo ""

