#!/bin/bash
# Script สำหรับจัดการ Transcription Tasks
#
# วิธีใช้งาน:
#   bash scripts/pod/task-service.sh list                    # แสดง list tasks
#   bash scripts/pod/task-service.sh stop <task-id>          # หยุด task
#   bash scripts/pod/task-service.sh clear <task-id>         # ลบ task
#   bash scripts/pod/task-service.sh clear-all                # ลบ tasks ทั้งหมด (completed/failed/cancelled)
#   bash scripts/pod/task-service.sh status <task-id>         # ดูสถานะ task
#   bash scripts/pod/task-service.sh cleanup [hours]          # ลบ tasks เก่า (default: 24 hours)

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

ACTION="${1}"
TASK_ID="${2}"
API_URL="${API_URL:-http://localhost:8001}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Function to check API health
check_api_health() {
    if ! curl -f -s --max-time 5 "$API_URL/health" > /dev/null 2>&1; then
        print_error "❌ API is not responding at $API_URL"
        print_status "💡 Check if services are running: bash scripts/pod/check-pod.sh"
        exit 1
    fi
}

# Function to list all tasks
list_tasks() {
    print_header "📋 Transcription Tasks List"
    echo "📅 $(date)"
    echo ""
    
    check_api_health
    
    print_status "Fetching tasks..."
    
    # Try /api/history/transcriptions first
    RESPONSE=$(curl -s "$API_URL/api/history/transcriptions?limit=100" 2>/dev/null || echo "")
    
    # Fallback to /transcribe/
    if [ -z "$RESPONSE" ] || echo "$RESPONSE" | grep -q "404\|Not Found" 2>/dev/null; then
        RESPONSE=$(curl -s "$API_URL/transcribe/" 2>/dev/null || echo "")
    fi
    
    if [ -z "$RESPONSE" ] || echo "$RESPONSE" | grep -q "404\|Not Found" 2>/dev/null; then
        RESPONSE=$(curl -s "$API_URL/api/transcription/" 2>/dev/null || echo "")
    fi
    
    if [ -z "$RESPONSE" ]; then
        print_error "❌ Failed to fetch tasks"
        exit 1
    fi
    
    if command -v jq &> /dev/null; then
        # Check if response is an object with 'history' key (from /history/transcriptions)
        if echo "$RESPONSE" | jq -e '.history' > /dev/null 2>&1; then
            TASKS_JSON=$(echo "$RESPONSE" | jq '.history' 2>/dev/null)
        # Check if response is an object with 'transcriptions' key
        elif echo "$RESPONSE" | jq -e '.transcriptions' > /dev/null 2>&1; then
            TASKS_JSON=$(echo "$RESPONSE" | jq '.transcriptions' 2>/dev/null)
        # Otherwise assume it's an array directly
        else
            TASKS_JSON="$RESPONSE"
        fi
        
        TASK_COUNT=$(echo "$TASKS_JSON" | jq 'length' 2>/dev/null || echo "0")
        
        if [ "$TASK_COUNT" -eq 0 ] || [ -z "$TASK_COUNT" ] || [ "$TASK_COUNT" = "null" ]; then
            print_warning "⚠️  No tasks found"
            exit 0
        fi
        
        echo ""
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "Available Tasks ($TASK_COUNT)"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        echo "$TASKS_JSON" | jq -r '.[] | "\(.task_id // .id // "")|\(.status // "unknown")|\(.file_name // .filename // .file_path // "N/A")|\(.progress // 0)|\(.created_at // "N/A")"' 2>/dev/null | while IFS='|' read -r task_id status filename progress created_at; do
            if [ -n "$task_id" ] && [ "$task_id" != "null" ]; then
                # Color code by status
                if [ "$status" = "completed" ]; then
                    STATUS_COLOR="${GREEN}"
                elif [ "$status" = "processing" ] || [ "$status" = "pending" ] || [ "$status" = "waiting_for_chunks" ] || [ "$status" = "processing_chunks" ]; then
                    STATUS_COLOR="${YELLOW}"
                elif [ "$status" = "failed" ]; then
                    STATUS_COLOR="${RED}"
                elif [ "$status" = "cancelled" ]; then
                    STATUS_COLOR="${CYAN}"
                else
                    STATUS_COLOR="${NC}"
                fi
                
                echo -e "  ${STATUS_COLOR}${status}${NC} | ${progress}% | ${task_id}"
                echo "      File: $filename"
                echo "      Created: $created_at"
                echo ""
            fi
        done
    else
        print_error "❌ jq not found - cannot parse JSON"
        print_status "💡 Install jq: apt-get install -y jq"
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    fi
}

# Function to stop/cancel a task
stop_task() {
    local task_id=$1
    
    if [ -z "$task_id" ]; then
        print_error "❌ Task ID is required"
        echo ""
        echo "Usage:"
        echo "  bash scripts/pod/task-service.sh stop <task-id>"
        exit 1
    fi
    
    print_header "🛑 Stopping Task: $task_id"
    echo ""
    
    check_api_health
    
    print_status "Cancelling task..."
    
    # Try DELETE /transcribe/{task_id}
    HTTP_CODE=$(curl -s -o /tmp/task_cancel_response.json -w "%{http_code}" -X DELETE "$API_URL/transcribe/$task_id" 2>/dev/null || echo "000")
    RESPONSE=$(cat /tmp/task_cancel_response.json 2>/dev/null || echo "")
    rm -f /tmp/task_cancel_response.json 2>/dev/null || true
    
    # Check HTTP status code
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "204" ]; then
        # Success - check response content
        if echo "$RESPONSE" | grep -q "ยกเลิก\|success\|message" 2>/dev/null || [ -z "$RESPONSE" ]; then
            print_success "✅ Task cancelled successfully"
            if [ -n "$RESPONSE" ] && command -v jq &> /dev/null; then
                echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
            fi
        else
            # Check if response contains error
            if echo "$RESPONSE" | jq -e '.detail' > /dev/null 2>&1; then
                ERROR_MSG=$(echo "$RESPONSE" | jq -r '.detail' 2>/dev/null)
                if echo "$ERROR_MSG" | grep -q "ไม่สามารถยกเลิก\|ไม่พบ\|not found" 2>/dev/null; then
                    print_error "❌ $ERROR_MSG"
                    exit 1
                fi
            fi
            print_success "✅ Task cancelled successfully"
            if command -v jq &> /dev/null; then
                echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
            else
                echo "$RESPONSE"
            fi
        fi
    elif [ "$HTTP_CODE" = "404" ]; then
        print_error "❌ Task not found: $task_id"
        if [ -n "$RESPONSE" ]; then
            if command -v jq &> /dev/null && echo "$RESPONSE" | jq -e '.detail' > /dev/null 2>&1; then
                ERROR_MSG=$(echo "$RESPONSE" | jq -r '.detail' 2>/dev/null)
                echo "   $ERROR_MSG"
            else
                echo "$RESPONSE"
            fi
        fi
        exit 1
    elif [ "$HTTP_CODE" = "000" ] || [ -z "$HTTP_CODE" ]; then
        print_error "❌ Failed to connect to API"
        exit 1
    else
        # Check response for error message
        if [ -n "$RESPONSE" ]; then
            if command -v jq &> /dev/null && echo "$RESPONSE" | jq -e '.detail' > /dev/null 2>&1; then
                ERROR_MSG=$(echo "$RESPONSE" | jq -r '.detail' 2>/dev/null)
                print_error "❌ $ERROR_MSG"
            else
                print_error "❌ Failed to cancel task (HTTP $HTTP_CODE)"
                echo "$RESPONSE"
            fi
        else
            print_error "❌ Failed to cancel task (HTTP $HTTP_CODE)"
        fi
        exit 1
    fi
}

# Function to clear/delete a task
clear_task() {
    local task_id=$1
    
    if [ -z "$task_id" ]; then
        print_error "❌ Task ID is required"
        echo ""
        echo "Usage:"
        echo "  bash scripts/pod/task-service.sh clear <task-id>"
        exit 1
    fi
    
    print_header "🗑️  Clearing Task: $task_id"
    echo ""
    
    check_api_health
    
    print_warning "⚠️  This will permanently delete the task and its data"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Cancelled"
        exit 0
    fi
    
    print_status "Deleting task..."
    
    # Try DELETE /api/history/transcriptions/{task_id}
    RESPONSE=$(curl -s -X DELETE "$API_URL/api/history/transcriptions/$task_id" 2>/dev/null || echo "")
    
    # Fallback to DELETE /transcribe/{task_id} (if it supports permanent delete)
    if [ -z "$RESPONSE" ] || echo "$RESPONSE" | grep -q "404\|Not Found" 2>/dev/null; then
        RESPONSE=$(curl -s -X DELETE "$API_URL/transcribe/$task_id" 2>/dev/null || echo "")
    fi
    
    # Also delete from storage directly
    TASK_DIR="$PROJECT_ROOT/storage/transcriptions/$task_id"
    if [ -d "$TASK_DIR" ]; then
        print_status "Removing storage directory..."
        rm -rf "$TASK_DIR" && print_success "✅ Storage directory removed"
    fi
    
    OLD_FILE="$PROJECT_ROOT/storage/transcriptions/$task_id.json"
    if [ -f "$OLD_FILE" ]; then
        print_status "Removing old format file..."
        rm -f "$OLD_FILE" && print_success "✅ Old format file removed"
    fi
    
    if echo "$RESPONSE" | grep -q "success\|deleted\|ลบ" 2>/dev/null; then
        print_success "✅ Task deleted successfully"
    elif echo "$RESPONSE" | grep -q "404\|Not Found\|ไม่พบ" 2>/dev/null; then
        print_warning "⚠️  Task not found in API, but storage files removed"
    else
        print_success "✅ Task storage files removed"
    fi
}

# Function to clear all tasks
clear_all() {
    print_header "🗑️  Clearing All Tasks"
    echo ""
    
    check_api_health
    
    print_warning "⚠️  This will permanently delete ALL completed/failed/cancelled tasks"
    print_warning "⚠️  Tasks with status: pending, processing will NOT be deleted"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Cancelled"
        exit 0
    fi
    
    print_status "Cleaning up tasks..."
    
    # Use cleanup endpoint
    RESPONSE=$(curl -s -X POST "$API_URL/transcribe/cleanup" \
        -H "Content-Type: application/json" \
        -d '{
            "max_age_hours": 0,
            "statuses": ["completed", "failed", "cancelled"]
        }' 2>/dev/null || echo "")
    
    if echo "$RESPONSE" | grep -q "success\|removed\|ลบ" 2>/dev/null; then
        if command -v jq &> /dev/null; then
            REMOVED_COUNT=$(echo "$RESPONSE" | jq -r '.removed_count // .count // 0' 2>/dev/null || echo "0")
            print_success "✅ Cleaned up $REMOVED_COUNT tasks"
            echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
        else
            print_success "✅ Tasks cleaned up"
            echo "$RESPONSE"
        fi
    else
        print_warning "⚠️  Unexpected response:"
        echo "$RESPONSE"
    fi
}

# Function to cleanup old tasks
cleanup_tasks() {
    local max_age_hours="${1:-24}"
    
    print_header "🧹 Cleanup Old Tasks (older than $max_age_hours hours)"
    echo ""
    
    check_api_health
    
    print_status "Cleaning up tasks older than $max_age_hours hours..."
    
    RESPONSE=$(curl -s -X POST "$API_URL/transcribe/cleanup" \
        -H "Content-Type: application/json" \
        -d "{
            \"max_age_hours\": $max_age_hours,
            \"statuses\": [\"completed\", \"failed\", \"cancelled\"]
        }" 2>/dev/null || echo "")
    
    if echo "$RESPONSE" | grep -q "success\|removed\|ลบ" 2>/dev/null; then
        if command -v jq &> /dev/null; then
            REMOVED_COUNT=$(echo "$RESPONSE" | jq -r '.removed_count // .count // 0' 2>/dev/null || echo "0")
            print_success "✅ Cleaned up $REMOVED_COUNT tasks"
            echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
        else
            print_success "✅ Tasks cleaned up"
            echo "$RESPONSE"
        fi
    else
        print_warning "⚠️  Unexpected response:"
        echo "$RESPONSE"
    fi
}

# Function to get task status
get_task_status() {
    local task_id=$1
    
    if [ -z "$task_id" ]; then
        print_error "❌ Task ID is required"
        echo ""
        echo "Usage:"
        echo "  bash scripts/pod/task-service.sh status <task-id>"
        exit 1
    fi
    
    print_header "📊 Task Status: $task_id"
    echo ""
    
    check_api_health
    
    print_status "Fetching task status..."
    
    # Try /transcribe/{task_id}
    RESPONSE=$(curl -s "$API_URL/transcribe/$task_id" 2>/dev/null || echo "")
    
    # Fallback to /api/history/transcriptions/{task_id}
    if [ -z "$RESPONSE" ] || echo "$RESPONSE" | grep -q "404\|Not Found" 2>/dev/null; then
        RESPONSE=$(curl -s "$API_URL/api/history/transcriptions/$task_id" 2>/dev/null || echo "")
    fi
    
    if [ -z "$RESPONSE" ] || echo "$RESPONSE" | grep -q "404\|Not Found\|ไม่พบ" 2>/dev/null; then
        print_error "❌ Task not found: $task_id"
        exit 1
    fi
    
    if command -v jq &> /dev/null; then
        STATUS=$(echo "$RESPONSE" | jq -r '.status // .basic_info.status // "unknown"' 2>/dev/null)
        PROGRESS=$(echo "$RESPONSE" | jq -r '.progress // .basic_info.progress // 0' 2>/dev/null)
        FILENAME=$(echo "$RESPONSE" | jq -r '.file_name // .filename // .file_path // "N/A"' 2>/dev/null)
        
        echo ""
        echo "   Status: $STATUS"
        echo "   Progress: ${PROGRESS}%"
        echo "   File: $FILENAME"
        echo ""
        echo "$RESPONSE" | jq . 2>/dev/null
    else
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    fi
}

# Function to purge RabbitMQ queue
purge_queue() {
    local queue_name="${1:-transcription_chunk_queue}"
    
    print_header "🗑️  Purging RabbitMQ Queue"
    echo ""
    
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
    
    print_status "Queue: $queue_name"
    print_status "RabbitMQ: $RABBITMQ_HOST:$RABBITMQ_MGMT_PORT"
    echo ""
    
    # Check queue status first
    QUEUE_INFO=$(curl -s -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues/%2F/${queue_name}" 2>/dev/null)
    
    if [ -z "$QUEUE_INFO" ] || echo "$QUEUE_INFO" | grep -q "Not Found\|404" 2>/dev/null; then
        print_error "❌ Queue '$queue_name' not found"
        exit 1
    fi
    
    MESSAGES=$(echo "$QUEUE_INFO" | jq -r '.messages // 0' 2>/dev/null || echo "0")
    
    if [ "$MESSAGES" -eq 0 ]; then
        print_success "✅ Queue is already empty"
        exit 0
    fi
    
    print_warning "⚠️  Queue has $MESSAGES messages"
    echo ""
    read -p "Are you sure you want to purge all messages? (y/N) " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Cancelled"
        exit 0
    fi
    
    # Purge queue
    RESPONSE=$(curl -s -X DELETE -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues/%2F/${queue_name}/contents" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        print_success "✅ Purged $MESSAGES messages from queue '$queue_name'"
    else
        print_error "❌ Failed to purge queue"
        exit 1
    fi
}

# Main command router
case "$ACTION" in
    list)
        list_tasks
        ;;
    stop)
        stop_task "$TASK_ID"
        ;;
    clear)
        clear_task "$TASK_ID"
        ;;
    clear-all)
        clear_all
        ;;
    cleanup)
        cleanup_tasks "$TASK_ID"  # TASK_ID is used as max_age_hours here
        ;;
    status)
        get_task_status "$TASK_ID"
        ;;
    purge-queue)
        purge_queue "$TASK_ID"  # TASK_ID is used as queue_name here
        ;;
    *)
        echo "📋 Task Service - Manage Transcription Tasks"
        echo ""
        echo "Usage:"
        echo "  bash scripts/pod/task-service.sh <command> [options]"
        echo ""
        echo "Commands:"
        echo "  list                    List all tasks"
        echo "  stop <task-id>          Stop/cancel a running task"
        echo "  clear <task-id>         Permanently delete a task"
        echo "  clear-all               Delete all completed/failed/cancelled tasks"
        echo "  cleanup [hours]         Cleanup old tasks (default: 24 hours)"
        echo "  status <task-id>        View task status"
        echo "  purge-queue [queue]     Purge RabbitMQ queue (default: transcription_chunk_queue)"
        echo ""
        echo "Examples:"
        echo "  bash scripts/pod/task-service.sh list"
        echo "  bash scripts/pod/task-service.sh stop 34a7d75c-2cc3-4138-a548-9955010cf2e2"
        echo "  bash scripts/pod/task-service.sh clear 34a7d75c-2cc3-4138-a548-9955010cf2e2"
        echo "  bash scripts/pod/task-service.sh clear-all"
        echo "  bash scripts/pod/task-service.sh cleanup 48"
        echo "  bash scripts/pod/task-service.sh status 34a7d75c-2cc3-4138-a548-9955010cf2e2"
        echo "  bash scripts/pod/task-service.sh purge-queue transcription_chunk_queue"
        exit 1
        ;;
esac

