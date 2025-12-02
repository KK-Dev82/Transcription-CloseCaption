#!/bin/bash
# Script สำหรับทดสอบการเชื่อมต่อและใช้งาน Transcription Service บน Pod
#
# วิธีใช้งาน:
#   bash scripts/test/test-pod-full.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
POD_IP="${POD_IP:-80.15.7.37}"
POD_SSH_PORT="${POD_SSH_PORT:-41475}"
POD_SERVICE_PORT="${POD_SERVICE_PORT:-8001}"
POD_URL="http://${POD_IP}:${POD_SERVICE_PORT}"

echo "🧪 Testing Transcription Service on Pod"
echo "========================================"
echo ""
echo "Configuration:"
echo "  Pod IP: $POD_IP"
echo "  SSH Port: $POD_SSH_PORT"
echo "  Service Port: $POD_SERVICE_PORT"
echo "  Service URL: $POD_URL"
echo ""

# Test 1: SSH Connection
echo "📋 Test 1: SSH Connection"
echo "-------------------------"
echo -n "Testing SSH connection... "
if ssh -p $POD_SSH_PORT -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@$POD_IP -i ~/.ssh/id_ed25519 "echo 'OK'" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Connected${NC}"
else
    echo -e "${RED}✗ Failed${NC}"
    echo "   Please check SSH configuration"
    exit 1
fi
echo ""

# Test 2: Service Status on Pod
echo "📋 Test 2: Service Status on Pod"
echo "---------------------------------"
echo "Checking service on Pod..."
ssh_output=$(ssh -p $POD_SSH_PORT root@$POD_IP -i ~/.ssh/id_ed25519 "cd /workspace/transcription-service && ps aux | grep -E 'uvicorn.*8001' | grep -v grep && echo '---' && netstat -tlnp 2>/dev/null | grep 8001 || ss -tlnp 2>/dev/null | grep 8001 || echo 'Port not listening'" 2>&1)

if echo "$ssh_output" | grep -q "uvicorn"; then
    echo -e "${GREEN}✓ Service is running${NC}"
    echo "$ssh_output" | head -3
else
    echo -e "${YELLOW}⚠ Service may not be running${NC}"
fi
echo ""

# Test 3: Health Check from Pod
echo "📋 Test 3: Health Check (from Pod)"
echo "-----------------------------------"
echo -n "Testing http://localhost:8001/health... "
health_response=$(ssh -p $POD_SSH_PORT root@$POD_IP -i ~/.ssh/id_ed25519 "curl -s http://localhost:8001/health 2>&1" || echo "ERROR")
if echo "$health_response" | grep -q "healthy\|status"; then
    echo -e "${GREEN}✓ OK${NC}"
    echo "  Response: $(echo "$health_response" | head -1)"
else
    echo -e "${RED}✗ Failed${NC}"
    echo "  Response: $health_response"
fi
echo ""

# Test 4: External Access
echo "📋 Test 4: External Access"
echo "--------------------------"
echo -n "Testing $POD_URL/health from external... "
external_response=$(curl -s -m 5 -w "\n%{http_code}" "$POD_URL/health" 2>&1 || echo "ERROR")
http_code=$(echo "$external_response" | tail -n1)

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ Accessible${NC}"
    body=$(echo "$external_response" | sed '$d')
    echo "  Response: $(echo "$body" | head -1)"
elif [ "$http_code" = "ERROR" ] || [ -z "$http_code" ]; then
    echo -e "${YELLOW}⚠ Cannot connect${NC}"
    echo "  This is normal if firewall blocks external access"
    echo "  Backend should still be able to connect from internal network"
else
    echo -e "${YELLOW}⚠ HTTP $http_code${NC}"
fi
echo ""

# Test 5: API Endpoints
echo "📋 Test 5: API Endpoints"
echo "------------------------"
echo "Testing API root endpoint..."

api_response=$(ssh -p $POD_SSH_PORT root@$POD_IP -i ~/.ssh/id_ed25519 "curl -s http://localhost:8001/ 2>&1" || echo "ERROR")
if echo "$api_response" | grep -q "Transcription\|message"; then
    echo -e "${GREEN}✓ API responding${NC}"
    echo "  $(echo "$api_response" | grep -o '\"message\":\"[^\"]*\"' | head -1)"
else
    echo -e "${YELLOW}⚠ API may not be ready${NC}"
fi
echo ""

# Summary
echo "=============================="
echo "✅ Test Complete"
echo ""
echo "Summary:"
echo "  SSH: $([ "$?" = "0" ] && echo "✓" || echo "✗")"
echo "  Service: $(echo "$ssh_output" | grep -q "uvicorn" && echo "✓ Running" || echo "⚠ Check manually")"
echo "  Internal: $(echo "$health_response" | grep -q "healthy\|status" && echo "✓ OK" || echo "✗ Failed")"
echo "  External: $([ "$http_code" = "200" ] && echo "✓ Accessible" || echo "⚠ Limited")"
echo ""
echo "💡 Next Steps:"
echo "   1. Update Backend configuration"
echo "   2. Test transcription through Backend"
echo ""

