#!/bin/bash
# Script สำหรับทดสอบ Transcription กับวิดีโอ 3 นาที
# เป้าหมาย: ตรวจสอบประสิทธิภาพและ GPU utilization

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

SSH_HOST="${RUNPOD_HOST:-calm-pink-turtle}"
PROJECT_DIR="/workspace/transcription-service"
VIDEO_FILE="${1:-uploads/test_3min.mp4}"
MODEL="${2:-medium}"
MAX_WAIT_TIME=180  # 3 นาที timeout

print_status "🧪 Testing 3-Minute Video Transcription"
print_status "Video: $VIDEO_FILE"
print_status "Model: $MODEL"
print_status "Timeout: ${MAX_WAIT_TIME}s (3 minutes)"
echo ""

# ตรวจสอบ GPU ก่อนเริ่ม
print_status "GPU Status (Before):"
ssh "$SSH_HOST" "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,utilization.memory --format=csv,noheader"
echo ""

# ตรวจสอบว่าไฟล์มีอยู่
print_status "Checking video file..."
if ! ssh "$SSH_HOST" "[ -f '$PROJECT_DIR/$VIDEO_FILE' ]"; then
    print_error "Video file not found: $VIDEO_FILE"
    print_status "Available files:"
    ssh "$SSH_HOST" "cd $PROJECT_DIR && ls -lh uploads/*.mp4 2>/dev/null | head -5"
    exit 1
fi

# ตรวจสอบ video duration
VIDEO_DURATION=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 '$VIDEO_FILE' 2>/dev/null | cut -d'.' -f1")
if [ -z "$VIDEO_DURATION" ]; then
    print_error "Cannot get video duration"
    exit 1
fi

print_success "Video duration: ${VIDEO_DURATION}s (~$((VIDEO_DURATION / 60)) minutes)"
echo ""

# ตรวจสอบ services
print_status "Checking services..."
if ! ssh "$SSH_HOST" "pgrep -f 'python.*video_worker' > /dev/null"; then
    print_warning "Video Worker is not running - Starting..."
    ssh "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/start-pod.sh worker 2>&1 | tail -5"
    sleep 5
fi

if ! ssh "$SSH_HOST" "curl -s http://localhost:8001/health > /dev/null 2>&1"; then
    print_error "Main API is not responding"
    exit 1
fi

print_success "Services are ready"
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

# Monitor progress และ GPU
print_status "Monitoring progress and GPU utilization..."
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

WAIT_TIME=0
CHECK_INTERVAL=2
LAST_PROGRESS=0
LAST_STATUS=""

# เก็บ GPU stats
GPU_STATS_FILE="/tmp/gpu_stats_${TASK_ID}.txt"
> "$GPU_STATS_FILE"

while [ $WAIT_TIME -lt $MAX_WAIT_TIME ]; do
    sleep $CHECK_INTERVAL
    WAIT_TIME=$((WAIT_TIME + CHECK_INTERVAL))
    
    # ตรวจสอบ GPU utilization
    GPU_STAT=$(ssh "$SSH_HOST" "nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader,nounits" 2>/dev/null)
    echo "$WAIT_TIME,$GPU_STAT" >> "$GPU_STATS_FILE"
    
    # ตรวจสอบ progress
    STATUS_RESPONSE=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && curl -s 'http://localhost:8001/api/v1/transcription/status/$TASK_ID'")
    STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
    PROGRESS=$(echo "$STATUS_RESPONSE" | grep -o '"progress":[0-9]*' | cut -d':' -f2)
    
    if [ -z "$PROGRESS" ]; then
        PROGRESS=0
    fi
    
    # แสดง progress เมื่อมีการเปลี่ยนแปลง
    if [ "$PROGRESS" != "$LAST_PROGRESS" ] || [ "$STATUS" != "$LAST_STATUS" ]; then
        GPU_UTIL=$(echo "$GPU_STAT" | cut -d',' -f1 | tr -d ' ')
        MEM_UTIL=$(echo "$GPU_STAT" | cut -d',' -f2 | tr -d ' ')
        MEM_USED=$(echo "$GPU_STAT" | cut -d',' -f3 | tr -d ' ')
        MEM_TOTAL=$(echo "$GPU_STAT" | cut -d',' -f4 | tr -d ' ')
        
        printf "\r⏳ Progress: %3d%% | Status: %-15s | GPU: %3s%% | Mem: %3s%% (%5s/%5s MiB) | Elapsed: %3ds" \
            "$PROGRESS" "$STATUS" "$GPU_UTIL" "$MEM_UTIL" "$MEM_USED" "$MEM_TOTAL" "$WAIT_TIME"
        
        LAST_PROGRESS=$PROGRESS
        LAST_STATUS=$STATUS
    fi
    
    if [ "$STATUS" = "completed" ]; then
        echo ""
        print_success "Transcription completed!"
        break
    elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "cancelled" ]; then
        echo ""
        print_error "Transcription failed: $status"
        exit 1
    fi
done

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

if [ $WAIT_TIME -ge $MAX_WAIT_TIME ]; then
    echo ""
    print_error "Timeout: Transcription took longer than ${MAX_WAIT_TIME}s"
    print_warning "This indicates performance issues that need optimization"
    exit 1
fi

echo ""
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "📊 Performance Summary"
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# คำนวณ performance metrics
SPEEDUP=$(echo "scale=2; $VIDEO_DURATION / $TOTAL_TIME" | bc 2>/dev/null || echo "N/A")
TARGET_TIME=$((VIDEO_DURATION / 5))  # เป้าหมาย: 5x real-time (3 นาที → 36 วินาที)

print_status "Video Duration: ${VIDEO_DURATION}s (~$((VIDEO_DURATION / 60)) minutes)"
print_status "Transcription Time: ${TOTAL_TIME}s (~$((TOTAL_TIME / 60)) minutes)"
print_status "Speed: ${SPEEDUP}x real-time"
echo ""

# เปรียบเทียบกับเป้าหมาย
if [ "$SPEEDUP" != "N/A" ] && (( $(echo "$SPEEDUP >= 5" | bc -l) )); then
    print_success "✅ Meets target (≥5x real-time)"
elif [ "$SPEEDUP" != "N/A" ] && (( $(echo "$SPEEDUP >= 3" | bc -l) )); then
    print_warning "⚠️  Below target (should be ≥5x real-time, got ${SPEEDUP}x)"
else
    print_error "❌ Poor performance (should be ≥5x real-time, got ${SPEEDUP}x)"
fi

# GPU utilization statistics
print_status ""
print_status "GPU Utilization Statistics:"
if [ -f "$GPU_STATS_FILE" ] && [ -s "$GPU_STATS_FILE" ]; then
    AVG_GPU=$(awk -F',' '{sum+=$2; count++} END {if(count>0) printf "%.1f", sum/count}' "$GPU_STATS_FILE")
    AVG_MEM=$(awk -F',' '{sum+=$3; count++} END {if(count>0) printf "%.1f", sum/count}' "$GPU_STATS_FILE")
    MAX_GPU=$(awk -F',' '{if($2>max) max=$2} END {print max}' "$GPU_STATS_FILE")
    MAX_MEM=$(awk -F',' '{if($3>max) max=$3} END {print max}' "$GPU_STATS_FILE")
    SAMPLES=$(wc -l < "$GPU_STATS_FILE")
    
    echo "   Average GPU Utilization: ${AVG_GPU}%"
    echo "   Average Memory Utilization: ${AVG_MEM}%"
    echo "   Peak GPU Utilization: ${MAX_GPU}%"
    echo "   Peak Memory Utilization: ${MAX_MEM}%"
    echo "   Samples: $SAMPLES"
    echo ""
    
    # วิเคราะห์ประสิทธิภาพ
    if (( $(echo "$AVG_GPU < 50" | bc -l) )); then
        print_warning "⚠️  Low GPU utilization (${AVG_GPU}%) - Consider increasing TRANSCRIPTION_MAX_WORKERS"
    elif (( $(echo "$AVG_GPU < 80" | bc -l) )); then
        print_warning "⚠️  Moderate GPU utilization (${AVG_GPU}%) - Can be improved"
    else
        print_success "✅ Good GPU utilization (${AVG_GPU}%)"
    fi
    
    rm -f "$GPU_STATS_FILE"
fi

# ตรวจสอบ configuration
print_status ""
print_status "Current Configuration:"
ssh "$SSH_HOST" "cd $PROJECT_DIR && cat .env.runpod | grep -E 'TRANSCRIPTION_MAX_WORKERS|WHISPER_USE_THREAD_LOCAL|WHISPER_MODEL|TRANSCRIPTION_PREFETCH_COUNT'"
echo ""

# คำแนะนำ
if [ "$SPEEDUP" != "N/A" ] && (( $(echo "$SPEEDUP < 5" | bc -l) )); then
    print_status "💡 Optimization Recommendations:"
    echo "   1. Increase TRANSCRIPTION_MAX_WORKERS (current: check config)"
    echo "   2. Ensure WHISPER_USE_THREAD_LOCAL=true"
    echo "   3. Use smaller model (base/small) for faster transcription"
    echo "   4. Check GPU memory usage - may need to reduce workers if OOM"
    echo ""
    print_status "Run: bash scripts/pod/optimize-gpu-performance.sh"
fi

print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

