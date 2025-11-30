#!/bin/bash
# Script สำหรับ Debug Transcription Task
#
# วิธีใช้งาน:
#   bash scripts/pod/debug-transcription-task.sh [task-id]

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

TASK_ID="${1}"

if [ -z "$TASK_ID" ]; then
    print_error "❌ Task ID is required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/debug-transcription-task.sh <task-id>"
    exit 1
fi

echo "🔍 Debugging Transcription Task"
echo "📅 $(date)"
echo ""
print_status "Task ID: $TASK_ID"
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

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "1. Check Task in Storage"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "storage/transcriptions/$TASK_ID.json" ]; then
    print_success "✅ Task file found in storage"
    echo ""
    print_status "Task data:"
    python3 -c "
import json
with open('storage/transcriptions/$TASK_ID.json') as f:
    data = json.load(f)
    print(f\"  Status: {data.get('status', 'unknown')}\")
    print(f\"  Progress: {data.get('progress', 0)}%\")
    print(f\"  File Path: {data.get('file_path', 'N/A')}\")
    print(f\"  Model Size: {data.get('model_size', 'N/A')}\")
    print(f\"  Language: {data.get('language', 'N/A')}\")
    print(f\"  Created At: {data.get('created_at', 'N/A')}\")
    print(f\"  Started At: {data.get('started_at', 'N/A')}\")
" 2>/dev/null || cat "storage/transcriptions/$TASK_ID.json" | python3 -m json.tool | head -20
else
    print_warning "⚠️  Task file not found in storage"
fi

echo ""

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "2. Check RabbitMQ Queue"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python3 << EOF
import pika
import json
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
    
    # Check queue status
    method = channel.queue_declare(queue=queue_name, passive=True)
    message_count = method.method.message_count
    consumer_count = method.method.consumer_count
    
    print(f"Queue: {queue_name}")
    print(f"Messages: {message_count}")
    print(f"Consumers: {consumer_count}")
    print("")
    
    if message_count > 0:
        print("⚠️  There are messages in queue. Checking if task is in queue...")
        # Note: We can't peek messages without consuming them
        # But we can check if consumers are active
        if consumer_count > 0:
            print(f"✅ {consumer_count} consumer(s) active - messages should be processed")
        else:
            print("❌ No consumers active - messages won't be processed")
    else:
        print("✅ Queue is empty")
        if consumer_count > 0:
            print(f"✅ {consumer_count} consumer(s) active - ready to process new tasks")
        else:
            print("❌ No consumers active - tasks won't be processed")
    
    connection.close()
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

echo ""

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "3. Check Video Worker Logs"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "/tmp/video-worker.log" ]; then
    TASK_LOGS=$(grep -i "$TASK_ID" /tmp/video-worker.log 2>/dev/null || echo "")
    if [ -n "$TASK_LOGS" ]; then
        print_success "✅ Found logs for this task:"
        echo "$TASK_LOGS"
    else
        print_warning "⚠️  No logs found for this task in Video Worker"
        print_status "Recent Video Worker activity:"
        tail -n 30 /tmp/video-worker.log | grep -i "transcription\|task\|processing\|รับ\|เริ่ม" | tail -10 || echo "No recent activity"
    fi
else
    print_warning "⚠️  Video Worker log file not found"
fi

echo ""

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "4. Check Main API Logs"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "/tmp/main-api.log" ]; then
    TASK_LOGS=$(grep -i "$TASK_ID" /tmp/main-api.log 2>/dev/null | tail -10 || echo "")
    if [ -n "$TASK_LOGS" ]; then
        print_success "✅ Found logs for this task:"
        echo "$TASK_LOGS"
    else
        print_warning "⚠️  No logs found for this task in Main API"
    fi
else
    print_warning "⚠️  Main API log file not found"
fi

echo ""

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "5. Check Task Status from API"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

API_URL="http://localhost:8001"
RESPONSE=$(curl -s "$API_URL/transcribe/$TASK_ID" 2>/dev/null || echo "")

if [ -z "$RESPONSE" ]; then
    RESPONSE=$(curl -s "$API_URL/api/transcription/$TASK_ID" 2>/dev/null || echo "")
fi

if [ -n "$RESPONSE" ]; then
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
else
    print_error "❌ Could not fetch task status from API"
fi

echo ""

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Summary"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

print_status "💡 Possible issues:"
echo "   1. Message was sent but Video Worker didn't receive it"
echo "   2. Message was consumed by another worker instance"
echo "   3. Video Worker is not listening to the correct queue"
echo "   4. Task was created but not sent to RabbitMQ"
echo ""
print_status "💡 Next steps:"
echo "   1. Check if Video Worker is running: bash scripts/pod/check-services-status.sh"
echo "   2. Check RabbitMQ queue: bash scripts/pod/check-rabbitmq-queue.sh"
echo "   3. Monitor Video Worker: tail -f /tmp/video-worker.log"
echo "   4. Try sending a new task to test"
echo ""

