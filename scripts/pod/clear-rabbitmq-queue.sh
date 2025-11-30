#!/bin/bash
# Script สำหรับ Clear/Purge RabbitMQ Queue
#
# วิธีใช้งาน:
#   bash scripts/pod/clear-rabbitmq-queue.sh [queue-name]
#
# ตัวอย่าง:
#   bash scripts/pod/clear-rabbitmq-queue.sh                    # Clear transcription_queue (default)
#   bash scripts/pod/clear-rabbitmq-queue.sh transcription_queue
#   bash scripts/pod/clear-rabbitmq-queue.sh all                # Clear all queues

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

QUEUE_NAME="${1:-transcription_queue}"

echo "🗑️  Clearing RabbitMQ Queue"
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

# Confirm before clearing
if [ "$QUEUE_NAME" != "all" ]; then
    print_warning "⚠️  This will purge all messages from queue: $QUEUE_NAME"
    echo ""
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Cancelled"
        exit 0
    fi
else
    print_warning "⚠️  This will purge ALL queues!"
    echo ""
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Cancelled"
        exit 0
    fi
fi

echo ""

# Clear queue(s)
python3 << EOF
import pika
import sys

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
    
    if '$QUEUE_NAME' == 'all':
        # Clear all queues
        queues = [
            'transcription_queue',
            'video_trim_queue',
            'video_merge_queue',
            'video_convert_queue',
            'video_resize_queue',
            'media.audio.chunk.extracted'
        ]
        
        print("🗑️  Clearing all queues...")
        print("")
        
        total_cleared = 0
        for queue_name in queues:
            try:
                method = channel.queue_declare(queue=queue_name, passive=True)
                message_count = method.method.message_count
                
                if message_count > 0:
                    channel.queue_purge(queue=queue_name)
                    print(f"  ✅ {queue_name}: Cleared {message_count} messages")
                    total_cleared += message_count
                else:
                    print(f"  ✅ {queue_name}: Already empty")
            except pika.exceptions.ChannelClosedByBroker:
                print(f"  ⚠️  {queue_name}: Queue not found (skipped)")
            except Exception as e:
                print(f"  ❌ {queue_name}: Error - {e}")
        
        print("")
        print(f"✅ Total messages cleared: {total_cleared}")
    else:
        # Clear specific queue
        try:
            method = channel.queue_declare(queue='$QUEUE_NAME', passive=True)
            message_count = method.method.message_count
            
            if message_count > 0:
                channel.queue_purge(queue='$QUEUE_NAME')
                print(f"✅ Cleared {message_count} messages from $QUEUE_NAME")
            else:
                print(f"✅ Queue $QUEUE_NAME is already empty")
        except pika.exceptions.ChannelClosedByBroker:
            print(f"❌ Queue $QUEUE_NAME not found")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    
    connection.close()
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
EOF

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    print_success "🎉 Queue cleared successfully!"
else
    print_error "❌ Failed to clear queue"
    exit 1
fi

echo ""

