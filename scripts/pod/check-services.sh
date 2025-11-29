#!/bin/bash
# Script สำหรับตรวจสอบสถานะ Services บน RunPod/Z2
#
# วิธีใช้งาน:
# bash scripts/pod/check-services.sh

set -e

echo "🔍 Checking Transcription Services Status..."
echo "📅 $(date)"
echo ""

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

# Check running processes
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "1. Checking Running Processes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Redis
if pgrep -f "redis-server" > /dev/null; then
    REDIS_PID=$(pgrep -f "redis-server" | head -1)
    print_success "✅ Redis is running (PID: $REDIS_PID)"
else
    print_error "❌ Redis is NOT running"
fi

# Check Whisper API
if pgrep -f "python3.*whisper_api.py" > /dev/null; then
    WHISPER_PID=$(pgrep -f "python3.*whisper_api.py" | head -1)
    print_success "✅ Whisper API is running (PID: $WHISPER_PID)"
else
    print_error "❌ Whisper API is NOT running"
fi

# Check Video Worker
if pgrep -f "python3.*video_worker" > /dev/null; then
    WORKER_PID=$(pgrep -f "python3.*video_worker" | head -1)
    print_success "✅ Video Worker is running (PID: $WORKER_PID)"
else
    print_warning "⚠️  Video Worker is NOT running (optional)"
fi

# Check Main API
if pgrep -f "python3.*uvicorn.*app.main:app" > /dev/null; then
    API_PID=$(pgrep -f "python3.*uvicorn.*app.main:app" | head -1)
    print_success "✅ Main API is running (PID: $API_PID)"
else
    print_error "❌ Main API is NOT running"
fi

echo ""

# Check listening ports
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "2. Checking Listening Ports"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check port 8001 (Main API)
if netstat -tuln 2>/dev/null | grep -q ":8001 " || ss -tuln 2>/dev/null | grep -q ":8001 "; then
    LISTENING=$(netstat -tuln 2>/dev/null | grep ":8001 " || ss -tuln 2>/dev/null | grep ":8001 ")
    if echo "$LISTENING" | grep -q "0.0.0.0:8001\|:::8001"; then
        print_success "✅ Port 8001 is listening on 0.0.0.0 (accessible externally)"
    else
        print_warning "⚠️  Port 8001 is listening but may not be accessible externally"
        echo "   $LISTENING"
    fi
else
    print_error "❌ Port 8001 is NOT listening"
fi

# Check port 8002 (Whisper API)
if netstat -tuln 2>/dev/null | grep -q ":8002 " || ss -tuln 2>/dev/null | grep -q ":8002 "; then
    LISTENING=$(netstat -tuln 2>/dev/null | grep ":8002 " || ss -tuln 2>/dev/null | grep ":8002 ")
    if echo "$LISTENING" | grep -q "0.0.0.0:8002\|:::8002"; then
        print_success "✅ Port 8002 is listening on 0.0.0.0 (accessible externally)"
    else
        print_warning "⚠️  Port 8002 is listening but may not be accessible externally"
        echo "   $LISTENING"
    fi
else
    print_error "❌ Port 8002 is NOT listening"
fi

# Check port 6379 (Redis)
if netstat -tuln 2>/dev/null | grep -q ":6379 " || ss -tuln 2>/dev/null | grep -q ":6379 "; then
    print_success "✅ Port 6379 (Redis) is listening"
else
    print_warning "⚠️  Port 6379 (Redis) is NOT listening (may be normal if using external Redis)"
fi

echo ""

# Check health endpoints (local)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "3. Checking Health Endpoints (Local)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Main API health
if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    print_success "✅ Main API health check passed (localhost:8001)"
    RESPONSE=$(curl -s http://localhost:8001/health 2>/dev/null || echo "")
    if [ -n "$RESPONSE" ]; then
        echo "   Response: $RESPONSE"
    fi
else
    print_error "❌ Main API health check failed (localhost:8001)"
fi

# Check Whisper API health
if curl -f http://localhost:8002/health > /dev/null 2>&1; then
    print_success "✅ Whisper API health check passed (localhost:8002)"
    RESPONSE=$(curl -s http://localhost:8002/health 2>/dev/null || echo "")
    if [ -n "$RESPONSE" ]; then
        echo "   Response: $RESPONSE"
    fi
else
    print_error "❌ Whisper API health check failed (localhost:8002)"
fi

echo ""

# Check external accessibility
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "4. Checking External Accessibility"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get external IP (if available)
EXTERNAL_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || echo "unknown")
if [ "$EXTERNAL_IP" != "unknown" ]; then
    print_status "External IP: $EXTERNAL_IP"
    echo ""
    
    # Try to check from external (this may fail if firewall blocks)
    print_status "Note: External checks may fail if firewall blocks connections"
    print_status "RunPod exposes ports through HTTP Services or Direct TCP"
    echo ""
fi

# Check RunPod HTTP Services
print_status "RunPod HTTP Services:"
print_status "  - Port 8001 → api (check RunPod Connect tab)"
print_status "  - Port 8002 → whisper (check RunPod Connect tab)"
echo ""

# Summary and recommendations
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "5. Summary & Recommendations"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Count issues
ISSUES=0

if ! pgrep -f "redis-server" > /dev/null; then
    ISSUES=$((ISSUES + 1))
fi

if ! pgrep -f "python3.*whisper_api.py" > /dev/null; then
    ISSUES=$((ISSUES + 1))
fi

if ! pgrep -f "python3.*uvicorn.*app.main:app" > /dev/null; then
    ISSUES=$((ISSUES + 1))
fi

if [ $ISSUES -eq 0 ]; then
    print_success "✅ All critical services are running!"
    echo ""
    print_status "💡 To access from external:"
    echo "   1. Use RunPod HTTP Services (Connect tab)"
    echo "   2. Or use Direct TCP ports (if configured)"
    echo ""
    print_status "💡 To test locally:"
    echo "   curl http://localhost:8001/health"
    echo "   curl http://localhost:8002/health"
else
    print_error "❌ Found $ISSUES issue(s)"
    echo ""
    print_status "💡 To start services:"
    echo "   bash scripts/pod/start-services-direct.sh"
    echo ""
    print_status "💡 To check logs:"
    echo "   tail -f /tmp/main-api.log"
    echo "   tail -f /tmp/whisper.log"
    echo "   tail -f /tmp/video-worker.log"
fi

echo ""

