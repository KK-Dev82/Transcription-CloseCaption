#!/bin/bash
# Script สำหรับตรวจสอบการทำงานของ Services ต่างๆ พร้อมแจ้ง error
#
# วิธีใช้งาน:
#   bash scripts/pod/check-pod.sh

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

echo "🔍 Checking Pod Services Status"
echo "📅 $(date)"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

ALL_HEALTHY=true

# Check Redis
print_status "Checking Redis..."
if pgrep -x "redis-server" > /dev/null; then
    REDIS_PID=$(pgrep -x "redis-server")
    print_success "✅ Redis is running (PID: $REDIS_PID)"
    if redis-cli ping > /dev/null 2>&1; then
        print_success "   Redis is responding"
    else
        print_warning "   Redis is not responding"
        ALL_HEALTHY=false
    fi
else
    print_error "❌ Redis is not running"
    ALL_HEALTHY=false
fi
echo ""

# Check Whisper API
print_status "Checking Whisper API..."
if pgrep -f "python.*whisper_api" > /dev/null; then
    WHISPER_PID=$(pgrep -f "python.*whisper_api")
    print_success "✅ Whisper API is running (PID: $WHISPER_PID)"
    if curl -f http://localhost:8002/health > /dev/null 2>&1; then
        print_success "   Whisper API is responding"
    else
        print_warning "   Whisper API is not responding"
        ALL_HEALTHY=false
    fi
else
    print_error "❌ Whisper API is not running"
    ALL_HEALTHY=false
fi
echo ""

# Check Video Worker
print_status "Checking Video Worker..."
WORKER_PIDS=$(pgrep -f "python.*video_worker" 2>/dev/null || echo "")
if [ -n "$WORKER_PIDS" ]; then
    WORKER_COUNT=$(echo "$WORKER_PIDS" | wc -l)
    if [ "$WORKER_COUNT" -eq 1 ]; then
        print_success "✅ Video Worker is running (PID: $WORKER_PIDS)"
    else
        print_warning "⚠️  Multiple Video Workers detected ($WORKER_COUNT)"
        print_warning "   PIDs: $WORKER_PIDS"
        print_warning "   This may cause duplicate message processing"
        ALL_HEALTHY=false
    fi
else
    print_error "❌ Video Worker is not running"
    ALL_HEALTHY=false
fi
echo ""

# Check Main API
print_status "Checking Main API..."
if pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
    MAIN_API_PID=$(pgrep -f "python.*uvicorn.*app.main")
    print_success "✅ Main API is running (PID: $MAIN_API_PID)"
    if curl -f http://localhost:8001/health > /dev/null 2>&1; then
        print_success "   Main API is responding"
    else
        print_warning "   Main API is not responding"
        ALL_HEALTHY=false
    fi
else
    print_error "❌ Main API is not running"
    ALL_HEALTHY=false
fi
echo ""

# Check RabbitMQ Connection
print_status "Checking RabbitMQ Connection..."
if [ -f ".env.runpod" ]; then
    set -a
    source .env.runpod
    set +a
fi

RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
RABBITMQ_USER=${RABBITMQ_USER:-senate}
RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}

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
    message_count = method.method.message_count
    consumer_count = method.method.consumer_count
    
    print("✅ RabbitMQ connection successful")
    print(f"   Queue: {queue_name}")
    print(f"   Messages: {message_count}")
    print(f"   Consumers: {consumer_count}")
    
    if consumer_count > 1:
        print(f"⚠️  Multiple consumers detected ({consumer_count}) - may cause duplicate processing")
    
    connection.close()
    sys.exit(0)
except Exception as e:
    print(f"❌ RabbitMQ connection failed: {e}")
    sys.exit(1)
EOF

echo ""

# Summary
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Summary"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$ALL_HEALTHY" = true ]; then
    print_success "✅ All services are running and healthy!"
else
    print_warning "⚠️  Some services have issues"
    echo ""
    print_status "💡 To restart services:"
    echo "   bash scripts/pod/restart-pod.sh"
fi
echo ""

