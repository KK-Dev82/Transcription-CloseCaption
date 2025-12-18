#!/bin/bash
# Script สำหรับเคลียร์ tasks เก่าทั้งหมด
#
# วิธีใช้งาน:
#   bash scripts/pod/clear-all-tasks.sh

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

print_header "🧹 Clear All Tasks"

# 1. Clear JSON Storage
print_header "1. Clearing JSON Storage"

JSON_STORAGE_DIR="data/transcriptions"
if [ -d "$JSON_STORAGE_DIR" ]; then
    TASK_COUNT=$(find "$JSON_STORAGE_DIR" -name "*.json" 2>/dev/null | wc -l)
    if [ "$TASK_COUNT" -gt 0 ]; then
        print_info "Found $TASK_COUNT task files"
        rm -f "$JSON_STORAGE_DIR"/*.json
        print_success "Cleared $TASK_COUNT task files"
    else
        print_info "No task files found"
    fi
else
    print_warning "JSON storage directory not found: $JSON_STORAGE_DIR"
fi

# 2. Clear Video Tasks
print_header "2. Clearing Video Tasks"

VIDEO_TASKS_DIR="data/video_tasks"
if [ -d "$VIDEO_TASKS_DIR" ]; then
    TASK_COUNT=$(find "$VIDEO_TASKS_DIR" -name "*.json" 2>/dev/null | wc -l)
    if [ "$TASK_COUNT" -gt 0 ]; then
        print_info "Found $TASK_COUNT video task files"
        rm -f "$VIDEO_TASKS_DIR"/*.json
        print_success "Cleared $TASK_COUNT video task files"
    else
        print_info "No video task files found"
    fi
else
    print_warning "Video tasks directory not found: $VIDEO_TASKS_DIR"
fi

# 3. Clear RabbitMQ Queues (optional - requires confirmation)
print_header "3. RabbitMQ Queues Status"

RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
RABBITMQ_USER=${RABBITMQ_USER:-senate}
RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}
RABBITMQ_MGMT_PORT=${RABBITMQ_MGMT_PORT:-15672}

QUEUES=(
    "transcription_request_queue"
    "audio_extraction_queue"
    "transcription_queue"
    "transcription_chunk_queue"
    "close_caption_request_queue"
    "close_caption_extraction_queue"
    "close_caption_queue"
)

TOTAL_MESSAGES=0
for queue in "${QUEUES[@]}"; do
    QUEUE_INFO=$(curl -s -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
        "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues/%2F/${queue}" 2>/dev/null)
    
    if [ -n "$QUEUE_INFO" ] && ! echo "$QUEUE_INFO" | grep -q "Not Found\|404"; then
        MESSAGES=$(echo "$QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages', 0))" 2>/dev/null || echo "0")
        UNACKED=$(echo "$QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages_unacknowledged', 0))" 2>/dev/null || echo "0")
        
        if [ "$MESSAGES" -gt 0 ] || [ "$UNACKED" -gt 0 ]; then
            print_warning "$queue: $MESSAGES messages, $UNACKED unacked"
            TOTAL_MESSAGES=$((TOTAL_MESSAGES + MESSAGES + UNACKED))
        else
            print_success "$queue: empty"
        fi
    else
        print_info "$queue: not found or not accessible"
    fi
done

if [ "$TOTAL_MESSAGES" -gt 0 ]; then
    echo ""
    print_warning "⚠️  Found $TOTAL_MESSAGES messages in queues"
    print_info "   💡 Messages will be processed or moved to DLQ automatically"
    print_info "   💡 To purge queues manually, use RabbitMQ Management UI"
else
    print_success "All queues are empty"
fi

# 4. Clear Temp Files
print_header "4. Clearing Temp Files"

TEMP_DIRS=(
    "uploads/temp"
    "uploads/audio"
)

for temp_dir in "${TEMP_DIRS[@]}"; do
    if [ -d "$temp_dir" ]; then
        FILE_COUNT=$(find "$temp_dir" -type f 2>/dev/null | wc -l)
        if [ "$FILE_COUNT" -gt 0 ]; then
            print_info "Found $FILE_COUNT files in $temp_dir"
            # Only clear files older than 1 hour
            find "$temp_dir" -type f -mmin +60 -delete 2>/dev/null || true
            print_success "Cleared old files from $temp_dir"
        else
            print_info "No files in $temp_dir"
        fi
    fi
done

# 5. Summary
print_header "📋 Summary"

print_success "✅ All tasks cleared"
print_info "   - JSON storage: cleared"
print_info "   - Video tasks: cleared"
print_info "   - Temp files: cleared (files older than 1 hour)"
print_info "   - RabbitMQ queues: checked (messages will be processed automatically)"
echo ""
print_info "💡 Ready for fresh testing!"
echo ""

