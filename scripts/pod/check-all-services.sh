#!/bin/bash
# Script สำหรับตรวจสอบ Services ทั้งหมด (MainAPI, Worker, Dashboard, FFmpeg, cuDNN, RabbitMQ)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
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

cd /workspace/transcription-service || exit 1

export PYTHONUSERBASE="/workspace/.local"
export PATH="/workspace/.local/bin:$PATH"
export PYTHONPATH="/workspace/.local/lib/python3.10/site-packages:$PYTHONPATH"

# ============================================
# Part 1: ตรวจสอบ Services
# ============================================
print_header "📋 Part 1: ตรวจสอบ Services"

# MainAPI
API_PID=$(pgrep -f "uvicorn.*app.main.*8010" | head -1)
if [ -n "$API_PID" ]; then
    print_success "MainAPI: RUNNING (PID: $API_PID)"
    API_HEALTH=$(curl -s http://localhost:8010/health 2>&1 | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('status', 'unknown'))" 2>/dev/null || echo "unknown")
    echo "   Health: $API_HEALTH"
else
    print_error "MainAPI: NOT RUNNING"
fi

# Video Worker
WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
if [ -n "$WORKER_PID" ]; then
    print_success "Video Worker: RUNNING (PID: $WORKER_PID)"
else
    print_error "Video Worker: NOT RUNNING"
fi

# Dashboard
DASHBOARD_PID=$(pgrep -f "uvicorn.*main:app.*8020" | head -1)
if [ -n "$DASHBOARD_PID" ]; then
    print_success "Dashboard: RUNNING (PID: $DASHBOARD_PID)"
    DASHBOARD_RESPONSE=$(curl -s http://localhost:8020/ 2>&1 | head -1)
    if echo "$DASHBOARD_RESPONSE" | grep -q "html\|Transcription"; then
        echo "   Status: OK"
    else
        print_warning "Dashboard may not be ready"
    fi
else
    print_error "Dashboard: NOT RUNNING"
fi

# ============================================
# Part 2: ตรวจสอบ FFmpeg
# ============================================
print_header "🔧 Part 2: ตรวจสอบ FFmpeg"

if command -v ffmpeg > /dev/null 2>&1; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')
    print_success "FFmpeg: ติดตั้งแล้ว (version $FFMPEG_VERSION)"
    
    # Test FFmpeg
    if timeout 5 ffmpeg -f lavfi -i testsrc=duration=1:size=320x240:rate=1 -t 1 -f null - 2>&1 | grep -q "video:"; then
        print_success "FFmpeg: ทดสอบสำเร็จ"
    else
        print_warning "FFmpeg: อาจมีปัญหา"
    fi
else
    print_error "FFmpeg: ไม่พบ - ต้องติดตั้ง"
fi

# ============================================
# Part 3: ตรวจสอบ cuDNN
# ============================================
print_header "🔬 Part 3: ตรวจสอบ cuDNN Compatibility"

python3 << 'EOF'
import sys
try:
    import torch
    print(f"✅ PyTorch: {torch.__version__}")
    print(f"✅ CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"✅ CUDA version: {torch.version.cuda}")
        if torch.backends.cudnn.is_available():
            print(f"✅ cuDNN version: {torch.backends.cudnn.version()}")
            print(f"✅ cuDNN enabled: {torch.backends.cudnn.enabled}")
        else:
            print("⚠️  cuDNN not available in PyTorch")
    
    import ctranslate2
    print(f"✅ CTranslate2: {ctranslate2.__version__}")
    print(f"✅ CUDA devices: {ctranslate2.get_cuda_device_count()}")
except Exception as e:
    print(f"❌ Error: {e}")
EOF

# ============================================
# Part 4: ตรวจสอบ RabbitMQ Queues
# ============================================
print_header "📋 Part 4: ตรวจสอบ RabbitMQ Queues"

python3 << 'EOF'
import sys
sys.path.insert(0, '.')
try:
    import aio_pika
    import asyncio
    import json
    from datetime import datetime, timezone
    
    async def check_queues():
        RABBITMQ_HOST = "178.128.105.100"
        RABBITMQ_PORT = 5672
        RABBITMQ_USER = "senate"
        RABBITMQ_PASSWORD = "qP2VtHz6fAX4xDksEpMrLT"
        
        try:
            connection = await aio_pika.connect_robust(
                f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/",
                timeout=5
            )
            channel = await connection.channel()
            
            queues_to_check = [
                'audio_extraction_queue',
                'audio_extraction_queue.dlq',
                'transcription_queue',
                'transcription_request_queue'
            ]
            
            print("Queue Status:")
            for queue_name in queues_to_check:
                try:
                    queue = await channel.declare_queue(queue_name, passive=True)
                    message_count = queue.declaration_result.message_count
                    consumer_count = queue.declaration_result.consumer_count
                    
                    print(f"\n  {queue_name}:")
                    print(f"    Messages: {message_count}")
                    print(f"    Consumers: {consumer_count}")
                    
                    # Check message age if any
                    if message_count > 0:
                        try:
                            message = await queue.get(no_ack=False)
                            if message:
                                body = message.body.decode('utf-8')
                                data = json.loads(body)
                                task_id = data.get('task_id', 'N/A')
                                created_at = data.get('created_at', 'N/A')
                                
                                # Determine if old or new
                                if created_at and created_at != 'N/A':
                                    try:
                                        from dateutil import parser
                                        created_dt = parser.parse(created_at)
                                        now = datetime.now(timezone.utc) if created_dt.tzinfo else datetime.now()
                                        age_minutes = (now - created_dt.replace(tzinfo=None)).total_seconds() / 60
                                        if age_minutes > 30:
                                            print(f"    ⚠️  Message age: {age_minutes:.1f} minutes (OLD)")
                                        else:
                                            print(f"    ✅ Message age: {age_minutes:.1f} minutes (NEW)")
                                    except:
                                        pass
                                
                                print(f"    Task ID: {task_id}")
                                await message.nack(requeue=True)
                        except Exception as e:
                            print(f"    Could not peek: {e}")
                except Exception as e:
                    print(f"\n  {queue_name}: Error - {e}")
            
            await connection.close()
        except Exception as e:
            print(f"❌ Connection error: {e}")
    
    asyncio.run(check_queues())
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
EOF

# ============================================
# Part 5: ตรวจสอบ Tracking Mechanism
# ============================================
print_header "📊 Part 5: ตรวจสอบ Tracking Mechanism"

echo "Webhook vs Polling:"
echo ""
echo "1. Webhook Service:"
echo "   - Primary method: Webhook callbacks"
echo "   - Fallback: Polling (10s interval)"
echo "   - Location: dashboard/static/js/webhook-service.js"
echo ""
echo "2. Monitoring Tab:"
echo "   - Uses: Polling (setInterval)"
echo "   - Interval: Configurable"
echo "   - Location: dashboard/static/js/monitoring-tab.js"
echo ""
echo "3. Overview Tab:"
echo "   - Uses: Polling (auto-refresh)"
echo "   - Location: dashboard/static/js/overview-tab.js"
echo ""
print_warning "ปัจจุบันใช้ Polling มากกว่า Webhook เพราะ:"
echo "   - Webhook ต้องมี callback_url ใน task"
echo "   - Polling เป็น fallback เมื่อ webhook ไม่ทำงาน"

# ============================================
# Summary
# ============================================
print_header "📋 Summary"

echo "Services:"
[ -n "$API_PID" ] && echo -e "   ${GREEN}✅ MainAPI${NC}" || echo -e "   ${RED}❌ MainAPI${NC}"
[ -n "$WORKER_PID" ] && echo -e "   ${GREEN}✅ Video Worker${NC}" || echo -e "   ${RED}❌ Video Worker${NC}"
[ -n "$DASHBOARD_PID" ] && echo -e "   ${GREEN}✅ Dashboard${NC}" || echo -e "   ${RED}❌ Dashboard${NC}"

echo ""
echo "Dependencies:"
command -v ffmpeg > /dev/null 2>&1 && echo -e "   ${GREEN}✅ FFmpeg${NC}" || echo -e "   ${RED}❌ FFmpeg${NC}"
python3 -c "import torch; print('✅ cuDNN' if torch.backends.cudnn.is_available() else '⚠️  cuDNN')" 2>/dev/null || echo -e "   ${YELLOW}⚠️  cuDNN${NC}"

echo ""
echo "💡 Useful Commands:"
echo "   Restart all: bash scripts/pod/restart-pod.sh"
echo "   Check logs:  bash scripts/pod/tail-all-logs.sh"
echo "   Check queue: curl http://localhost:8010/queue/health"
echo ""

