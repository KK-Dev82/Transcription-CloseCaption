#!/bin/bash

# Script to check RabbitMQ queue status using curl
# Usage: bash scripts/pod/check-rabbitmq-queue.sh [queue_name]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

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
RABBITMQ_MGMT_PORT=${RABBITMQ_MGMT_PORT:-15672}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    print_warning "jq not found. Installing..."
    apt-get update -qq && apt-get install -y -qq jq > /dev/null 2>&1 || {
        print_error "Cannot install jq. Please install manually: apt-get install -y jq"
        exit 1
    }
fi

# Check if curl is installed
if ! command -v curl &> /dev/null; then
    print_error "curl not found. Please install: apt-get install -y curl"
    exit 1
fi

print_header "RabbitMQ Queue Status Check"
echo ""

# Test RabbitMQ connection
print_status "Testing RabbitMQ connection..."
if curl -s -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/overview" > /dev/null 2>&1; then
    print_status "✅ RabbitMQ Management API accessible"
else
    print_warning "⚠️  RabbitMQ Management API not accessible at http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}"
    print_warning "   Trying to check queues using Python/pika instead..."
    
    # Fallback to Python/pika
    python3 << 'PYTHON_EOF' 2>/dev/null || {
        print_error "Cannot connect to RabbitMQ"
        exit 1
    }
import pika
import sys
import json

try:
    credentials = pika.PlainCredentials('${RABBITMQ_USER}', '${RABBITMQ_PASSWORD}')
    parameters = pika.ConnectionParameters(
        host='${RABBITMQ_HOST}',
        port=${RABBITMQ_PORT},
        credentials=credentials,
        connection_attempts=2,
        retry_delay=1
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    # List of queues to check
    queues = [
        'transcription_queue',
        'transcription_chunk_queue',
        'video_trim_queue',
        'video_merge_queue',
        'video_convert_queue',
        'video_resize_queue',
        'media.audio.chunk.extracted'
    ]
    
    print("Queue Name | Messages | Consumers | Status")
    print("-" * 60)
    
    for queue_name in queues:
        try:
            method = channel.queue_declare(queue=queue_name, passive=True)
            message_count = method.method.message_count
            consumer_count = method.method.consumer_count
            
            status = "✅ Active" if consumer_count > 0 else "⚠️  No consumers"
            print(f"{queue_name:30} | {message_count:8} | {consumer_count:9} | {status}")
        except pika.exceptions.ChannelClosedByBroker:
            print(f"{queue_name:30} | {'N/A':8} | {'N/A':9} | ❌ Queue not found")
        except Exception as e:
            print(f"{queue_name:30} | {'ERROR':8} | {'ERROR':9} | ❌ {str(e)}")
    
    connection.close()
    sys.exit(0)
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)
PYTHON_EOF
    
    if [ $? -ne 0 ]; then
        print_error "Cannot connect to RabbitMQ"
        exit 1
    fi
    exit 0
fi

echo ""

# Get all queues
print_status "Fetching queue information..."
QUEUES_JSON=$(curl -s -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues")

if [ -z "$QUEUES_JSON" ] || [ "$QUEUES_JSON" = "null" ]; then
    print_error "Cannot fetch queue information"
    exit 1
fi

# If specific queue name provided
if [ -n "$1" ]; then
    QUEUE_NAME="$1"
    print_header "Queue: $QUEUE_NAME"
    
    QUEUE_INFO=$(echo "$QUEUES_JSON" | jq -r ".[] | select(.name == \"$QUEUE_NAME\")")
    
    if [ -z "$QUEUE_INFO" ] || [ "$QUEUE_INFO" = "null" ]; then
        print_warning "Queue '$QUEUE_NAME' not found"
        echo ""
        print_status "Available queues:"
        echo "$QUEUES_JSON" | jq -r '.[].name' | sort
        exit 1
    fi
    
    MESSAGES=$(echo "$QUEUE_INFO" | jq -r '.messages // 0')
    CONSUMERS=$(echo "$QUEUE_INFO" | jq -r '.consumers // 0')
    MESSAGE_RATE=$(echo "$QUEUE_INFO" | jq -r '.message_stats.publish_details.rate // 0')
    CONSUMER_UTILIZATION=$(echo "$QUEUE_INFO" | jq -r '.consumer_utilisation // 0')
    
    echo ""
    echo "Messages: $MESSAGES"
    echo "Consumers: $CONSUMERS"
    echo "Message Rate: $MESSAGE_RATE msg/s"
    echo "Consumer Utilization: $(echo "$CONSUMER_UTILIZATION * 100" | bc -l 2>/dev/null || echo "N/A")%"
    echo ""
    
    if [ "$CONSUMERS" -eq 0 ]; then
        print_warning "⚠️  No consumers for this queue"
    elif [ "$CONSUMERS" -gt 1 ]; then
        print_status "✅ Multiple consumers ($CONSUMERS) - parallel processing enabled"
    else
        print_warning "⚠️  Only 1 consumer - sequential processing"
    fi
    
    if [ "$MESSAGES" -gt 0 ]; then
        print_warning "⚠️  $MESSAGES messages waiting in queue"
    else
        print_status "✅ Queue is empty"
    fi
    
    exit 0
fi

# Show all transcription-related queues
print_header "Transcription Queues"
echo ""

# Filter transcription queues
TRANSCRIPTION_QUEUES=$(echo "$QUEUES_JSON" | jq -r '.[] | select(.name | contains("transcription") or contains("chunk") or contains("media.audio"))')

if [ -z "$TRANSCRIPTION_QUEUES" ]; then
    print_warning "No transcription queues found"
else
    echo "Queue Name | Messages | Consumers | Status"
    echo "----------------------------------------------------------------------"
    
    echo "$TRANSCRIPTION_QUEUES" | jq -r '
        .name as $name |
        .messages as $messages |
        .consumers as $consumers |
        (if $consumers > 1 then "✅ Parallel" elif $consumers == 1 then "⚠️  Sequential" else "❌ No consumers" end) as $status |
        "\($name | .[0:30]) | \($messages // 0 | tostring | .[0:8]) | \($consumers // 0 | tostring | .[0:9]) | \($status)"
    ' | column -t -s '|'
fi

echo ""

# Show all queues summary
print_header "All Queues Summary"
echo ""

echo "$QUEUES_JSON" | jq -r '.[] | "\(.name) | \(.messages // 0) | \(.consumers // 0)"' | \
    awk 'BEGIN {printf "%-40s %10s %10s\n", "Queue Name", "Messages", "Consumers"; print "----------------------------------------------------------------"} 
         {printf "%-40s %10s %10s\n", $1, $3, $5}' | \
    sort

echo ""

# Check for transcription_queue specifically
TRANSCRIPTION_QUEUE=$(echo "$QUEUES_JSON" | jq -r '.[] | select(.name == "transcription_queue")')
if [ -n "$TRANSCRIPTION_QUEUE" ]; then
    MESSAGES=$(echo "$TRANSCRIPTION_QUEUE" | jq -r '.messages // 0')
    CONSUMERS=$(echo "$TRANSCRIPTION_QUEUE" | jq -r '.consumers // 0')
    
    echo ""
    print_header "transcription_queue Analysis"
    echo ""
    echo "Messages waiting: $MESSAGES"
    echo "Active consumers: $CONSUMERS"
    echo ""
    
    if [ "$CONSUMERS" -eq 0 ]; then
        print_error "❌ No consumers - tasks will not be processed!"
    elif [ "$CONSUMERS" -eq 1 ]; then
        print_warning "⚠️  Only 1 consumer - processing is SEQUENTIAL (slow)"
        echo ""
        echo "Current behavior:"
        echo "  - Video Worker receives full video task"
        echo "  - Extracts audio and creates chunks"
        echo "  - Processes chunks ONE BY ONE (sequential)"
        echo "  - GPU utilization: ~23% (low)"
        echo ""
        echo "Recommendation:"
        echo "  - Implement transcription_chunk_queue for parallel processing"
        echo "  - Send individual chunks to queue"
        echo "  - Multiple workers process chunks in parallel"
        echo "  - Expected GPU utilization: 80-100%"
    else
        print_status "✅ Multiple consumers ($CONSUMERS) - parallel processing possible"
    fi
fi

echo ""

