#!/bin/bash
# ตรวจสอบว่า Worker consume จาก transcription_request_queue หรือไม่

echo "=" | head -c 80 && echo
echo "🔍 ตรวจสอบ Worker Consumers"
echo "=" | head -c 80 && echo
echo

# 1. ตรวจสอบ Worker Process
echo "1️⃣ ตรวจสอบ Worker Process:"
echo "--------------------------------------------------------------------------------"
if pgrep -f "video_worker" > /dev/null; then
    echo "✅ Worker process กำลังรัน"
    pgrep -f "video_worker" | head -5 | while read pid; do
        echo "   PID: $pid"
        ps -p $pid -o cmd= | head -c 100
        echo
    done
else
    echo "❌ Worker process ไม่ได้รัน!"
    echo "   → ต้อง start worker ก่อน"
fi
echo

# 2. ตรวจสอบ Worker Logs
echo "2️⃣ ตรวจสอบ Worker Logs (ล่าสุด 20 บรรทัด):"
echo "--------------------------------------------------------------------------------"
LOG_FILES=(
    "/tmp/video-worker.log"
    "/workspace/transcription-service/logs/video-worker.log"
    "/var/log/video-worker.log"
)

FOUND_LOG=false
for log_file in "${LOG_FILES[@]}"; do
    if [ -f "$log_file" ]; then
        echo "📋 Log file: $log_file"
        echo "   Last 20 lines:"
        tail -20 "$log_file" | grep -E "(transcription_request|Consumer|Listening|consume)" || echo "   (ไม่พบ log ที่เกี่ยวข้อง)"
        FOUND_LOG=true
        echo
    fi
done

if [ "$FOUND_LOG" = false ]; then
    echo "⚠️  ไม่พบ log file"
    echo "   → ตรวจสอบว่า worker กำลังรันหรือไม่"
fi
echo

# 3. ตรวจสอบ RabbitMQ Connection
echo "3️⃣ ตรวจสอบ RabbitMQ Connection:"
echo "--------------------------------------------------------------------------------"
if command -v rabbitmqadmin &> /dev/null; then
    # Load env
    if [ -f "/workspace/transcription-service/env.runpod" ]; then
        source /workspace/transcription-service/env.runpod 2>/dev/null || true
    fi
    
    RABBITMQ_HOST="${RABBITMQ_HOST:-178.128.105.100}"
    RABBITMQ_USER="${RABBITMQ_USER:-senate}"
    RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}"
    
    echo "   Checking queue: transcription_request_queue"
    rabbitmqadmin -H "$RABBITMQ_HOST" -u "$RABBITMQ_USER" -p "$RABBITMQ_PASSWORD" \
        list queues name consumers messages_ready messages_unacknowledged arguments 2>/dev/null | \
        grep -E "(transcription_request|name|consumers)" || echo "   ❌ ไม่สามารถเชื่อมต่อ RabbitMQ ได้"
else
    echo "⚠️  rabbitmqadmin ไม่ได้ติดตั้ง"
fi
echo

# 4. ตรวจสอบ Environment Variables
echo "4️⃣ ตรวจสอบ Environment Variables:"
echo "--------------------------------------------------------------------------------"
if [ -f "/workspace/transcription-service/env.runpod" ]; then
    echo "   VIDEO_WORKER_TYPE: $(grep '^VIDEO_WORKER_TYPE=' /workspace/transcription-service/env.runpod | cut -d'=' -f2 || echo 'NOT SET')"
    echo "   USE_3QUEUE_ARCHITECTURE: $(grep '^USE_3QUEUE_ARCHITECTURE=' /workspace/transcription-service/env.runpod | cut -d'=' -f2 || echo 'NOT SET')"
    echo "   TRANSCRIPTION_REQUEST_PREFETCH_COUNT: $(grep '^TRANSCRIPTION_REQUEST_PREFETCH_COUNT=' /workspace/transcription-service/env.runpod | cut -d'=' -f2 || echo 'NOT SET')"
else
    echo "   ⚠️  env.runpod ไม่พบ"
fi
echo

# 5. Recommendations
echo "5️⃣ Recommendations:"
echo "--------------------------------------------------------------------------------"
echo "   ✅ ถ้า Worker ไม่ได้รัน:"
echo "      - Start worker: python3 -m app.workers.video_worker"
echo "      - หรือ restart service"
echo
echo "   ✅ ถ้า Worker รันแต่ไม่มี consumers:"
echo "      - ตรวจสอบ worker logs สำหรับ errors"
echo "      - ตรวจสอบว่า worker เชื่อมต่อ RabbitMQ สำเร็จหรือไม่"
echo "      - ตรวจสอบว่า VIDEO_WORKER_TYPE ถูกต้องหรือไม่ (async/sync)"
echo
echo "   ✅ ตรวจสอบ Queue Arguments:"
echo "      - ดู RabbitMQ Management UI"
echo "      - ตรวจสอบว่า queue มี x-max-length=51"
echo "      - ตรวจสอบว่า consumers > 0"
echo

