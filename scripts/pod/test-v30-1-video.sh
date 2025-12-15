#!/bin/bash
# Script สำหรับทดสอบ Transcription ด้วย video v30-1.mp4
#
# วิธีใช้งาน:
#   bash scripts/pod/test-v30-1-video.sh [API_URL] [VIDEO_PATH]
#
# Parameters:
#   API_URL     - API endpoint URL (optional, default: http://localhost:8010)
#   VIDEO_PATH  - Path to video file (optional, default: v30-1.mp4)

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse parameters
API_URL="${1:-http://localhost:8010}"
VIDEO_PATH="${2:-v30-1.mp4}"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🧪 Testing Transcription with v30-1.mp4                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
print_status "API URL: $API_URL"
print_status "Video Path: $VIDEO_PATH"
echo ""

# Check if video file exists
if [ ! -f "$VIDEO_PATH" ]; then
    print_error "❌ Video file not found: $VIDEO_PATH"
    echo ""
    echo "💡 Please provide the correct path to v30-1.mp4"
    echo "   Example: bash scripts/pod/test-v30-1-video.sh http://localhost:8010 /path/to/v30-1.mp4"
    exit 1
fi

# Check API health
print_status "Checking API health..."
HEALTH_RESPONSE=$(curl -s -f "$API_URL/health" 2>/dev/null || echo "")
if [ -z "$HEALTH_RESPONSE" ]; then
    print_error "❌ API is not responding at $API_URL"
    echo "   Please check if the service is running"
    exit 1
fi
print_success "✅ API is healthy"

# Check queue status
print_status "Checking queue status..."
QUEUE_STATUS=$(curl -s "$API_URL/api/queue/status" 2>/dev/null || echo "")
if [ -n "$QUEUE_STATUS" ]; then
    echo "$QUEUE_STATUS" | python3 -m json.tool 2>/dev/null || echo "$QUEUE_STATUS"
    echo ""
fi

# Upload video file (if needed)
# Note: This assumes the video is already accessible via file_path or file_url
# If you need to upload, use the /upload endpoint first

# Test 1: Normal Transcription (full_text)
print_status ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 Test 1: Normal Transcription (full_text, priority=5)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

REQUEST_BODY=$(cat <<EOF
{
    "file_path": "$VIDEO_PATH",
    "file_name": "v30-1.mp4",
    "language": "th",
    "model_size": "medium",
    "chunk_duration": 30,
    "use_chunking": true,
    "display_mode": "full_text",
    "enable_initial_prompt": false
}
EOF
)

print_status "Sending transcription request..."
RESPONSE=$(curl -s -X POST "$API_URL/transcribe/" \
    -H "Content-Type: application/json" \
    -d "$REQUEST_BODY" 2>/dev/null || echo "")

if [ -z "$RESPONSE" ]; then
    print_error "❌ Failed to send request"
    exit 1
fi

TASK_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))" 2>/dev/null || echo "")

if [ -z "$TASK_ID" ]; then
    print_error "❌ Failed to get task_id from response"
    echo "Response: $RESPONSE"
    exit 1
fi

print_success "✅ Task created: $TASK_ID"
echo ""

# Display response
echo "Response:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

# Test 2: Close Caption (realtime_chunks, priority=10)
print_status ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎬 Test 2: Close Caption (realtime_chunks, priority=10)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

REQUEST_BODY_CC=$(cat <<EOF
{
    "file_path": "$VIDEO_PATH",
    "file_name": "v30-1-cc.mp4",
    "language": "th",
    "model_size": "medium",
    "chunk_duration": 3,
    "use_chunking": true,
    "display_mode": "realtime_chunks",
    "enable_initial_prompt": false
}
EOF
)

print_status "Sending close caption request..."
RESPONSE_CC=$(curl -s -X POST "$API_URL/transcribe/" \
    -H "Content-Type: application/json" \
    -d "$REQUEST_BODY_CC" 2>/dev/null || echo "")

if [ -z "$RESPONSE_CC" ]; then
    print_error "❌ Failed to send close caption request"
    exit 1
fi

TASK_ID_CC=$(echo "$RESPONSE_CC" | python3 -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))" 2>/dev/null || echo "")

if [ -z "$TASK_ID_CC" ]; then
    print_error "❌ Failed to get task_id from close caption response"
    echo "Response: $RESPONSE_CC"
    exit 1
fi

print_success "✅ Close Caption Task created: $TASK_ID_CC"
echo ""

# Display response
echo "Response:"
echo "$RESPONSE_CC" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_CC"
echo ""

# Monitor tasks
print_status ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Monitoring Tasks..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

print_status "Task 1 (Normal): $TASK_ID"
print_status "Task 2 (Close Caption): $TASK_ID_CC"
echo ""

# Check task status
check_task_status() {
    local task_id=$1
    local task_name=$2
    
    print_status "Checking $task_name status..."
    STATUS_RESPONSE=$(curl -s "$API_URL/transcribe/$task_id" 2>/dev/null || echo "")
    
    if [ -n "$STATUS_RESPONSE" ]; then
        STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
        PROGRESS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('progress', 0))" 2>/dev/null || echo "0")
        
        echo "   Status: $STATUS"
        echo "   Progress: $PROGRESS%"
        
        if [ "$STATUS" = "completed" ]; then
            print_success "✅ $task_name completed!"
        elif [ "$STATUS" = "failed" ]; then
            print_error "❌ $task_name failed"
        fi
    else
        print_warning "⚠️  Could not get status for $task_name"
    fi
    echo ""
}

# Check both tasks
check_task_status "$TASK_ID" "Normal Transcription"
check_task_status "$TASK_ID_CC" "Close Caption"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Test Complete                                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
print_status "💡 Useful Commands:"
echo "   Check task status: curl $API_URL/transcribe/$TASK_ID"
echo "   Check close caption: curl $API_URL/transcribe/$TASK_ID_CC"
echo "   Check queue status: curl $API_URL/api/queue/status"
echo ""

