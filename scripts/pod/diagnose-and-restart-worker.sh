#!/bin/bash

# Script สำหรับวินิจฉัยและแก้ไขปัญหา Video Worker ที่หยุดทำงาน

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_status() {
    echo -e "${BLUE}ℹ️  $1${NC}"
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

cd "$(dirname "$0")/../.." || exit 1

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

print_header "🔍 วินิจฉัยปัญหา Video Worker และ RabbitMQ"

# Step 1: Check Video Worker Process
print_header "Step 1: ตรวจสอบ Video Worker Process"

WORKER_PIDS=$(pgrep -f "python.*video_worker" 2>/dev/null || echo "")
if [ -n "$WORKER_PIDS" ]; then
    WORKER_COUNT=$(echo "$WORKER_PIDS" | wc -l | tr -d ' ')
    print_success "พบ Video Worker process(es): $WORKER_COUNT"
    echo "$WORKER_PIDS" | while read pid; do
        if [ -n "$pid" ]; then
            print_status "  PID: $pid"
            ps -p "$pid" -o pid,etime,command --no-headers 2>/dev/null | head -1 || true
        fi
    done
else
    print_error "ไม่พบ Video Worker process!"
    WORKER_RUNNING=false
fi
echo ""

# Step 2: Check Video Worker Logs
print_header "Step 2: ตรวจสอบ Video Worker Logs (100 บรรทัดล่าสุด)"

if [ -f "/tmp/video-worker.log" ]; then
    print_status "Log file: /tmp/video-worker.log"
    echo ""
    
    # Check for errors
    ERROR_COUNT=$(tail -100 /tmp/video-worker.log | grep -iE "error|exception|traceback|failed|crash" | wc -l | tr -d ' ' || echo "0")
    if [ "$ERROR_COUNT" -gt 0 ]; then
        print_warning "พบ $ERROR_COUNT errors ใน logs ล่าสุด:"
        tail -100 /tmp/video-worker.log | grep -iE "error|exception|traceback|failed|crash" | tail -10 || true
    else
        print_success "ไม่พบ errors ใน logs ล่าสุด"
    fi
    echo ""
    
    # Check for "Channel is closed"
    CHANNEL_CLOSED_COUNT=$(tail -100 /tmp/video-worker.log | grep -i "channel is closed" | wc -l | tr -d ' ' || echo "0")
    if [ "$CHANNEL_CLOSED_COUNT" -gt 0 ]; then
        print_warning "พบ 'Channel is closed' $CHANNEL_CLOSED_COUNT ครั้ง"
    fi
    
    # Check last activity
    LAST_ACTIVITY=$(tail -5 /tmp/video-worker.log | tail -1 || echo "")
    if [ -n "$LAST_ACTIVITY" ]; then
        print_status "Last log entry:"
        echo "  $LAST_ACTIVITY"
    fi
else
    print_warning "ไม่พบ log file: /tmp/video-worker.log"
fi
echo ""

# Step 3: Check RabbitMQ Queue
print_header "Step 3: ตรวจสอบ RabbitMQ Queue"

python3 << PYTHON_EOF 2>/dev/null || print_error "ไม่สามารถเชื่อมต่อ RabbitMQ ได้"
import pika
import sys
import json

try:
    credentials = pika.PlainCredentials('${RABBITMQ_USER}', '${RABBITMQ_PASSWORD}')
    parameters = pika.ConnectionParameters(
        host='${RABBITMQ_HOST}',
        port=${RABBITMQ_PORT},
        credentials=credentials,
        connection_attempts=3,
        retry_delay=2,
        heartbeat=600
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    # Check transcription_queue
    try:
        method = channel.queue_declare(queue='transcription_queue', passive=True)
        message_count = method.method.message_count
        consumer_count = method.method.consumer_count
        
        print(f"📋 transcription_queue:")
        print(f"   Messages waiting: {message_count}")
        print(f"   Active consumers: {consumer_count}")
        print("")
        
        if message_count > 0:
            print(f"⚠️  มี {message_count} messages รอในคิว!")
        
        if consumer_count == 0:
            print("❌ ไม่มี consumers - tasks จะไม่ถูก process!")
        elif consumer_count == 1:
            print("✅ มี 1 consumer")
        else:
            print(f"⚠️  มี {consumer_count} consumers (อาจมีปัญหา duplicate processing)")
    except pika.exceptions.ChannelClosedByBroker as e:
        print(f"❌ Queue not found or error: {e}")
    
    connection.close()
    sys.exit(0)
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)
PYTHON_EOF

PYTHON_EXIT_CODE=$?
if [ $PYTHON_EXIT_CODE -ne 0 ]; then
    print_error "ไม่สามารถตรวจสอบ RabbitMQ queue ได้"
fi
echo ""

# Step 4: Check System Resources
print_header "Step 4: ตรวจสอบ System Resources"

# Check memory
MEM_USAGE=$(free -h | awk '/^Mem:/ {print $3 "/" $2}' || echo "N/A")
print_status "Memory usage: $MEM_USAGE"

# Check GPU
if command -v nvidia-smi > /dev/null 2>&1; then
    GPU_PROCESSES=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null | wc -l | tr -d ' ' || echo "0")
    print_status "GPU processes: $GPU_PROCESSES"
    if [ "$GPU_PROCESSES" -eq 0 ]; then
        print_warning "ไม่มี processes ใช้ GPU"
    fi
else
    print_warning "nvidia-smi not available"
fi
echo ""

# Step 5: Diagnosis Summary
print_header "Step 5: สรุปผลการวินิจฉัย"

ISSUES_FOUND=0

if [ -z "$WORKER_PIDS" ]; then
    print_error "Video Worker ไม่ได้ทำงาน"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

if [ "$CHANNEL_CLOSED_COUNT" -gt 10 ]; then
    print_warning "พบ 'Channel is closed' หลายครั้ง - อาจเกิดจาก connection instability"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

if [ "$ERROR_COUNT" -gt 0 ]; then
    print_warning "พบ errors ใน logs"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

if [ $ISSUES_FOUND -eq 0 ]; then
    print_success "ไม่พบปัญหา - ระบบทำงานปกติ"
else
    print_warning "พบ $ISSUES_FOUND ปัญหา"
fi
echo ""

# Step 6: Restart Worker (if needed)
if [ $ISSUES_FOUND -gt 0 ] || [ -z "$WORKER_PIDS" ]; then
    print_header "Step 6: แก้ไขปัญหา - Restart Video Worker"
    
    read -p "ต้องการ restart Video Worker หรือไม่? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "กำลัง stop Video Worker..."
        
        # Stop existing workers
        if [ -n "$WORKER_PIDS" ]; then
            echo "$WORKER_PIDS" | while read pid; do
                if [ -n "$pid" ]; then
                    print_status "  Killing PID: $pid"
                    kill -TERM "$pid" 2>/dev/null || true
                fi
            done
            sleep 3
            
            # Force kill if still running
            REMAINING=$(pgrep -f "python.*video_worker" 2>/dev/null || echo "")
            if [ -n "$REMAINING" ]; then
                echo "$REMAINING" | while read pid; do
                    if [ -n "$pid" ]; then
                        print_warning "  Force killing PID: $pid"
                        kill -9 "$pid" 2>/dev/null || true
                    fi
                done
                sleep 2
            fi
        fi
        
        # Start new worker
        print_status "กำลัง start Video Worker..."
        cd "$(dirname "$0")/../.." || exit 1
        
        if [ -f ".env.runpod" ]; then
            set -a
            source .env.runpod
            set +a
        fi
        
        # Start worker with proper environment
        nohup env RABBITMQ_HOST="${RABBITMQ_HOST}" \
                 RABBITMQ_PORT="${RABBITMQ_PORT}" \
                 RABBITMQ_USER="${RABBITMQ_USER}" \
                 RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD}" \
                 WHISPER_PROVIDER="${WHISPER_PROVIDER}" \
                 WHISPER_MODEL="${WHISPER_MODEL}" \
                 WHISPER_DEVICE="${WHISPER_DEVICE}" \
                 LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}" \
                 PYTHONPATH="$(pwd)" \
                 python3 -m app.workers.video_worker > /tmp/video-worker.log 2>&1 & disown
        
        sleep 3
        
        # Verify
        NEW_WORKER_PIDS=$(pgrep -f "python.*video_worker" 2>/dev/null || echo "")
        if [ -n "$NEW_WORKER_PIDS" ]; then
            NEW_WORKER_COUNT=$(echo "$NEW_WORKER_PIDS" | wc -l | tr -d ' ')
            if [ "$NEW_WORKER_COUNT" -eq 1 ]; then
                print_success "Video Worker restarted successfully (PID: $NEW_WORKER_PIDS)"
                
                # Wait and check logs
                print_status "รอ 5 วินาทีเพื่อให้ worker เชื่อมต่อ..."
                sleep 5
                
                if grep -q "Connected to RabbitMQ" /tmp/video-worker.log 2>/dev/null || grep -q "Starting consumer" /tmp/video-worker.log 2>/dev/null; then
                    print_success "Worker เชื่อมต่อ RabbitMQ สำเร็จ"
                else
                    print_warning "ยังไม่เห็น log การเชื่อมต่อ - ตรวจสอบ logs: tail -f /tmp/video-worker.log"
                fi
            else
                print_warning "พบ Video Workers $NEW_WORKER_COUNT ตัว (ควรมีแค่ 1 ตัว)"
            fi
        else
            print_error "Video Worker ไม่ได้ start"
            print_status "ตรวจสอบ logs: tail -20 /tmp/video-worker.log"
        fi
    else
        print_status "ข้ามการ restart"
    fi
else
    print_status "ไม่จำเป็นต้อง restart"
fi

echo ""
print_header "✅ เสร็จสมบูรณ์"

