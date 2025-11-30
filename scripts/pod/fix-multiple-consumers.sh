#!/bin/bash
# Script สำหรับแก้ไขปัญหา Multiple Consumers ใน RabbitMQ
#
# วิธีใช้งาน:
#   bash scripts/pod/fix-multiple-consumers.sh

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

echo "🔧 Fixing Multiple Consumers Issue"
echo "📅 $(date)"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Load environment variables
if [ -f ".env.runpod" ]; then
    set -a
    source .env.runpod
    set +a
fi

RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
RABBITMQ_USER=${RABBITMQ_USER:-senate}
RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}

# Step 1: Check Video Worker processes
print_header "Step 1: Checking Video Worker Processes"
WORKER_PIDS=$(pgrep -f "python.*video_worker" 2>/dev/null || echo "")
if [ -n "$WORKER_PIDS" ]; then
    WORKER_COUNT=$(echo "$WORKER_PIDS" | wc -l | tr -d ' ')
    print_status "Found $WORKER_COUNT Video Worker process(es):"
    echo "$WORKER_PIDS" | while read pid; do
        if [ -n "$pid" ]; then
            print_status "   PID: $pid"
            ps -p "$pid" -o command --no-headers 2>/dev/null | head -c 80 || true
            echo ""
        fi
    done
    
    if [ "$WORKER_COUNT" -gt 1 ]; then
        print_warning "⚠️  Multiple Video Workers detected"
        echo ""
        read -p "Stop all Video Workers and restart? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Stopping all Video Workers..."
            pkill -f "python.*video_worker" && print_success "✅ Video Workers stopped" || print_warning "⚠️  No Video Workers to stop"
            sleep 2
        fi
    fi
else
    print_warning "⚠️  No Video Worker processes found"
fi
echo ""

# Step 2: Check RabbitMQ consumers
print_header "Step 2: Checking RabbitMQ Consumers"
python3 << EOF 2>/dev/null || print_warning "⚠️  Cannot check RabbitMQ (python3/pika may not be available)"
import pika
import sys

try:
    credentials = pika.PlainCredentials('$RABBITMQ_USER', '$RABBITMQ_PASSWORD')
    parameters = pika.ConnectionParameters(
        host='$RABBITMQ_HOST',
        port=$RABBITMQ_PORT,
        credentials=credentials,
        connection_attempts=2,
        retry_delay=1
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    queue_name = 'transcription_queue'
    method = channel.queue_declare(queue=queue_name, passive=True)
    consumer_count = method.method.consumer_count
    
    print(f"Current consumers on '{queue_name}': {consumer_count}")
    
    if consumer_count > 1:
        print("⚠️  Multiple consumers detected!")
        print("")
        print("💡 This may be caused by:")
        print("   1. Old connections from previous sessions")
        print("   2. Workers from other environments (staging/local)")
        print("   3. Duplicate worker instances")
        print("")
        print("💡 Solutions:")
        print("   1. Restart services: bash scripts/pod/restart-pod.sh")
        print("   2. Check RabbitMQ Management UI for active connections")
        print("   3. Wait a few minutes - old connections may timeout")
    elif consumer_count == 1:
        print("✅ Only 1 consumer (expected)")
    else:
        print("⚠️  No consumers (Video Worker may not be running)")
    
    connection.close()
    sys.exit(0)
except Exception as e:
    print(f"❌ RabbitMQ connection failed: {e}")
    sys.exit(1)
EOF

echo ""

# Step 3: Restart Video Worker
print_header "Step 3: Restarting Video Worker"
if [ "$WORKER_COUNT" -gt 1 ] || [ -z "$WORKER_PIDS" ]; then
    print_status "Restarting Video Worker..."
    bash scripts/pod/stop-pod.sh > /dev/null 2>&1 || true
    sleep 2
    bash scripts/pod/start-pod.sh > /dev/null 2>&1 || {
        print_error "❌ Failed to restart services"
        exit 1
    }
    sleep 5
    
    # Verify
    NEW_WORKER_PIDS=$(pgrep -f "python.*video_worker" 2>/dev/null || echo "")
    if [ -n "$NEW_WORKER_PIDS" ]; then
        NEW_WORKER_COUNT=$(echo "$NEW_WORKER_PIDS" | wc -l | tr -d ' ')
        if [ "$NEW_WORKER_COUNT" -eq 1 ]; then
            print_success "✅ Video Worker restarted successfully (PID: $NEW_WORKER_PIDS)"
        else
            print_warning "⚠️  Still have $NEW_WORKER_COUNT Video Workers"
        fi
    else
        print_error "❌ Video Worker failed to start"
    fi
else
    print_status "Only 1 Video Worker found, no restart needed"
fi
echo ""

# Step 4: Final check
print_header "Step 4: Final Check"
print_status "Checking RabbitMQ consumers again..."
sleep 3

python3 << EOF 2>/dev/null || print_warning "⚠️  Cannot check RabbitMQ"
import pika
import sys

try:
    credentials = pika.PlainCredentials('$RABBITMQ_USER', '$RABBITMQ_PASSWORD')
    parameters = pika.ConnectionParameters(
        host='$RABBITMQ_HOST',
        port=$RABBITMQ_PORT,
        credentials=credentials,
        connection_attempts=2,
        retry_delay=1
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    queue_name = 'transcription_queue'
    method = channel.queue_declare(queue=queue_name, passive=True)
    consumer_count = method.method.consumer_count
    
    if consumer_count == 1:
        print("✅ Fixed! Now has 1 consumer (expected)")
    elif consumer_count > 1:
        print(f"⚠️  Still has {consumer_count} consumers")
        print("💡 This may be from other environments or old connections")
        print("💡 Old connections will timeout automatically (heartbeat: 600s)")
    else:
        print("⚠️  No consumers (Video Worker may not be connected yet)")
    
    connection.close()
    sys.exit(0)
except Exception as e:
    print(f"❌ RabbitMQ connection failed: {e}")
    sys.exit(1)
EOF

echo ""
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_success "🎉 Fix completed!"
echo ""
print_status "💡 If multiple consumers persist:"
echo "   1. Check RabbitMQ Management UI: http://$RABBITMQ_HOST:15672"
echo "   2. Check for connections from other environments"
echo "   3. Wait a few minutes - old connections will timeout"
echo ""

