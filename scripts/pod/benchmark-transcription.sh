#!/bin/bash
# Script สำหรับ Benchmark Transcription Performance
# วัดเวลาและ GPU utilization

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

SSH_HOST="${RUNPOD_HOST:-calm-pink-turtle}"
PROJECT_DIR="/workspace/transcription-service"
VIDEO_FILE="${1:-uploads/v10-1.mp4}"
MODEL="${2:-medium}"

print_status "📊 Benchmarking Transcription Performance"
print_status "Video: $VIDEO_FILE"
print_status "Model: $MODEL"
echo ""

# ตรวจสอบ GPU ก่อนเริ่ม
print_status "GPU Status (Before):"
ssh "$SSH_HOST" "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,utilization.memory --format=csv,noheader"
echo ""

# เริ่ม transcription
print_status "Starting transcription..."
START_TIME=$(date +%s)
TASK_RESPONSE=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && curl -s -X POST 'http://localhost:8001/api/v1/transcription/start' \
    -H 'Content-Type: application/json' \
    -d '{
        \"file_path\": \"$VIDEO_FILE\",
        \"model\": \"$MODEL\",
        \"language\": \"th\"
    }'")

TASK_ID=$(echo "$TASK_RESPONSE" | grep -o '"task_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$TASK_ID" ]; then
    print_error "Failed to start transcription"
    echo "Response: $TASK_RESPONSE"
    exit 1
fi

print_success "Task ID: $TASK_ID"
echo ""

# Monitor GPU utilization ใน background
print_status "Monitoring GPU utilization..."
ssh "$SSH_HOST" "while true; do nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader; sleep 2; done" > /tmp/gpu_monitor.log &
MONITOR_PID=$!

# Monitor progress
print_status "Monitoring progress..."
MAX_WAIT=600
WAIT_TIME=0
CHECK_INTERVAL=2

while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    sleep $CHECK_INTERVAL
    WAIT_TIME=$((WAIT_TIME + CHECK_INTERVAL))
    
    STATUS_RESPONSE=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && curl -s 'http://localhost:8001/api/v1/transcription/status/$TASK_ID'")
    STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
    PROGRESS=$(echo "$STATUS_RESPONSE" | grep -o '"progress":[0-9]*' | cut -d':' -f2)
    
    if [ -z "$PROGRESS" ]; then
        PROGRESS=0
    fi
    
    ELAPSED=$((WAIT_TIME))
    printf "\r⏳ Progress: %d%% - Status: %s - Elapsed: %ds" "$PROGRESS" "$STATUS" "$ELAPSED"
    
    if [ "$STATUS" = "completed" ]; then
        echo ""
        print_success "Transcription completed!"
        break
    elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "cancelled" ]; then
        echo ""
        print_error "Transcription failed: $status"
        kill $MONITOR_PID 2>/dev/null || true
        exit 1
    fi
done

# Stop GPU monitor
kill $MONITOR_PID 2>/dev/null || true

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

echo ""
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "📊 Performance Summary"
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ตรวจสอบ video duration
VIDEO_DURATION=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 '$VIDEO_FILE' 2>/dev/null | cut -d'.' -f1")
if [ -n "$VIDEO_DURATION" ]; then
    SPEEDUP=$(echo "scale=2; $VIDEO_DURATION / $TOTAL_TIME" | bc)
    print_status "Video Duration: ${VIDEO_DURATION}s"
    print_status "Transcription Time: ${TOTAL_TIME}s"
    print_status "Speed: ${SPEEDUP}x real-time"
    echo ""
    
    # เปรียบเทียบกับเป้าหมาย (10 นาที = 1-2 นาที)
    TARGET_MIN=60
    TARGET_MAX=120
    if [ $TOTAL_TIME -le $TARGET_MAX ]; then
        print_success "✅ Meets target (≤2 minutes for 10-minute video)"
    else
        print_warning "⚠️  Exceeds target (should be ≤2 minutes for 10-minute video)"
    fi
fi

# GPU utilization statistics
print_status "GPU Utilization Statistics:"
if [ -f /tmp/gpu_monitor.log ]; then
    awk -F',' '{gpu+=$1; mem+=$2; count++} END {if(count>0) printf "   Average GPU: %.1f%%\n   Average Memory: %.1f%%\n   Samples: %d\n", gpu/count, mem/count, count}' /tmp/gpu_monitor.log
    MAX_GPU=$(awk -F',' '{if($1>max) max=$1} END {print max}' /tmp/gpu_monitor.log)
    MAX_MEM=$(awk -F',' '{if($2>max) max=$2} END {print max}' /tmp/gpu_monitor.log)
    echo "   Peak GPU: ${MAX_GPU}%"
    echo "   Peak Memory: ${MAX_MEM}%"
    rm -f /tmp/gpu_monitor.log
fi

echo ""
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

