#!/bin/bash
# Script สำหรับรัน Benchmark บน GPU ต่างๆ
#
# วิธีใช้งาน:
#   bash scripts/benchmark/run-benchmark.sh <video-path> [model] [gpu-name]
#
# ตัวอย่าง:
#   bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 medium rtx4080
#   bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 large-v3 rtx4000

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
MODEL="${2:-medium}"
GPU_NAME="${3:-auto}"

if [ -z "$VIDEO_PATH" ]; then
    print_error "❌ Error: Video path is required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/benchmark/run-benchmark.sh <video-path> [model] [gpu-name]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 medium rtx4080"
    echo "  bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 large-v3 rtx4000"
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
print_header "GPU Benchmark: $GPU_NAME"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

print_status "Video: $VIDEO_PATH"
print_status "Model: $MODEL"
print_status "GPU: $GPU_NAME"
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
RESULT_FILE="$BENCHMARK_DIR/benchmark-${GPU_NAME}-${MODEL}-${TIMESTAMP}.json"
RESULT_LOG="$BENCHMARK_DIR/benchmark-${GPU_NAME}-${MODEL}-${TIMESTAMP}.log"

print_status "Result file: $RESULT_FILE"
print_status "Log file: $RESULT_LOG"
echo ""

# Start benchmark
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Starting Benchmark..."
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

START_TIME=$(date +%s.%N)

# Detect API port (8001 or 8010)
API_PORT=""
if curl -s -f http://localhost:8001/health > /dev/null 2>&1; then
    API_PORT=8001
    print_success "✅ API found on port 8001"
elif curl -s -f http://localhost:8010/health > /dev/null 2>&1; then
    API_PORT=8010
    print_success "✅ API found on port 8010"
else
    print_error "❌ API not found on port 8001 or 8010"
    print_status "💡 Start API: bash scripts/pod/start-pod.sh"
    exit 1
fi
print_status "Using API port: $API_PORT"
echo ""

# Submit transcription task
print_status "Submitting transcription task..."

# First, upload the file (if needed) or use file_path directly
# For benchmark, we'll use file_path directly
FILE_NAME=$(basename "$VIDEO_PATH")
ABSOLUTE_VIDEO_PATH=$(cd "$(dirname "$VIDEO_PATH")" && pwd)/$(basename "$VIDEO_PATH")

# Submit transcription using file_path
TASK_RESPONSE=$(curl -s -X POST "http://localhost:${API_PORT}/transcribe/" \
    -H "Content-Type: application/json" \
    -d "{
        \"file_path\": \"$ABSOLUTE_VIDEO_PATH\",
        \"file_name\": \"$FILE_NAME\",
        \"language\": \"th\",
        \"model_size\": \"$MODEL\"
    }" 2>&1 | tee "$RESULT_LOG")

TASK_ID=$(echo "$TASK_RESPONSE" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4 || echo "")

if [ -z "$TASK_ID" ]; then
    print_error "❌ Failed to submit task"
    print_status "Response: $TASK_RESPONSE"
    exit 1
fi

print_success "✅ Task submitted: $TASK_ID"
echo ""

# Monitor task
print_status "Monitoring task progress..."
print_status "Task ID: $TASK_ID"
echo ""

STATUS="pending"
PROGRESS=0
LAST_PROGRESS=0

while [ "$STATUS" != "completed" ] && [ "$STATUS" != "failed" ]; do
    sleep 2
    
    TASK_STATUS=$(curl -s "http://localhost:${API_PORT}/transcribe/$TASK_ID" 2>/dev/null || echo "")
    
    if [ -z "$TASK_STATUS" ]; then
        print_warning "⚠️  Failed to get task status"
        continue
    fi
    
    STATUS=$(echo "$TASK_STATUS" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
    PROGRESS=$(echo "$TASK_STATUS" | grep -o '"progress":[0-9.]*' | cut -d':' -f2 || echo "0")
    
    if [ "$PROGRESS" != "$LAST_PROGRESS" ]; then
        print_status "Progress: ${PROGRESS}% (Status: $STATUS)"
        LAST_PROGRESS=$PROGRESS
    fi
    
    # Get VRAM usage during processing
    if command -v nvidia-smi &> /dev/null; then
        VRAM_CURRENT=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -n1)
        if [ "$VRAM_CURRENT" != "$VRAM_BEFORE" ]; then
            print_status "VRAM: ${VRAM_CURRENT} MB"
        fi
    fi
done

END_TIME=$(date +%s.%N)
# Calculate elapsed time without bc
if command -v python3 > /dev/null 2>&1; then
    ELAPSED=$(python3 -c "print($END_TIME - $START_TIME)")
elif command -v awk > /dev/null 2>&1; then
    ELAPSED=$(awk "BEGIN {print $END_TIME - $START_TIME}")
else
    # Fallback: use integer seconds
    END_INT=$(echo "$END_TIME" | cut -d. -f1)
    START_INT=$(echo "$START_TIME" | cut -d. -f1)
    ELAPSED=$((END_INT - START_INT))
fi

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
print_header "Benchmark Results"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$STATUS" = "completed" ]; then
    print_success "✅ Task completed successfully"
    
    # Get result (already have it from status check)
    RESULT="$TASK_STATUS"
    
    # Calculate metrics without bc
    if command -v python3 > /dev/null 2>&1; then
        ELAPSED_INT=$(python3 -c "print(int($ELAPSED))")
        ELAPSED_MS=$(python3 -c "print(int($ELAPSED * 1000))")
        if [ "$DURATION_INT" -gt 0 ]; then
            SPEEDUP=$(python3 -c "print(f'{($DURATION_INT / $ELAPSED):.2f}')")
            REALTIME_RATIO=$(python3 -c "print(f'{($ELAPSED / $DURATION_INT):.2f}')")
            THROUGHPUT=$(python3 -c "print(f'{(3600 / $ELAPSED):.2f}')")
        else
            SPEEDUP="N/A"
            REALTIME_RATIO="N/A"
            THROUGHPUT="N/A"
        fi
    elif command -v awk > /dev/null 2>&1; then
        ELAPSED_INT=$(awk "BEGIN {print int($ELAPSED)}")
        ELAPSED_MS=$(awk "BEGIN {print int($ELAPSED * 1000)}")
        if [ "$DURATION_INT" -gt 0 ]; then
            SPEEDUP=$(awk "BEGIN {printf \"%.2f\", $DURATION_INT / $ELAPSED}")
            REALTIME_RATIO=$(awk "BEGIN {printf \"%.2f\", $ELAPSED / $DURATION_INT}")
            THROUGHPUT=$(awk "BEGIN {printf \"%.2f\", 3600 / $ELAPSED}")
        else
            SPEEDUP="N/A"
            REALTIME_RATIO="N/A"
            THROUGHPUT="N/A"
        fi
    else
        ELAPSED_INT=${ELAPSED%.*}
        ELAPSED_MS=$((ELAPSED_INT * 1000))
        SPEEDUP="N/A"
        REALTIME_RATIO="N/A"
        THROUGHPUT="N/A"
    fi
    
    # Save results to JSON
    cat > "$RESULT_FILE" << EOF
{
  "benchmark": {
    "timestamp": "$TIMESTAMP",
    "gpu_name": "$GPU_NAME",
    "model": "$MODEL",
    "video_path": "$VIDEO_PATH",
    "video_duration_seconds": $DURATION_INT,
    "task_id": "$TASK_ID"
  },
  "performance": {
    "elapsed_time_seconds": $ELAPSED,
    "elapsed_time_ms": ${ELAPSED_MS:-0},
    "speedup": "$SPEEDUP",
    "realtime_ratio": "$REALTIME_RATIO",
    "throughput_videos_per_hour": "$THROUGHPUT"
  },
  "resources": {
    "vram_before_mb": $VRAM_BEFORE,
    "vram_after_mb": $VRAM_AFTER,
    "vram_used_mb": $VRAM_USED
  },
  "status": "$STATUS"
}
EOF
    
    print_success "✅ Results saved to: $RESULT_FILE"
    echo ""
    
    print_status "Performance Metrics:"
    echo "  ⏱️  Elapsed Time: ${ELAPSED}s"
    echo "  🚀 Speedup: ${SPEEDUP}x"
    echo "  ⚡ Realtime Ratio: ${REALTIME_RATIO}x"
    echo "  📊 Throughput: $(echo "scale=2; 3600 / $ELAPSED" | bc) videos/hour"
    echo ""
    
    print_status "Resource Usage:"
    echo "  💾 VRAM Used: ${VRAM_USED} MB"
    echo "  💾 VRAM After: ${VRAM_AFTER} MB"
    echo ""
    
else
    print_error "❌ Task failed"
    print_status "Status: $STATUS"
    print_status "Check logs: $RESULT_LOG"
    exit 1
fi

print_success "🎉 Benchmark completed!"
echo ""
print_status "💡 Compare results: bash scripts/benchmark/compare-results.sh"

