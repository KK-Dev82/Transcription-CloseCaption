#!/bin/bash
# Script สำหรับรัน Benchmark แบบ Concurrent (หลาย Tasks พร้อมกัน)
# ใช้ Video เดียว แต่ส่ง Transcription Tasks หลายตัวพร้อมกัน
#
# วิธีใช้งาน:
#   bash scripts/pod/run-benchmark-concurrent.sh <video-path> [num-tasks] [model] [gpu-name]
#
# ตัวอย่าง:
#   bash scripts/pod/run-benchmark-concurrent.sh uploads/v10-1.mp4 10 medium rtx4080
#   bash scripts/pod/run-benchmark-concurrent.sh uploads/v10-1.mp4 5 large-v3 rtx5080

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
BENCHMARK_DIR="$PROJECT_ROOT/benchmark-results"
mkdir -p "$BENCHMARK_DIR"

# Parse arguments
VIDEO_PATH="${1:-}"
NUM_TASKS="${2:-10}"
MODEL="${3:-medium}"
GPU_NAME="${4:-auto}"

if [ -z "$VIDEO_PATH" ]; then
    print_error "❌ Error: Video path is required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/run-benchmark-concurrent.sh <video-path> [num-tasks] [model] [gpu-name]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pod/run-benchmark-concurrent.sh uploads/v10-1.mp4 10 medium rtx4080"
    echo "  bash scripts/pod/run-benchmark-concurrent.sh uploads/v10-1.mp4 5 large-v3 rtx5080"
    exit 1
fi

if [ ! -f "$VIDEO_PATH" ]; then
    print_error "❌ Error: Video file not found: $VIDEO_PATH"
    exit 1
fi

# Detect GPU if not specified
if [ "$GPU_NAME" = "auto" ]; then
    if command -v nvidia-smi &> /dev/null; then
        GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1 | tr ' ' '_' | tr -d '()')
        print_status "Auto-detected GPU: $GPU_NAME"
    else
        print_warning "⚠️  nvidia-smi not found, using 'unknown'"
        GPU_NAME="unknown"
    fi
fi

# Get video info
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Concurrent Benchmark: $GPU_NAME"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

print_status "Video: $VIDEO_PATH"
print_status "Model: $MODEL"
print_status "GPU: $GPU_NAME"
print_status "Concurrent Tasks: $NUM_TASKS"
echo ""

# Get video duration
if command -v ffprobe &> /dev/null; then
    DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO_PATH" 2>/dev/null || echo "0")
    DURATION_INT=$(echo "$DURATION" | cut -d. -f1)
    print_status "Video Duration: ${DURATION_INT}s ($(echo "scale=2; $DURATION_INT/60" | bc) minutes)"
else
    print_warning "⚠️  ffprobe not found, cannot get video duration"
    DURATION_INT=0
fi
echo ""

# Get GPU info
print_status "Collecting GPU information..."
if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv,noheader | head -n1)
    print_status "GPU Info: $GPU_INFO"
    
    # Get VRAM before
    VRAM_BEFORE=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -n1)
    print_status "VRAM Before: ${VRAM_BEFORE} MB"
else
    print_warning "⚠️  nvidia-smi not found"
    VRAM_BEFORE=0
fi
echo ""

# Create result file
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RESULT_FILE="$BENCHMARK_DIR/concurrent-benchmark-${GPU_NAME}-${MODEL}-${NUM_TASKS}tasks-${TIMESTAMP}.json"
RESULT_LOG="$BENCHMARK_DIR/concurrent-benchmark-${GPU_NAME}-${MODEL}-${NUM_TASKS}tasks-${TIMESTAMP}.log"

print_status "Result file: $RESULT_FILE"
print_status "Log file: $RESULT_LOG"
echo ""

# Check if API is running
if ! curl -f http://localhost:8001/health > /dev/null 2>&1; then
    print_error "❌ Main API is not running"
    print_status "💡 Start API first: bash scripts/pod/start-pod.sh"
    exit 1
fi

# Get absolute video path
FILE_NAME=$(basename "$VIDEO_PATH")
ABSOLUTE_VIDEO_PATH=$(cd "$(dirname "$VIDEO_PATH")" && pwd)/$(basename "$VIDEO_PATH")

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Starting Concurrent Benchmark..."
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

START_TIME=$(date +%s.%N)

# Submit all tasks concurrently
print_status "Submitting $NUM_TASKS concurrent tasks..."
TASK_IDS=()
FAILED_TASKS=0

for i in $(seq 1 $NUM_TASKS); do
    print_status "[$i/$NUM_TASKS] Submitting task..."
    
    TASK_RESPONSE=$(curl -s -X POST "http://localhost:8001/transcribe/" \
        -H "Content-Type: application/json" \
        -d "{
            \"file_path\": \"$ABSOLUTE_VIDEO_PATH\",
            \"file_name\": \"$FILE_NAME\",
            \"language\": \"th\",
            \"model_size\": \"$MODEL\"
        }" 2>&1 | tee -a "$RESULT_LOG")
    
    TASK_ID=$(echo "$TASK_RESPONSE" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4 || echo "")
    
    if [ -n "$TASK_ID" ]; then
        TASK_IDS+=("$TASK_ID")
        print_success "   ✅ Task $i: $TASK_ID"
    else
        FAILED_TASKS=$((FAILED_TASKS + 1))
        print_error "   ❌ Task $i: Failed to submit"
        echo "   Response: $TASK_RESPONSE" | tee -a "$RESULT_LOG"
    fi
    
    # Small delay to avoid overwhelming the API
    sleep 0.1
done

echo ""
print_status "Submitted: ${#TASK_IDS[@]}/$NUM_TASKS tasks"
if [ $FAILED_TASKS -gt 0 ]; then
    print_warning "⚠️  Failed to submit: $FAILED_TASKS tasks"
fi
echo ""

if [ ${#TASK_IDS[@]} -eq 0 ]; then
    print_error "❌ No tasks were submitted successfully"
    exit 1
fi

# Monitor all tasks
print_status "Monitoring ${#TASK_IDS[@]} tasks..."
echo ""

COMPLETED_TASKS=0
FAILED_TASKS=0
TASK_RESULTS=()

# Function to check task status
check_task_status() {
    local task_id=$1
    curl -s "http://localhost:8001/transcribe/$task_id" 2>/dev/null || echo ""
}

# Monitor loop
while [ $COMPLETED_TASKS -lt ${#TASK_IDS[@]} ]; do
    sleep 2
    
    COMPLETED_COUNT=0
    FAILED_COUNT=0
    PROCESSING_COUNT=0
    
    for task_id in "${TASK_IDS[@]}"; do
        TASK_STATUS=$(check_task_status "$task_id")
        
        if [ -z "$TASK_STATUS" ]; then
            continue
        fi
        
        STATUS=$(echo "$TASK_STATUS" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
        PROGRESS=$(echo "$TASK_STATUS" | grep -o '"progress":[0-9.]*' | cut -d':' -f2 || echo "0")
        
        case "$STATUS" in
            "completed")
                COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
                # Store result if not already stored
                if ! echo "${TASK_RESULTS[@]}" | grep -q "$task_id"; then
                    TASK_RESULTS+=("$task_id|$STATUS")
                fi
                ;;
            "failed")
                FAILED_COUNT=$((FAILED_COUNT + 1))
                if ! echo "${TASK_RESULTS[@]}" | grep -q "$task_id"; then
                    TASK_RESULTS+=("$task_id|$STATUS")
                fi
                ;;
            *)
                PROCESSING_COUNT=$((PROCESSING_COUNT + 1))
                ;;
        esac
    done
    
    COMPLETED_TASKS=$COMPLETED_COUNT
    FAILED_TASKS=$FAILED_COUNT
    
    if [ $PROCESSING_COUNT -gt 0 ] || [ $COMPLETED_TASKS -lt ${#TASK_IDS[@]} ]; then
        print_status "Progress: Completed=$COMPLETED_TASKS, Processing=$PROCESSING_COUNT, Failed=$FAILED_TASKS / ${#TASK_IDS[@]}"
    fi
    
    # Get VRAM usage during processing
    if command -v nvidia-smi &> /dev/null && [ $PROCESSING_COUNT -gt 0 ]; then
        VRAM_CURRENT=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -n1)
        print_status "VRAM: ${VRAM_CURRENT} MB"
    fi
done

END_TIME=$(date +%s.%N)
ELAPSED=$(echo "$END_TIME - $START_TIME" | bc)

# Get VRAM after
if command -v nvidia-smi &> /dev/null; then
    VRAM_AFTER=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -n1)
    VRAM_USED=$((VRAM_AFTER - VRAM_BEFORE))
else
    VRAM_AFTER=0
    VRAM_USED=0
fi

echo ""
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Collecting Results..."
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Collect detailed results for each task
TASK_DETAILS=()
TOTAL_ELAPSED=0
SUCCESSFUL_TASKS=0

for task_id in "${TASK_IDS[@]}"; do
    TASK_STATUS=$(check_task_status "$task_id")
    STATUS=$(echo "$TASK_STATUS" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
    
    if [ "$STATUS" = "completed" ]; then
        # Get task details (created_at, updated_at, completed_at)
        CREATED_AT=$(echo "$TASK_STATUS" | grep -o '"created_at":"[^"]*"' | cut -d'"' -f4 || echo "")
        UPDATED_AT=$(echo "$TASK_STATUS" | grep -o '"updated_at":"[^"]*"' | cut -d'"' -f4 || echo "")
        COMPLETED_AT=$(echo "$TASK_STATUS" | grep -o '"completed_at":"[^"]*"' | cut -d'"' -f4 || echo "")
        
        # Calculate task duration if timestamps are available
        if [ -n "$CREATED_AT" ] && [ -n "$COMPLETED_AT" ]; then
            # Simple calculation (assuming ISO format)
            TASK_DETAILS+=("{\"task_id\":\"$task_id\",\"status\":\"$STATUS\",\"created_at\":\"$CREATED_AT\",\"completed_at\":\"$COMPLETED_AT\"}")
            SUCCESSFUL_TASKS=$((SUCCESSFUL_TASKS + 1))
        else
            TASK_DETAILS+=("{\"task_id\":\"$task_id\",\"status\":\"$STATUS\"}")
            SUCCESSFUL_TASKS=$((SUCCESSFUL_TASKS + 1))
        fi
    else
        TASK_DETAILS+=("{\"task_id\":\"$task_id\",\"status\":\"$STATUS\"}")
    fi
done

# Calculate metrics
ELAPSED_INT=$(echo "$ELAPSED" | cut -d. -f1)
ELAPSED_MS=$(echo "$ELAPSED * 1000" | bc | cut -d. -f1)

if [ "$DURATION_INT" -gt 0 ] && [ $SUCCESSFUL_TASKS -gt 0 ]; then
    # Average throughput per task
    AVG_TASK_TIME=$(echo "scale=2; $ELAPSED / $SUCCESSFUL_TASKS" | bc)
    TOTAL_PROCESSED_TIME=$(echo "scale=2; $DURATION_INT * $SUCCESSFUL_TASKS" | bc)
    OVERALL_SPEEDUP=$(echo "scale=2; $TOTAL_PROCESSED_TIME / $ELAPSED" | bc)
    TASKS_PER_HOUR=$(echo "scale=2; 3600 / $AVG_TASK_TIME" | bc)
else
    AVG_TASK_TIME="N/A"
    OVERALL_SPEEDUP="N/A"
    TASKS_PER_HOUR="N/A"
fi

# Save results to JSON
TASK_DETAILS_JSON=$(IFS=','; echo "[${TASK_DETAILS[*]}]")

cat > "$RESULT_FILE" << EOF
{
  "benchmark": {
    "timestamp": "$TIMESTAMP",
    "gpu_name": "$GPU_NAME",
    "model": "$MODEL",
    "video_path": "$VIDEO_PATH",
    "video_duration_seconds": $DURATION_INT,
    "num_concurrent_tasks": $NUM_TASKS,
    "task_ids": $(IFS=','; echo "[$(printf '"%s"' "${TASK_IDS[@]}")]")
  },
  "performance": {
    "total_elapsed_time_seconds": $ELAPSED,
    "total_elapsed_time_ms": $ELAPSED_MS,
    "avg_task_time_seconds": "$AVG_TASK_TIME",
    "overall_speedup": "$OVERALL_SPEEDUP",
    "tasks_per_hour": "$TASKS_PER_HOUR",
    "successful_tasks": $SUCCESSFUL_TASKS,
    "failed_tasks": $FAILED_TASKS
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
print_header "Concurrent Benchmark Results"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

print_success "✅ Benchmark completed!"
echo ""

print_status "Performance Metrics:"
echo "  ⏱️  Total Elapsed Time: ${ELAPSED}s"
echo "  📊 Successful Tasks: $SUCCESSFUL_TASKS/$NUM_TASKS"
if [ "$AVG_TASK_TIME" != "N/A" ]; then
    echo "  ⚡ Average Task Time: ${AVG_TASK_TIME}s"
    echo "  🚀 Overall Speedup: ${OVERALL_SPEEDUP}x"
    echo "  📈 Tasks Per Hour: ${TASKS_PER_HOUR}"
fi
echo ""

print_status "Resource Usage:"
echo "  💾 VRAM Used: ${VRAM_USED} MB"
echo "  💾 VRAM After: ${VRAM_AFTER} MB"
echo ""

print_success "✅ Results saved to: $RESULT_FILE"
echo ""
print_status "💡 Compare results: bash scripts/benchmark/compare-results.sh rtx4080 rtx4000 rtx5080"

