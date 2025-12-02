#!/bin/bash
# Script สำหรับทดสอบ Transcription Callback Flow
#
# วิธีใช้งาน:
#   bash scripts/test/test-transcription-callback.sh [file_url] [callback_url]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TRANSCRIPTION_SERVICE_URL="${TRANSCRIPTION_SERVICE_URL:-http://localhost:8001}"
BACKEND_URL="${BACKEND_URL:-http://localhost:5173}"

# Parameters
FILE_URL="${1:-http://localhost:5000/api/files/test-file-id}"
CALLBACK_URL="${2:-$BACKEND_URL/api/transcription/webhook/completed}"
JOB_ID="${3:-999}"
USER_ID="${4:-1}"

echo "🧪 Testing Transcription Callback Flow"
echo "======================================"
echo ""
echo "Configuration:"
echo "  Transcription Service: $TRANSCRIPTION_SERVICE_URL"
echo "  File URL: $FILE_URL"
echo "  Callback URL: $CALLBACK_URL"
echo "  Job ID: $JOB_ID"
echo "  User ID: $USER_ID"
echo ""

# Step 1: Start Transcription
echo "📤 Step 1: Starting Transcription"
echo "---------------------------------"

TASK_RESPONSE=$(curl -s -X POST "$TRANSCRIPTION_SERVICE_URL/transcribe/" \
    -H "Content-Type: application/json" \
    -d '{
        "file_url": "'"$FILE_URL"'",
        "file_name": "test-video.mp4",
        "language": "th",
        "model_size": "tiny",
        "chunk_duration": 30,
        "callback_url": "'"$CALLBACK_URL"'",
        "job_id": '"$JOB_ID"',
        "user_id": "'"$USER_ID"'"
    }')

TASK_ID=$(echo "$TASK_RESPONSE" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4 || echo "")

if [ -z "$TASK_ID" ]; then
    echo -e "${RED}✗ Failed to start transcription${NC}"
    echo "Response: $TASK_RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ Transcription started${NC}"
echo "  Task ID: $TASK_ID"
echo ""

# Step 2: Monitor Progress
echo "📊 Step 2: Monitoring Progress"
echo "------------------------------"
echo "  (Waiting for transcription to complete...)"
echo ""

MAX_WAIT=600  # 10 minutes
WAIT_INTERVAL=5
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS_RESPONSE=$(curl -s "$TRANSCRIPTION_SERVICE_URL/transcribe/$TASK_ID")
    STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
    PROGRESS=$(echo "$STATUS_RESPONSE" | grep -o '"progress":[0-9]*' | cut -d':' -f2 || echo "0")
    
    echo -ne "\r  Status: $STATUS | Progress: ${PROGRESS}% | Elapsed: ${ELAPSED}s"
    
    if [ "$STATUS" = "completed" ]; then
        echo ""
        echo -e "${GREEN}✓ Transcription completed${NC}"
        break
    elif [ "$STATUS" = "failed" ]; then
        echo ""
        echo -e "${RED}✗ Transcription failed${NC}"
        ERROR_MSG=$(echo "$STATUS_RESPONSE" | grep -o '"error_message":"[^"]*"' | cut -d'"' -f4 || echo "")
        echo "  Error: $ERROR_MSG"
        exit 1
    fi
    
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo ""
    echo -e "${YELLOW}⚠ Timeout waiting for transcription${NC}"
    exit 1
fi

echo ""

# Step 3: Check Callback
echo "📥 Step 3: Checking Callback"
echo "---------------------------"
echo "  Note: Check Backend logs to verify callback was received"
echo "  Callback URL: $CALLBACK_URL"
echo ""

# Step 4: Get Results
echo "📄 Step 4: Getting Transcription Results"
echo "----------------------------------------"

FULL_TEXT=$(curl -s "$TRANSCRIPTION_SERVICE_URL/transcribe/$TASK_ID/text")

echo -e "${GREEN}✓ Results retrieved${NC}"
echo ""
echo "Full Text Preview:"
echo "$FULL_TEXT" | head -c 200
echo "..."
echo ""

echo "=============================="
echo -e "${GREEN}✅ Test Complete${NC}"
echo ""
echo "Task ID: $TASK_ID"
echo "Results: $TRANSCRIPTION_SERVICE_URL/transcribe/$TASK_ID"

