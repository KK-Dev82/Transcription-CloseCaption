#!/bin/bash
# Script สำหรับตรวจสอบ Worker Instances ทั้งหมด
#
# วิธีใช้งาน:
#   bash scripts/pod/check-all-workers.sh

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

print_header() {
    echo -e "${CYAN}$1${NC}"
}

echo "🔍 Checking All Worker Instances"
echo "📅 $(date)"
echo ""

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Video Worker Processes"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Find all video worker processes
WORKER_PIDS=$(pgrep -f "python.*video_worker" 2>/dev/null || echo "")

if [ -z "$WORKER_PIDS" ]; then
    print_error "❌ No Video Worker processes found"
else
    print_success "✅ Found Video Worker processes:"
    echo "$WORKER_PIDS" | while read pid; do
        if [ -n "$pid" ]; then
            print_status "   PID: $pid"
            # Get process info
            if [ -f "/proc/$pid/cmdline" ]; then
                CMDLINE=$(cat /proc/$pid/cmdline 2>/dev/null | tr '\0' ' ' || echo "N/A")
                print_status "   Command: $CMDLINE"
            fi
            # Get process start time
            START_TIME=$(ps -o lstart= -p $pid 2>/dev/null || echo "N/A")
            print_status "   Started: $START_TIME"
            echo ""
        fi
    done
fi

echo ""

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "RabbitMQ Consumers"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get script directory
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

python3 << EOF
import pika
import sys

try:
    credentials = pika.PlainCredentials('$RABBITMQ_USER', '$RABBITMQ_PASSWORD')
    parameters = pika.ConnectionParameters(
        host='$RABBITMQ_HOST',
        port=$RABBITMQ_PORT,
        credentials=credentials,
        connection_attempts=3,
        retry_delay=2
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    queue_name = 'transcription_queue'
    method = channel.queue_declare(queue=queue_name, passive=True)
    consumer_count = method.method.consumer_count
    
    print(f"Queue: {queue_name}")
    print(f"Active Consumers: {consumer_count}")
    print("")
    
    if consumer_count > 1:
        print(f"⚠️  Multiple consumers detected ({consumer_count})")
        print("   This might indicate:")
        print("   1. Multiple Video Worker instances running")
        print("   2. Docker containers + Direct mode workers")
        print("   3. Old worker processes still running")
    elif consumer_count == 1:
        print("✅ Single consumer (expected)")
    else:
        print("❌ No consumers active")
    
    connection.close()
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
EOF

echo ""

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Recommendations"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -n "$WORKER_PIDS" ]; then
    PID_COUNT=$(echo "$WORKER_PIDS" | wc -l)
    if [ "$PID_COUNT" -gt 1 ]; then
        print_warning "⚠️  Multiple Video Worker processes detected ($PID_COUNT)"
        print_status "💡 Recommendations:"
        echo "   1. Stop all workers: pkill -f 'python.*video_worker'"
        echo "   2. Start single worker: bash scripts/pod/restart-video-worker.sh"
        echo "   3. Verify only one process: bash scripts/pod/check-all-workers.sh"
    else
        print_success "✅ Single Video Worker process (expected)"
    fi
else
    print_error "❌ No Video Worker processes found"
    print_status "💡 Start worker: bash scripts/pod/restart-video-worker.sh"
fi

echo ""

