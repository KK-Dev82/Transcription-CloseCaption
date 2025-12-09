#!/bin/bash
# Script สำหรับทดสอบการ Transcription แบบเพิ่มทีละ Task (1, 2, 3... 10)
# เพื่อตรวจสอบว่า prefetch_count ทำงานถูกต้อง
#
# วิธีใช้งาน:
#   bash scripts/pod/test-transcription-incremental.sh <video-path> [model] [gpu-name]
#
# ตัวอย่าง:
#   bash scripts/pod/test-transcription-incremental.sh uploads/v10-1.mp4 medium rtx4080

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

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BENCHMARK_DIR="$PROJECT_ROOT/docs/RunPod-Z2/Benchmark"
mkdir -p "$BENCHMARK_DIR"

# Parse arguments
VIDEO_PATH="${1:-}"
MODEL="${2:-medium}"
GPU_NAME="${3:-auto}"

if [ -z "$VIDEO_PATH" ]; then
    print_error "❌ Error: Video path is required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/test-transcription-incremental.sh <video-path> [model] [gpu-name]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pod/test-transcription-incremental.sh uploads/v10-1.mp4 medium rtx4080"
    exit 1
fi

# Resolve absolute path for video
ABSOLUTE_VIDEO_PATH=$(realpath "$VIDEO_PATH")
FILE_NAME=$(basename "$ABSOLUTE_VIDEO_PATH")

print_header "🚀 Starting Incremental Transcription Test"
print_status "Video: $FILE_NAME"
print_status "Model: $MODEL"
print_status "GPU: $GPU_NAME"
echo ""

# Detect API port (8001 or 8010)
API_PORT=""
API_HEALTH_8001=$(curl -s http://localhost:8001/health 2>/dev/null || echo "")
if echo "$API_HEALTH_8001" | grep -q '"status":"healthy"'; then
    API_PORT=8001
    print_success "✅ API found on port 8001"
else
    API_HEALTH_8010=$(curl -s http://localhost:8010/health 2>/dev/null || echo "")
    if echo "$API_HEALTH_8010" | grep -q '"status":"healthy"'; then
        API_PORT=8010
        print_success "✅ API found on port 8010"
    else
        print_error "❌ API not found on port 8001 or 8010"
        exit 1
    fi
fi
print_status "Using API port: $API_PORT"
echo ""

# Test from 1 to 10 tasks
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
RESULT_FILE="$BENCHMARK_DIR/incremental-transcription-test-${GPU_NAME}-${MODEL}-${TIMESTAMP}.md"

{
    echo "# Incremental Transcription Test Results - $GPU_NAME ($MODEL)"
    echo ""
    echo "**Date**: $(date)"
    echo "**GPU**: $GPU_NAME"
    echo "**Model**: $MODEL"
    echo "**Video**: $FILE_NAME"
    echo ""
    echo "## 📊 Test Results"
    echo ""
    echo "| Tasks | Submitted | Completed | Avg Time (s) | Status |"
    echo "|-------|-----------|-----------|--------------|--------|"
} | tee "$RESULT_FILE"

for NUM_TASKS in {1..10}; do
    print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_header "Testing with $NUM_TASKS task(s)"
    print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Array to store task IDs
    TASK_IDS=()
    TASK_START_TIMES=()
    TASK_END_TIMES=()
    
    # Submit tasks
    print_status "Submitting $NUM_TASKS transcription task(s)..."
    START_SUBMIT_TIME=$(date +%s.%N)
    
    for i in $(seq 1 $NUM_TASKS); do
        print_status "[$i/$NUM_TASKS] Submitting task..."
        
        TASK_RESPONSE=$(curl -s -X POST "http://localhost:${API_PORT}/transcribe/" \
            -H "Content-Type: application/json" \
            -d "{
                \"file_path\": \"$ABSOLUTE_VIDEO_PATH\",
                \"file_name\": \"$FILE_NAME\",
                \"language\": \"th\",
                \"model_size\": \"$MODEL\"
            }")
        
        TASK_ID=$(echo "$TASK_RESPONSE" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4 || echo "")
        
        if [ -n "$TASK_ID" ]; then
            TASK_IDS+=("$TASK_ID")
            TASK_START_TIMES+=("$(date +%s.%N)")
            print_success "   ✅ Task $i submitted: $TASK_ID"
        else
            print_error "   ❌ Task $i: Failed to submit"
            RESPONSE_PREVIEW=$(echo "$TASK_RESPONSE" | head -c 200)
            print_status "   Response preview: $RESPONSE_PREVIEW..."
            continue
        fi
        sleep 0.1
    done
    
    END_SUBMIT_TIME=$(date +%s.%N)
    SUBMIT_ELAPSED=$(python3 -c "print($END_SUBMIT_TIME - $START_SUBMIT_TIME)")
    print_success "✅ All $NUM_TASKS task(s) submitted in ${SUBMIT_ELAPSED:.2f} seconds."
    echo ""
    
    # Monitor tasks
    print_status "Monitoring $NUM_TASKS task(s)..."
    
    COMPLETED_COUNT=0
    MONITOR_START_TIME=$(date +%s.%N)
    MAX_WAIT_TIME=600  # 10 minutes max wait
    ELAPSED_TIME=0
    
    while [ $COMPLETED_COUNT -lt $NUM_TASKS ] && [ $ELAPSED_TIME -lt $MAX_WAIT_TIME ]; do
        sleep 2
        COMPLETED_COUNT=0
        CURRENT_TIME=$(date +%s.%N)
        ELAPSED_TIME=$(python3 -c "print($CURRENT_TIME - $MONITOR_START_TIME)")
        
        for i in "${!TASK_IDS[@]}"; do
            task_id="${TASK_IDS[$i]}"
            
            # Skip if already completed
            if [ -n "${TASK_END_TIMES[$i]}" ]; then
                COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
                continue
            fi
            
            TASK_STATUS_RESPONSE=$(curl -s "http://localhost:${API_PORT}/transcribe/$task_id" 2>/dev/null || echo "")
            STATUS=$(echo "$TASK_STATUS_RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
            
            if [ "$STATUS" = "completed" ]; then
                TASK_END_TIMES[$i]="$(date +%s.%N)"
                COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
                print_success "   ✅ Task $task_id completed. Progress: $COMPLETED_COUNT/$NUM_TASKS"
            elif [ "$STATUS" = "failed" ]; then
                print_error "   ❌ Task $task_id failed!"
                TASK_END_TIMES[$i]="$(date +%s.%N)"
                COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
            fi
        done
        print_status "Progress: Completed=$COMPLETED_COUNT/$NUM_TASKS (Elapsed: ${ELAPSED_TIME:.0f}s)"
    done
    
    MONITOR_END_TIME=$(date +%s.%N)
    MONITOR_ELAPSED=$(python3 -c "print($MONITOR_END_TIME - $MONITOR_START_TIME)")
    
    # Calculate average task time
    TOTAL_TASK_PROCESSING_TIME=0
    VALID_TASKS=0
    for i in "${!TASK_IDS[@]}"; do
        start_time="${TASK_START_TIMES[$i]}"
        end_time="${TASK_END_TIMES[$i]}"
        
        if [ -n "$start_time" ] && [ -n "$end_time" ]; then
            TASK_ELAPSED=$(python3 -c "print($end_time - $start_time)")
            TOTAL_TASK_PROCESSING_TIME=$(python3 -c "print($TOTAL_TASK_PROCESSING_TIME + $TASK_ELAPSED)")
            VALID_TASKS=$((VALID_TASKS + 1))
        fi
    done
    
    if [ $VALID_TASKS -gt 0 ]; then
        AVG_TASK_PROCESSING_TIME=$(python3 -c "print($TOTAL_TASK_PROCESSING_TIME / $VALID_TASKS)")
    else
        AVG_TASK_PROCESSING_TIME=0
    fi
    
    # Determine status
    if [ $COMPLETED_COUNT -eq $NUM_TASKS ]; then
        STATUS_ICON="✅"
        STATUS_TEXT="PASS"
    elif [ $ELAPSED_TIME -ge $MAX_WAIT_TIME ]; then
        STATUS_ICON="⏱️"
        STATUS_TEXT="TIMEOUT"
    else
        STATUS_ICON="❌"
        STATUS_TEXT="FAIL"
    fi
    
    print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_status "Summary for $NUM_TASKS task(s):"
    print_status "  Submitted: $NUM_TASKS"
    print_status "  Completed: $COMPLETED_COUNT"
    print_status "  Average time: ${AVG_TASK_PROCESSING_TIME:.2f}s"
    print_status "  Total elapsed: ${MONITOR_ELAPSED:.2f}s"
    print_status "  Status: $STATUS_ICON $STATUS_TEXT"
    print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Append to result file
    {
        echo "| $NUM_TASKS | $NUM_TASKS | $COMPLETED_COUNT | ${AVG_TASK_PROCESSING_TIME:.2f} | $STATUS_ICON $STATUS_TEXT |"
    } >> "$RESULT_FILE"
    
    # Wait a bit before next test
    if [ $NUM_TASKS -lt 10 ]; then
        print_status "Waiting 10 seconds before next test..."
        sleep 10
        echo ""
    fi
done

print_success "✅ All incremental tests completed!"
print_success "📄 Results saved to: $RESULT_FILE"
echo ""

