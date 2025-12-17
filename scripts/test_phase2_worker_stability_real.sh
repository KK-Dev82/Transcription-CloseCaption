#!/bin/bash
# Phase 2: Worker Stability Test (ใช้ transcription endpoint จริง)
# ทดสอบ 10 tasks และ 15 tasks เพื่อตรวจสอบ worker stability

set -e

API_URL="${API_URL:-http://localhost:8010}"
LOG_DIR="${LOG_DIR:-/workspace/transcription-service/logs}"
TEST_RESULTS_DIR="${TEST_RESULTS_DIR:-/workspace/transcription-service/test_results}"

mkdir -p "$TEST_RESULTS_DIR"
mkdir -p "$LOG_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Phase 2: Worker Stability Test (Real Tasks)                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check worker is running
echo "🔍 Checking worker status..."
WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
if [ -z "$WORKER_PID" ]; then
    echo "❌ Worker is not running!"
    exit 1
fi
echo "✅ Worker is running (PID: $WORKER_PID)"
echo ""

# Get initial memory usage
echo "📊 Initial Worker Memory Usage:"
ps -p "$WORKER_PID" -o pid,rss,vsz,pcpu,comm 2>/dev/null || echo "Worker not found"
echo ""

# Test 1: 10 Tasks
echo "📋 Test 2.1: 10 Tasks Concurrent"
echo "─────────────────────────────────────────────────────────────"
RESULT_FILE="$TEST_RESULTS_DIR/phase2_test1_ten_tasks.json"
TASK_IDS=()
START_TIME=$(date +%s)

for i in {1..10}; do
    RESULT=$(curl -s -X POST "$API_URL/transcribe/" \
      -H "Content-Type: application/json" \
      -d "{\"file_path\":\"/tmp/test_phase2_${i}.mp4\",\"language\":\"th\",\"model_size\":\"base\"}")
    TASK_ID=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))")
    TASK_IDS+=("$TASK_ID")
    echo "  Task $i: $TASK_ID"
    sleep 0.2  # Small delay to avoid overwhelming
done

echo "{\"task_ids\": [$(IFS=,; echo "\"${TASK_IDS[*]}\"")]}" > "$RESULT_FILE"
echo "Total tasks sent: ${#TASK_IDS[@]}"
echo ""

# Monitor worker
echo "📊 Monitoring worker (PID: $WORKER_PID)..."
for i in {1..12}; do
    sleep 10
    
    # Check worker is still running
    if ! ps -p "$WORKER_PID" > /dev/null; then
        echo "❌ Worker crashed at check $i!"
        exit 1
    fi
    
    # Check memory usage
    MEM_USAGE=$(ps -p "$WORKER_PID" -o rss= 2>/dev/null | awk '{print $1/1024}')
    echo "  Check $i/12: Worker running, Memory: ${MEM_USAGE}MB"
    
    # Check queue status
    QUEUE_STATUS=$(curl -s "$API_URL/queue/status")
    REQUEST_QUEUE=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('queues', {}).get('request', {}).get('current', 0))")
    EXTRACTION_QUEUE=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('queues', {}).get('extraction', {}).get('current', 0))")
    TRANSCRIPTION_QUEUE=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('queues', {}).get('transcription', {}).get('current', 0))")
    
    TOTAL_IN_QUEUE=$((REQUEST_QUEUE + EXTRACTION_QUEUE + TRANSCRIPTION_QUEUE))
    PROCESSED=$((10 - TOTAL_IN_QUEUE))
    
    echo "    Queue: Request=$REQUEST_QUEUE, Extraction=$EXTRACTION_QUEUE, Transcription=$TRANSCRIPTION_QUEUE, Processed=$PROCESSED/10"
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "📊 Final Queue Status (10 tasks):"
curl -s "$API_URL/queue/status" | python3 -m json.tool | head -30
echo ""

# Check memory usage
echo "📊 Worker Memory Usage After 10 Tasks:"
ps -p "$WORKER_PID" -o pid,rss,vsz,pcpu,comm 2>/dev/null || echo "Worker not found"
echo ""

# Test 2: 15 Tasks
echo "📋 Test 2.2: 15 Tasks Concurrent"
echo "─────────────────────────────────────────────────────────────"
RESULT_FILE="$TEST_RESULTS_DIR/phase2_test2_fifteen_tasks.json"
TASK_IDS=()
START_TIME=$(date +%s)

for i in {1..15}; do
    RESULT=$(curl -s -X POST "$API_URL/transcribe/" \
      -H "Content-Type: application/json" \
      -d "{\"file_path\":\"/tmp/test_phase2_15_${i}.mp4\",\"language\":\"th\",\"model_size\":\"base\"}")
    TASK_ID=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))")
    TASK_IDS+=("$TASK_ID")
    echo "  Task $i: $TASK_ID"
    sleep 0.2  # Small delay to avoid overwhelming
done

echo "{\"task_ids\": [$(IFS=,; echo "\"${TASK_IDS[*]}\"")]}" > "$RESULT_FILE"
echo "Total tasks sent: ${#TASK_IDS[@]}"
echo ""

# Monitor worker
echo "📊 Monitoring worker (PID: $WORKER_PID)..."
for i in {1..18}; do
    sleep 10
    
    # Check worker is still running
    if ! ps -p "$WORKER_PID" > /dev/null; then
        echo "❌ Worker crashed at check $i!"
        exit 1
    fi
    
    # Check memory usage
    MEM_USAGE=$(ps -p "$WORKER_PID" -o rss= 2>/dev/null | awk '{print $1/1024}')
    echo "  Check $i/18: Worker running, Memory: ${MEM_USAGE}MB"
    
    # Check queue status
    QUEUE_STATUS=$(curl -s "$API_URL/queue/status")
    REQUEST_QUEUE=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('queues', {}).get('request', {}).get('current', 0))")
    EXTRACTION_QUEUE=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('queues', {}).get('extraction', {}).get('current', 0))")
    TRANSCRIPTION_QUEUE=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('queues', {}).get('transcription', {}).get('current', 0))")
    
    TOTAL_IN_QUEUE=$((REQUEST_QUEUE + EXTRACTION_QUEUE + TRANSCRIPTION_QUEUE))
    PROCESSED=$((15 - TOTAL_IN_QUEUE))
    
    echo "    Queue: Request=$REQUEST_QUEUE, Extraction=$EXTRACTION_QUEUE, Transcription=$TRANSCRIPTION_QUEUE, Processed=$PROCESSED/15"
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "📊 Final Queue Status (15 tasks):"
curl -s "$API_URL/queue/status" | python3 -m json.tool | head -30
echo ""

# Check memory usage
echo "📊 Worker Memory Usage After 15 Tasks:"
ps -p "$WORKER_PID" -o pid,rss,vsz,pcpu,comm 2>/dev/null || echo "Worker not found"
echo ""

# Check worker logs for errors
echo "📋 Recent Worker Errors (last 30 lines):"
tail -30 "$LOG_DIR"/*.log 2>/dev/null | grep -E "error|Error|ERROR|exception|Exception|crash|Crash" | tail -15 || echo "No errors found"
echo ""

echo "✅ Phase 2 Complete"
echo "📊 Results saved to: $TEST_RESULTS_DIR/phase2_*.json"
echo "⏱️  Total duration: ${DURATION}s"

