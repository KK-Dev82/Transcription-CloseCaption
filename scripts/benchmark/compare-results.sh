#!/bin/bash
# Script สำหรับเปรียบเทียบผลลัพธ์ Benchmark จาก GPU หลายตัว
#
# วิธีใช้งาน:
#   bash scripts/benchmark/compare-results.sh [gpu1] [gpu2] [gpu3]
#
# ตัวอย่าง:
#   bash scripts/benchmark/compare-results.sh rtx4080 rtx4000 rtx5080

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

if [ ! -d "$BENCHMARK_DIR" ]; then
    print_error "❌ Benchmark results directory not found: $BENCHMARK_DIR"
    exit 1
fi

# Parse GPU names
GPU1="${1:-rtx4080}"
GPU2="${2:-rtx4000}"
GPU3="${3:-rtx5080}"

print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "GPU Performance Comparison"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Find latest results for each GPU
find_latest_result() {
    local gpu=$1
    find "$BENCHMARK_DIR" -name "benchmark-${gpu}-*.json" -type f | sort -r | head -n1
}

RESULT1=$(find_latest_result "$GPU1")
RESULT2=$(find_latest_result "$GPU2")
RESULT3=$(find_latest_result "$GPU3")

if [ -z "$RESULT1" ] && [ -z "$RESULT2" ] && [ -z "$RESULT3" ]; then
    print_error "❌ No benchmark results found"
    print_status "💡 Run benchmark first: bash scripts/benchmark/run-benchmark.sh <video> <model> <gpu>"
    exit 1
fi

# Function to extract value from JSON
extract_json() {
    local file=$1
    local key=$2
    python3 -c "import json, sys; data = json.load(open('$file')); print(data$key)" 2>/dev/null || echo "N/A"
}

# Function to format number
format_number() {
    local num=$1
    if [ "$num" = "N/A" ]; then
        echo "N/A"
    else
        printf "%.2f" "$num" 2>/dev/null || echo "$num"
    fi
}

# Display comparison table
print_header "Performance Comparison"
echo ""

printf "%-20s" "Metric"
[ -n "$RESULT1" ] && printf "%-20s" "$GPU1"
[ -n "$RESULT2" ] && printf "%-20s" "$GPU2"
[ -n "$RESULT3" ] && printf "%-20s" "$GPU3"
echo ""
echo "────────────────────────────────────────────────────────────────────────────"

# Elapsed Time
printf "%-20s" "Elapsed Time (s)"
[ -n "$RESULT1" ] && printf "%-20s" "$(format_number $(extract_json "$RESULT1" "['performance']['elapsed_time_seconds']"))"
[ -n "$RESULT2" ] && printf "%-20s" "$(format_number $(extract_json "$RESULT2" "['performance']['elapsed_time_seconds']"))"
[ -n "$RESULT3" ] && printf "%-20s" "$(format_number $(extract_json "$RESULT3" "['performance']['elapsed_time_seconds']"))"
echo ""

# Speedup
printf "%-20s" "Speedup (x)"
[ -n "$RESULT1" ] && printf "%-20s" "$(extract_json "$RESULT1" "['performance']['speedup']")"
[ -n "$RESULT2" ] && printf "%-20s" "$(extract_json "$RESULT2" "['performance']['speedup']")"
[ -n "$RESULT3" ] && printf "%-20s" "$(extract_json "$RESULT3" "['performance']['speedup']")"
echo ""

# Realtime Ratio
printf "%-20s" "Realtime Ratio"
[ -n "$RESULT1" ] && printf "%-20s" "$(extract_json "$RESULT1" "['performance']['realtime_ratio']")"
[ -n "$RESULT2" ] && printf "%-20s" "$(extract_json "$RESULT2" "['performance']['realtime_ratio']")"
[ -n "$RESULT3" ] && printf "%-20s" "$(extract_json "$RESULT3" "['performance']['realtime_ratio']")"
echo ""

# Throughput
printf "%-20s" "Throughput (v/h)"
[ -n "$RESULT1" ] && printf "%-20s" "$(format_number $(extract_json "$RESULT1" "['performance']['throughput_videos_per_hour']"))"
[ -n "$RESULT2" ] && printf "%-20s" "$(format_number $(extract_json "$RESULT2" "['performance']['throughput_videos_per_hour']"))"
[ -n "$RESULT3" ] && printf "%-20s" "$(format_number $(extract_json "$RESULT3" "['performance']['throughput_videos_per_hour']"))"
echo ""

echo ""
print_header "Resource Usage Comparison"
echo ""

printf "%-20s" "Metric"
[ -n "$RESULT1" ] && printf "%-20s" "$GPU1"
[ -n "$RESULT2" ] && printf "%-20s" "$GPU2"
[ -n "$RESULT3" ] && printf "%-20s" "$GPU3"
echo ""
echo "────────────────────────────────────────────────────────────────────────────"

# VRAM Used
printf "%-20s" "VRAM Used (MB)"
[ -n "$RESULT1" ] && printf "%-20s" "$(extract_json "$RESULT1" "['resources']['vram_used_mb']")"
[ -n "$RESULT2" ] && printf "%-20s" "$(extract_json "$RESULT2" "['resources']['vram_used_mb']")"
[ -n "$RESULT3" ] && printf "%-20s" "$(extract_json "$RESULT3" "['resources']['vram_used_mb']")"
echo ""

# VRAM After
printf "%-20s" "VRAM After (MB)"
[ -n "$RESULT1" ] && printf "%-20s" "$(extract_json "$RESULT1" "['resources']['vram_after_mb']")"
[ -n "$RESULT2" ] && printf "%-20s" "$(extract_json "$RESULT2" "['resources']['vram_after_mb']")"
[ -n "$RESULT3" ] && printf "%-20s" "$(extract_json "$RESULT3" "['resources']['vram_after_mb']")"
echo ""

echo ""
print_header "Test Configuration"
echo ""

if [ -n "$RESULT1" ]; then
    print_status "$GPU1:"
    echo "  Model: $(extract_json "$RESULT1" "['benchmark']['model']")"
    echo "  Video: $(extract_json "$RESULT1" "['benchmark']['video_path']")"
    echo "  Duration: $(extract_json "$RESULT1" "['benchmark']['video_duration_seconds']")s"
    echo ""
fi

if [ -n "$RESULT2" ]; then
    print_status "$GPU2:"
    echo "  Model: $(extract_json "$RESULT2" "['benchmark']['model']")"
    echo "  Video: $(extract_json "$RESULT2" "['benchmark']['video_path']")"
    echo "  Duration: $(extract_json "$RESULT2" "['benchmark']['video_duration_seconds']")s"
    echo ""
fi

if [ -n "$RESULT3" ]; then
    print_status "$GPU3:"
    echo "  Model: $(extract_json "$RESULT3" "['benchmark']['model']")"
    echo "  Video: $(extract_json "$RESULT3" "['benchmark']['video_path']")"
    echo "  Duration: $(extract_json "$RESULT3" "['benchmark']['video_duration_seconds']")s"
    echo ""
fi

echo ""
print_success "✅ Comparison completed!"
echo ""
print_status "💡 Results saved in: $BENCHMARK_DIR"
print_status "💡 Generate report: bash scripts/benchmark/generate-report.sh"

