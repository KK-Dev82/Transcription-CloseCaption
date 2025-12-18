#!/bin/bash
# Script สำหรับทดสอบ Video Transcription
#
# วิธีใช้งาน:
#   bash scripts/pod/test-video-transcription.sh [video_file_path]

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

API_URL="http://localhost:8010"
TASK_ID="test-$(date +%s)"

print_header "🧪 Test Video Transcription"

# Check if video file provided
if [ -z "$1" ]; then
    print_warning "No video file provided"
    print_info "Creating a test video file (5 seconds)..."
    
    # Create a simple test video using FFmpeg
    TEST_VIDEO="/tmp/test-video-${TASK_ID}.mp4"
    if command -v ffmpeg > /dev/null 2>&1; then
        ffmpeg -f lavfi -i testsrc=duration=5:size=320x240:rate=1 -c:v libx264 -pix_fmt yuv420p "$TEST_VIDEO" -y > /dev/null 2>&1
        if [ -f "$TEST_VIDEO" ]; then
            VIDEO_FILE="$TEST_VIDEO"
            print_success "Test video created: $VIDEO_FILE"
        else
            print_error "Failed to create test video"
            exit 1
        fi
    else
        print_error "FFmpeg not found - cannot create test video"
        print_info "Please provide a video file: bash scripts/pod/test-video-transcription.sh /path/to/video.mp4"
        exit 1
    fi
else
    VIDEO_FILE="$1"
    if [ ! -f "$VIDEO_FILE" ]; then
        print_error "Video file not found: $VIDEO_FILE"
        exit 1
    fi
    print_success "Using video file: $VIDEO_FILE"
fi

# Check API
print_header "1. Checking API Service"

if curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
    print_success "API Service is healthy"
else
    print_error "API Service is not responding"
    exit 1
fi

# Check Worker
print_header "2. Checking Worker"

if curl -s -f "http://localhost:8030/health" > /dev/null 2>&1; then
    print_success "Worker is healthy"
else
    print_warning "Worker health endpoint not responding (may still be starting)"
fi

# Step 1: Upload file
print_header "3. Uploading Video File"

print_info "Video File: $VIDEO_FILE"
print_info "Upload URL: ${API_URL}/upload/"
echo ""

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
echo ""

# Step 2: Send transcription request
print_header "4. Sending Transcription Request"

print_info "Task ID: $TASK_ID"
print_info "File Path: $FILE_PATH"
print_info "API URL: ${API_URL}/transcribe/"
echo ""

RESPONSE=$(curl -s -X POST "${API_URL}/transcribe/" \
    -H "Content-Type: application/json" \
    -d "{
        \"file_path\": \"${FILE_PATH}\",
        \"file_name\": \"${FILE_NAME}\",
        \"language\": \"th\",
        \"model_size\": \"base\",
        \"chunk_duration\": 30,
        \"use_chunking\": false,
        \"display_mode\": \"full_text\"
    }" \
    -w "\nHTTP_CODE:%{http_code}")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
RESPONSE_BODY=$(echo "$RESPONSE" | grep -v "HTTP_CODE:")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "202" ]; then
    print_success "Transcription request sent successfully"
    echo "$RESPONSE_BODY" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
else
    print_error "Failed to send transcription request (HTTP $HTTP_CODE)"
    echo "$RESPONSE_BODY"
    exit 1
fi

# Monitor task status
print_header "5. Monitoring Task Status"

print_info "Waiting for task to be processed..."
print_info "Task ID: $TASK_ID"
echo ""

MAX_WAIT=300  # 5 minutes
WAIT_INTERVAL=5
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    TASK_STATUS=$(curl -s "${API_URL}/transcribe/${TASK_ID}" 2>/dev/null || echo "")
    
    if [ -n "$TASK_STATUS" ]; then
        STATUS=$(echo "$TASK_STATUS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('status', 'unknown'))" 2>/dev/null || echo "unknown")
        
        case "$STATUS" in
            "completed")
                print_success "✅ Task completed!"
                echo "$TASK_STATUS" | python3 -m json.tool 2>/dev/null || echo "$TASK_STATUS"
                break
                ;;
            "processing"|"pending")
                print_info "   Status: $STATUS (${ELAPSED}s/${MAX_WAIT}s)"
                ;;
            "failed"|"error")
                print_error "❌ Task failed!"
                echo "$TASK_STATUS" | python3 -m json.tool 2>/dev/null || echo "$TASK_STATUS"
                break
                ;;
            *)
                print_info "   Status: $STATUS (${ELAPSED}s/${MAX_WAIT}s)"
                ;;
        esac
    else
        print_warning "   Cannot get task status (${ELAPSED}s/${MAX_WAIT}s)"
    fi
    
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    print_warning "⚠️  Timeout waiting for task completion"
    print_info "   Check task status manually: curl ${API_URL}/transcribe/${TASK_ID}"
fi

# Check DLQ
print_header "6. Checking DLQ Status"

bash scripts/pod/check-dlq-status.sh 2>&1 | grep -A 3 "audio_extraction_queue" || echo "No DLQ issues"

# Cleanup test video if created
if [ -n "$TEST_VIDEO" ] && [ -f "$TEST_VIDEO" ]; then
    rm -f "$TEST_VIDEO"
    print_info "Cleaned up test video: $TEST_VIDEO"
fi

echo ""
print_header "📋 Test Complete"

