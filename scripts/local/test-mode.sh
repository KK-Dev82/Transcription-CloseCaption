#!/bin/bash
# Script สำหรับทดสอบ Parallel หรือ Sequential Processing แบบแยก
# Usage: bash scripts/local/test-mode.sh [parallel|sequential] [video_file] [model]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
CONTAINER_NAME="transcription-local-base"
API_URL="http://localhost:8001"
MODE="${1:-parallel}"
TEST_VIDEO="${2:-uploads/trimmed_short.mp4}"
MODEL="${3:-base}"

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Validate mode
if [ "$MODE" != "parallel" ] && [ "$MODE" != "sequential" ]; then
    print_error "Mode ต้องเป็น 'parallel' หรือ 'sequential'"
    exit 1
fi

# ตรวจสอบ container
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    print_error "Container $CONTAINER_NAME ไม่ได้ทำงานอยู่"
    exit 1
fi

# ตรวจสอบไฟล์วิดีโอ
if [ ! -f "$TEST_VIDEO" ]; then
    print_error "ไม่พบไฟล์วิดีโอ: $TEST_VIDEO"
    exit 1
fi

# ตั้งค่า use_thread_local
if [ "$MODE" = "parallel" ]; then
    USE_THREAD_LOCAL="true"
    MODE_NAME="Parallel"
else
    USE_THREAD_LOCAL="false"
    MODE_NAME="Sequential"
fi

print_header "🧪 ทดสอบ $MODE_NAME Processing"

# ตั้งค่า environment variable
print_info "ตั้งค่า WHISPER_USE_THREAD_LOCAL=$USE_THREAD_LOCAL"
docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && sed -i 's/WHISPER_USE_THREAD_LOCAL=.*/WHISPER_USE_THREAD_LOCAL=$USE_THREAD_LOCAL/' .env.runpod"

# Restart worker
print_info "Restart Video Worker..."
docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && pkill -f 'python.*video_worker' || true"
sleep 2

# Load environment variables
docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && \
    source .env.runpod 2>/dev/null || true && \
    export RABBITMQ_HOST=\${RABBITMQ_HOST:-host.docker.internal} && \
    export RABBITMQ_PORT=\${RABBITMQ_PORT:-5672} && \
    export RABBITMQ_USER=\${RABBITMQ_USER:-admin} && \
    export RABBITMQ_PASSWORD=\${RABBITMQ_PASSWORD:-admin123} && \
    export WHISPER_PROVIDER=\${WHISPER_PROVIDER:-openai-whisper} && \
    export WHISPER_USE_THREAD_LOCAL=$USE_THREAD_LOCAL && \
    nohup python3 -m app.workers.video_worker > /tmp/video-worker.log 2>&1 & disown"

sleep 5

# ตรวจสอบ worker
if ! docker exec "$CONTAINER_NAME" bash -c "pgrep -f 'python.*video_worker' > /dev/null"; then
    print_error "Video Worker ไม่ได้ทำงาน"
    exit 1
fi

print_success "Video Worker ทำงานแล้ว"

# ตรวจสอบ logs
print_info "ตรวจสอบ configuration..."
docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && tail -30 /tmp/video-worker.log 2>/dev/null | grep -E 'ThreadPoolExecutor|WHISPER_USE_THREAD_LOCAL|Initialized|Thread-local' | tail -5"

# เริ่ม transcription
print_info "เริ่ม transcription: $TEST_VIDEO (model: $MODEL)"
response=$(docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && curl -s -X POST \"$API_URL/api/v1/transcription/start\" \
    -H \"Content-Type: application/json\" \
    -d '{
        \"file_path\": \"$TEST_VIDEO\",
        \"model\": \"$MODEL\",
        \"language\": \"th\"
    }'")

task_id=$(echo "$response" | grep -o '"task_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$task_id" ]; then
    print_error "ไม่สามารถสร้าง task ได้"
    echo "Response: $response"
    exit 1
fi

print_success "Task ID: $task_id"

# Monitor progress
print_info "Monitor progress..."
start_time=$(date +%s)
max_wait=600
wait_time=0
check_interval=2

while [ $wait_time -lt $max_wait ]; do
    sleep $check_interval
    wait_time=$((wait_time + check_interval))
    
    status_response=$(docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && curl -s \"$API_URL/api/v1/transcription/status/$task_id\"")
    status=$(echo "$status_response" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
    progress=$(echo "$status_response" | grep -o '"progress":[0-9]*' | cut -d':' -f2)
    
    if [ -z "$progress" ]; then
        progress=0
    fi
    
    elapsed=$((wait_time))
    printf "\r⏳ Progress: %d%% - Status: %s - Elapsed: %ds" "$progress" "$status" "$elapsed"
    
    if [ "$status" = "completed" ]; then
        echo ""
        print_success "Transcription เสร็จสิ้น!"
        break
    elif [ "$status" = "failed" ] || [ "$status" = "cancelled" ]; then
        echo ""
        print_error "Transcription ล้มเหลว: $status"
        exit 1
    fi
done

if [ $wait_time -ge $max_wait ]; then
    echo ""
    print_error "Timeout"
    exit 1
fi

end_time=$(date +%s)
total_time=$((end_time - start_time))

print_success "ใช้เวลา: ${total_time} วินาที"

# ตรวจสอบ logs
print_info "ตรวจสอบ logs..."
echo ""
echo "=== Thread-local/Shared Model Usage ==="
docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && tail -200 /tmp/video-worker.log 2>/dev/null | grep -E 'Thread-local|thread-local|Using thread-local|Using shared model|Loading thread-local' | head -10"

echo ""
echo "=== Chunk Processing Timeline ==="
docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && tail -500 /tmp/video-worker.log 2>/dev/null | grep -E 'Starting chunk|Completed chunk|Thread chunk_worker' | grep '$task_id' | head -20"

print_success "การทดสอบเสร็จสิ้น!"
print_info "Task ID: $task_id"
print_info "Mode: $MODE_NAME"
print_info "Time: ${total_time}s"

