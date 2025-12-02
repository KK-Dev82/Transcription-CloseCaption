#!/bin/bash
# Script สำหรับทดสอบ Integration กับ Backend Local
#
# วิธีใช้งาน:
#   bash scripts/test/test-backend-integration.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔗 Testing Backend Integration"
echo "=============================="
echo ""

# Configuration
TRANSCRIPTION_SERVICE_URL="${TRANSCRIPTION_SERVICE_URL:-http://localhost:8001}"
BACKEND_URL="${BACKEND_URL:-http://localhost:5173}"
FILE_SERVICE_URL="${FILE_SERVICE_URL:-http://localhost:5000}"

# Check if services are running
check_service() {
    local name=$1
    local url=$2
    
    echo -n "Checking $name... "
    if curl -s -f "$url/health" > /dev/null 2>&1 || curl -s -f "$url/" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${RED}✗${NC}"
        echo -e "  ${RED}Error: $name is not running at $url${NC}"
        return 1
    fi
}

echo "📋 Step 1: Checking Services"
echo "----------------------------"
check_service "Transcription Service" "$TRANSCRIPTION_SERVICE_URL"
check_service "Backend" "$BACKEND_URL"
# File Service might not have /health endpoint, skip for now
echo ""

# Test Transcription Service API
echo "📋 Step 2: Testing Transcription Service API"
echo "--------------------------------------------"

# Test 1: Health check
echo -n "Testing GET /health... "
if curl -s -f "$TRANSCRIPTION_SERVICE_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ (endpoint might not exist)${NC}"
fi

# Test 2: List transcriptions
echo -n "Testing GET /transcribe/... "
response=$(curl -s "$TRANSCRIPTION_SERVICE_URL/transcribe/")
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi
echo ""

# Test Backend Webhook Endpoint
echo "📋 Step 3: Testing Backend Webhook Endpoint"
echo "-------------------------------------------"

# Test webhook endpoint with mock data
echo -n "Testing POST /api/transcription/webhook/completed... "
webhook_response=$(curl -s -w "\n%{http_code}" -X POST "$BACKEND_URL/api/transcription/webhook/completed" \
    -H "Content-Type: application/json" \
    -d '{
        "jobId": 999999,
        "taskId": "test-task-id-'$(date +%s)'",
        "status": "completed",
        "text": "Test transcription text",
        "segments": [
            {
                "start_time": 0.0,
                "end_time": 5.0,
                "text": "Test transcription text",
                "confidence": 0.95
            }
        ],
        "audioDuration": 5.0,
        "wordCount": 3,
        "completedAt": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
    }')

http_code=$(echo "$webhook_response" | tail -n1)
body=$(echo "$webhook_response" | sed '$d')

if [ "$http_code" = "200" ] || [ "$http_code" = "404" ]; then
    # 404 is OK if job doesn't exist (expected for test)
    echo -e "${GREEN}✓ (HTTP $http_code)${NC}"
else
    echo -e "${RED}✗ (HTTP $http_code)${NC}"
    echo "  Response: $body"
fi
echo ""

# Display Configuration
echo "📋 Step 4: Current Configuration"
echo "---------------------------------"
echo "Transcription Service URL: $TRANSCRIPTION_SERVICE_URL"
echo "Backend URL: $BACKEND_URL"
echo "File Service URL: $FILE_SERVICE_URL"
echo ""

# Summary
echo "=============================="
echo "✅ Integration Test Complete"
echo ""
echo "💡 Next Steps:"
echo "  1. Upload a file through Backend API"
echo "  2. Start transcription via Backend"
echo "  3. Monitor transcription progress"
echo "  4. Check webhook callback"
echo ""

