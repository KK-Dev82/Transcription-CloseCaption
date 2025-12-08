#!/bin/bash
# Script สำหรับรัน Benchmark หลาย Video พร้อมกัน
#
# วิธีใช้งาน:
#   bash scripts/pod/run-benchmark-batch.sh <video-pattern> [model] [gpu-name]
#
# ตัวอย่าง:
#   bash scripts/pod/run-benchmark-batch.sh uploads/v10-*.mp4 medium rtx4080
#   bash scripts/pod/run-benchmark-batch.sh uploads/v10-{1..10}.mp4 medium rtx4000

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
VIDEO_PATTERN="${1:-}"
MODEL="${2:-medium}"
GPU_NAME="${3:-auto}"

if [ -z "$VIDEO_PATTERN" ]; then
    print_error "❌ Error: Video pattern is required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/run-benchmark-batch.sh <video-pattern> [model] [gpu-name]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pod/run-benchmark-batch.sh uploads/v10-*.mp4 medium rtx4080"
    echo "  bash scripts/pod/run-benchmark-batch.sh uploads/v10-{1..10}.mp4 medium rtx4000"
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

# Expand pattern to get video files
VIDEO_FILES=($(ls $VIDEO_PATTERN 2>/dev/null || echo ""))

if [ ${#VIDEO_FILES[@]} -eq 0 ]; then
    print_error "❌ No video files found matching pattern: $VIDEO_PATTERN"
    exit 1
fi

TOTAL_VIDEOS=${#VIDEO_FILES[@]}

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Batch Benchmark: $GPU_NAME"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_status "Model: $MODEL"
print_status "GPU: $GPU_NAME"
print_status "Total Videos: $TOTAL_VIDEOS"
echo ""

# Check if API is running
if ! curl -f http://localhost:8001/health > /dev/null 2>&1; then
    print_error "❌ Main API is not running"
    print_status "💡 Start API first: bash scripts/pod/start-pod.sh"
    exit 1
fi

SUCCESS_COUNT=0
FAILED_COUNT=0

for i in "${!VIDEO_FILES[@]}"; do
    VIDEO_FILE="${VIDEO_FILES[$i]}"
    VIDEO_NUM=$((i + 1))
    
    print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_status "[$VIDEO_NUM/$TOTAL_VIDEOS] Processing: $(basename "$VIDEO_FILE")"
    print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Run benchmark for this video
    if bash "$PROJECT_ROOT/scripts/benchmark/run-benchmark.sh" "$VIDEO_FILE" "$MODEL" "$GPU_NAME"; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        print_success "✅ Completed: $(basename "$VIDEO_FILE")"
    else
        FAILED_COUNT=$((FAILED_COUNT + 1))
        print_error "❌ Failed: $(basename "$VIDEO_FILE")"
    fi
    
    echo ""
    print_status "Progress: $VIDEO_NUM/$TOTAL_VIDEOS completed"
    echo ""
done

# Summary
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Batch Benchmark Summary"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_success "✅ Success: $SUCCESS_COUNT/$TOTAL_VIDEOS"
if [ $FAILED_COUNT -gt 0 ]; then
    print_error "❌ Failed: $FAILED_COUNT/$TOTAL_VIDEOS"
fi
echo ""
print_status "💡 Results saved in: $BENCHMARK_DIR"
print_status "💡 Compare results: bash scripts/benchmark/compare-results.sh rtx4080 rtx4000 rtx5080"
echo ""

