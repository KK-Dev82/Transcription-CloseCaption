#!/bin/bash
# Script สำหรับ Restart Video Worker เท่านั้น
#
# วิธีใช้งาน:
#   bash scripts/pod/restart-video-worker.sh

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

echo "🔄 Restarting Video Worker"
echo "📅 $(date)"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Stop existing Video Worker
print_status "Stopping existing Video Worker..."
pkill -f "python.*video_worker" || print_warning "⚠️  No Video Worker process found"
sleep 2

# Check if still running
if pgrep -f "python.*video_worker" > /dev/null; then
    print_warning "⚠️  Video Worker still running, force killing..."
    pkill -9 -f "python.*video_worker"
    sleep 1
fi

print_success "✅ Video Worker stopped"
echo ""

# Load environment variables from .env.runpod FIRST
if [ -f ".env.runpod" ]; then
    print_status "Loading environment variables from .env.runpod..."
    set -a
    source .env.runpod
    set +a
    print_success "✅ Environment variables loaded"
else
    print_warning "⚠️  .env.runpod not found"
fi

# Check RabbitMQ configuration
print_status "Checking RabbitMQ configuration..."
if [ -f ".env.runpod" ]; then
    # Use loaded variables or defaults
    RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
    RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
    RABBITMQ_USER=${RABBITMQ_USER:-senate}
    RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}
    
    print_status "RabbitMQ Host: $RABBITMQ_HOST:$RABBITMQ_PORT"
    
    # Test RabbitMQ connection
    if command -v python3 &> /dev/null; then
        print_status "Testing RabbitMQ connection..."
        python3 << EOF
import pika
import sys

try:
    credentials = pika.PlainCredentials('${RABBITMQ_USER:-senate}', '${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}')
    parameters = pika.ConnectionParameters(
        host='$RABBITMQ_HOST',
        port=$RABBITMQ_PORT,
        credentials=credentials,
        connection_attempts=3,
        retry_delay=2
    )
    connection = pika.BlockingConnection(parameters)
    connection.close()
    print("✅ RabbitMQ connection successful")
    sys.exit(0)
except Exception as e:
    print(f"❌ RabbitMQ connection failed: {e}")
    sys.exit(1)
EOF
        
        if [ $? -ne 0 ]; then
            print_error "❌ Cannot connect to RabbitMQ"
            print_warning "💡 Video Worker may not be able to process tasks"
        fi
    fi
else
    print_warning "⚠️  .env.runpod not found"
fi
echo ""

# Ensure environment variables are loaded (already loaded above, but ensure they're set)
if [ -z "$RABBITMQ_HOST" ]; then
    # If not loaded, try to load again
    if [ -f ".env.runpod" ]; then
        set -a
        source .env.runpod
        set +a
    fi
    # Set defaults if still not set
    RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
    RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
    RABBITMQ_USER=${RABBITMQ_USER:-senate}
    RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}
fi

print_status "Final RabbitMQ configuration:"
print_status "  RABBITMQ_HOST=$RABBITMQ_HOST"
print_status "  RABBITMQ_PORT=$RABBITMQ_PORT"
echo ""

# Start Video Worker
print_status "Starting Video Worker..."
export PYTHONPATH="$PROJECT_ROOT"

# Export RabbitMQ environment variables explicitly
if [ -n "$RABBITMQ_HOST" ]; then
    export RABBITMQ_HOST
    export RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
    export RABBITMQ_USER=${RABBITMQ_USER:-senate}
    export RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}
    print_status "Exported RabbitMQ env vars: RABBITMQ_HOST=$RABBITMQ_HOST"
fi

if [ -f "app/workers/video_worker.py" ]; then
    # Start with environment variables
    nohup env RABBITMQ_HOST="${RABBITMQ_HOST:-178.128.105.100}" \
             RABBITMQ_PORT="${RABBITMQ_PORT:-5672}" \
             RABBITMQ_USER="${RABBITMQ_USER:-senate}" \
             RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}" \
             python3 -m app.workers.video_worker > /tmp/video-worker.log 2>&1 & disown
    VIDEO_WORKER_PID=$!
    
    sleep 2
    
    # Check if started successfully
    if pgrep -f "python.*video_worker" > /dev/null; then
        print_success "✅ Video Worker started (PID: $VIDEO_WORKER_PID)"
        print_status "💡 Logs: tail -f /tmp/video-worker.log"
    else
        print_error "❌ Video Worker failed to start"
        print_status "💡 Check logs: tail /tmp/video-worker.log"
        exit 1
    fi
else
    print_error "❌ video_worker.py not found"
    exit 1
fi

echo ""
print_success "🎉 Video Worker restarted successfully!"
echo ""
print_status "💡 Useful commands:"
echo "   # View logs:"
echo "   tail -f /tmp/video-worker.log"
echo ""
echo "   # Check status:"
echo "   bash scripts/pod/check-services-status.sh"
echo ""

