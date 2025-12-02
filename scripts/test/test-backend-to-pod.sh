#!/bin/bash
# Script สำหรับทดสอบการเชื่อมต่อจาก Backend ไป Transcription Service บน Pod
#
# วิธีใช้งาน:
#   bash scripts/test/test-backend-to-pod.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
POD_IP="${POD_IP:-80.15.7.37}"
POD_PORT="${POD_PORT:-8001}"
BACKEND_URL="${BACKEND_URL:-http://localhost:5173}"
POD_URL="http://${POD_IP}:${POD_PORT}"

echo "🧪 Testing Backend → Pod Connection"
echo "===================================="
echo ""
echo "Configuration:"
echo "  Pod URL: $POD_URL"
echo "  Backend URL: $BACKEND_URL"
echo ""

# Test 1: Check Backend is running
echo "📋 Test 1: Backend Status"
echo "-------------------------"
echo -n "Checking Backend... "
if curl -s -f "$BACKEND_URL/health" > /dev/null 2>&1 || curl -s -f "$BACKEND_URL/" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${YELLOW}⚠ Not accessible${NC}"
    echo "   Backend may not be running or URL is incorrect"
fi
echo ""

# Test 2: Check Pod Service
echo "📋 Test 2: Pod Service Status"
echo "-----------------------------"
echo -n "Checking $POD_URL/health... "
response=$(curl -s -m 10 -w "\n%{http_code}" "$POD_URL/health" 2>&1 || echo "ERROR")
http_code=$(echo "$response" | tail -n1)

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ Accessible${NC}"
    body=$(echo "$response" | sed '$d')
    echo "  Response: $(echo "$body" | head -1)"
elif [ "$http_code" = "ERROR" ] || [ -z "$http_code" ]; then
    echo -e "${RED}✗ Cannot connect${NC}"
    echo "   Please check:"
    echo "   1. Pod service is running"
    echo "   2. Network connectivity"
    echo "   3. Firewall rules"
    exit 1
else
    echo -e "${YELLOW}⚠ HTTP $http_code${NC}"
    body=$(echo "$response" | sed '$d')
    echo "  Response: $body"
fi
echo ""

# Test 3: Test Transcription API
echo "📋 Test 3: Transcription API"
echo "----------------------------"
echo "Testing GET /transcribe/..."

api_response=$(curl -s -m 10 "$POD_URL/transcribe/" 2>&1)
api_code=$?

if [ $api_code -eq 0 ]; then
    echo -e "${GREEN}✓ API accessible${NC}"
    if echo "$api_response" | grep -q "task_id\|\[\]"; then
        echo "  Response: OK (list endpoint working)"
    else
        echo "  Response: $(echo "$api_response" | head -1)"
    fi
else
    echo -e "${RED}✗ API not accessible${NC}"
    echo "  Error: $api_response"
fi
echo ""

# Test 4: Backend Configuration Check
echo "📋 Test 4: Backend Configuration"
echo "--------------------------------"
echo "Checking Backend configuration..."

if [ -f "src/Shorthand.Api/appsettings.Development.json" ]; then
    transcription_url=$(grep -o '"TranscriptionUrl":\s*"[^"]*"' src/Shorthand.Api/appsettings.Development.json | cut -d'"' -f4 || echo "")
    if [ "$transcription_url" = "$POD_URL" ]; then
        echo -e "${GREEN}✓ Configuration correct${NC}"
        echo "  TranscriptionUrl: $transcription_url"
    else
        echo -e "${YELLOW}⚠ Configuration mismatch${NC}"
        echo "  Current: $transcription_url"
        echo "  Expected: $POD_URL"
        echo ""
        echo "  Update configuration:"
        echo "    cp src/Shorthand.Api/appsettings.Development.POD.json \\"
        echo "       src/Shorthand.Api/appsettings.Development.json"
    fi
else
    echo -e "${YELLOW}⚠ Configuration file not found${NC}"
fi
echo ""

# Summary
echo "=============================="
echo "✅ Test Complete"
echo ""
echo "Summary:"
echo "  Pod Service: $([ "$http_code" = "200" ] && echo "✓ OK" || echo "✗ Failed")"
echo "  API Access: $([ $api_code -eq 0 ] && echo "✓ OK" || echo "✗ Failed")"
echo ""
echo "💡 Next Steps:"
if [ "$http_code" != "200" ]; then
    echo "   1. Start transcription service on Pod"
    echo "   2. Check network connectivity"
else
    echo "   1. Update Backend configuration"
    echo "   2. Test transcription through Backend"
fi
echo ""

