#!/bin/bash
# Script สำหรับทดสอบ Transcription กับวิดีโอทั้ง 3 ตัว
#
# วิธีใช้งาน:
#   bash scripts/pod/test-all-videos.sh [model]
#
# ตัวอย่าง:
#   bash scripts/pod/test-all-videos.sh medium

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
MODEL="${1:-medium}"

# วิดีโอที่จะทดสอบ (filename, expected_duration_seconds, timeout_seconds)
declare -A VIDEOS=(
    ["v05-1.mp4"]="5:30"      # 5 วินาที, timeout 30 วินาที
    ["v10-1.mp4"]="600:180"   # 10 นาที, timeout 3 นาที
    ["v60-1.mp4"]="3600:600"  # 60 นาที, timeout 10 นาที
)

echo "🧪 Testing Transcription with All Videos"
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
    print_status "Starting services..."
    ssh "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/start-pod.sh" || {
        print_error "❌ Failed to start services"
        exit 1
    }
    sleep 5
fi

if ! ssh "$SSH_HOST" "curl -s http://localhost:8001/health > /dev/null 2>&1"; then
    print_error "❌ Main API is not responding"
    exit 1
fi
print_success "✅ Services are ready"
echo ""

# ทดสอบแต่ละวิดีโอ
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Testing Videos"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RESULTS=()

for filename in "${!VIDEOS[@]}"; do
    IFS=':' read -r EXPECTED_DURATION TIMEOUT <<< "${VIDEOS[$filename]}"
    
    print_header ""
    print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_status "Testing: $filename"
    print_status "   Expected Duration: ${EXPECTED_DURATION}s"
    print_status "   Timeout: ${TIMEOUT}s"
    print_status "   Model: $MODEL"
    print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # ตรวจสอบว่ามีไฟล์หรือไม่
    if ! ssh "$SSH_HOST" "[ -f '$PROJECT_DIR/uploads/$filename' ]"; then
        print_error "   ❌ File not found: uploads/$filename"
        RESULTS+=("$filename:FAILED:File not found")
        continue
    fi
    
    # เริ่ม transcription
    START_TIME=$(date +%s)
    TASK_RESPONSE=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && curl -s -X POST 'http://localhost:8001/api/v1/transcription/start' \
        -H 'Content-Type: application/json' \
        -d '{
            \"file_path\": \"uploads/$filename\",
            \"model\": \"$MODEL\",
            \"language\": \"th\"
        }'")
    
    TASK_ID=$(echo "$TASK_RESPONSE" | grep -o '"task_id":"[^"]*' | cut -d'"' -f4)
    
    if [ -z "$TASK_ID" ]; then
        print_error "   ❌ Failed to start transcription"
        echo "   Response: $TASK_RESPONSE"
        RESULTS+=("$filename:FAILED:Start failed")
        continue
    fi
    
    print_success "   ✅ Task ID: $TASK_ID"
    
    # Monitor progress
    WAIT_TIME=0
    CHECK_INTERVAL=2
    LAST_PROGRESS=0
    LAST_STATUS=""
    COMPLETED=false
    
    while [ $WAIT_TIME -lt $TIMEOUT ]; do
        sleep $CHECK_INTERVAL
        WAIT_TIME=$((WAIT_TIME + CHECK_INTERVAL))
        
        # ตรวจสอบ progress
        STATUS_RESPONSE=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && curl -s 'http://localhost:8001/api/v1/transcription/status/$TASK_ID'")
        STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
        PROGRESS=$(echo "$STATUS_RESPONSE" | grep -o '"progress":[0-9]*' | cut -d':' -f2)
        
        if [ -z "$PROGRESS" ]; then
            PROGRESS=0
        fi
        
        # แสดง progress เมื่อมีการเปลี่ยนแปลง
        if [ "$PROGRESS" != "$LAST_PROGRESS" ] || [ "$STATUS" != "$LAST_STATUS" ]; then
            printf "\r   ⏳ Progress: %3d%% | Status: %-15s | Elapsed: %3ds" \
                "$PROGRESS" "$STATUS" "$WAIT_TIME"
            LAST_PROGRESS=$PROGRESS
            LAST_STATUS=$STATUS
        fi
        
        if [ "$STATUS" = "completed" ]; then
            COMPLETED=true
            break
        elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "cancelled" ]; then
            echo ""
            print_error "   ❌ Transcription failed: $STATUS"
            RESULTS+=("$filename:FAILED:$STATUS")
            continue 2
        fi
    done
    
    END_TIME=$(date +%s)
    TOTAL_TIME=$((END_TIME - START_TIME))
    
    echo ""
    
    if [ "$COMPLETED" = true ]; then
        # คำนวณ speed
        if [ "$EXPECTED_DURATION" -gt 0 ]; then
            SPEEDUP=$(echo "scale=2; $EXPECTED_DURATION / $TOTAL_TIME" | bc 2>/dev/null || echo "N/A")
            print_success "   ✅ Completed in ${TOTAL_TIME}s (${SPEEDUP}x real-time)"
        else
            print_success "   ✅ Completed in ${TOTAL_TIME}s"
        fi
        
        RESULTS+=("$filename:SUCCESS:${TOTAL_TIME}s")
    else
        print_error "   ❌ TIMEOUT: Not completed in ${TIMEOUT}s"
        RESULTS+=("$filename:TIMEOUT:${TIMEOUT}s")
    fi
    
    # รอสักครู่ก่อนทดสอบวิดีโอถัดไป
    sleep 2
done

# Summary
print_header ""
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Test Summary"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SUCCESS_COUNT=0
FAILED_COUNT=0
TIMEOUT_COUNT=0

for result in "${RESULTS[@]}"; do
    IFS=':' read -r filename status time <<< "$result"
    case "$status" in
        SUCCESS)
            print_success "   ✅ $filename: $status ($time)"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
            ;;
        TIMEOUT)
            print_warning "   ⚠️  $filename: $status ($time)"
            TIMEOUT_COUNT=$((TIMEOUT_COUNT + 1))
            ;;
        *)
            print_error "   ❌ $filename: $status ($time)"
            FAILED_COUNT=$((FAILED_COUNT + 1))
            ;;
    esac
done

echo ""
print_status "Total: ${#RESULTS[@]} videos"
print_success "   Success: $SUCCESS_COUNT"
print_warning "   Timeout: $TIMEOUT_COUNT"
print_error "   Failed: $FAILED_COUNT"
echo ""

if [ $TIMEOUT_COUNT -gt 0 ] || [ $FAILED_COUNT -gt 0 ]; then
    print_warning "⚠️  Some tests failed or timed out"
    print_status "💡 Check logs: tail -f /tmp/video-worker.log"
    exit 1
else
    print_success "✅ All tests passed!"
fi

