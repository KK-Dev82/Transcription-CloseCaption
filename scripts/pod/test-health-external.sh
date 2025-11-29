#!/bin/bash
# Script สำหรับทดสอบ Health Check จาก External (MacOS) ไปยัง RunPod
#
# วิธีใช้งาน:
# bash scripts/pod/test-health-external.sh [pod-ip] [api-port] [whisper-port]
#
# ตัวอย่าง:
# bash scripts/pod/test-health-external.sh 205.196.17.108 8001 8002

set -e

POD_IP="${1:-205.196.17.108}"
API_PORT="${2:-8001}"
WHISPER_PORT="${3:-8002}"

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

echo "🧪 Testing Health Check from External (MacOS) to RunPod"
echo "📅 $(date)"
echo ""
echo "📋 Configuration:"
echo "   Pod IP: $POD_IP"
echo "   API Port: $API_PORT"
echo "   Whisper Port: $WHISPER_PORT"
echo ""

# Test API Health
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Testing Main API Health (Port $API_PORT)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

API_URL="http://${POD_IP}:${API_PORT}"
print_status "URL: $API_URL/health"

if curl -f -s --max-time 5 "$API_URL/health" > /dev/null 2>&1; then
    print_success "✅ Main API is accessible!"
    RESPONSE=$(curl -s --max-time 5 "$API_URL/health" 2>/dev/null || echo "")
    if [ -n "$RESPONSE" ]; then
        echo "   Response: $RESPONSE"
    fi
else
    print_error "❌ Main API is NOT accessible"
    echo ""
    print_warning "Possible reasons:"
    echo "   1. Services are not started on Pod"
    echo "   2. Services are not listening on 0.0.0.0"
    echo "   3. Firewall is blocking connections"
    echo "   4. Need to use RunPod HTTP Services URL instead"
    echo ""
    print_status "💡 Solutions:"
    echo "   1. SSH to Pod and check: bash scripts/pod/check-services.sh"
    echo "   2. Start services: bash scripts/pod/start-services-direct.sh"
    echo "   3. Use RunPod HTTP Services URL from Connect tab"
fi

echo ""

# Test Whisper Health
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Testing Whisper API Health (Port $WHISPER_PORT)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

WHISPER_URL="http://${POD_IP}:${WHISPER_PORT}"
print_status "URL: $WHISPER_URL/health"

if curl -f -s --max-time 5 "$WHISPER_URL/health" > /dev/null 2>&1; then
    print_success "✅ Whisper API is accessible!"
    RESPONSE=$(curl -s --max-time 5 "$WHISPER_URL/health" 2>/dev/null || echo "")
    if [ -n "$RESPONSE" ]; then
        echo "   Response: $RESPONSE"
    fi
else
    print_error "❌ Whisper API is NOT accessible"
    echo ""
    print_warning "Possible reasons:"
    echo "   1. Services are not started on Pod"
    echo "   2. Services are not listening on 0.0.0.0"
    echo "   3. Firewall is blocking connections"
    echo "   4. Need to use RunPod HTTP Services URL instead"
    echo ""
    print_status "💡 Solutions:"
    echo "   1. SSH to Pod and check: bash scripts/pod/check-services.sh"
    echo "   2. Start services: bash scripts/pod/start-services-direct.sh"
    echo "   3. Use RunPod HTTP Services URL from Connect tab"
fi

echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

API_OK=false
WHISPER_OK=false

if curl -f -s --max-time 5 "$API_URL/health" > /dev/null 2>&1; then
    API_OK=true
fi

if curl -f -s --max-time 5 "$WHISPER_URL/health" > /dev/null 2>&1; then
    WHISPER_OK=true
fi

if [ "$API_OK" = true ] && [ "$WHISPER_OK" = true ]; then
    print_success "✅ Both services are accessible!"
    echo ""
    print_status "💡 Next steps:"
    echo "   - Test transcription: bash scripts/pod/upload-and-test.sh <video-file> $POD_IP $API_PORT medium"
else
    print_warning "⚠️  Some services are not accessible"
    echo ""
    print_status "💡 Alternative: Use RunPod HTTP Services"
    echo "   1. Go to RunPod Console → Connect tab"
    echo "   2. Click on External Link for Port $API_PORT and $WHISPER_PORT"
    echo "   3. Use the provided URLs (e.g., https://xxxxx-8001.proxy.runpod.net)"
    echo ""
    print_status "💡 Or SSH to Pod and check services:"
    echo "   ssh root@$POD_IP -p 13027"
    echo "   bash scripts/pod/check-services.sh"
fi

echo ""

