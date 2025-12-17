#!/bin/bash
# Phase 1: Connection Stability Test (ใช้ transcription endpoint จริง)
# ทดสอบ 1 task และ 5 tasks เพื่อตรวจสอบ connection stability

set -e

API_URL="${API_URL:-http://localhost:8010}"
LOG_DIR="${LOG_DIR:-/workspace/transcription-service/logs}"
TEST_RESULTS_DIR="${TEST_RESULTS_DIR:-/workspace/transcription-service/test_results}"

mkdir -p "$TEST_RESULTS_DIR"
mkdir -p "$LOG_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Phase 1: Connection Stability Test (Real Tasks)           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Test 1: Single Task
echo "📋 Test 1.1: Single Task"
echo "─────────────────────────────────────────────────────────────"
RESULT_FILE="$TEST_RESULTS_DIR/phase1_test1_single_task.json"
RESULT=$(curl -s -X POST "$API_URL/transcribe/" \
  -H "Content-Type: application/json" \
  -d '{"file_path":"/tmp/test.mp4","language":"th","model_size":"base"}')
echo "$RESULT" > "$RESULT_FILE"
TASK_ID=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))")
echo "Task ID: $TASK_ID"
echo "$RESULT" | python3 -m json.tool | head -15
echo ""

# Wait for processing
echo "⏳ Waiting 10 seconds for processing..."
sleep 10

# Check queue status
echo "📊 Queue Status:"
curl -s "$API_URL/queue/status" | python3 -m json.tool | head -30
echo ""

# Check task status
if [ -n "$TASK_ID" ]; then
    echo "📋 Task Status:"
    curl -s "$API_URL/transcribe/$TASK_ID" | python3 -m json.tool | head -15
    echo ""
fi

# Test 2: 5 Tasks
echo "📋 Test 1.2: 5 Tasks Concurrent"
echo "─────────────────────────────────────────────────────────────"
RESULT_FILE="$TEST_RESULTS_DIR/phase1_test2_five_tasks.json"
TASK_IDS=()

for i in {1..5}; do
    RESULT=$(curl -s -X POST "$API_URL/transcribe/" \
      -H "Content-Type: application/json" \
      -d "{\"file_path\":\"/tmp/test_${i}.mp4\",\"language\":\"th\",\"model_size\":\"base\"}")
    TASK_ID=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))")
    TASK_IDS+=("$TASK_ID")
    echo "  Task $i: $TASK_ID"
done

echo "{\"task_ids\": [$(IFS=,; echo "${TASK_IDS[*]}")]}" > "$RESULT_FILE"
echo "Total tasks: ${#TASK_IDS[@]}"
echo ""

# Wait for processing
echo "⏳ Waiting 30 seconds for processing..."
sleep 30

# Check queue status
echo "📊 Queue Status:"
curl -s "$API_URL/queue/status" | python3 -m json.tool | head -30
echo ""

# Check worker logs for errors
echo "📋 Recent Worker Errors (last 20 lines):"
tail -20 "$LOG_DIR"/*.log 2>/dev/null | grep -E "error|Error|ERROR|exception|Exception|crash|Crash" | tail -10 || echo "No errors found"
echo ""

echo "✅ Phase 1 Complete"
echo "📊 Results saved to: $TEST_RESULTS_DIR/phase1_*.json"

