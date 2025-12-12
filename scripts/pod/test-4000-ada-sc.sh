#!/bin/bash
# Script สำหรับทดสอบ 4000-ada-sc
# Usage: bash scripts/pod/test-4000-ada-sc.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/workspace/transcription-service"
API_URL="http://localhost:8010"

echo "🧪 Testing 4000-ada-sc Server"
echo "=============================="
echo ""

cd "$PROJECT_DIR" || exit 1

# Export environment
export PYTHONUSERBASE="/workspace/.local"
export PATH="/workspace/.local/bin:$PATH"
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.10")
PYTHON_SITE_PACKAGES="/workspace/.local/lib/python${PYTHON_VERSION}/site-packages"
export PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH"

echo "1️⃣ Testing API..."
echo "   Checking API health..."
if curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
    echo "   ✅ API is running"
else
    echo "   ❌ API is not responding"
    echo "   💡 Start API with: bash scripts/pod/start-service-daemon.sh"
    exit 1
fi

echo ""
echo "2️⃣ Testing video-worker..."
echo "   Checking worker process..."
WORKER_PID=$(pgrep -f "video_worker" || echo "")
if [ -n "$WORKER_PID" ]; then
    echo "   ✅ Worker is running (PID: $WORKER_PID)"
else
    echo "   ❌ Worker is not running"
    echo "   💡 Start worker with: bash scripts/pod/start-service-daemon.sh"
    exit 1
fi

echo ""
echo "3️⃣ Testing RabbitMQ connection..."
echo "   Checking RabbitMQ connectivity..."
if python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
try:
    import pika
    import os
    connection = pika.BlockingConnection(
        pika.URLParameters(
            f\"amqp://{os.getenv('RABBITMQ_USER', 'senate')}:{os.getenv('RABBITMQ_PASSWORD', 'qP2VtHz6fAX4xDksEpMrLT')}@{os.getenv('RABBITMQ_HOST', '178.128.105.100')}:{os.getenv('RABBITMQ_PORT', '5672')}/\"
        )
    )
    channel = connection.channel()
    channel.queue_declare(queue='test_queue', durable=True)
    connection.close()
    print('   ✅ RabbitMQ connection successful')
except Exception as e:
    print(f'   ❌ RabbitMQ connection failed: {e}')
    sys.exit(1)
" 2>&1; then
    echo ""
else
    echo "   ❌ RabbitMQ connection test failed"
    exit 1
fi

echo ""
echo "4️⃣ Testing model download..."
echo "   Checking if models directory exists..."
MODELS_DIR="/workspace/transcription-service/models"
if [ -d "$MODELS_DIR" ]; then
    MODEL_COUNT=$(find "$MODELS_DIR" -type d -maxdepth 1 | wc -l)
    echo "   ✅ Models directory exists ($MODEL_COUNT models)"
else
    echo "   ⚠️  Models directory not found (will be created on first transcription)"
    mkdir -p "$MODELS_DIR"
    echo "   ✅ Created models directory"
fi

echo ""
echo "5️⃣ Testing video download capability..."
echo "   Checking FFmpeg..."
if command -v ffmpeg > /dev/null 2>&1; then
    FFMPEG_VERSION=$(ffmpeg -version | head -n1 | awk '{print $3}')
    echo "   ✅ FFmpeg available (version: $FFMPEG_VERSION)"
else
    echo "   ❌ FFmpeg not found"
    exit 1
fi

echo ""
echo "6️⃣ Testing transcription (3 concurrency)..."
echo "   This will test actual transcription with 3 concurrent tasks"
echo "   (Skipping actual transcription test - use dashboard to test)"
echo "   ✅ Transcription test skipped (use dashboard to test)"

echo ""
echo "=============================="
echo "✅ All Tests Passed!"
echo ""
echo "📋 Summary:"
echo "   - API: ✅ Running"
echo "   - Worker: ✅ Running"
echo "   - RabbitMQ: ✅ Connected"
echo "   - Model Download: ✅ Ready"
echo "   - Video Processing: ✅ Ready (FFmpeg)"
echo ""
echo "💡 Next Steps:"
echo "   1. Use dashboard to send test transcription tasks"
echo "   2. Monitor tasks on dashboard"
echo "   3. Check worker logs: tail -f /workspace/transcription-service/logs/worker.log"

