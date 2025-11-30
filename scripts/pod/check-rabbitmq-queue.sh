#!/bin/bash
# Script สำหรับตรวจสอบ RabbitMQ Queue Status
#
# วิธีใช้งาน:
#   bash scripts/pod/check-rabbitmq-queue.sh

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

echo "📊 Checking RabbitMQ Queue Status"
echo "📅 $(date)"
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

print_status "RabbitMQ Host: $RABBITMQ_HOST:$RABBITMQ_PORT"
echo ""

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    print_error "❌ python3 not found"
    exit 1
fi

# Check queue status using Python
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Queue Status"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python3 << EOF
import pika
import sys
import json

try:
    # Connect to RabbitMQ
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
    
    # Queue names
    queues = [
        'transcription_queue',
        'video_trim_queue',
        'video_merge_queue',
        'video_convert_queue',
        'video_resize_queue',
        'media.audio.chunk.extracted'
    ]
    
    print("📋 Queue Information:")
    print("")
    
    total_messages = 0
    queues_with_messages = []
    
    for queue_name in queues:
        try:
            # Declare queue to get its info
            method = channel.queue_declare(queue=queue_name, passive=True)
            message_count = method.method.message_count
            consumer_count = method.method.consumer_count
            
            if message_count > 0:
                queues_with_messages.append((queue_name, message_count, consumer_count))
                total_messages += message_count
                print(f"  ⚠️  {queue_name}:")
                print(f"     Messages: {message_count}")
                print(f"     Consumers: {consumer_count}")
            else:
                print(f"  ✅ {queue_name}: Empty (Consumers: {consumer_count})")
        except pika.exceptions.ChannelClosedByBroker as e:
            # Queue doesn't exist
            print(f"  ⚠️  {queue_name}: Queue not found")
        except Exception as e:
            print(f"  ❌ {queue_name}: Error - {e}")
    
    print("")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("")
    
    if total_messages > 0:
        print(f"⚠️  Total pending messages: {total_messages}")
        print("")
        print("💡 Pending tasks will be processed automatically when Video Worker is running")
        print("💡 To clear pending tasks, run:")
        print("   bash scripts/pod/clear-rabbitmq-queue.sh")
    else:
        print("✅ All queues are empty")
        print("")
        print("💡 Ready to accept new transcription tasks")
    
    connection.close()
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
EOF

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    print_error "❌ Failed to check queue status"
    exit 1
fi

echo ""

