#!/bin/bash
# Script สำหรับทดสอบ Transcription (Optional: เลือก model และ video ได้)
#
# วิธีใช้งาน:
#   bash scripts/pod/test-transcription.sh [video-file] [model-size] [api-url]

set -e

VIDEO_FILE="${1}"
MODEL_SIZE="${2:-medium}"
API_URL="${3:-http://localhost:8001}"

if [ -z "$VIDEO_FILE" ]; then
    echo "❌ Error: Video file path is required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/test-transcription.sh <video-file> [model-size] [api-url]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pod/test-transcription.sh uploads/video.mp4 medium"
    echo "  bash scripts/pod/test-transcription.sh uploads/video.mp4 large-v3"
    echo ""
    echo "Model sizes: base, small, medium, large, large-v2, large-v3"
    exit 1
fi

# Check if file exists
if [ ! -f "$VIDEO_FILE" ]; then
    echo "❌ Error: Video file not found: $VIDEO_FILE"
    exit 1
fi

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_perf() { echo -e "${CYAN}[PERF]${NC} $1"; }

echo "🧪 Testing Transcription"
echo "📅 $(date)"
echo ""
echo "📋 Configuration:"
echo "   Video File: $VIDEO_FILE"
echo "   Model Size: $MODEL_SIZE"
echo "   API URL: $API_URL"
echo ""

# Get file information
FILE_SIZE=$(du -h "$VIDEO_FILE" | cut -f1)
print_perf "📊 File Information:"
echo "   Size: $FILE_SIZE"
echo ""

# Check API health
print_status "Checking API health..."
if ! curl -f -s --max-time 5 "$API_URL/health" > /dev/null 2>&1; then
    print_error "❌ API is not responding at $API_URL"
    exit 1
fi
print_success "✅ API is healthy"
echo ""

# Prepare file path
FILE_PATH="$VIDEO_FILE"
if [[ "$VIDEO_FILE" == uploads/* ]]; then
    FILE_PATH="$VIDEO_FILE"
fi

print_status "Starting transcription..."
TRANSCRIBE_START=$(date +%s)

# Start transcription
RESPONSE=$(curl -s -X POST "$API_URL/transcribe/" \
    -H "Content-Type: application/json" \
    -d "{
        \"file_path\": \"$FILE_PATH\",
        \"language\": \"th\",
        \"model_size\": \"$MODEL_SIZE\"
    }" 2>&1)

# Fallback to legacy endpoint
if echo "$RESPONSE" | grep -q "404\|Not Found" 2>/dev/null; then
    RESPONSE=$(curl -s -X POST "$API_URL/api/transcription/" \
        -H "Content-Type: application/json" \
        -d "{
            \"file_path\": \"$FILE_PATH\",
            \"language\": \"th\",
            \"model_size\": \"$MODEL_SIZE\"
        }" 2>&1)
fi

# Extract task_id
TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id // .id // empty' 2>/dev/null || echo "")

if [ -z "$TASK_ID" ]; then
    print_error "❌ Could not extract task_id from response:"
    echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

print_success "✅ Transcription job started!"
print_perf "   Task ID: $TASK_ID"
echo ""

# Monitor progress
print_status "Monitoring progress..."
MAX_WAIT=3600
WAIT_INTERVAL=5
ELAPSED_WAIT=0

while [ $ELAPSED_WAIT -lt $MAX_WAIT ]; do
    # Try multiple endpoints
    STATUS_RESPONSE=$(curl -s "$API_URL/transcribe/$TASK_ID" 2>/dev/null || echo "")
    
    # Fallback to other endpoints if needed
    if [ -z "$STATUS_RESPONSE" ] || echo "$STATUS_RESPONSE" | grep -q "404\|Not Found" 2>/dev/null; then
        STATUS_RESPONSE=$(curl -s "$API_URL/api/transcription/$TASK_ID" 2>/dev/null || echo "")
    fi
    
    if [ -z "$STATUS_RESPONSE" ] || echo "$STATUS_RESPONSE" | grep -q "404\|Not Found" 2>/dev/null; then
        STATUS_RESPONSE=$(curl -s "$API_URL/history/transcriptions/$TASK_ID" 2>/dev/null || echo "")
    fi
    
    # Check if response is valid JSON
    if [ -z "$STATUS_RESPONSE" ] || ! echo "$STATUS_RESPONSE" | jq . > /dev/null 2>&1; then
        # If first few attempts, wait a bit longer (task might not be created yet)
        if [ $ELAPSED_WAIT -lt 30 ]; then
            sleep $WAIT_INTERVAL
            ELAPSED_WAIT=$((ELAPSED_WAIT + WAIT_INTERVAL))
            continue
        else
            print_warning "⚠️  Invalid API response, retrying..."
            sleep $WAIT_INTERVAL
            ELAPSED_WAIT=$((ELAPSED_WAIT + WAIT_INTERVAL))
            continue
        fi
    fi
    
    # Check for error response
    if echo "$STATUS_RESPONSE" | jq -e '.detail' > /dev/null 2>&1; then
        ERROR_MSG=$(echo "$STATUS_RESPONSE" | jq -r '.detail' 2>/dev/null)
        if echo "$ERROR_MSG" | grep -q "ไม่พบ\|not found\|404" 2>/dev/null; then
            if [ $ELAPSED_WAIT -lt 30 ]; then
                # First 30 seconds, task might not be created yet
                sleep $WAIT_INTERVAL
                ELAPSED_WAIT=$((ELAPSED_WAIT + WAIT_INTERVAL))
                continue
            else
                print_error "❌ Task not found: $TASK_ID"
                exit 1
            fi
        fi
    fi
    
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status // .state // "unknown"' 2>/dev/null || echo "unknown")
    PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.progress // 0' 2>/dev/null || echo "0")
    
    # Validate progress value (should be 0-100)
    if ! [[ "$PROGRESS" =~ ^[0-9]+$ ]] || [ "$PROGRESS" -lt 0 ] || [ "$PROGRESS" -gt 100 ]; then
        PROGRESS=0
    fi
    
    # Only show progress if we have valid data
    if [ "$STATUS" != "unknown" ] && [ "$STATUS" != "" ]; then
        print_status "Progress: ${PROGRESS}% - Status: ${STATUS}"
    elif [ "$PROGRESS" -gt 0 ]; then
        print_status "Progress: ${PROGRESS}% - Status: processing"
    else
        # If status is unknown and progress is 0, might be API issue or task not started yet
        if [ $ELAPSED_WAIT -lt 30 ]; then
            # First 30 seconds, wait silently
            sleep $WAIT_INTERVAL
            ELAPSED_WAIT=$((ELAPSED_WAIT + WAIT_INTERVAL))
            continue
        else
            print_warning "⚠️  Status unknown (Progress: ${PROGRESS}%), checking again..."
        fi
    fi
    
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "success" ]; then
        TRANSCRIBE_END=$(date +%s)
        TRANSCRIBE_TIME=$((TRANSCRIBE_END - TRANSCRIBE_START))
        
        echo ""
        print_success "✅ Transcription completed!"
        print_perf "⏱️  Transcription time: ${TRANSCRIBE_TIME}s"
        echo ""
        exit 0
    elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "error" ]; then
        print_error "❌ Transcription failed!"
        exit 1
    fi
    
    sleep $WAIT_INTERVAL
    ELAPSED_WAIT=$((ELAPSED_WAIT + WAIT_INTERVAL))
done

print_error "❌ Transcription timeout"
exit 1
