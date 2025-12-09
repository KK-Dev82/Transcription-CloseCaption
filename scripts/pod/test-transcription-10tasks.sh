#!/bin/bash
# Script สำหรับทดสอบ Transcription 10 Tasks
# วัดเวลาของแต่ละ Task และเวลารวม
#
# วิธีใช้งาน:
#   bash scripts/pod/test-transcription-10tasks.sh <video-path> [model] [gpu-name]
#
# ตัวอย่าง:
#   bash scripts/pod/test-transcription-10tasks.sh uploads/v10-1.mp4 medium rtx4000

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
cd "$PROJECT_ROOT"

# Parse arguments
VIDEO_PATH="${1:-}"
MODEL="${2:-medium}"
GPU_NAME="${3:-auto}"

if [ -z "$VIDEO_PATH" ]; then
    print_error "❌ Error: Video path is required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/test-transcription-10tasks.sh <video-path> [model] [gpu-name]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pod/test-transcription-10tasks.sh uploads/v10-1.mp4 medium rtx4000"
    exit 1
fi

# Check if video exists
if [ ! -f "$VIDEO_PATH" ]; then
    print_error "❌ Video file not found: $VIDEO_PATH"
    exit 1
fi

# Get absolute path
ABSOLUTE_VIDEO_PATH="$(cd "$(dirname "$VIDEO_PATH")" && pwd)/$(basename "$VIDEO_PATH")"
FILE_NAME="$(basename "$VIDEO_PATH")"

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

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Transcription Test: 10 Tasks"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_status "GPU: $GPU_NAME"
print_status "Model: $MODEL"
print_status "Video: $VIDEO_PATH"
print_status "API Port: $API_PORT"
echo ""

# Get video duration
print_status "Getting video duration..."
if command -v ffprobe > /dev/null 2>&1; then
    DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$ABSOLUTE_VIDEO_PATH" 2>/dev/null || echo "0")
    if [ -z "$DURATION" ] || [ "$DURATION" = "0" ]; then
        print_warning "⚠️  Could not get video duration, using 0"
        DURATION=0
    else
        DURATION_INT=$(python3 -c "print(int($DURATION))" 2>/dev/null || echo "0")
        print_success "✅ Video duration: ${DURATION_INT}s"
    fi
else
    print_warning "⚠️  ffprobe not found, cannot get video duration"
    DURATION=0
    DURATION_INT=0
fi
echo ""

# Get VRAM before
VRAM_BEFORE=0
if command -v nvidia-smi &> /dev/null; then
    VRAM_BEFORE=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -n1)
    print_status "VRAM Before: ${VRAM_BEFORE} MB"
fi

# Start time
START_TIME=$(date +%s.%N)

# Submit 10 tasks
print_status "Submitting 10 transcription tasks..."
echo ""

TASK_IDS=()
TASK_START_TIMES=()

for i in $(seq 1 10); do
    print_status "[$i/10] Submitting task..."
    
    TASK_START=$(date +%s.%N)
    TASK_RESPONSE=$(curl -s -X POST "http://localhost:${API_PORT}/transcribe/" \
        -H "Content-Type: application/json" \
        -d "{
            \"file_path\": \"$ABSOLUTE_VIDEO_PATH\",
            \"file_name\": \"$FILE_NAME\",
            \"language\": \"th\",
            \"model_size\": \"$MODEL\"
        }" 2>&1)
    
    TASK_ID=$(echo "$TASK_RESPONSE" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4 || echo "")
    
    if [ -n "$TASK_ID" ]; then
        TASK_IDS+=("$TASK_ID")
        TASK_START_TIMES+=("$TASK_START")
        print_success "   ✅ Task $i: $TASK_ID"
    else
        print_error "   ❌ Task $i: Failed to submit"
        RESPONSE_PREVIEW=$(echo "$TASK_RESPONSE" | head -c 200)
        print_status "   Response: $RESPONSE_PREVIEW..."
    fi
    
    sleep 0.1
done

echo ""
print_status "Submitted: ${#TASK_IDS[@]}/10 tasks"
echo ""

if [ ${#TASK_IDS[@]} -eq 0 ]; then
    print_error "❌ No tasks were submitted successfully"
    exit 1
fi

# Monitor tasks and measure individual times
print_status "Monitoring tasks and measuring individual task times..."
echo ""

TASK_RESULTS=()
COMPLETED_COUNT=0

# Function to check task status
check_task_status() {
    local task_id=$1
    curl -s "http://localhost:${API_PORT}/transcribe/$task_id" 2>/dev/null || echo ""
}

# Wait for all tasks to complete
while [ $COMPLETED_COUNT -lt ${#TASK_IDS[@]} ]; do
    sleep 2
    
    COMPLETED_COUNT=0
    
    for i in "${!TASK_IDS[@]}"; do
        task_id="${TASK_IDS[$i]}"
        task_start="${TASK_START_TIMES[$i]}"
        
        # Skip if already completed
        if echo "${TASK_RESULTS[@]}" | grep -q "$task_id"; then
            COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
            continue
        fi
        
        TASK_STATUS=$(check_task_status "$task_id")
        
        if [ -z "$TASK_STATUS" ]; then
            continue
        fi
        
        STATUS=$(echo "$TASK_STATUS" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
        
        if [ "$STATUS" = "completed" ]; then
            TASK_END=$(date +%s.%N)
            
            # Calculate task duration
            if command -v python3 > /dev/null 2>&1; then
                TASK_DURATION=$(python3 -c "print($TASK_END - $task_start)" 2>/dev/null || echo "0")
            elif command -v awk > /dev/null 2>&1; then
                TASK_DURATION=$(awk "BEGIN {print $TASK_END - $task_start}")
            else
                TASK_DURATION=0
            fi
            
            # Get task details
            CREATED_AT=$(echo "$TASK_STATUS" | grep -o '"created_at":"[^"]*"' | cut -d'"' -f4 || echo "")
            COMPLETED_AT=$(echo "$TASK_STATUS" | grep -o '"completed_at":"[^"]*"' | cut -d'"' -f4 || echo "")
            FULL_TEXT=$(echo "$TASK_STATUS" | grep -o '"full_text":"[^"]*"' | cut -d'"' -f4 || echo "")
            TEXT_LEN=${#FULL_TEXT}
            
            TASK_RESULTS+=("$task_id|$TASK_DURATION|$TEXT_LEN|$CREATED_AT|$COMPLETED_AT")
            COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
            
            print_success "✅ Task $((i+1)) completed in ${TASK_DURATION}s (text: ${TEXT_LEN} chars)"
        elif [ "$STATUS" = "failed" ]; then
            TASK_RESULTS+=("$task_id|failed|0||")
            COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
            print_error "❌ Task $((i+1)) failed"
        fi
    done
    
    if [ $COMPLETED_COUNT -lt ${#TASK_IDS[@]} ]; then
        print_status "Progress: Completed=$COMPLETED_COUNT/${#TASK_IDS[@]}"
    fi
done

# End time
END_TIME=$(date +%s.%N)

# Calculate total elapsed time
if command -v python3 > /dev/null 2>&1; then
    TOTAL_ELAPSED=$(python3 -c "print($END_TIME - $START_TIME)" 2>/dev/null || echo "0")
elif command -v awk > /dev/null 2>&1; then
    TOTAL_ELAPSED=$(awk "BEGIN {print $END_TIME - $START_TIME}")
else
    TOTAL_ELAPSED=0
fi

# Calculate average task time
SUCCESSFUL_TASKS=0
TOTAL_TASK_TIME=0

for result in "${TASK_RESULTS[@]}"; do
    IFS='|' read -r task_id task_duration text_len created_at completed_at <<< "$result"
    if [ "$task_duration" != "failed" ] && [ -n "$task_duration" ]; then
        SUCCESSFUL_TASKS=$((SUCCESSFUL_TASKS + 1))
        if command -v python3 > /dev/null 2>&1; then
            TOTAL_TASK_TIME=$(python3 -c "print($TOTAL_TASK_TIME + $task_duration)" 2>/dev/null || echo "$TOTAL_TASK_TIME")
        elif command -v awk > /dev/null 2>&1; then
            TOTAL_TASK_TIME=$(awk "BEGIN {print $TOTAL_TASK_TIME + $task_duration}")
        fi
    fi
done

if [ $SUCCESSFUL_TASKS -gt 0 ]; then
    if command -v python3 > /dev/null 2>&1; then
        AVG_TASK_TIME=$(python3 -c "print($TOTAL_TASK_TIME / $SUCCESSFUL_TASKS)" 2>/dev/null || echo "0")
    elif command -v awk > /dev/null 2>&1; then
        AVG_TASK_TIME=$(awk "BEGIN {print $TOTAL_TASK_TIME / $SUCCESSFUL_TASKS}")
    else
        AVG_TASK_TIME=0
    fi
else
    AVG_TASK_TIME=0
fi

# Get VRAM after
VRAM_AFTER=0
if command -v nvidia-smi &> /dev/null; then
    VRAM_AFTER=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -n1)
fi

VRAM_USED=$((VRAM_AFTER - VRAM_BEFORE))

# Create results directory
RESULTS_DIR="$PROJECT_ROOT/docs/RunPod-Z2/Benchmark"
mkdir -p "$RESULTS_DIR"

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Save results to JSON
RESULT_FILE="$RESULTS_DIR/transcription-test-${GPU_NAME}-${MODEL}-10tasks-${TIMESTAMP}.json"

# Build task details JSON
TASK_DETAILS_JSON="["
for result in "${TASK_RESULTS[@]}"; do
    IFS='|' read -r task_id task_duration text_len created_at completed_at <<< "$result"
    if [ "$TASK_DETAILS_JSON" != "[" ]; then
        TASK_DETAILS_JSON+=","
    fi
    TASK_DETAILS_JSON+="{\"task_id\":\"$task_id\",\"duration_seconds\":\"$task_duration\",\"text_length\":$text_len,\"created_at\":\"$created_at\",\"completed_at\":\"$completed_at\"}"
done
TASK_DETAILS_JSON+="]"

cat > "$RESULT_FILE" << EOF
{
  "test": {
    "timestamp": "$TIMESTAMP",
    "gpu_name": "$GPU_NAME",
    "model": "$MODEL",
    "video_path": "$VIDEO_PATH",
    "video_duration_seconds": $DURATION_INT,
    "num_tasks": ${#TASK_IDS[@]},
    "task_ids": $(IFS=','; echo "[$(printf '"%s"' "${TASK_IDS[@]}")]")
  },
  "performance": {
    "total_elapsed_time_seconds": "$TOTAL_ELAPSED",
    "average_task_time_seconds": "$AVG_TASK_TIME",
    "successful_tasks": $SUCCESSFUL_TASKS,
    "failed_tasks": $((10 - SUCCESSFUL_TASKS))
  },
  "resources": {
    "vram_before_mb": $VRAM_BEFORE,
    "vram_after_mb": $VRAM_AFTER,
    "vram_used_mb": $VRAM_USED
  },
  "task_details": $TASK_DETAILS_JSON
}
EOF

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Transcription Test Results"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

print_success "✅ Test completed!"
echo ""

print_status "Performance Metrics:"
echo "  ⏱️  Total Elapsed Time: ${TOTAL_ELAPSED}s"
echo "  📊 Successful Tasks: $SUCCESSFUL_TASKS/10"
if [ "$AVG_TASK_TIME" != "0" ]; then
    echo "  ⚡ Average Task Time: ${AVG_TASK_TIME}s"
fi
echo ""

print_status "Resource Usage:"
echo "  💾 VRAM Used: ${VRAM_USED} MB"
echo "  💾 VRAM After: ${VRAM_AFTER} MB"
echo ""

print_status "Individual Task Times:"
for i in "${!TASK_RESULTS[@]}"; do
    result="${TASK_RESULTS[$i]}"
    IFS='|' read -r task_id task_duration text_len created_at completed_at <<< "$result"
    if [ "$task_duration" != "failed" ]; then
        echo "  Task $((i+1)): ${task_duration}s (text: ${text_len} chars)"
    else
        echo "  Task $((i+1)): Failed"
    fi
done
echo ""

print_success "✅ Results saved to: $RESULT_FILE"
echo ""

