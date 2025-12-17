#!/bin/bash
# Phase 2: Worker Stability Test
# ทดสอบ 10 tasks และ 15 tasks เพื่อตรวจสอบ worker stability

set -e

API_URL="${API_URL:-http://localhost:8010}"
LOG_DIR="${LOG_DIR:-/workspace/transcription-service/logs}"
TEST_RESULTS_DIR="${TEST_RESULTS_DIR:-/workspace/transcription-service/test_results}"

mkdir -p "$TEST_RESULTS_DIR"
mkdir -p "$LOG_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Phase 2: Worker Stability Test                            ║"
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

# Test 1: 10 Tasks
echo "📋 Test 2.1: 10 Tasks Concurrent"
echo "─────────────────────────────────────────────────────────────"
RESULT_FILE="$TEST_RESULTS_DIR/phase2_test1_ten_tasks.json"
curl -s -X POST "$API_URL/queue/test-flow?count=10" > "$RESULT_FILE"
cat "$RESULT_FILE" | python3 -m json.tool
echo ""

# Monitor worker
echo "📊 Monitoring worker (PID: $WORKER_PID)..."
for i in {1..6}; do
    sleep 10
    if ! ps -p "$WORKER_PID" > /dev/null; then
        echo "❌ Worker crashed!"
        exit 1
    fi
    echo "  ✅ Worker still running (check $i/6)"
done
echo ""

# Check queue status
echo "📊 Queue Status:"
curl -s "$API_URL/queue/status" | python3 -m json.tool | head -30
echo ""

# Test 2: 15 Tasks
echo "📋 Test 2.2: 15 Tasks Concurrent"
echo "─────────────────────────────────────────────────────────────"
RESULT_FILE="$TEST_RESULTS_DIR/phase2_test2_fifteen_tasks.json"
curl -s -X POST "$API_URL/queue/test-flow?count=15" > "$RESULT_FILE"
cat "$RESULT_FILE" | python3 -m json.tool
echo ""

# Monitor worker
echo "📊 Monitoring worker (PID: $WORKER_PID)..."
for i in {1..9}; do
    sleep 10
    if ! ps -p "$WORKER_PID" > /dev/null; then
        echo "❌ Worker crashed!"
        exit 1
    fi
    echo "  ✅ Worker still running (check $i/9)"
done
echo ""

# Check queue status
echo "📊 Queue Status:"
curl -s "$API_URL/queue/status" | python3 -m json.tool | head -30
echo ""

# Check worker logs for errors
echo "📋 Recent Worker Errors (last 30 lines):"
tail -30 "$LOG_DIR"/*.log 2>/dev/null | grep -E "error|Error|ERROR|exception|Exception|crash|Crash" | tail -15 || echo "No errors found"
echo ""

# Check memory usage
echo "📊 Worker Memory Usage:"
ps -p "$WORKER_PID" -o pid,rss,vsz,pcpu,comm 2>/dev/null || echo "Worker not found"
echo ""

echo "✅ Phase 2 Complete"
echo "📊 Results saved to: $TEST_RESULTS_DIR/phase2_*.json"

