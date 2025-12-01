#!/bin/bash
# Script สำหรับทดสอบ Transcription กับวิดีโอเดียว
# ตรวจสอบ GPU utilization และ performance

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

SSH_HOST="${RUNPOD_HOST:-calm-pink-turtle}"
PROJECT_DIR="/workspace/transcription-service"
VIDEO_FILE="${1:-uploads/v05-1.mp4}"
MODEL="${2:-medium}"
EXPECTED_TIME="${3:-1}"

echo "🧪 Testing Transcription: $VIDEO_FILE"
echo "📅 $(date)"
echo ""

# ตรวจสอบ SSH connection
print_status "Checking SSH connection..."
if ! ssh -o ConnectTimeout=5 "$SSH_HOST" "echo 'Connection OK'" > /dev/null 2>&1; then
    print_error "Cannot connect to $SSH_HOST"
    exit 1
fi
print_success "✅ SSH connection OK"
echo ""

# ตรวจสอบ services
print_status "Checking services..."
if ! ssh "$SSH_HOST" "pgrep -f 'python.*video_worker' > /dev/null"; then
    print_warning "⚠️  Video Worker is not running"
    exit 1
fi

if ! ssh "$SSH_HOST" "curl -s http://localhost:8001/health > /dev/null 2>&1"; then
    print_error "❌ Main API is not responding"
    exit 1
fi
print_success "✅ Services are ready"
echo ""

# ตรวจสอบ GPU
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "GPU Status (Before)"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ssh "$SSH_HOST" "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,utilization.memory --format=csv,noheader"
echo ""

# ตรวจสอบ video file
print_status "Checking video file..."
if ! ssh "$SSH_HOST" "[ -f '$PROJECT_DIR/$VIDEO_FILE' ]"; then
    print_error "File not found: $VIDEO_FILE"
    exit 1
fi

VIDEO_DURATION=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 '$VIDEO_FILE' 2>/dev/null | cut -d'.' -f1" || echo "0")
if [ -z "$VIDEO_DURATION" ] || [ "$VIDEO_DURATION" = "0" ]; then
    print_warning "Cannot get video duration"
else
    print_success "Video duration: ${VIDEO_DURATION}s (~$((VIDEO_DURATION / 60)) minutes)"
fi
echo ""

# ตรวจสอบ configuration
print_status "Current Configuration:"
ssh "$SSH_HOST" "cd $PROJECT_DIR && cat .env.runpod | grep -E 'TRANSCRIPTION_MAX_WORKERS|WHISPER_USE_THREAD_LOCAL|WHISPER_MODEL|TRANSCRIPTION_PREFETCH_COUNT'"
echo ""

# เริ่ม transcription
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Starting Transcription"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

START_TIME=$(date +%s)
TASK_RESPONSE=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && curl -s -X POST 'http://localhost:8001/transcribe/' \
    -H 'Content-Type: application/json' \
    -d '{
        \"file_path\": \"$VIDEO_FILE\",
        \"model_size\": \"$MODEL\",
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
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Monitoring Progress and GPU Utilization"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

WAIT_TIME=0
CHECK_INTERVAL=1
LAST_PROGRESS=0
LAST_STATUS=""
GPU_STATS=()
MAX_WAIT=$((EXPECTED_TIME * 20))  # Timeout = 20x expected time (minimum 30s)
if [ $MAX_WAIT -lt 30 ]; then
    MAX_WAIT=30  # Minimum 30 seconds
fi

while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    sleep $CHECK_INTERVAL
    WAIT_TIME=$((WAIT_TIME + CHECK_INTERVAL))
    
    # ตรวจสอบ GPU utilization
    GPU_STAT=$(ssh "$SSH_HOST" "nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader,nounits" 2>/dev/null)
    GPU_UTIL=$(echo "$GPU_STAT" | cut -d',' -f1 | tr -d ' ')
    MEM_UTIL=$(echo "$GPU_STAT" | cut -d',' -f2 | tr -d ' ')
    MEM_USED=$(echo "$GPU_STAT" | cut -d',' -f3 | tr -d ' ')
    MEM_TOTAL=$(echo "$GPU_STAT" | cut -d',' -f4 | tr -d ' ')
    GPU_STATS+=("$GPU_UTIL")
    
    # ตรวจสอบ progress
    STATUS_RESPONSE=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && curl -s 'http://localhost:8001/transcribe/$TASK_ID'")
    STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
    PROGRESS=$(echo "$STATUS_RESPONSE" | grep -o '"progress":[0-9]*' | cut -d':' -f2)
    
    if [ -z "$PROGRESS" ]; then
        PROGRESS=0
    fi
    
    # แสดง progress เมื่อมีการเปลี่ยนแปลง
    if [ "$PROGRESS" != "$LAST_PROGRESS" ] || [ "$STATUS" != "$LAST_STATUS" ]; then
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
        print_error "❌ Transcription failed: $STATUS"
        exit 1
    fi
done

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

echo ""
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Results"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ตรวจสอบว่าเสร็จหรือ timeout
if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    print_error "❌ TIMEOUT: Transcription took longer than ${MAX_WAIT}s"
    exit 1
fi

# คำนวณ speed
if [ "$VIDEO_DURATION" != "0" ] && [ "$VIDEO_DURATION" -gt 0 ]; then
    SPEEDUP=$(echo "scale=2; $VIDEO_DURATION / $TOTAL_TIME" | bc 2>/dev/null || echo "N/A")
    print_status "Video Duration: ${VIDEO_DURATION}s"
    print_status "Transcription Time: ${TOTAL_TIME}s"
    print_status "Speed: ${SPEEDUP}x real-time"
else
    print_status "Transcription Time: ${TOTAL_TIME}s (Expected: ~${EXPECTED_TIME}s)"
fi
echo ""

# GPU utilization statistics
if [ ${#GPU_STATS[@]} -gt 0 ]; then
    AVG_GPU=0
    MAX_GPU=0
    MIN_GPU=100
    COUNT=0
    for stat in "${GPU_STATS[@]}"; do
        if [ -n "$stat" ] && [ "$stat" != "N/A" ] && [ "$stat" -ge 0 ] && [ "$stat" -le 100 ]; then
            AVG_GPU=$((AVG_GPU + stat))
            if [ $stat -gt $MAX_GPU ]; then
                MAX_GPU=$stat
            fi
            if [ $stat -lt $MIN_GPU ]; then
                MIN_GPU=$stat
            fi
            COUNT=$((COUNT + 1))
        fi
    done
    if [ $COUNT -gt 0 ]; then
        AVG_GPU=$((AVG_GPU / COUNT))
        echo ""
        print_status "GPU Utilization Statistics:"
        echo "   Average: ${AVG_GPU}%"
        echo "   Peak: ${MAX_GPU}%"
        echo "   Minimum: ${MIN_GPU}%"
        echo ""
        
        if [ $AVG_GPU -lt 50 ]; then
            print_warning "   ⚠️  Low GPU utilization - GPU is underutilized"
            print_status "   💡 Consider: Increase TRANSCRIPTION_MAX_WORKERS"
        elif [ $AVG_GPU -lt 80 ]; then
            print_warning "   ⚠️  Moderate GPU utilization - Can be improved"
            print_status "   💡 Consider: Increase TRANSCRIPTION_MAX_WORKERS or use smaller model"
        else
            print_success "   ✅ Good GPU utilization"
        fi
    fi
fi

# เปรียบเทียบกับ expected time
if [ "$EXPECTED_TIME" -gt 0 ]; then
    echo ""
    if [ "$TOTAL_TIME" -le "$EXPECTED_TIME" ]; then
        print_success "✅ Excellent! Completed in ${TOTAL_TIME}s (Expected: ~${EXPECTED_TIME}s)"
    elif [ "$TOTAL_TIME" -le $((EXPECTED_TIME * 2)) ]; then
        print_warning "⚠️  Acceptable: Completed in ${TOTAL_TIME}s (Expected: ~${EXPECTED_TIME}s)"
    else
        print_warning "⚠️  Slow: Completed in ${TOTAL_TIME}s (Expected: ~${EXPECTED_TIME}s)"
        print_status "💡 Consider optimization"
    fi
fi

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

