#!/bin/bash
# Script สำหรับตรวจสอบ Logs และวินิจฉัยปัญหา
#
# วิธีใช้งาน:
#   bash scripts/pod/check-logs-diagnosis.sh

set -e

PROJECT_DIR="/workspace/transcription-service"
cd "$PROJECT_DIR" 2>/dev/null || cd "/workspace/transcription-close-caption-service" 2>/dev/null || {
    echo "❌ Error: Cannot find project directory"
    exit 1
}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔍 ตรวจสอบ Logs และวินิจฉัยปัญหา                              ║"
echo "║  เวลา: $(date '+%Y-%m-%d %H:%M:%S')                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

SERVICE_LOG="/tmp/transcription-service.log"
WORKER_LOG="/tmp/video-worker.log"

# 1. ตรวจสอบ Service Status
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 1. Service Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if pgrep -f "python.*uvicorn.*app.main.*8010" > /dev/null; then
    SERVICE_PID=$(pgrep -f "python.*uvicorn.*app.main.*8010" | head -1)
    echo "✅ API Service: RUNNING (PID: $SERVICE_PID)"
else
    echo "❌ API Service: NOT RUNNING"
fi

if pgrep -f "python.*video_worker" > /dev/null; then
    WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
    echo "✅ Video Worker: RUNNING (PID: $WORKER_PID)"
else
    echo "❌ Video Worker: NOT RUNNING"
fi
echo ""

# 2. ตรวจสอบ Queue Status
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 2. Queue Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
QUEUE_STATS=$(curl -s http://localhost:8010/queue/stats 2>/dev/null || echo "{}")

REQ_MSG=$(echo "$QUEUE_STATS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('stats', {}).get('queue_details', {}).get('transcription_request_queue', {}).get('message_count', 0))" 2>/dev/null || echo "0")
REQ_CONSUMER=$(echo "$QUEUE_STATS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('stats', {}).get('queue_details', {}).get('transcription_request_queue', {}).get('consumer_count', 0))" 2>/dev/null || echo "0")

EXT_MSG=$(echo "$QUEUE_STATS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('stats', {}).get('queue_details', {}).get('audio_extraction_queue', {}).get('message_count', 0))" 2>/dev/null || echo "0")
EXT_CONSUMER=$(echo "$QUEUE_STATS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('stats', {}).get('queue_details', {}).get('audio_extraction_queue', {}).get('consumer_count', 0))" 2>/dev/null || echo "0")

TRANS_MSG=$(echo "$QUEUE_STATS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('stats', {}).get('queue_details', {}).get('transcription_queue', {}).get('message_count', 0))" 2>/dev/null || echo "0")
TRANS_CONSUMER=$(echo "$QUEUE_STATS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('stats', {}).get('queue_details', {}).get('transcription_queue', {}).get('consumer_count', 0))" 2>/dev/null || echo "0")

echo "transcription_request_queue: $REQ_MSG messages, $REQ_CONSUMER consumers"
if [ "$REQ_MSG" -gt "0" ] && [ "$REQ_CONSUMER" -eq "0" ]; then
    echo "   ⚠️  มี messages รอแต่ไม่มี consumers!"
fi

echo "audio_extraction_queue: $EXT_MSG messages, $EXT_CONSUMER consumers"
echo "transcription_queue: $TRANS_MSG messages, $TRANS_CONSUMER consumers"
echo ""

# 3. ตรวจสอบ Worker Consumer Setup
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 3. Worker Consumer Queues"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "$WORKER_LOG" ]; then
    echo "Queues ที่ Worker Consumer:"
    grep "Listening to queues:" -A 10 "$WORKER_LOG" 2>/dev/null | grep "   -" | head -10 || echo "   (ไม่พบ)"
    echo ""
    
    if ! grep -q "transcription_request_queue" "$WORKER_LOG" 2>/dev/null; then
        echo "❌ Worker ไม่ได้ consumer จาก transcription_request_queue"
    else
        echo "✅ Worker consumer จาก transcription_request_queue"
    fi
    
    if ! grep -q "audio_extraction_queue" "$WORKER_LOG" 2>/dev/null; then
        echo "❌ Worker ไม่ได้ consumer จาก audio_extraction_queue"
    else
        echo "✅ Worker consumer จาก audio_extraction_queue"
    fi
else
    echo "⚠️  Worker log ไม่พบ"
fi
echo ""

# 4. ตรวจสอบ Errors
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 4. Errors (last 10)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "$SERVICE_LOG" ]; then
    echo "API Service Errors:"
    tail -200 "$SERVICE_LOG" | grep -i "error\|exception\|failed\|traceback" | tail -5 || echo "   (ไม่มี errors)"
fi
echo ""

if [ -f "$WORKER_LOG" ]; then
    echo "Worker Errors:"
    tail -200 "$WORKER_LOG" | grep -i "error\|exception\|failed\|traceback" | tail -5 || echo "   (ไม่มี errors)"
fi
echo ""

# 5. สรุปปัญหา
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 5. สรุปปัญหา"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$REQ_MSG" -gt "0" ] && [ "$REQ_CONSUMER" -eq "0" ]; then
    echo "❌ ปัญหาหลัก:"
    echo "   Worker ไม่ได้ consumer จาก transcription_request_queue"
    echo "   มี $REQ_MSG messages รอแต่ไม่มี consumers"
    echo ""
    echo "💡 วิธีแก้ไข:"
    echo "   1. เพิ่ม consumer สำหรับ transcription_request_queue ใน video_worker.py"
    echo "   2. เพิ่ม handler function สำหรับ process request messages"
    echo "   3. Restart Video Worker"
fi

if [ "$EXT_MSG" -gt "0" ] && [ "$EXT_CONSUMER" -eq "0" ]; then
    echo "❌ ปัญหารอง:"
    echo "   Worker ไม่ได้ consumer จาก audio_extraction_queue"
    echo "   มี $EXT_MSG messages รอแต่ไม่มี consumers"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ การตรวจสอบเสร็จสิ้น                                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"

