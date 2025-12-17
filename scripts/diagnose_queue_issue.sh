#!/bin/bash
# สคริปต์ตรวจสอบปัญหาที่ queue รับได้แค่ 5 messages

echo "=" | head -c 80 && echo
echo "🔍 ตรวจสอบปัญหา Queue รับได้แค่ 5 Messages"
echo "=" | head -c 80 && echo
echo

# Load environment
if [ -f "env.runpod" ]; then
    source env.runpod 2>/dev/null || true
elif [ -f ".env.runpod" ]; then
    source .env.runpod 2>/dev/null || true
fi

RABBITMQ_HOST="${RABBITMQ_HOST:-178.128.105.100}"
RABBITMQ_USER="${RABBITMQ_USER:-senate}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}"
RABBITMQ_MGMT_PORT="${RABBITMQ_MGMT_PORT:-15672}"

# 1. ตรวจสอบ Queue Status
echo "1️⃣ ตรวจสอบ Queue Status:"
echo "--------------------------------------------------------------------------------"
QUEUE_INFO=$(curl -s -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
    "http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues/%2F/transcription_request_queue" 2>/dev/null)

if [ -z "$QUEUE_INFO" ] || echo "$QUEUE_INFO" | grep -q "Not Found\|404" 2>/dev/null; then
    echo "❌ Queue 'transcription_request_queue' not found"
else
    MESSAGES_READY=$(echo "$QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages_ready', 0))" 2>/dev/null || echo "0")
    MESSAGES_UNACKED=$(echo "$QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('messages_unacknowledged', 0))" 2>/dev/null || echo "0")
    CONSUMERS=$(echo "$QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('consumers', 0))" 2>/dev/null || echo "0")
    MAX_LENGTH=$(echo "$QUEUE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); args=d.get('arguments', {}); print(args.get('x-max-length', 'unlimited'))" 2>/dev/null || echo "unknown")
    
    echo "   Messages Ready: $MESSAGES_READY"
    echo "   Messages Unacked: $MESSAGES_UNACKED"
    echo "   Total Messages: $((MESSAGES_READY + MESSAGES_UNACKED))"
    echo "   Consumers: $CONSUMERS"
    echo "   Max Length: $MAX_LENGTH"
    
    if [ "$CONSUMERS" -eq 0 ]; then
        echo "   ⚠️  PROBLEM: No consumers connected!"
    fi
    
    if [ "$MAX_LENGTH" != "51" ] && [ "$MAX_LENGTH" != "unlimited" ]; then
        echo "   ⚠️  PROBLEM: Max length is $MAX_LENGTH (should be 51)"
    fi
fi
echo

# 2. ตรวจสอบ Worker Status
echo "2️⃣ ตรวจสอบ Worker Status:"
echo "--------------------------------------------------------------------------------"
if pgrep -f "python.*video_worker" > /dev/null; then
    WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
    echo "✅ Worker is running (PID: $WORKER_PID)"
    
    # Check worker logs for consumer registration
    if [ -f "logs/video-worker.log" ]; then
        if grep -q "transcription_request_queue" logs/video-worker.log 2>/dev/null; then
            echo "✅ Worker has registered consumer for transcription_request_queue"
        else
            echo "⚠️  Worker may not have registered consumer (check logs)"
        fi
        
        # Check for errors
        ERROR_COUNT=$(grep -i "error\|exception\|failed" logs/video-worker.log 2>/dev/null | tail -5 | wc -l)
        if [ "$ERROR_COUNT" -gt 0 ]; then
            echo "⚠️  Found errors in worker logs (last 5):"
            grep -i "error\|exception\|failed" logs/video-worker.log 2>/dev/null | tail -5 | sed 's/^/   /'
        fi
    fi
else
    echo "❌ Worker is NOT running!"
    echo "   → Run: bash scripts/pod/restart-worker-only.sh"
fi
echo

# 3. ตรวจสอบ API Logs
echo "3️⃣ ตรวจสอบ API Logs (publish errors):"
echo "--------------------------------------------------------------------------------"
if [ -f "/tmp/transcription-service.log" ]; then
    PUBLISH_ERRORS=$(grep -i "queue.*full\|reject.*publish\|ChannelClosedByBroker\|publish.*error" /tmp/transcription-service.log 2>/dev/null | tail -10 | wc -l)
    if [ "$PUBLISH_ERRORS" -gt 0 ]; then
        echo "⚠️  Found publish errors in API logs (last 10):"
        grep -i "queue.*full\|reject.*publish\|ChannelClosedByBroker\|publish.*error" /tmp/transcription-service.log 2>/dev/null | tail -10 | sed 's/^/   /'
    else
        echo "✅ No publish errors found in recent logs"
    fi
else
    echo "⚠️  API log file not found: /tmp/transcription-service.log"
fi
echo

# 4. ตรวจสอบ Environment Variables
echo "4️⃣ ตรวจสอบ Environment Variables:"
echo "--------------------------------------------------------------------------------"
echo "   MAX_QUEUE_REQUEST: ${MAX_QUEUE_REQUEST:-NOT SET}"
echo "   ADMISSION_CONTROL_MODE: ${ADMISSION_CONTROL_MODE:-NOT SET}"
echo "   VIDEO_WORKER_TYPE: ${VIDEO_WORKER_TYPE:-NOT SET}"
echo "   TRANSCRIPTION_REQUEST_PREFETCH_COUNT: ${TRANSCRIPTION_REQUEST_PREFETCH_COUNT:-NOT SET}"
echo

# 5. สรุปปัญหาและวิธีแก้
echo "5️⃣ สรุปปัญหาและวิธีแก้:"
echo "--------------------------------------------------------------------------------"
if [ "$CONSUMERS" -eq 0 ]; then
    echo "❌ PROBLEM: No consumers connected to queue"
    echo "   → Worker ไม่ได้ consume จาก transcription_request_queue"
    echo "   → Messages ค้างใน queue เพราะไม่มี consumer"
    echo ""
    echo "   💡 Solution:"
    echo "      1. Restart worker: bash scripts/pod/restart-worker-only.sh"
    echo "      2. ตรวจสอบ worker logs: tail -f logs/video-worker.log"
    echo "      3. ตรวจสอบว่า worker เชื่อมต่อ RabbitMQ สำเร็จหรือไม่"
fi

if [ "$MESSAGES_READY" -gt 0 ] && [ "$CONSUMERS" -eq 0 ]; then
    echo ""
    echo "⚠️  Messages are stuck in queue (no consumers)"
    echo "   → Messages Ready: $MESSAGES_READY"
    echo "   → Consumers: $CONSUMERS"
    echo ""
    echo "   💡 Solution:"
    echo "      1. Restart worker เพื่อให้ consume messages"
    echo "      2. หรือ purge queue ถ้า messages เก่า:"
    echo "         curl -X DELETE -u ${RABBITMQ_USER}:${RABBITMQ_PASSWORD} \\"
    echo "              http://${RABBITMQ_HOST}:${RABBITMQ_MGMT_PORT}/api/queues/%2F/transcription_request_queue/contents"
fi

if [ "$MAX_LENGTH" != "51" ] && [ "$MAX_LENGTH" != "unlimited" ]; then
    echo ""
    echo "⚠️  Queue max-length is incorrect"
    echo "   → Current: $MAX_LENGTH"
    echo "   → Expected: 51"
    echo ""
    echo "   💡 Solution:"
    echo "      1. Delete old queue"
    echo "      2. Restart service to recreate queue with correct max-length"
fi
echo

