#!/bin/bash
# Script สำหรับ republish messages จาก DLQ กลับไป queue หลัก
# ใช้เมื่อ messages ไปอยู่ที่ DLQ เพราะ worker ไม่ได้ทำงาน

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

cd /workspace/transcription-service 2>/dev/null || {
    print_error "Cannot find project directory"
    exit 1
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

print_header "🔄 Republish Messages from DLQ"

# Queue to check
QUEUE_NAME="${1:-audio_extraction_queue}"
DLQ_NAME="${QUEUE_NAME}.dlq"

print_header "Queue: $QUEUE_NAME"
echo "   DLQ: $DLQ_NAME"
echo ""

# Check DLQ message count
print_header "Step 1: Check DLQ Status"

DLQ_INFO=$(curl -s -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
    "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues/%2F/${DLQ_NAME}" 2>/dev/null)

if [ -z "$DLQ_INFO" ] || echo "$DLQ_INFO" | grep -q "Not Found\|404" 2>/dev/null; then
    print_warning "DLQ '$DLQ_NAME' not found (may not exist yet)"
    exit 0
fi

MESSAGES=$(echo "$DLQ_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages', 0))" 2>/dev/null || echo "0")

if [ "$MESSAGES" -eq 0 ]; then
    print_success "DLQ '$DLQ_NAME' is empty - no messages to republish"
    exit 0
fi

print_warning "Found $MESSAGES messages in DLQ '$DLQ_NAME'"
echo ""

# Republish messages
print_header "Step 2: Republish Messages"

print_info "Republishing messages from DLQ to main queue..."
print_warning "⚠️  This will move messages from DLQ back to main queue"
echo ""
read -p "Continue? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Cancelled"
    exit 0
fi

# Use Python script to republish
python3 << PYTHON_EOF
import pika
import json
import sys

try:
    credentials = pika.PlainCredentials('${RABBITMQ_USER}', '${RABBITMQ_PASSWORD}')
    parameters = pika.ConnectionParameters(
        host='${RABBITMQ_HOST}',
        port=${RABBITMQ_PORT},
        credentials=credentials,
        connection_attempts=3,
        retry_delay=2
    )
    
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    dlq_name = '${DLQ_NAME}'
    main_queue = '${QUEUE_NAME}'
    
    republished = 0
    failed = 0
    
    # Get messages from DLQ
    while True:
        method_frame, header_frame, body = channel.basic_get(queue=dlq_name, auto_ack=False)
        
        if method_frame is None:
            break
        
        try:
            # Republish to main queue
            channel.basic_publish(
                exchange='',
                routing_key=main_queue,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    headers=header_frame.headers if header_frame else None
                )
            )
            
            # Acknowledge DLQ message
            channel.basic_ack(delivery_tag=method_frame.delivery_tag)
            republished += 1
            
            print(f"✅ Republished message {republished}")
            
        except Exception as e:
            print(f"❌ Failed to republish message: {e}")
            # Reject and requeue in DLQ
            channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
            failed += 1
    
    connection.close()
    
    print(f"\n✅ Republished: {republished} messages")
    if failed > 0:
        print(f"⚠️  Failed: {failed} messages")
    
    sys.exit(0 if failed == 0 else 1)
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
PYTHON_EOF

REPUBLISH_RESULT=$?

echo ""
if [ $REPUBLISH_RESULT -eq 0 ]; then
    print_success "Messages republished successfully"
    echo ""
    print_info "💡 Next steps:"
    echo "   1. Start worker: bash scripts/pod/start-service-daemon.sh"
    echo "   2. Monitor logs: bash scripts/pod/tail-worker-log.sh"
else
    print_error "Failed to republish some messages"
fi

