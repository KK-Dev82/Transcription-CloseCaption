#!/bin/bash
# Script สำหรับทดสอบการ Transcription แบบ Incremental (5, 10, 15 tasks)
# วัดเวลา Queue, Task Processing, และ Total Time
# เก็บ Fulltext (corrected text) ของทุก task
#
# วิธีใช้งาน:
#   bash scripts/pod/test-transcription-5-10-15.sh <video-path> [model] [gpu-name]
#
# ตัวอย่าง:
#   bash scripts/pod/test-transcription-5-10-15.sh uploads/v10-1.mp4 medium rtx4080

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
    echo "  bash scripts/pod/test-transcription-5-10-15.sh <video-path> [model] [gpu-name]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pod/test-transcription-5-10-15.sh uploads/v10-1.mp4 medium rtx4080"
    exit 1
fi

# Resolve absolute path for video
ABSOLUTE_VIDEO_PATH=$(realpath "$VIDEO_PATH" 2>/dev/null || echo "$VIDEO_PATH")
FILE_NAME=$(basename "$ABSOLUTE_VIDEO_PATH")

print_header "🚀 Starting Incremental Transcription Test (5, 10, 15 tasks)"
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

# Test configurations: 5, 10, 15 tasks
TEST_CONFIGS=(5 10 15)
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
RESULT_FILE="$BENCHMARK_DIR/incremental-test-${GPU_NAME}-${MODEL}-${TIMESTAMP}.md"
FULLTEXT_FILE="$BENCHMARK_DIR/incremental-test-${GPU_NAME}-${MODEL}-${TIMESTAMP}-fulltext.md"

# Initialize result files
{
    echo "# Incremental Transcription Test Results - $GPU_NAME ($MODEL)"
    echo ""
    echo "**Date**: $(date)"
    echo "**GPU**: $GPU_NAME"
    echo "**Model**: $MODEL"
    echo "**Video**: $FILE_NAME"
    echo ""
    echo "## 📊 Test Summary"
    echo ""
    echo "| Tasks | Submitted | Completed | Avg Queue Time | Avg Task Time | Total Time | Status |"
    echo "|-------|-----------|-----------|----------------|---------------|------------|--------|"
} | tee "$RESULT_FILE"

{
    echo "# Fulltext (Corrected Text) - $GPU_NAME ($MODEL)"
    echo ""
    echo "**Date**: $(date)"
    echo "**GPU**: $GPU_NAME"
    echo "**Model**: $MODEL"
    echo "**Video**: $FILE_NAME"
    echo ""
} > "$FULLTEXT_FILE"

# Run tests for each configuration
for NUM_TASKS in "${TEST_CONFIGS[@]}"; do
    print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_header "Testing with $NUM_TASKS task(s)"
    print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Array to store task data
    TASK_IDS=()
    TASK_START_TIMES=()
    TASK_END_TIMES=()
    TASK_QUEUE_START_TIMES=()
    TASK_PROCESSING_START_TIMES=()
    TASK_FULL_TEXTS=()
    
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
    MAX_WAIT_TIME=1800  # 30 minutes max wait
    ELAPSED_TIME=0
    
    while [ $COMPLETED_COUNT -lt $NUM_TASKS ] && [ $ELAPSED_TIME -lt $MAX_WAIT_TIME ]; do
        sleep 3
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
            
            # Check if task started processing (moved from pending/routing to processing/transcribing)
            if [ -z "${TASK_QUEUE_START_TIMES[$i]}" ] && [ "$STATUS" != "pending" ] && [ "$STATUS" != "routing" ] && [ "$STATUS" != "routing_to_transcription" ]; then
                TASK_QUEUE_START_TIMES[$i]="${TASK_START_TIMES[$i]}"
                TASK_PROCESSING_START_TIMES[$i]="$(date +%s.%N)"
            fi
            
            if [ "$STATUS" = "completed" ]; then
                TASK_END_TIMES[$i]="$(date +%s.%N)"
                COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
                
                # Extract fulltext (corrected_text or full_text)
                FULL_TEXT=$(echo "$TASK_STATUS_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('corrected_text', d.get('full_text', '')))" 2>/dev/null || echo "")
                TASK_FULL_TEXTS[$i]="$FULL_TEXT"
                
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
    
    # Calculate statistics
    TOTAL_QUEUE_TIME=0
    TOTAL_TASK_TIME=0
    TOTAL_PROCESSING_TIME=0
    VALID_TASKS=0
    
    for i in "${!TASK_IDS[@]}"; do
        start_time="${TASK_START_TIMES[$i]}"
        queue_start_time="${TASK_QUEUE_START_TIMES[$i]:-$start_time}"
        processing_start_time="${TASK_PROCESSING_START_TIMES[$i]:-$start_time}"
        end_time="${TASK_END_TIMES[$i]}"
        
        if [ -n "$start_time" ] && [ -n "$end_time" ]; then
            TOTAL_TIME=$(python3 -c "print($end_time - $start_time)")
            QUEUE_TIME=$(python3 -c "print($processing_start_time - $queue_start_time)")
            PROCESSING_TIME=$(python3 -c "print($end_time - $processing_start_time)")
            
            TOTAL_QUEUE_TIME=$(python3 -c "print($TOTAL_QUEUE_TIME + $QUEUE_TIME)")
            TOTAL_PROCESSING_TIME=$(python3 -c "print($TOTAL_PROCESSING_TIME + $PROCESSING_TIME)")
            TOTAL_TASK_TIME=$(python3 -c "print($TOTAL_TASK_TIME + $TOTAL_TIME)")
            VALID_TASKS=$((VALID_TASKS + 1))
        fi
    done
    
    if [ $VALID_TASKS -gt 0 ]; then
        AVG_QUEUE_TIME=$(python3 -c "print($TOTAL_QUEUE_TIME / $VALID_TASKS)")
        AVG_PROCESSING_TIME=$(python3 -c "print($TOTAL_PROCESSING_TIME / $VALID_TASKS)")
        AVG_TASK_TIME=$(python3 -c "print($TOTAL_TASK_TIME / $VALID_TASKS)")
    else
        AVG_QUEUE_TIME=0
        AVG_PROCESSING_TIME=0
        AVG_TASK_TIME=0
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
    print_status "  Average Queue Time: ${AVG_QUEUE_TIME:.2f}s"
    print_status "  Average Processing Time: ${AVG_PROCESSING_TIME:.2f}s"
    print_status "  Average Total Time: ${AVG_TASK_TIME:.2f}s"
    print_status "  Total Elapsed: ${MONITOR_ELAPSED:.2f}s"
    print_status "  Status: $STATUS_ICON $STATUS_TEXT"
    print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Append to result file
    {
        echo "| $NUM_TASKS | $NUM_TASKS | $COMPLETED_COUNT | ${AVG_QUEUE_TIME:.2f}s | ${AVG_PROCESSING_TIME:.2f}s | ${MONITOR_ELAPSED:.2f}s | $STATUS_ICON $STATUS_TEXT |"
    } >> "$RESULT_FILE"
    
    # Append fulltext to fulltext file
    {
        echo "## 📝 Fulltext for $NUM_TASKS Tasks"
        echo ""
        for i in "${!TASK_IDS[@]}"; do
            task_id="${TASK_IDS[$i]}"
            full_text="${TASK_FULL_TEXTS[$i]}"
            
            echo "### Task ${task_id:0:8}... (Task $((i+1))/$NUM_TASKS)"
            echo ""
            if [ -n "$full_text" ] && [ ${#full_text} -gt 0 ]; then
                echo "\`\`\`"
                echo "$full_text"
                echo "\`\`\`"
                echo ""
                echo "**Text Length**: ${#full_text} characters"
            else
                echo "*⚠️ No text available*"
            fi
            echo ""
            echo "---"
            echo ""
        done
    } >> "$FULLTEXT_FILE"
    
    # Wait before next test
    if [ $NUM_TASKS -lt 15 ]; then
        print_status "Waiting 15 seconds before next test..."
        sleep 15
        echo ""
    fi
done

# Final summary
{
    echo ""
    echo "## 📋 Detailed Results"
    echo ""
    echo "### Test Configuration"
    echo "- **Video**: $FILE_NAME"
    echo "- **Model**: $MODEL"
    echo "- **GPU**: $GPU_NAME"
    echo "- **Test Configurations**: 5, 10, 15 tasks"
    echo ""
    echo "### Notes"
    echo "- Queue Time: Time from task submission to start of processing"
    echo "- Processing Time: Time from start of processing to completion"
    echo "- Total Time: Total time from submission to completion"
    echo ""
} >> "$RESULT_FILE"

print_success "✅ All incremental tests completed!"
print_success "📄 Results saved to: $RESULT_FILE"
print_success "📝 Fulltext saved to: $FULLTEXT_FILE"
echo ""

