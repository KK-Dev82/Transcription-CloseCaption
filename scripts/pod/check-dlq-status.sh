#!/bin/bash
# Script สำหรับตรวจสอบ DLQ status และ republish messages

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

cd /workspace/transcription-service 2>/dev/null || {
    print_error "Cannot find project directory"
    exit 1
}

# Load environment variables
if [ -f ".env.runpod" ]; then
    set -a
    source .env.runpod
    set +a
fi

RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
RABBITMQ_USER=${RABBITMQ_USER:-senate}
RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}
RABBITMQ_MGMT_PORT=${RABBITMQ_MGMT_PORT:-15672}

print_header "🔍 Check DLQ Status"

# Queues to check
QUEUES=(
    "audio_extraction_queue"
    "transcription_queue"
    "transcription_request_queue"
)

TOTAL_DLQ_MESSAGES=0

for QUEUE_NAME in "${QUEUES[@]}"; do
    DLQ_NAME="${QUEUE_NAME}.dlq"
    
    echo ""
    print_header "Queue: $QUEUE_NAME"
    
    # Check main queue
    MAIN_QUEUE_INFO=$(curl -s -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
        "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues/%2F/${QUEUE_NAME}" 2>/dev/null)
    
    if [ -z "$MAIN_QUEUE_INFO" ] || echo "$MAIN_QUEUE_INFO" | grep -q "Not Found\|404" 2>/dev/null; then
        print_warning "Main queue '$QUEUE_NAME' not found"
    else
        MAIN_MESSAGES=$(echo "$MAIN_QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages', 0))" 2>/dev/null || echo "0")
        MAIN_CONSUMERS=$(echo "$MAIN_QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('consumers', 0))" 2>/dev/null || echo "0")
        
        echo "   Main queue: $MAIN_MESSAGES messages, $MAIN_CONSUMERS consumers"
    fi
    
    # Check DLQ
    DLQ_INFO=$(curl -s -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
        "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues/%2F/${DLQ_NAME}" 2>/dev/null)
    
    if [ -z "$DLQ_INFO" ] || echo "$DLQ_INFO" | grep -q "Not Found\|404" 2>/dev/null; then
        print_success "DLQ '$DLQ_NAME' not found (no messages in DLQ)"
    else
        DLQ_MESSAGES=$(echo "$DLQ_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages', 0))" 2>/dev/null || echo "0")
        
        if [ "$DLQ_MESSAGES" -gt 0 ]; then
            print_warning "⚠️  DLQ '$DLQ_NAME' has $DLQ_MESSAGES messages"
            TOTAL_DLQ_MESSAGES=$((TOTAL_DLQ_MESSAGES + DLQ_MESSAGES))
        else
            print_success "DLQ '$DLQ_NAME' is empty"
        fi
    fi
done

echo ""
print_header "Summary"

if [ $TOTAL_DLQ_MESSAGES -gt 0 ]; then
    print_warning "Total messages in DLQ: $TOTAL_DLQ_MESSAGES"
    echo ""
    print_info "💡 Actions:"
    echo "   1. Start worker: bash scripts/pod/start-service-daemon.sh"
    echo "   2. Republish DLQ messages: bash scripts/pod/republish-dlq-messages.sh [queue_name]"
    echo ""
    echo "   Example:"
    echo "   bash scripts/pod/republish-dlq-messages.sh audio_extraction_queue"
else
    print_success "No messages in DLQ - all queues are healthy"
fi

