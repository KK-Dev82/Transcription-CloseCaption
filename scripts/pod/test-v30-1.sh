#!/bin/bash
# Script สำหรับทดสอบ transcription ด้วยไฟล์ /uploads/v30-1.mp4
#
# วิธีใช้งาน:
#   bash scripts/pod/test-v30-1.sh

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

VIDEO_FILE="/workspace/transcription-service/uploads/v30-1.mp4"
API_URL="http://localhost:8010"

print_header "🧪 Test Transcription with v30-1.mp4"

# Check if file exists
if [ ! -f "$VIDEO_FILE" ]; then
    print_error "Video file not found: $VIDEO_FILE"
    exit 1
fi

print_success "Video file found: $VIDEO_FILE"
FILE_SIZE=$(du -h "$VIDEO_FILE" | cut -f1)
print_info "   File size: $FILE_SIZE"

# Step 1: Upload file
print_header "1. Uploading Video File"

UPLOAD_RESPONSE=$(curl -s -X POST "${API_URL}/upload/" \
    -F "file=@${VIDEO_FILE}" \
    -w "\nHTTP_CODE:%{http_code}")

UPLOAD_HTTP_CODE=$(echo "$UPLOAD_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
UPLOAD_BODY=$(echo "$UPLOAD_RESPONSE" | grep -v "HTTP_CODE:")

if [ "$UPLOAD_HTTP_CODE" != "200" ]; then
    print_error "Failed to upload file (HTTP $UPLOAD_HTTP_CODE)"
    echo "$UPLOAD_BODY"
    exit 1
fi

print_success "File uploaded successfully"
FILE_PATH=$(echo "$UPLOAD_BODY" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('file_path', ''))" 2>/dev/null || echo "")
FILE_NAME=$(echo "$UPLOAD_BODY" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('file_name', ''))" 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
    print_error "Failed to get file_path from upload response"
    echo "$UPLOAD_BODY"
    exit 1
fi

print_info "   File Path: $FILE_PATH"
print_info "   File Name: $FILE_NAME"

# Step 2: Start transcription
print_header "2. Starting Transcription"

TASK_RESPONSE=$(curl -s -X POST "${API_URL}/transcribe/" \
    -H "Content-Type: application/json" \
    -d "{
        \"file_path\": \"${FILE_PATH}\",
        \"file_name\": \"${FILE_NAME}\",
        \"language\": \"th\",
        \"model_size\": \"base\",
        \"chunk_duration\": 30,
        \"use_chunking\": true,
        \"display_mode\": \"full_text\"
    }" \
    -w "\nHTTP_CODE:%{http_code}")

TASK_HTTP_CODE=$(echo "$TASK_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
TASK_BODY=$(echo "$TASK_RESPONSE" | grep -v "HTTP_CODE:")

if [ "$TASK_HTTP_CODE" != "200" ]; then
    print_error "Failed to start transcription (HTTP $TASK_HTTP_CODE)"
    echo "$TASK_BODY"
    exit 1
fi

TASK_ID=$(echo "$TASK_BODY" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('task_id', ''))" 2>/dev/null || echo "")

if [ -z "$TASK_ID" ]; then
    print_error "Failed to get task_id from response"
    echo "$TASK_BODY"
    exit 1
fi

print_success "Transcription started"
print_info "   Task ID: $TASK_ID"
print_info "   Status URL: ${API_URL}/transcribe/${TASK_ID}"

# Step 3: Monitor progress
print_header "3. Monitoring Progress"

MAX_WAIT=600  # 10 minutes
CHECK_INTERVAL=5
ELAPSED=0
LAST_STATUS=""
LAST_PROGRESS=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS_RESPONSE=$(curl -s "${API_URL}/transcribe/${TASK_ID}" 2>/dev/null || echo "{}")
    STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('status', 'unknown'))" 2>/dev/null || echo "unknown")
    PROGRESS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('progress', 0))" 2>/dev/null || echo "0")
    STAGE=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('current_stage', ''))" 2>/dev/null || echo "")
    
    # Only print if status or progress changed
    if [ "$STATUS" != "$LAST_STATUS" ] || [ "$PROGRESS" != "$LAST_PROGRESS" ]; then
        if [ -n "$STAGE" ] && [ "$STAGE" != "null" ]; then
            print_info "[${ELAPSED}s] Status: $STATUS, Progress: $PROGRESS%, Stage: $STAGE"
        else
            print_info "[${ELAPSED}s] Status: $STATUS, Progress: $PROGRESS%"
        fi
        LAST_STATUS="$STATUS"
        LAST_PROGRESS="$PROGRESS"
    fi
    
    if [ "$STATUS" = "completed" ]; then
        print_success "Transcription completed!"
        break
    elif [ "$STATUS" = "failed" ]; then
        ERROR_MSG=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('error_message', 'Unknown error'))" 2>/dev/null || echo "Unknown error")
        print_error "Transcription failed: $ERROR_MSG"
        break
    fi
    
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    print_warning "Timeout waiting for completion"
fi

# Step 4: Show final result
print_header "4. Final Result"

FINAL_RESPONSE=$(curl -s "${API_URL}/transcribe/${TASK_ID}" 2>/dev/null || echo "{}")
FINAL_STATUS=$(echo "$FINAL_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('status', 'unknown'))" 2>/dev/null || echo "unknown")

if [ "$FINAL_STATUS" = "completed" ]; then
    FULL_TEXT=$(echo "$FINAL_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('full_text', '')[:200])" 2>/dev/null || echo "")
    SEGMENTS_COUNT=$(echo "$FINAL_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('chunks', [])))" 2>/dev/null || echo "0")
    
    print_success "✅ Transcription completed successfully!"
    print_info "   Segments: $SEGMENTS_COUNT"
    if [ -n "$FULL_TEXT" ] && [ "$FULL_TEXT" != "null" ]; then
        print_info "   Preview: ${FULL_TEXT}..."
    fi
else
    print_error "❌ Transcription status: $FINAL_STATUS"
    echo "$FINAL_RESPONSE" | python3 -m json.tool 2>/dev/null | head -20
fi

echo ""
print_info "💡 Check full result: curl ${API_URL}/transcribe/${TASK_ID}"
echo ""

