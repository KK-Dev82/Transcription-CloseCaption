#!/bin/bash
# วางแผนการทดสอบและตรวจสอบระบบ Transcription

set -e

API_URL="${API_URL:-http://localhost:8010}"
VIDEO_FILE="${VIDEO_FILE:-/workspace/transcription-service/uploads/960629c3-86fa-4c2f-92d5-59c8b5e89ded_v10-1.mp4}"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  📋 วางแผนการทดสอบและตรวจสอบระบบ Transcription              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: ตรวจสอบสถานะ Worker
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Step 1: ตรวจสอบสถานะ Worker"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check worker process
WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
if [ -n "$WORKER_PID" ]; then
    echo "✅ Worker process: Running (PID: $WORKER_PID)"
    ps -p $WORKER_PID -o pid,cmd,etime,stat --no-headers
else
    echo "❌ Worker process: NOT FOUND (ตายแล้ว)"
    echo "   💡 ควร restart worker"
fi

echo ""

# Check worker health endpoint
if curl -s -f "http://localhost:8030/health" > /dev/null 2>&1; then
    echo "✅ Worker health endpoint: OK"
    curl -s "http://localhost:8030/health" | python3 -m json.tool 2>/dev/null || echo "   Response: $(curl -s http://localhost:8030/health)"
else
    echo "❌ Worker health endpoint: ไม่ตอบสนอง"
fi

echo ""

# Check API health
if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
    echo "✅ API server: OK"
else
    echo "❌ API server: ไม่ตอบสนอง"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Step 2: ตรวจสอบ Logs และ Errors"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "logs/video-worker.log" ]; then
    echo "📋 Recent errors in worker logs:"
    tail -100 logs/video-worker.log | grep -E "ERROR|Exception|Traceback|Failed|died|killed" | tail -10 || echo "   ✅ No recent errors"
else
    echo "⚠️  Worker log file not found"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Step 3: ทดสอบระบบ Transcription"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ ! -f "$VIDEO_FILE" ]; then
    echo "⚠️  Video file not found: $VIDEO_FILE"
    echo "   💡 ใช้ไฟล์อื่นหรืออัปโหลดไฟล์ใหม่"
    exit 1
fi

echo "📝 Sending transcription request..."
echo "   Video: $VIDEO_FILE"
echo "   API: $API_URL/transcribe/"
echo ""

RESPONSE=$(curl -s -X POST "$API_URL/transcribe/" \
    -H "Content-Type: application/json" \
    -d "{
        \"file_path\": \"$VIDEO_FILE\",
        \"file_name\": \"test.mp4\",
        \"language\": \"th\",
        \"model_size\": \"base\",
        \"chunk_duration\": 30,
        \"use_chunking\": true,
        \"display_mode\": \"full_text\"
    }" 2>/dev/null || echo "")

if [ -z "$RESPONSE" ]; then
    echo "❌ Failed to send request"
    exit 1
fi

TASK_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))" 2>/dev/null || echo "")

if [ -z "$TASK_ID" ]; then
    echo "❌ Failed to get task_id"
    echo "Response: $RESPONSE"
    exit 1
fi

echo "✅ Task created: $TASK_ID"
echo ""

# Monitor task
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Step 4: Monitor Task Progress"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

MAX_WAIT=300
WAIT_INTERVAL=5
ELAPSED=0
START_TIME=$(date +%s)

while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS_RESPONSE=$(curl -s "$API_URL/transcribe/$TASK_ID" 2>/dev/null || echo "")
    
    if [ -n "$STATUS_RESPONSE" ]; then
        STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
        PROGRESS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('progress', 0))" 2>/dev/null || echo "0")
        COMPLETED=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('completed_chunks', 0) or 0)" 2>/dev/null || echo "0")
        TOTAL=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total_chunks', 0) or 0)" 2>/dev/null || echo "0")
        
        CURRENT_TIME=$(date +%s)
        ELAPSED=$((CURRENT_TIME - START_TIME))
        
        echo "[${ELAPSED}s] Status: $STATUS, Progress: $PROGRESS%, Chunks: $COMPLETED/$TOTAL"
        
        if [ "$STATUS" = "completed" ]; then
            echo ""
            echo "✅ Task completed!"
            TEXT=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('text', ''))" 2>/dev/null || echo "")
            echo "   Text length: ${#TEXT} characters"
            if [ ${#TEXT} -gt 0 ]; then
                echo "   Text preview: ${TEXT:0:100}..."
            fi
            break
        elif [ "$STATUS" = "failed" ]; then
            echo ""
            echo "❌ Task failed!"
            ERROR=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error_message', 'Unknown error'))" 2>/dev/null || echo "Unknown error")
            echo "   Error: $ERROR"
            break
        fi
    else
        echo "[${ELAPSED}s] ⚠️  Could not get task status"
    fi
    
    sleep $WAIT_INTERVAL
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo ""
    echo "⚠️  Timeout after ${MAX_WAIT}s"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Step 5: ตรวจสอบ Logs หลังทดสอบ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "logs/video-worker.log" ]; then
    echo "📋 Recent logs related to task $TASK_ID:"
    tail -200 logs/video-worker.log | grep -E "$TASK_ID|collect_segments_async|LOOP_ITERATION|ERROR|Exception" | tail -20 || echo "   No relevant logs found"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ การทดสอบเสร็จสิ้น                                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"

