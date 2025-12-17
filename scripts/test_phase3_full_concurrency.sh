#!/bin/bash
# Phase 3: Full Concurrency Test
# ทดสอบ 25 tasks เพื่อตรวจสอบ full concurrency

set -e

API_URL="${API_URL:-http://localhost:8010}"
LOG_DIR="${LOG_DIR:-/workspace/transcription-service/logs}"
TEST_RESULTS_DIR="${TEST_RESULTS_DIR:-/workspace/transcription-service/test_results}"

mkdir -p "$TEST_RESULTS_DIR"
mkdir -p "$LOG_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Phase 3: Full Concurrency Test (25 Tasks)                  ║"
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

# Get initial queue status
echo "📊 Initial Queue Status:"
INITIAL_STATUS=$(curl -s "$API_URL/queue/status")
echo "$INITIAL_STATUS" | python3 -m json.tool | head -30
echo ""

# Test: 25 Tasks
echo "📋 Test 3.1: 25 Tasks Concurrent"
echo "─────────────────────────────────────────────────────────────"
START_TIME=$(date +%s)
RESULT_FILE="$TEST_RESULTS_DIR/phase3_test1_twenty_five_tasks.json"
RESULT=$(curl -s -X POST "$API_URL/queue/test-flow?count=25")
echo "$RESULT" > "$RESULT_FILE"
echo "$RESULT" | python3 -m json.tool
echo ""

# Extract task IDs
TASK_IDS=$(echo "$RESULT" | python3 -c "import sys, json; data=json.load(sys.stdin); print(' '.join(data.get('task_ids', [])))")
echo "📋 Task IDs: $TASK_IDS"
echo ""

# Monitor progress
echo "📊 Monitoring progress..."
SUCCESS_COUNT=0
FAILED_COUNT=0
TOTAL_COUNT=25

for i in {1..30}; do
    sleep 10
    
    # Check worker is still running
    if ! ps -p "$WORKER_PID" > /dev/null; then
        echo "❌ Worker crashed at check $i!"
        exit 1
    fi
    
    # Check queue status
    QUEUE_STATUS=$(curl -s "$API_URL/queue/status")
    REQUEST_QUEUE=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('queues', {}).get('request', {}).get('current', 0))")
    EXTRACTION_QUEUE=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('queues', {}).get('extraction', {}).get('current', 0))")
    TRANSCRIPTION_QUEUE=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('queues', {}).get('transcription', {}).get('current', 0))")
    
    TOTAL_IN_QUEUE=$((REQUEST_QUEUE + EXTRACTION_QUEUE + TRANSCRIPTION_QUEUE))
    PROCESSED=$((TOTAL_COUNT - TOTAL_IN_QUEUE))
    
    echo "  Check $i/30: Request=$REQUEST_QUEUE, Extraction=$EXTRACTION_QUEUE, Transcription=$TRANSCRIPTION_QUEUE, Processed=$PROCESSED/$TOTAL_COUNT"
    
    if [ "$TOTAL_IN_QUEUE" -eq 0 ] && [ "$PROCESSED" -ge "$TOTAL_COUNT" ]; then
        echo "✅ All tasks processed!"
        SUCCESS_COUNT=$PROCESSED
        break
    fi
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "📊 Final Queue Status:"
curl -s "$API_URL/queue/status" | python3 -m json.tool | head -30
echo ""

# Check worker logs for errors
echo "📋 Recent Worker Errors (last 50 lines):"
tail -50 "$LOG_DIR"/*.log 2>/dev/null | grep -E "error|Error|ERROR|exception|Exception|crash|Crash" | tail -20 || echo "No errors found"
echo ""

# Check memory usage
echo "📊 Worker Memory Usage:"
ps -p "$WORKER_PID" -o pid,rss,vsz,pcpu,comm 2>/dev/null || echo "Worker not found"
echo ""

# Summary
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Test Summary                                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo "Total Tasks: $TOTAL_COUNT"
echo "Processed: $SUCCESS_COUNT"
echo "Failed: $FAILED_COUNT"
echo "Duration: ${DURATION}s"
echo "Worker Status: $(ps -p "$WORKER_PID" > /dev/null && echo "✅ Running" || echo "❌ Crashed")"
echo ""

if [ "$SUCCESS_COUNT" -eq "$TOTAL_COUNT" ]; then
    echo "✅ Phase 3 PASSED: All 25 tasks processed successfully!"
else
    echo "❌ Phase 3 FAILED: Only $SUCCESS_COUNT/$TOTAL_COUNT tasks processed"
fi

echo "📊 Results saved to: $TEST_RESULTS_DIR/phase3_*.json"

