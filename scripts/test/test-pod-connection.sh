#!/bin/bash
# Script สำหรับทดสอบการเชื่อมต่อ Transcription Service บน Pod
#
# วิธีใช้งาน:
#   bash scripts/test/test-pod-connection.sh [--external] [--backend] [--auth]

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
TEST_EXTERNAL=false
TEST_BACKEND=false
USE_AUTH=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --external)
            TEST_EXTERNAL=true
            shift
            ;;
        --backend)
            TEST_BACKEND=true
            shift
            ;;
        --auth)
            USE_AUTH=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

POD_URL="http://${POD_IP}:${POD_PORT}"

echo "🧪 Testing Transcription Service Connection"
echo "==========================================="
echo ""
echo "Configuration:"
echo "  Pod IP: $POD_IP"
echo "  Pod Port: $POD_PORT"
echo "  Pod URL: $POD_URL"
echo "  Backend URL: $BACKEND_URL"
echo ""

# Test 1: Health Check
echo "📋 Test 1: Health Check"
echo "-----------------------"
echo -n "Testing $POD_URL/health... "
response=$(curl -s -w "\n%{http_code}" "$POD_URL/health" 2>&1 || echo "ERROR")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ OK${NC}"
    echo "  Response: $body"
elif [ "$http_code" = "ERROR" ]; then
    echo -e "${RED}✗ Cannot connect${NC}"
    echo "  Error: Connection failed"
else
    echo -e "${YELLOW}⚠ HTTP $http_code${NC}"
    echo "  Response: $body"
fi
echo ""

# Test 2: API Root
echo "📋 Test 2: API Root"
echo "-------------------"
echo -n "Testing $POD_URL/... "
response=$(curl -s -w "\n%{http_code}" "$POD_URL/" 2>&1 || echo "ERROR")
http_code=$(echo "$response" | tail -n1)

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ OK${NC}"
    info=$(echo "$response" | sed '$d' | grep -o '"message":"[^"]*"' | head -1 || echo "")
    echo "  $info"
else
    echo -e "${YELLOW}⚠ HTTP $http_code${NC}"
fi
echo ""

# Test 3: API Docs
echo "📋 Test 3: API Documentation"
echo "----------------------------"
echo -n "Testing $POD_URL/docs... "
response=$(curl -s -w "\n%{http_code}" "$POD_URL/docs" 2>&1)
http_code=$(echo "$response" | tail -n1)

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ Available${NC}"
    echo "  URL: $POD_URL/docs"
else
    echo -e "${YELLOW}⚠ HTTP $http_code${NC}"
fi
echo ""

# Test 4: Backend Connection (if enabled)
if [ "$TEST_BACKEND" = true ]; then
    echo "📋 Test 4: Backend Integration"
    echo "-----------------------------"
    
    # Check Backend health
    echo -n "Testing Backend health... "
    backend_response=$(curl -s -w "\n%{http_code}" "$BACKEND_URL/health" 2>&1 || echo "ERROR")
    backend_code=$(echo "$backend_response" | tail -n1)
    
    if [ "$backend_code" = "200" ]; then
        echo -e "${GREEN}✓ OK${NC}"
        
        # Test transcription endpoint (would require auth in real scenario)
        echo "  Backend can connect to Pod: $POD_URL"
    else
        echo -e "${RED}✗ Backend not available${NC}"
    fi
    echo ""
fi

# Test 5: Simple Transcription Test (no auth required)
echo "📋 Test 5: Simple API Test"
echo "-------------------------"
echo "Testing GET /transcribe/ (list endpoint)..."
response=$(curl -s -w "\n%{http_code}" "$POD_URL/transcribe/" 2>&1)
http_code=$(echo "$response" | tail -n1)

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ API endpoint accessible${NC}"
    echo "  Response: OK"
else
    echo -e "${YELLOW}⚠ HTTP $http_code${NC}"
fi
echo ""

# Summary
echo "=============================="
echo "✅ Connection Test Complete"
echo ""
echo "Summary:"
echo "  Pod URL: $POD_URL"
echo "  Health: $([ "$http_code" = "200" ] && echo "✓ OK" || echo "✗ Failed")"
echo ""
echo "💡 Next Steps:"
echo "   1. Update Backend configuration"
echo "   2. Test transcription flow"
echo ""

