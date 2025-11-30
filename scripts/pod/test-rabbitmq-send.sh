#!/bin/bash
# Script สำหรับทดสอบการส่ง Message ไปยัง RabbitMQ Queue
#
# วิธีใช้งาน:
#   bash scripts/pod/test-rabbitmq-send.sh

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

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "🧪 Testing RabbitMQ Send Message"
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

# Test sending message
python3 << EOF
import pika
import json
import sys
import uuid
from datetime import datetime

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
    
    # Declare queue
    queue_name = 'transcription_queue'
    channel.queue_declare(queue=queue_name, durable=True)
    
    # Create test message
    task_id = str(uuid.uuid4())
    task_data = {
        "task_id": task_id,
        "task_type": "transcription",
        "file_path": "uploads/test.mp4",
        "language": "th",
        "model_size": "base",
        "chunk_duration": 30,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    # Send message
    channel.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=json.dumps(task_data),
        properties=pika.BasicProperties(
            delivery_mode=2,  # Persistent message
        )
    )
    
    print(f"✅ Message sent successfully!")
    print(f"   Task ID: {task_id}")
    print(f"   Queue: {queue_name}")
    
    # Check queue status
    method = channel.queue_declare(queue=queue_name, passive=True)
    message_count = method.method.message_count
    print(f"   Queue messages: {message_count}")
    
    connection.close()
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    print_success "🎉 Test completed successfully!"
    echo ""
    print_status "💡 Check queue status:"
    echo "   bash scripts/pod/check-rabbitmq-queue.sh"
else
    print_error "❌ Test failed"
    exit 1
fi

echo ""

