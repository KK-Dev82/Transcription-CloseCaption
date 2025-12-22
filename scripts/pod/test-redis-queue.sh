#!/bin/bash
# Test Redis Queue System
# ทดสอบ 1 request และ 5 concurrent requests

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

# Load environment
if [ -f ".env.runpod" ]; then
    set +u
    source .env.runpod
    set -u
fi

API_URL=${API_URL:-http://localhost:8010}
FILE_PATH=${1:-uploads/v30-1.mp4}

print_info "Testing Redis Queue System"
print_info "API URL: $API_URL"
print_info "File: $FILE_PATH"
echo ""

# Test 1: Single Request
print_info "=" | head -c 70 && echo ""
print_info "Test 1: Single Request"
print_info "=" | head -c 70 && echo ""

START_TIME=$(date +%s)
RESPONSE=$(curl -s -X POST "$API_URL/api/transcribe/" \
  -H "Content-Type: application/json" \
  -d "{
    \"file_path\": \"$FILE_PATH\",
    \"language\": \"th\",
    \"model_size\": \"base\",
    \"chunk_duration\": 90
  }")

TASK_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))" 2>/dev/null)
QUEUE_TYPE=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('queue', 'unknown'))" 2>/dev/null)

if [ -n "$TASK_ID" ]; then
    print_success "✅ Task created: $TASK_ID"
    print_info "   Queue: $QUEUE_TYPE"
    print_info "   Response time: $(($(date +%s) - START_TIME))s"
    
    # Monitor progress
    print_info ""
    print_info "Monitoring progress..."
    MAX_WAIT=600  # 10 minutes
    ELAPSED=0
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        STATUS_RESP=$(curl -s "$API_URL/api/tasks/$TASK_ID")
        STATUS=$(echo "$STATUS_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null)
        PROGRESS=$(echo "$STATUS_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('progress', 0))" 2>/dev/null)
        
        echo -ne "\r   Status: $STATUS | Progress: $PROGRESS% | Elapsed: ${ELAPSED}s"
        
        if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
            echo ""
            END_TIME=$(date +%s)
            TOTAL_TIME=$((END_TIME - START_TIME))
            
            if [ "$STATUS" = "completed" ]; then
                print_success "✅ Task completed in ${TOTAL_TIME}s"
                TEXT_LENGTH=$(echo "$STATUS_RESP" | python3 -c "import sys, json; text=json.load(sys.stdin).get('full_text', ''); print(len(text))" 2>/dev/null)
                print_info "   Text length: ${TEXT_LENGTH} chars"
            else
                ERROR=$(echo "$STATUS_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error_message', 'Unknown error'))" 2>/dev/null)
                print_error "❌ Task failed: $ERROR"
            fi
            break
        fi
        
        sleep 2
        ELAPSED=$((ELAPSED + 2))
    done
    
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo ""
        print_warning "⚠️  Timeout waiting for task completion"
    fi
else
    print_error "❌ Failed to create task"
    echo "$RESPONSE"
    exit 1
fi

echo ""
print_info "=" | head -c 70 && echo ""
print_info "Test 2: 5 Concurrent Requests"
print_info "=" | head -c 70 && echo ""

# Test 2: 5 Concurrent Requests
CONCURRENT_START=$(date +%s)
TASK_IDS=()

for i in {1..5}; do
    print_info "Creating request $i/5..."
    RESP=$(curl -s -X POST "$API_URL/api/transcribe/" \
      -H "Content-Type: application/json" \
      -d "{
        \"file_path\": \"$FILE_PATH\",
        \"language\": \"th\",
        \"model_size\": \"base\",
        \"chunk_duration\": 90
      }")
    
    TID=$(echo "$RESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))" 2>/dev/null)
    if [ -n "$TID" ]; then
        TASK_IDS+=("$TID")
        print_success "  Request $i: $TID"
    else
        print_error "  Request $i: Failed"
    fi
done

print_info ""
print_info "Monitoring ${#TASK_IDS[@]} tasks..."
COMPLETED=0
FAILED=0

while [ $COMPLETED -lt ${#TASK_IDS[@]} ] && [ $FAILED -lt ${#TASK_IDS[@]} ]; do
    COMPLETED=0
    FAILED=0
    
    for TID in "${TASK_IDS[@]}"; do
        STATUS_RESP=$(curl -s "$API_URL/api/tasks/$TID")
        STATUS=$(echo "$STATUS_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null)
        
        if [ "$STATUS" = "completed" ]; then
            COMPLETED=$((COMPLETED + 1))
        elif [ "$STATUS" = "failed" ]; then
            FAILED=$((FAILED + 1))
        fi
    done
    
    echo -ne "\r   Completed: $COMPLETED/${#TASK_IDS[@]} | Failed: $FAILED/${#TASK_IDS[@]}"
    sleep 2
done

echo ""
CONCURRENT_END=$(date +%s)
CONCURRENT_TIME=$((CONCURRENT_END - CONCURRENT_START))

print_success "✅ All tasks finished in ${CONCURRENT_TIME}s"
print_info "   Completed: $COMPLETED"
print_info "   Failed: $FAILED"

echo ""
print_info "=" | head -c 70 && echo ""
print_info "Summary"
print_info "=" | head -c 70 && echo ""
print_info "Single request time: ${TOTAL_TIME}s"
print_info "5 concurrent requests time: ${CONCURRENT_TIME}s"
print_info "Average per request: $((CONCURRENT_TIME / 5))s"

