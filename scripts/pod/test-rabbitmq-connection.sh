#!/bin/bash
# Script สำหรับทดสอบ RabbitMQ Connection
#
# วิธีใช้งาน:
# bash scripts/pod/test-rabbitmq-connection.sh [rabbitmq-host] [rabbitmq-port] [username] [password]
#
# ตัวอย่าง:
# bash scripts/pod/test-rabbitmq-connection.sh 178.128.105.100 5672 senate qP2VtHz6fAX4xDksEpMrLT

set -e

RABBITMQ_HOST="${1:-178.128.105.100}"
RABBITMQ_PORT="${2:-5672}"
RABBITMQ_USER="${3:-senate}"
RABBITMQ_PASSWORD="${4:-qP2VtHz6fAX4xDksEpMrLT}"

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

echo "🔌 Testing RabbitMQ Connection"
echo "📅 $(date)"
echo ""
echo "📋 Configuration:"
echo "   Host: $RABBITMQ_HOST"
echo "   Port: $RABBITMQ_PORT"
echo "   User: $RABBITMQ_USER"
echo ""

# Test 1: Network connectivity
print_status "Test 1: Network Connectivity"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v nc &> /dev/null || command -v netcat &> /dev/null; then
    NC_CMD=$(command -v nc || command -v netcat)
    if timeout 5 $NC_CMD -z "$RABBITMQ_HOST" "$RABBITMQ_PORT" 2>/dev/null; then
        print_success "✅ Port $RABBITMQ_PORT is reachable on $RABBITMQ_HOST"
    else
        print_error "❌ Port $RABBITMQ_PORT is NOT reachable on $RABBITMQ_HOST"
        echo ""
        print_warning "Possible reasons:"
        echo "   1. Firewall is blocking port $RABBITMQ_PORT"
        echo "   2. RabbitMQ is not running"
        echo "   3. IP address is incorrect"
        echo ""
        print_status "💡 Solutions:"
        echo "   1. Check firewall: sudo ufw status (on Backend Server)"
        echo "   2. Check RabbitMQ: docker ps | grep rabbitmq (on Backend Server)"
        echo "   3. Verify IP address"
        exit 1
    fi
else
    print_warning "⚠️  nc/netcat not found, skipping network test"
fi

echo ""

# Test 2: RabbitMQ connection
print_status "Test 2: RabbitMQ Connection"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if pika is installed
if ! python3 -c "import pika" 2>/dev/null; then
    print_warning "⚠️  pika not installed, installing..."
    pip3 install --no-cache-dir pika || {
        print_error "❌ Failed to install pika"
        exit 1
    }
fi

# Test connection
if python3 << EOF
import pika
import sys

try:
    print("Attempting to connect to RabbitMQ...")
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host='$RABBITMQ_HOST',
            port=$RABBITMQ_PORT,
            credentials=pika.PlainCredentials('$RABBITMQ_USER', '$RABBITMQ_PASSWORD'),
            connection_attempts=3,
            retry_delay=2,
            socket_timeout=5
        )
    )
    print("✅ RabbitMQ connection successful!")
    
    # Test channel
    channel = connection.channel()
    print("✅ Channel created successfully!")
    
    # List queues (optional)
    try:
        queues = channel.queue_declare(queue='', exclusive=True)
        print("✅ Queue operations working!")
    except Exception as e:
        print(f"⚠️  Queue operation warning: {e}")
    
    connection.close()
    print("✅ Connection closed gracefully")
    sys.exit(0)
except pika.exceptions.AMQPConnectionError as e:
    print(f"❌ AMQP Connection Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)
EOF
then
    print_success "✅ RabbitMQ connection test passed!"
else
    print_error "❌ RabbitMQ connection test failed!"
    echo ""
    print_warning "Possible reasons:"
    echo "   1. Wrong credentials (username/password)"
    echo "   2. RabbitMQ is not accepting connections"
    echo "   3. Network issues"
    echo ""
    print_status "💡 Solutions:"
    echo "   1. Verify credentials:"
    echo "      User: $RABBITMQ_USER"
    echo "      Password: $RABBITMQ_PASSWORD"
    echo "   2. Check RabbitMQ logs on Backend Server:"
    echo "      docker logs kk-rabbitmq"
    echo "   3. Check RabbitMQ Management UI:"
    echo "      http://$RABBITMQ_HOST:15672"
    exit 1
fi

echo ""

# Test 3: Check queues
print_status "Test 3: Check Queues"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if python3 << EOF
import pika
import sys

try:
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host='$RABBITMQ_HOST',
            port=$RABBITMQ_PORT,
            credentials=pika.PlainCredentials('$RABBITMQ_USER', '$RABBITMQ_PASSWORD'),
            connection_attempts=3,
            retry_delay=2
        )
    )
    channel = connection.channel()
    
    # Check required queues
    required_queues = [
        'media.audio.chunk.extracted',
        'transcription_queue',
        'video_trim_queue',
        'video_merge_queue',
        'video_convert_queue'
    ]
    
    print("Checking required queues...")
    for queue in required_queues:
        try:
            channel.queue_declare(queue=queue, durable=True, passive=True)
            print(f"✅ Queue '{queue}' exists")
        except pika.exceptions.ChannelClosedByBroker:
            print(f"⚠️  Queue '{queue}' does not exist (will be created automatically)")
        except Exception as e:
            print(f"⚠️  Queue '{queue}' check failed: {e}")
    
    connection.close()
    sys.exit(0)
except Exception as e:
    print(f"❌ Queue check failed: {e}")
    sys.exit(1)
EOF
then
    print_success "✅ Queue check completed!"
else
    print_warning "⚠️  Queue check failed (queues will be created automatically when needed)"
fi

echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

print_success "✅ RabbitMQ connection test completed successfully!"
echo ""
print_status "💡 Next steps:"
echo "   1. Update .env.runpod with correct RabbitMQ settings:"
echo "      RABBITMQ_HOST=$RABBITMQ_HOST"
echo "      RABBITMQ_PORT=$RABBITMQ_PORT"
echo "      RABBITMQ_USER=$RABBITMQ_USER"
echo "      RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD"
echo ""
echo "   2. Restart services:"
echo "      bash scripts/pod/stop-services.sh"
echo "      bash scripts/pod/start-services-direct.sh"
echo ""
echo "   3. Check Video Worker logs:"
echo "      tail -f /tmp/video-worker.log"

