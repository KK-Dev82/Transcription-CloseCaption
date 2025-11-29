#!/bin/bash
# Script สำหรับทดสอบ Health Check ด้วย RunPod HTTP Services URL
#
# วิธีใช้งาน:
# bash scripts/pod/test-health-runpod-url.sh [api-url] [whisper-url]
#
# ตัวอย่าง:
# bash scripts/pod/test-health-runpod-url.sh \
#   https://xxxxx-8001.proxy.runpod.net \
#   https://xxxxx-8002.proxy.runpod.net

set -e

API_URL="${1}"
WHISPER_URL="${2}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

if [ -z "$API_URL" ] || [ -z "$WHISPER_URL" ]; then
    print_error "Error: API URL and Whisper URL are required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/test-health-runpod-url.sh [api-url] [whisper-url]"
    echo ""
    echo "Example:"
    echo "  bash scripts/pod/test-health-runpod-url.sh \\"
    echo "    https://xxxxx-8001.proxy.runpod.net \\"
    echo "    https://xxxxx-8002.proxy.runpod.net"
    echo ""
    echo "💡 How to get URLs:"
    echo "   1. Go to RunPod Console → Connect tab"
    echo "   2. Click on External Link for Port 8001 and 8002"
    echo "   3. Copy the URLs"
    exit 1
fi

echo "🧪 Testing Health Check using RunPod HTTP Services URLs"
echo "📅 $(date)"
echo ""
echo "📋 Configuration:"
echo "   API URL: $API_URL"
echo "   Whisper URL: $WHISPER_URL"
echo ""

# Test API Health
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Testing Main API Health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

print_status "URL: $API_URL/health"

if curl -f -s --max-time 10 "$API_URL/health" > /dev/null 2>&1; then
    print_success "✅ Main API is accessible!"
    RESPONSE=$(curl -s --max-time 10 "$API_URL/health" 2>/dev/null || echo "")
    if [ -n "$RESPONSE" ]; then
        echo "   Response: $RESPONSE"
    fi
else
    print_error "❌ Main API is NOT accessible"
    echo ""
    print_warning "Possible reasons:"
    echo "   1. Services are not started on Pod"
    echo "   2. URL is incorrect"
    echo "   3. RunPod HTTP Services are not enabled"
fi

echo ""

# Test Whisper Health
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Testing Whisper API Health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

print_status "URL: $WHISPER_URL/health"

if curl -f -s --max-time 10 "$WHISPER_URL/health" > /dev/null 2>&1; then
    print_success "✅ Whisper API is accessible!"
    RESPONSE=$(curl -s --max-time 10 "$WHISPER_URL/health" 2>/dev/null || echo "")
    if [ -n "$RESPONSE" ]; then
        echo "   Response: $RESPONSE"
    fi
else
    print_error "❌ Whisper API is NOT accessible"
    echo ""
    print_warning "Possible reasons:"
    echo "   1. Services are not started on Pod"
    echo "   2. URL is incorrect"
    echo "   3. RunPod HTTP Services are not enabled"
fi

echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

API_OK=false
WHISPER_OK=false

if curl -f -s --max-time 10 "$API_URL/health" > /dev/null 2>&1; then
    API_OK=true
fi

if curl -f -s --max-time 10 "$WHISPER_URL/health" > /dev/null 2>&1; then
    WHISPER_OK=true
fi

if [ "$API_OK" = true ] && [ "$WHISPER_OK" = true ]; then
    print_success "✅ Both services are accessible via RunPod HTTP Services!"
    echo ""
    print_status "💡 Next steps:"
    echo "   - Test transcription using these URLs"
    echo "   - Update your backend configuration to use these URLs"
else
    print_warning "⚠️  Some services are not accessible"
    echo ""
    print_status "💡 Solutions:"
    echo "   1. SSH to Pod and check services:"
    echo "      ssh root@205.196.17.108 -p 13027"
    echo "      bash scripts/pod/check-services.sh"
    echo ""
    echo "   2. Start services if not running:"
    echo "      bash scripts/pod/start-services-direct.sh"
    echo ""
    echo "   3. Verify RunPod HTTP Services URLs are correct"
fi

echo ""

