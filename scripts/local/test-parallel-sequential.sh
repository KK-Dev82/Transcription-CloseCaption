#!/bin/bash
# Script สำหรับทดสอบทั้ง Parallel และ Sequential Processing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_NAME="transcription-local-base"
API_URL="http://localhost:8001"
TEST_VIDEO="${1:-uploads/trimmed_short.mp4}"
MODEL="${2:-base}"

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

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# ตรวจสอบว่า container ทำงานอยู่หรือไม่
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    print_error "Container $CONTAINER_NAME ไม่ได้ทำงานอยู่"
    print_info "กรุณารัน: bash scripts/local/start-local.sh"
    exit 1
fi

# ตรวจสอบว่าไฟล์วิดีโอมีอยู่หรือไม่
if [ ! -f "$TEST_VIDEO" ]; then
    print_error "ไม่พบไฟล์วิดีโอ: $TEST_VIDEO"
    exit 1
fi

# ฟังก์ชันสำหรับทดสอบ transcription
test_transcription() {
    local mode=$1
    local use_thread_local=$2
    local mode_name=$3
    
    print_header "🧪 ทดสอบ $mode_name Processing"
    
    # ตั้งค่า environment variable
    print_info "ตั้งค่า WHISPER_USE_THREAD_LOCAL=$use_thread_local"
    docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && sed -i 's/WHISPER_USE_THREAD_LOCAL=.*/WHISPER_USE_THREAD_LOCAL=$use_thread_local/' .env.runpod"
    
    # Restart worker เพื่อให้ใช้ค่าใหม่
    print_info "Restart Video Worker..."
    docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && pkill -f 'python.*video_worker' || true"
    sleep 2
    docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && export RABBITMQ_HOST=\$(grep RABBITMQ_HOST .env.runpod | cut -d'=' -f2) && export RABBITMQ_PORT=\$(grep RABBITMQ_PORT .env.runpod | cut -d'=' -f2) && export RABBITMQ_USER=\$(grep RABBITMQ_USER .env.runpod | cut -d'=' -f2) && export RABBITMQ_PASSWORD=\$(grep RABBITMQ_PASSWORD .env.runpod | cut -d'=' -f2) && export WHISPER_PROVIDER=\$(grep WHISPER_PROVIDER .env.runpod | cut -d'=' -f2) && export WHISPER_USE_THREAD_LOCAL=$use_thread_local && nohup python3 -m app.workers.video_worker > /tmp/video-worker.log 2>&1 & disown"
    sleep 5
    
    # ตรวจสอบว่า worker ทำงานอยู่
    if ! docker exec "$CONTAINER_NAME" bash -c "pgrep -f 'python.*video_worker' > /dev/null"; then
        print_error "Video Worker ไม่ได้ทำงาน"
        return 1
    fi
    
    # ตรวจสอบ logs เพื่อดูว่าใช้ thread-local หรือไม่
    print_info "ตรวจสอบ configuration..."
    docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && tail -20 /tmp/video-worker.log 2>/dev/null | grep -E 'ThreadPoolExecutor|WHISPER_USE_THREAD_LOCAL|Initialized' | tail -5"
    
    # เริ่ม transcription
    print_info "เริ่ม transcription: $TEST_VIDEO (model: $MODEL)"
    print_info "API URL: $API_URL"
    
    local start_time=$(date +%s)
    local response=$(docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && curl -s -X POST \"$API_URL/api/v1/transcription/start\" \
        -H \"Content-Type: application/json\" \
        -d '{
            \"file_path\": \"$TEST_VIDEO\",
            \"model\": \"$MODEL\",
            \"language\": \"th\"
        }'")
    
    local task_id=$(echo "$response" | grep -o '"task_id":"[^"]*' | cut -d'"' -f4)
    
    if [ -z "$task_id" ]; then
        print_error "ไม่สามารถสร้าง task ได้"
        echo "Response: $response"
        return 1
    fi
    
    print_success "Task ID: $task_id"
    
    # รอให้ transcription เสร็จ
    print_info "รอ transcription เสร็จ..."
    local max_wait=600  # 10 นาที
    local wait_time=0
    local check_interval=2
    
    while [ $wait_time -lt $max_wait ]; do
        sleep $check_interval
        wait_time=$((wait_time + check_interval))
        
        local status_response=$(docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && curl -s \"$API_URL/api/v1/transcription/status/$task_id\"")
        local status=$(echo "$status_response" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
        local progress=$(echo "$status_response" | grep -o '"progress":[0-9]*' | cut -d':' -f2)
        
        if [ -z "$progress" ]; then
            progress=0
        fi
        
        local elapsed=$((wait_time))
        printf "\r⏳ Progress: %d%% - Status: %s - Elapsed: %ds" "$progress" "$status" "$elapsed"
        
        if [ "$status" = "completed" ]; then
            echo ""
            print_success "Transcription เสร็จสิ้น!"
            break
        elif [ "$status" = "failed" ] || [ "$status" = "cancelled" ]; then
            echo ""
            print_error "Transcription ล้มเหลว: $status"
            return 1
        fi
    done
    
    if [ $wait_time -ge $max_wait ]; then
        echo ""
        print_error "Timeout: Transcription ใช้เวลานานเกินไป"
        return 1
    fi
    
    local end_time=$(date +%s)
    local total_time=$((end_time - start_time))
    
    print_success "ใช้เวลา: ${total_time} วินาที"
    
    # ตรวจสอบ logs
    print_info "ตรวจสอบ logs..."
    docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && tail -100 /tmp/video-worker.log 2>/dev/null | grep -E 'Thread-local|thread-local|Using thread-local|Using shared model|Loading thread-local' | head -10"
    
    # ตรวจสอบว่า chunks ถูกประมวลผลแบบ parallel หรือ sequential
    print_info "ตรวจสอบการประมวลผล chunks..."
    docker exec "$CONTAINER_NAME" bash -c "cd /workspace/transcription-service && tail -500 /tmp/video-worker.log 2>/dev/null | grep -E 'Starting chunk|Completed chunk|Thread chunk_worker' | grep '$task_id' | head -20"
    
    # เก็บผลลัพธ์
    echo "$task_id|$total_time|$mode" >> /tmp/transcription_test_results.txt
    
    return 0
}

# สร้างไฟล์เก็บผลลัพธ์
rm -f /tmp/transcription_test_results.txt
touch /tmp/transcription_test_results.txt

print_header "🚀 เริ่มทดสอบ Parallel และ Sequential Processing"

# ทดสอบ Sequential Processing (WHISPER_USE_THREAD_LOCAL=false)
print_warning "⚠️  หมายเหตุ: Sequential processing จะใช้เวลานานกว่า"
test_transcription "sequential" "false" "Sequential"

print_info "รอ 10 วินาทีก่อนทดสอบโหมดถัดไป..."
sleep 10

# ทดสอบ Parallel Processing (WHISPER_USE_THREAD_LOCAL=true)
test_transcription "parallel" "true" "Parallel"

# สรุปผลลัพธ์
print_header "📊 สรุปผลการทดสอบ"

if [ -f /tmp/transcription_test_results.txt ]; then
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Task ID                          | Time (s) | Mode${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    while IFS='|' read -r task_id time mode; do
        if [ "$mode" = "parallel" ]; then
            echo -e "${GREEN}$task_id | $time      | $mode${NC}"
        else
            echo -e "${YELLOW}$task_id | $time      | $mode${NC}"
        fi
    done < /tmp/transcription_test_results.txt
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
fi

print_success "การทดสอบเสร็จสิ้น!"
print_info "ตรวจสอบ logs เพิ่มเติม: docker exec $CONTAINER_NAME tail -f /tmp/video-worker.log"

