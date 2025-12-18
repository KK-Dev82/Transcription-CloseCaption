#!/bin/bash
# Script สำหรับตั้งค่า Dashboard Webhook URL
# ใช้เมื่อ Dashboard ทำงานบน external URL (เช่น RunPod HTTP Expose)

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

cd /workspace/transcription-service 2>/dev/null || {
    echo "❌ Cannot find project directory"
    exit 1
}

print_header "🔧 Setup Dashboard Webhook URL"

# Get dashboard URL from user or environment
DASHBOARD_URL="${1:-${DASHBOARD_BASE_URL}}"

if [ -z "$DASHBOARD_URL" ]; then
    echo ""
    echo "📋 Dashboard URL Options:"
    echo "   1. https://n2l8ke53h14aaw-8020.proxy.runpod.net (RunPod HTTP Expose)"
    echo "   2. Custom URL"
    echo ""
    read -p "Enter Dashboard URL (or press Enter to use default): " DASHBOARD_URL
    
    if [ -z "$DASHBOARD_URL" ]; then
        DASHBOARD_URL="https://n2l8ke53h14aaw-8020.proxy.runpod.net"
        print_warning "Using default: $DASHBOARD_URL"
    fi
fi

# Remove trailing slash
DASHBOARD_URL="${DASHBOARD_URL%/}"

print_info "Dashboard URL: $DASHBOARD_URL"
print_info "Webhook URL: $DASHBOARD_URL/api/webhook/transcription"
echo ""

# Check if .env.runpod exists
ENV_FILE=".env.runpod"
if [ ! -f "$ENV_FILE" ]; then
    print_warning ".env.runpod not found, creating..."
    touch "$ENV_FILE"
fi

# Update or add DASHBOARD_BASE_URL
if grep -q "^DASHBOARD_BASE_URL=" "$ENV_FILE" 2>/dev/null; then
    # Update existing
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|^DASHBOARD_BASE_URL=.*|DASHBOARD_BASE_URL=$DASHBOARD_URL|" "$ENV_FILE"
    else
        # Linux
        sed -i "s|^DASHBOARD_BASE_URL=.*|DASHBOARD_BASE_URL=$DASHBOARD_URL|" "$ENV_FILE"
    fi
    print_success "Updated DASHBOARD_BASE_URL in $ENV_FILE"
else
    # Add new
    echo "" >> "$ENV_FILE"
    echo "# Dashboard Webhook URL" >> "$ENV_FILE"
    echo "DASHBOARD_BASE_URL=$DASHBOARD_URL" >> "$ENV_FILE"
    print_success "Added DASHBOARD_BASE_URL to $ENV_FILE"
fi

# Also set DASHBOARD_EXTERNAL_URL as fallback
if grep -q "^DASHBOARD_EXTERNAL_URL=" "$ENV_FILE" 2>/dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|^DASHBOARD_EXTERNAL_URL=.*|DASHBOARD_EXTERNAL_URL=$DASHBOARD_URL|" "$ENV_FILE"
    else
        sed -i "s|^DASHBOARD_EXTERNAL_URL=.*|DASHBOARD_EXTERNAL_URL=$DASHBOARD_URL|" "$ENV_FILE"
    fi
else
    echo "DASHBOARD_EXTERNAL_URL=$DASHBOARD_URL" >> "$ENV_FILE"
fi

echo ""
print_success "Configuration updated!"
echo ""
print_info "💡 Next steps:"
echo "   1. Restart Dashboard (if running):"
echo "      pkill -f 'uvicorn.*dashboard.*main'"
echo "      cd dashboard && python3 -m uvicorn main:app --host 0.0.0.0 --port 8020"
echo ""
echo "   2. Start Worker (if not running):"
echo "      bash scripts/pod/start-service-daemon.sh"
echo ""
echo "   3. Verify webhook URL:"
echo "      curl $DASHBOARD_URL/api/webhook/events"
echo ""

