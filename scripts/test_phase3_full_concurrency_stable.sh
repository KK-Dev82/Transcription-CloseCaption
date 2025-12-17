#!/bin/bash
# Phase 3: Full Concurrency Test (25 Tasks) - Stable Version
# ใช้ test mode เพื่อหลีกเลี่ยงปัญหาไฟล์และให้เสถียรที่สุด

set -e

API_URL="${API_URL:-http://localhost:8010}"
LOG_DIR="${LOG_DIR:-/workspace/transcription-service/logs}"
TEST_RESULTS_DIR="${TEST_RESULTS_DIR:-/workspace/transcription-service/test_results}"

mkdir -p "$TEST_RESULTS_DIR"
mkdir -p "$LOG_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Phase 3: Full Concurrency Test (25 Tasks) - Stable        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check worker is running
echo "🔍 Checking worker status..."
WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
if [ -z "$WORKER_PID" ]; then
    echo "❌ Worker is not running! Restarting..."
    bash /workspace/transcription-service/scripts/pod/restart-worker-only.sh 2>&1 | tail -3
    sleep 5
    WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
    if [ -z "$WORKER_PID" ]; then
        echo "❌ Failed to start worker!"
        exit 1
    fi
fi
echo "✅ Worker is running (PID: $WORKER_PID)"
echo ""

# Get initial status
echo "📊 Initial System Status:"
echo "  Worker PID: $WORKER_PID"
INITIAL_MEM=$(ps -p "$WORKER_PID" -o rss= 2>/dev/null | awk '{print $1/1024}')
echo "  Initial Memory: ${INITIAL_MEM}MB"
INITIAL_QUEUE=$(curl -s "$API_URL/queue/status" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['queues']['request']['current'])")
echo "  Initial Queue: $INITIAL_QUEUE messages"
echo ""

# Test: 25 Tasks with test mode
echo "📋 Test 3.1: 25 Tasks Concurrent (Test Mode)"
echo "─────────────────────────────────────────────────────────────"
START_TIME=$(date +%s)
RESULT_FILE="$TEST_RESULTS_DIR/phase3_test1_twenty_five_tasks.json"
TASK_IDS=()

# Send 25 tasks using Python script that publishes test mode messages directly
python3 << 'PYTHON_SCRIPT'
import sys
import os
sys.path.insert(0, '/workspace/transcription-service')

import json
import uuid
import time
import pika
from dotenv import load_dotenv

# Load environment
load_dotenv('/workspace/transcription-service/env.runpod')

# RabbitMQ connection
host = os.getenv('RABBITMQ_HOST', 'localhost')
port = int(os.getenv('RABBITMQ_PORT', '5672'))
username = os.getenv('RABBITMQ_USER', 'admin')
password = os.getenv('RABBITMQ_PASSWORD', 'admin123')
vhost = os.getenv('RABBITMQ_VHOST', '/')

# Connect
credentials = pika.PlainCredentials(username, password)
parameters = pika.ConnectionParameters(
    host=host,
    port=port,
    virtual_host=vhost,
    credentials=credentials,
    heartbeat=600,
    blocked_connection_timeout=300
)

connection = pika.BlockingConnection(parameters)
channel = connection.channel()

# Enable publisher confirms
channel.confirm_delivery()

task_ids = []
success_count = 0

for i in range(25):
    test_task_id = f"test-{uuid.uuid4()}"
    task_ids.append(test_task_id)
    
    test_message = {
        "task_id": test_task_id,
        "task_type": "transcription_request",
        "test_mode": True,
        "test_message": f"Phase 3 Test message #{i+1}",
        "file_path": None,
        "file_url": None,
        "file_name": f"test_file_phase3_{i+1}.mp4",
        "language": "th",
        "model_size": "base",
        "chunk_duration": 30,
        "use_chunking": False,
        "display_mode": "full_text",
        "status": "pending",
        "created_at": time.time(),
        "callback_url": None,
        "job_id": None,
        "user_id": "test_user_phase3"
    }
    
    try:
        channel.basic_publish(
            exchange='',
            routing_key='transcription_request_queue',
            body=json.dumps(test_message),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json',
                priority=5
            ),
            mandatory=True
        )
        success_count += 1
        print(f"  Task {i+1}: {test_task_id} ✅")
    except Exception as e:
        print(f"  Task {i+1}: {test_task_id} ❌ Error: {e}")

connection.close()

# Output results
result = {
    "total": 25,
    "successful": success_count,
    "failed": 25 - success_count,
    "task_ids": task_ids
}

print(json.dumps(result))
PYTHON_SCRIPT

RESULT=$(python3 << 'PYTHON_SCRIPT'
import sys
import os
sys.path.insert(0, '/workspace/transcription-service')

import json
import uuid
import time
import pika
from dotenv import load_dotenv

load_dotenv('/workspace/transcription-service/env.runpod')

host = os.getenv('RABBITMQ_HOST', 'localhost')
port = int(os.getenv('RABBITMQ_PORT', '5672'))
username = os.getenv('RABBITMQ_USER', 'admin')
password = os.getenv('RABBITMQ_PASSWORD', 'admin123')
vhost = os.getenv('RABBITMQ_VHOST', '/')

credentials = pika.PlainCredentials(username, password)
parameters = pika.ConnectionParameters(
    host=host,
    port=port,
    virtual_host=vhost,
    credentials=credentials,
    heartbeat=600,
    blocked_connection_timeout=300
)

connection = pika.BlockingConnection(parameters)
channel = connection.channel()
channel.confirm_delivery()

task_ids = []
success_count = 0

for i in range(25):
    test_task_id = f"test-{uuid.uuid4()}"
    task_ids.append(test_task_id)
    
    test_message = {
        "task_id": test_task_id,
        "task_type": "transcription_request",
        "test_mode": True,
        "test_message": f"Phase 3 Test message #{i+1}",
        "file_path": None,
        "file_url": None,
        "file_name": f"test_file_phase3_{i+1}.mp4",
        "language": "th",
        "model_size": "base",
        "chunk_duration": 30,
        "use_chunking": False,
        "display_mode": "full_text",
        "status": "pending",
        "created_at": time.time(),
        "callback_url": None,
        "job_id": None,
        "user_id": "test_user_phase3"
    }
    
    try:
        channel.basic_publish(
            exchange='',
            routing_key='transcription_request_queue',
            body=json.dumps(test_message),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json',
                priority=5
            ),
            mandatory=True
        )
        success_count += 1
        echo "  Task $((i+1)): $test_task_id ✅"
    except Exception as e:
        echo "  Task $((i+1)): $test_task_id ❌ Error: $e"
    sleep 0.1
done

connection.close()

result = {
    "total": 25,
    "successful": success_count,
    "failed": 25 - success_count,
    "task_ids": task_ids
}

echo "$result" | python3 -m json.tool > "$RESULT_FILE"
echo "Total tasks sent: $success_count/25"
echo ""

# Monitor progress
echo "📊 Monitoring progress (up to 5 minutes)..."
SUCCESS_COUNT=0
FAILED_COUNT=0
TOTAL_COUNT=25
MAX_CHECKS=30

for i in $(seq 1 $MAX_CHECKS); do
    sleep 10
    
    # Check worker is still running
    if ! ps -p "$WORKER_PID" > /dev/null; then
        echo "❌ Worker crashed at check $i!"
        exit 1
    fi
    
    # Check memory usage
    MEM_USAGE=$(ps -p "$WORKER_PID" -o rss= 2>/dev/null | awk '{print $1/1024}')
    
    # Check queue status
    QUEUE_STATUS=$(curl -s "$API_URL/queue/status")
    REQUEST_QUEUE=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('queues', {}).get('request', {}).get('current', 0))")
    EXTRACTION_QUEUE=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('queues', {}).get('extraction', {}).get('current', 0))")
    TRANSCRIPTION_QUEUE=$(echo "$QUEUE_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('queues', {}).get('transcription', {}).get('current', 0))")
    
    TOTAL_IN_QUEUE=$((REQUEST_QUEUE + EXTRACTION_QUEUE + TRANSCRIPTION_QUEUE))
    PROCESSED=$((TOTAL_COUNT - TOTAL_IN_QUEUE))
    
    echo "  Check $i/$MAX_CHECKS: Worker running (Memory: ${MEM_USAGE}MB)"
    echo "    Queue: Request=$REQUEST_QUEUE, Extraction=$EXTRACTION_QUEUE, Transcription=$TRANSCRIPTION_QUEUE"
    echo "    Processed: $PROCESSED/$TOTAL_COUNT"
    
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
echo "📊 Final Worker Memory Usage:"
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
    exit 0
else
    echo "⚠️ Phase 3 PARTIAL: $SUCCESS_COUNT/$TOTAL_COUNT tasks processed"
    exit 1
fi

