#!/bin/bash
# Script สำหรับตรวจสอบ Webhook Configuration
#
# วิธีใช้งาน:
#   bash scripts/pod/verify-webhook-config.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

cd /workspace/transcription-service || exit 1

print_header "🔍 Verify Webhook Configuration"

# Load environment variables
if [ -f "env.runpod" ]; then
    set -a
    source env.runpod
    set +a
fi

# Check DASHBOARD_BASE_URL
echo ""
print_header "1. Dashboard Base URL Configuration"

DASHBOARD_BASE_URL="${DASHBOARD_BASE_URL:-${DASHBOARD_EXTERNAL_URL}}"

if [ -n "$DASHBOARD_BASE_URL" ]; then
    print_success "DASHBOARD_BASE_URL is set"
    print_info "   Value: $DASHBOARD_BASE_URL"
    
    # Check if URL is accessible
    if echo "$DASHBOARD_BASE_URL" | grep -qE "^https?://"; then
        print_success "   URL format is valid"
        
        # Try to access webhook endpoint
        WEBHOOK_URL="${DASHBOARD_BASE_URL}/api/webhook/transcription"
        print_info "   Webhook URL: $WEBHOOK_URL"
        
        if curl -s -f "$WEBHOOK_URL" > /dev/null 2>&1 || curl -s -f -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -d '{}' > /dev/null 2>&1; then
            print_success "   Webhook endpoint is accessible"
        else
            print_warning "   Webhook endpoint may not be accessible (may require POST request)"
        fi
    else
        print_warning "   URL format may be invalid (should start with http:// or https://)"
    fi
else
    print_error "DASHBOARD_BASE_URL is not set"
    print_info "   💡 Set it in env.runpod:"
    print_info "      DASHBOARD_BASE_URL=https://n2l8ke53h14aaw-8020.proxy.runpod.net"
fi

# Check Dashboard service
echo ""
print_header "2. Dashboard Service Status"

DASHBOARD_PORT=8020
if pgrep -f "uvicorn.*main:app.*${DASHBOARD_PORT}" > /dev/null; then
    DASHBOARD_PID=$(pgrep -f "uvicorn.*main:app.*${DASHBOARD_PORT}" | head -1)
    print_success "Dashboard is running (PID: $DASHBOARD_PID)"
    
    # Check if dashboard is responding
    if curl -s -f "http://localhost:${DASHBOARD_PORT}/" > /dev/null 2>&1; then
        print_success "Dashboard is responding"
    else
        print_warning "Dashboard is running but not responding"
    fi
    
    # Check webhook endpoint
    if curl -s -f "http://localhost:${DASHBOARD_PORT}/api/webhook/events" > /dev/null 2>&1; then
        print_success "Webhook endpoint is accessible"
        
        # Get webhook events count
        EVENTS=$(curl -s "http://localhost:${DASHBOARD_PORT}/api/webhook/events" 2>/dev/null | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('total_events', 0))" 2>/dev/null || echo "0")
        print_info "   Total webhook events: $EVENTS"
    else
        print_warning "Webhook endpoint is not accessible"
    fi
else
    print_error "Dashboard is NOT running"
    print_info "   💡 Start dashboard: bash scripts/pod/start-dashboard.sh"
fi

# Check API service
echo ""
print_header "3. API Service Status"

API_PORT=8010
if pgrep -f "uvicorn.*app.main.*${API_PORT}" > /dev/null; then
    API_PID=$(pgrep -f "uvicorn.*app.main.*${API_PORT}" | head -1)
    print_success "API Service is running (PID: $API_PID)"
    
    # Check health
    if curl -s -f "http://localhost:${API_PORT}/health" > /dev/null 2>&1; then
        print_success "API Service is healthy"
    else
        print_warning "API Service is running but health check failed"
    fi
else
    print_error "API Service is NOT running"
fi

# Check Worker
echo ""
print_header "4. Video-Worker Status"

WORKER_RUNNING=false
for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker"; do
    if pgrep -f "$pattern" > /dev/null; then
        WORKER_RUNNING=true
        WORKER_PID=$(pgrep -f "$pattern" | head -1)
        print_success "Video-Worker is running (PID: $WORKER_PID)"
        break
    fi
done

if [ "$WORKER_RUNNING" = false ]; then
    print_error "Video-Worker is NOT running"
    print_info "   💡 Start worker: bash scripts/pod/start-service-daemon.sh"
fi

# Summary
echo ""
print_header "📋 Summary"

if [ -n "$DASHBOARD_BASE_URL" ] && pgrep -f "uvicorn.*main:app.*8020" > /dev/null; then
    print_success "Webhook configuration looks good!"
    print_info "   Dashboard URL: $DASHBOARD_BASE_URL"
    print_info "   Webhook URL: ${DASHBOARD_BASE_URL}/api/webhook/transcription"
else
    print_warning "Webhook configuration needs attention"
    if [ -z "$DASHBOARD_BASE_URL" ]; then
        print_info "   - Set DASHBOARD_BASE_URL in env.runpod"
    fi
    if ! pgrep -f "uvicorn.*main:app.*8020" > /dev/null; then
        print_info "   - Start Dashboard service"
    fi
fi

echo ""

