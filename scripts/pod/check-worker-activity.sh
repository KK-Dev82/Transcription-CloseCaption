#!/bin/bash

# Script สำหรับตรวจสอบว่า Video Worker กำลังทำงานจริงหรือไม่

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

print_header "🔍 ตรวจสอบ Activity ของ Video Worker"

# Step 1: Check recent logs activity
print_header "Step 1: ตรวจสอบ Logs Activity (500 บรรทัดล่าสุด)"

# Check both log locations (current and legacy)
WORKER_LOG=""
if [ -f "logs/video-worker.log" ]; then
    WORKER_LOG="logs/video-worker.log"
elif [ -f "/tmp/video-worker.log" ]; then
    WORKER_LOG="/tmp/video-worker.log"
fi

if [ -n "$WORKER_LOG" ] && [ -f "$WORKER_LOG" ]; then
    LOG_SIZE=$(wc -l < "$WORKER_LOG" 2>/dev/null || echo "0")
    print_status "Log file: $WORKER_LOG (Total lines: $LOG_SIZE)"
    echo ""
    
    # Check last 30 minutes activity
    LAST_30MIN=$(date -d '30 minutes ago' '+%Y-%m-%d %H:%M' 2>/dev/null || date -v-30M '+%Y-%m-%d %H:%M' 2>/dev/null || echo "")
    
    if [ -n "$LAST_30MIN" ]; then
        RECENT_LOGS=$(grep -E "^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}" "$WORKER_LOG" | tail -100 | grep -E "(INFO|ERROR|WARNING)" | tail -20 || echo "")
        
        if [ -n "$RECENT_LOGS" ]; then
            print_status "Recent activity (last 20 log entries):"
            echo "$RECENT_LOGS" | tail -10
        else
            print_warning "ไม่พบ recent activity ใน logs"
        fi
    fi
    echo ""
    
    # Check for specific patterns
    print_status "Checking for specific patterns..."
    
    # Check if worker is consuming
    CONSUMING_COUNT=$(tail -500 "$WORKER_LOG" | grep -iE "processing.*task|received.*message|starting.*transcription|extract.*audio" | wc -l | tr -d ' ' || echo "0")
    print_status "  Processing tasks: $CONSUMING_COUNT (ใน 500 บรรทัดล่าสุด)"
    
    # Check for transcription activity
    TRANSCRIBE_COUNT=$(tail -500 "$WORKER_LOG" | grep -iE "transcrib|faster.*whisper|whisper.*transcribe" | wc -l | tr -d ' ' || echo "0")
    print_status "  Transcription activity: $TRANSCRIBE_COUNT (ใน 500 บรรทัดล่าสุด)"
    
    # Check for errors
    ERROR_COUNT=$(tail -500 "$WORKER_LOG" | grep -iE "error|exception|traceback|failed" | wc -l | tr -d ' ' || echo "0")
    if [ "$ERROR_COUNT" -gt 0 ]; then
        print_warning "  Errors: $ERROR_COUNT (ใน 500 บรรทัดล่าสุด)"
        tail -500 "$WORKER_LOG" | grep -iE "error|exception|traceback|failed" | tail -5
    else
        print_success "  Errors: 0"
    fi
    
    # Check for "Channel is closed"
    CHANNEL_CLOSED=$(tail -500 "$WORKER_LOG" | grep -i "channel is closed" | wc -l | tr -d ' ' || echo "0")
    if [ "$CHANNEL_CLOSED" -gt 0 ]; then
        print_warning "  'Channel is closed': $CHANNEL_CLOSED ครั้ง"
    fi
    
    # Check last log timestamp
    LAST_LOG_TIME=$(tail -1 "$WORKER_LOG" | grep -oE "^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}" || echo "")
    if [ -n "$LAST_LOG_TIME" ]; then
        print_status "  Last log time: $LAST_LOG_TIME"
        
        # Calculate time difference
        LAST_LOG_EPOCH=$(date -d "$LAST_LOG_TIME" '+%s' 2>/dev/null || echo "")
        NOW_EPOCH=$(date '+%s')
        
        if [ -n "$LAST_LOG_EPOCH" ]; then
            DIFF_SECONDS=$((NOW_EPOCH - LAST_LOG_EPOCH))
            DIFF_MINUTES=$((DIFF_SECONDS / 60))
            
            if [ "$DIFF_MINUTES" -gt 5 ]; then
                print_warning "  ⚠️ Last log was $DIFF_MINUTES minutes ago - worker อาจหยุดทำงาน!"
            else
                print_success "  Last log was $DIFF_MINUTES minutes ago"
            fi
        fi
    fi
    
else
    print_warning "ไม่พบ log file ทั้ง 2 ที่:"
    print_warning "  - logs/video-worker.log"
    print_warning "  - /tmp/video-worker.log"
    print_status "💡 Worker อาจไม่ได้ทำงาน หรือยังไม่ได้ start"
fi
echo ""

# Step 2: Check RabbitMQ activity
print_header "Step 2: ตรวจสอบ RabbitMQ Queue Activity"

python3 << PYTHON_EOF 2>/dev/null || print_error "ไม่สามารถเชื่อมต่อ RabbitMQ ได้"
import pika
import sys
from datetime import datetime

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
        
        print(f"📋 transcription_queue Status:")
        print(f"   Messages waiting: {message_count}")
        print(f"   Active consumers: {consumer_count}")
        print("")
        
        if message_count > 0 and consumer_count > 0:
            print("⚠️  มี messages รอ แต่ worker ไม่ได้ process!")
            print("")
            print("💡 สาเหตุที่เป็นไปได้:")
            print("   1. Worker กำลัง stuck ใน transcription process")
            print("   2. Worker ไม่ได้ consume messages จาก queue")
            print("   3. Connection หลุดแต่ process ยังทำงานอยู่")
            print("   4. Worker กำลังรอ GPU หรือ resources")
        
        if consumer_count == 0:
            print("❌ ไม่มี consumers - worker ไม่ได้เชื่อมต่อกับ queue!")
        
        if message_count == 0:
            print("✅ Queue ว่างเปล่า")
        
    except pika.exceptions.ChannelClosedByBroker as e:
        print(f"❌ Queue error: {e}")
    
    connection.close()
    sys.exit(0)
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)
PYTHON_EOF

echo ""

# Step 3: Check worker process state
print_header "Step 3: ตรวจสอบ Worker Process State"

# Check worker with multiple patterns (priority: app.workers.video_worker > python3.*video_worker > python.*video_worker)
WORKER_PID=""
for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker"; do
    WORKER_PID=$(pgrep -f "$pattern" | head -1)
    if [ -n "$WORKER_PID" ]; then
        break
    fi
done

if [ -n "$WORKER_PID" ]; then
    print_success "Worker PID: $WORKER_PID"
    
    # Check process state
    PS_OUTPUT=$(ps -p "$WORKER_PID" -o pid,state,etime,pcpu,pmem,command --no-headers 2>/dev/null || echo "")
    
    if [ -n "$PS_OUTPUT" ]; then
        STATE=$(echo "$PS_OUTPUT" | awk '{print $2}')
        ETIME=$(echo "$PS_OUTPUT" | awk '{print $3}')
        CPU=$(echo "$PS_OUTPUT" | awk '{print $4}')
        MEM=$(echo "$PS_OUTPUT" | awk '{print $5}')
        
        print_status "  State: $STATE"
        print_status "  Uptime: $ETIME"
        print_status "  CPU: ${CPU}%"
        print_status "  Memory: ${MEM}%"
        
        if [ "$STATE" = "D" ]; then
            print_warning "  ⚠️ Process อยู่ใน uninterruptible sleep (อาจ stuck)"
        elif [ "$STATE" = "T" ]; then
            print_warning "  ⚠️ Process ถูก stopped"
        elif [ "$STATE" = "Z" ]; then
            print_error "  ❌ Process เป็น zombie"
        fi
        
        # Check CPU usage
        if [ -n "$CPU" ]; then
            CPU_INT=$(echo "$CPU" | cut -d. -f1)
            if [ "$CPU_INT" -lt 1 ]; then
                print_warning "  ⚠️ CPU usage ต่ำมาก (${CPU}%) - อาจไม่ได้ทำงาน"
            fi
        fi
    fi
    
    # Check open files/sockets
    OPEN_FILES=$(lsof -p "$WORKER_PID" 2>/dev/null | wc -l || echo "0")
    print_status "  Open files/sockets: $OPEN_FILES"
    
else
    print_error "ไม่พบ Worker process"
fi
echo ""

# Step 4: Check for stuck processes
print_header "Step 4: ตรวจสอบ Stuck Processes"

# Check if there are multiple transcription processes running
TRANSCRIBE_PROCS=$(ps aux | grep -E "[p]ython.*transcribe|[f]aster.*whisper" | wc -l || echo "0")
print_status "Transcription-related processes: $TRANSCRIBE_PROCS"

# Check GPU usage
if command -v nvidia-smi > /dev/null 2>&1; then
    GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1 || echo "0")
    GPU_MEM=$(nvidia-smi --query-gpu=utilization.memory --format=csv,noheader,nounits 2>/dev/null | head -1 || echo "0")
    
    print_status "GPU Utilization: ${GPU_UTIL}%"
    print_status "GPU Memory: ${GPU_MEM}%"
    
    if [ "$GPU_UTIL" -lt 5 ] && [ -n "$WORKER_PID" ]; then
        print_warning "⚠️ GPU ไม่ได้ถูกใช้งาน - worker อาจไม่ได้ process transcription"
    fi
fi
echo ""

# Step 5: Recommendations
print_header "Step 5: คำแนะนำ"

if [ -n "$WORKER_PID" ] && [ "$CONSUMING_COUNT" -eq 0 ] && [ "$TRANSCRIBE_COUNT" -eq 0 ]; then
    print_warning "⚠️ Worker ทำงานอยู่แต่ไม่มีการ process messages"
    echo ""
    print_status "💡 แนะนำให้:"
    echo "   1. ตรวจสอบ logs อย่างละเอียด: tail -200 logs/video-worker.log"
    echo "      หรือใช้: bash scripts/pod/tail-worker-log.sh"
    echo "   2. Restart worker: bash scripts/pod/restart-pod.sh"
    echo "   3. ตรวจสอบ RabbitMQ connection ใน logs"
    echo "   4. ตรวจสอบว่ามี errors ที่ซ่อนอยู่"
elif [ "$CHANNEL_CLOSED" -gt 10 ]; then
    print_warning "⚠️ พบ 'Channel is closed' หลายครั้ง"
    echo ""
    print_status "💡 แนะนำให้:"
    echo "   1. Restart worker เพื่อ reconnect RabbitMQ"
    echo "   2. ตรวจสอบ RabbitMQ server stability"
elif [ -z "$WORKER_PID" ]; then
    print_error "❌ Worker ไม่ได้ทำงาน"
    echo ""
    print_status "💡 แนะนำให้:"
    echo "   bash scripts/pod/start-pod.sh"
fi

echo ""
print_header "✅ เสร็จสมบูรณ์"

