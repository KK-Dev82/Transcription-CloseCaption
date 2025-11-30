#!/bin/bash
# Script สำหรับ Restart Main API เท่านั้น
#
# วิธีใช้งาน:
#   bash scripts/pod/restart-main-api.sh

set -e

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

echo "🔄 Restarting Main API"
echo "📅 $(date)"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Stop existing Main API
print_status "Stopping existing Main API..."
pkill -f "python.*uvicorn.*app.main" || print_warning "⚠️  No Main API process found"
sleep 2

# Check if still running
if pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
    print_warning "⚠️  Main API still running, force killing..."
    pkill -9 -f "python.*uvicorn.*app.main"
    sleep 1
fi

print_success "✅ Main API stopped"
echo ""

# Load environment variables from .env.runpod
if [ -f ".env.runpod" ]; then
    print_status "Loading environment variables from .env.runpod..."
    set -a
    source .env.runpod
    set +a
    print_success "✅ Environment variables loaded"
else
    print_warning "⚠️  .env.runpod not found"
fi

# Ensure environment variables are set
RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
RABBITMQ_USER=${RABBITMQ_USER:-senate}
RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}

print_status "Final RabbitMQ configuration:"
print_status "  RABBITMQ_HOST=$RABBITMQ_HOST"
print_status "  RABBITMQ_PORT=$RABBITMQ_PORT"
echo ""

# Start Main API
print_status "Starting Main API..."
export PYTHONPATH="$PROJECT_ROOT"

# Start with environment variables
nohup env RABBITMQ_HOST="${RABBITMQ_HOST}" \
         RABBITMQ_PORT="${RABBITMQ_PORT}" \
         RABBITMQ_USER="${RABBITMQ_USER}" \
         RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD}" \
         python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/main-api.log 2>&1 & disown
MAIN_API_PID=$!

sleep 3

# Check if started successfully
if pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
    print_success "✅ Main API started (PID: $MAIN_API_PID)"
    print_status "💡 Logs: tail -f /tmp/main-api.log"
    
    # Wait for API to be ready
    print_status "⏳ Waiting for Main API to be ready..."
    for i in {1..30}; do
        if curl -f http://localhost:8001/health > /dev/null 2>&1; then
            print_success "✅ Main API is ready"
            break
        fi
        sleep 1
    done
    
    if ! curl -f http://localhost:8001/health > /dev/null 2>&1; then
        print_warning "⚠️  Main API health check failed. Check logs: tail -f /tmp/main-api.log"
    fi
else
    print_error "❌ Main API failed to start"
    print_status "💡 Check logs: tail /tmp/main-api.log"
    exit 1
fi

echo ""
print_success "🎉 Main API restarted successfully!"
echo ""
print_status "💡 Useful commands:"
echo "   # View logs:"
echo "   tail -f /tmp/main-api.log"
echo ""
echo "   # Check status:"
echo "   bash scripts/pod/check-services-status.sh"
echo ""

