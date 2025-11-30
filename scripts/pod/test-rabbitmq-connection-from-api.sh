#!/bin/bash
# Script สำหรับทดสอบ RabbitMQ Connection จาก Main API Context
#
# วิธีใช้งาน:
#   bash scripts/pod/test-rabbitmq-connection-from-api.sh

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

echo "🧪 Testing RabbitMQ Connection from Main API Context"
echo "📅 $(date)"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Load environment variables (same as Main API)
if [ -f ".env.runpod" ]; then
    set -a
    source .env.runpod
    set +a
fi

# Export environment variables (same as Main API)
export RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
export RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
export RABBITMQ_USER=${RABBITMQ_USER:-senate}
export RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}

print_status "Environment Variables:"
print_status "  RABBITMQ_HOST=$RABBITMQ_HOST"
print_status "  RABBITMQ_PORT=$RABBITMQ_PORT"
print_status "  RABBITMQ_USER=$RABBITMQ_USER"
echo ""

# Test connection using Python (simulating Main API)
python3 << EOF
import os
import sys
import pika
from pika.exceptions import AMQPConnectionError

# Get environment variables (same as RabbitMQService)
host = os.getenv("RABBITMQ_HOST", "rabbitmq")
port = int(os.getenv("RABBITMQ_PORT", "5672"))
username = os.getenv("RABBITMQ_USER", "admin")
password = os.getenv("RABBITMQ_PASSWORD", "admin123")

print(f"🔌 Testing RabbitMQ Connection...")
print(f"   Host: {host}:{port}")
print(f"   User: {username}")
print("")

try:
    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=credentials,
        connection_attempts=3,
        retry_delay=2
    )
    
    print("📡 Connecting...")
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    print("✅ Connection successful!")
    print("")
    
    # Test queue operations
    queue_name = 'transcription_queue'
    print(f"📋 Testing queue: {queue_name}")
    
    # Declare queue
    method = channel.queue_declare(queue=queue_name, durable=True)
    message_count = method.method.message_count
    consumer_count = method.method.consumer_count
    
    print(f"   Queue exists: ✅")
    print(f"   Messages: {message_count}")
    print(f"   Consumers: {consumer_count}")
    print("")
    
    # Test publishing a message
    test_message = {"test": "message", "timestamp": "2025-11-30T08:00:00"}
    import json
    channel.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=json.dumps(test_message),
        properties=pika.BasicProperties(
            delivery_mode=2,
        )
    )
    print(f"✅ Test message published successfully!")
    print("")
    
    # Check queue again
    method = channel.queue_declare(queue=queue_name, passive=True)
    message_count = method.method.message_count
    print(f"   Messages after publish: {message_count}")
    
    if message_count > 0:
        print("✅ Message is in queue!")
    else:
        print("⚠️  Message was consumed immediately (consumers are active)")
    
    connection.close()
    print("")
    print("✅ All tests passed!")
    sys.exit(0)
    
except AMQPConnectionError as e:
    print(f"❌ Connection failed: {e}")
    print("")
    print("💡 Possible issues:")
    print("   1. RabbitMQ server is not accessible")
    print("   2. Wrong host/port")
    print("   3. Wrong credentials")
    print("   4. Network/firewall issue")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    print_success "🎉 Connection test completed successfully!"
else
    print_error "❌ Connection test failed"
    exit 1
fi

echo ""

