#!/bin/bash
# Script สำหรับทดสอบ Transcription กับวิดีโอ v10-1.mp4
# Timeout: 3 นาที - ถ้าไม่เสร็จแสดงว่ามีปัญหา

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
VIDEO_FILE="uploads/v10-1.mp4"
MODEL="${1:-medium}"
MAX_WAIT_TIME=180  # 3 นาที timeout

print_status "🧪 Testing Transcription Performance"
print_status "Video: $VIDEO_FILE"
print_status "Model: $MODEL"
print_status "Timeout: ${MAX_WAIT_TIME}s (3 minutes) - If not completed, there's a problem"
echo ""

# ตรวจสอบ SSH connection
if ! ssh -o ConnectTimeout=5 "$SSH_HOST" "echo 'Connection OK'" > /dev/null 2>&1; then
    print_error "Cannot connect to $SSH_HOST"
    print_status "Please check SSH connection and port"
    exit 1
fi

# ตรวจสอบ GPU
print_status "GPU Status (Before):"
ssh "$SSH_HOST" "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,utilization.memory --format=csv,noheader"
echo ""

# ตรวจสอบ video duration
print_status "Checking video file..."
VIDEO_DURATION=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 '$VIDEO_FILE' 2>/dev/null | cut -d'.' -f1")
if [ -z "$VIDEO_DURATION" ]; then
    print_error "Cannot get video duration or file not found"
    exit 1
fi

print_success "Video duration: ${VIDEO_DURATION}s (~$((VIDEO_DURATION / 60)) minutes)"
echo ""

# ตรวจสอบ configuration
print_status "Current Configuration:"
ssh "$SSH_HOST" "cd $PROJECT_DIR && cat .env.runpod | grep -E 'TRANSCRIPTION_MAX_WORKERS|WHISPER_USE_THREAD_LOCAL|WHISPER_MODEL|TRANSCRIPTION_PREFETCH_COUNT'"
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
GPU_STATS=()

while [ $WAIT_TIME -lt $MAX_WAIT_TIME ]; do
    sleep $CHECK_INTERVAL
    WAIT_TIME=$((WAIT_TIME + CHECK_INTERVAL))
    
    # ตรวจสอบ GPU utilization
    GPU_STAT=$(ssh "$SSH_HOST" "nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader,nounits" 2>/dev/null)
    GPU_UTIL=$(echo "$GPU_STAT" | cut -d',' -f1 | tr -d ' ')
    MEM_UTIL=$(echo "$GPU_STAT" | cut -d',' -f2 | tr -d ' ')
    GPU_STATS+=("$GPU_UTIL")
    
    # ตรวจสอบ progress
    STATUS_RESPONSE=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && curl -s 'http://localhost:8001/api/v1/transcription/status/$TASK_ID'")
    STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
    PROGRESS=$(echo "$STATUS_RESPONSE" | grep -o '"progress":[0-9]*' | cut -d':' -f2)
    
    if [ -z "$PROGRESS" ]; then
        PROGRESS=0
    fi
    
    # แสดง progress เมื่อมีการเปลี่ยนแปลง
    if [ "$PROGRESS" != "$LAST_PROGRESS" ] || [ "$STATUS" != "$LAST_STATUS" ]; then
        MEM_USED=$(echo "$GPU_STAT" | cut -d',' -f3 | tr -d ' ')
        MEM_TOTAL=$(echo "$GPU_STAT" | cut -d',' -f4 | tr -d ' ')
        
        printf "\r⏳ Progress: %3d%% | Status: %-15s | GPU: %3s%% | Mem: %3s%% (%5s/%5s MiB) | Elapsed: %3ds" \
            "$PROGRESS" "$STATUS" "$GPU_UTIL" "$MEM_UTIL" "$MEM_USED" "$MEM_TOTAL" "$WAIT_TIME"
        
        LAST_PROGRESS=$PROGRESS
        LAST_STATUS=$STATUS
    fi
    
    if [ "$STATUS" = "completed" ]; then
        echo ""
        print_success "✅ Transcription completed!"
        break
    elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "cancelled" ]; then
        echo ""
        print_error "❌ Transcription failed: $status"
        exit 1
    fi
done

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

echo ""
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "📊 Performance Analysis"
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ตรวจสอบว่าเสร็จหรือ timeout
if [ $WAIT_TIME -ge $MAX_WAIT_TIME ]; then
    print_error "❌ TIMEOUT: Transcription took longer than ${MAX_WAIT_TIME}s (3 minutes)"
    print_error "This indicates a performance problem that needs to be fixed!"
    echo ""
    
    # วิเคราะห์ปัญหา
    print_status "🔍 Problem Analysis:"
    
    # ตรวจสอบ GPU utilization
    if [ ${#GPU_STATS[@]} -gt 0 ]; then
        AVG_GPU=0
        COUNT=0
        for stat in "${GPU_STATS[@]}"; do
            if [ -n "$stat" ] && [ "$stat" != "N/A" ]; then
                AVG_GPU=$((AVG_GPU + stat))
                COUNT=$((COUNT + 1))
            fi
        done
        if [ $COUNT -gt 0 ]; then
            AVG_GPU=$((AVG_GPU / COUNT))
            echo "   Average GPU Utilization: ${AVG_GPU}%"
            
            if [ $AVG_GPU -lt 50 ]; then
                print_warning "   ⚠️  Low GPU utilization - GPU is underutilized"
                print_status "   💡 Solution: Increase TRANSCRIPTION_MAX_WORKERS"
            elif [ $AVG_GPU -lt 80 ]; then
                print_warning "   ⚠️  Moderate GPU utilization - Can be improved"
                print_status "   💡 Solution: Increase TRANSCRIPTION_MAX_WORKERS or use smaller model"
            fi
        fi
    fi
    
    # ตรวจสอบ progress
    if [ "$PROGRESS" -lt 100 ]; then
        print_warning "   ⚠️  Progress: ${PROGRESS}% - Transcription not completed"
        print_status "   💡 Possible causes:"
        echo "      - Too few workers (TRANSCRIPTION_MAX_WORKERS too low)"
        echo "      - Sequential processing (WHISPER_USE_THREAD_LOCAL=false)"
        echo "      - Model too large for parallel processing"
        echo "      - GPU memory issues"
    fi
    
    # ตรวจสอบ logs
    print_status ""
    print_status "Recent worker logs:"
    ssh "$SSH_HOST" "cd $PROJECT_DIR && tail -50 /tmp/video-worker.log 2>/dev/null | grep -E 'ERROR|WARNING|Starting chunk|Completed chunk|ThreadPoolExecutor' | tail -10"
    
    echo ""
    print_status "💡 Recommended Actions:"
    echo "   1. Run: bash scripts/pod/optimize-gpu-performance.sh"
    echo "   2. Check GPU memory: nvidia-smi"
    echo "   3. Increase TRANSCRIPTION_MAX_WORKERS (if GPU memory allows)"
    echo "   4. Ensure WHISPER_USE_THREAD_LOCAL=true"
    
    exit 1
fi

# ถ้าเสร็จแล้ว - แสดงผลลัพธ์
SPEEDUP=$(echo "scale=2; $VIDEO_DURATION / $TOTAL_TIME" | bc 2>/dev/null || echo "N/A")
TARGET_SPEEDUP=5  # เป้าหมาย: 5x real-time (10 นาที → 2 นาที)

print_status "Video Duration: ${VIDEO_DURATION}s (~$((VIDEO_DURATION / 60)) minutes)"
print_status "Transcription Time: ${TOTAL_TIME}s (~$((TOTAL_TIME / 60)) minutes)"
print_status "Speed: ${SPEEDUP}x real-time"
echo ""

# เปรียบเทียบกับเป้าหมาย
if [ "$SPEEDUP" != "N/A" ] && (( $(echo "$SPEEDUP >= $TARGET_SPEEDUP" | bc -l) )); then
    print_success "✅ Excellent performance (≥${TARGET_SPEEDUP}x real-time)"
elif [ "$SPEEDUP" != "N/A" ] && (( $(echo "$SPEEDUP >= 3" | bc -l) )); then
    print_warning "⚠️  Acceptable performance (${SPEEDUP}x real-time, target: ≥${TARGET_SPEEDUP}x)"
else
    print_warning "⚠️  Below target (${SPEEDUP}x real-time, target: ≥${TARGET_SPEEDUP}x)"
fi

# GPU utilization statistics
if [ ${#GPU_STATS[@]} -gt 0 ]; then
    AVG_GPU=0
    MAX_GPU=0
    COUNT=0
    for stat in "${GPU_STATS[@]}"; do
        if [ -n "$stat" ] && [ "$stat" != "N/A" ]; then
            AVG_GPU=$((AVG_GPU + stat))
            if [ $stat -gt $MAX_GPU ]; then
                MAX_GPU=$stat
            fi
            COUNT=$((COUNT + 1))
        fi
    done
    if [ $COUNT -gt 0 ]; then
        AVG_GPU=$((AVG_GPU / COUNT))
        echo ""
        print_status "GPU Utilization:"
        echo "   Average: ${AVG_GPU}%"
        echo "   Peak: ${MAX_GPU}%"
        
        if [ $AVG_GPU -lt 50 ]; then
            print_warning "   ⚠️  Low GPU utilization - Consider optimization"
        elif [ $AVG_GPU -lt 80 ]; then
            print_warning "   ⚠️  Moderate GPU utilization - Can be improved"
        else
            print_success "   ✅ Good GPU utilization"
        fi
    fi
fi

print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

