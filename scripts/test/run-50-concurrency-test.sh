#!/bin/bash
# Script สำหรับทดสอบ 50 Concurrency (รันบน Server โดยตรง)
#
# วิธีใช้งาน:
#   bash scripts/test/run-50-concurrency-test.sh <file_name> [options]
#
# ตัวอย่าง:
#   bash scripts/test/run-50-concurrency-test.sh v10-1.mp4
#   bash scripts/test/run-50-concurrency-test.sh v10-1.mp4 http://localhost:8010 50 medium

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

# Default values
FILE_NAME="${1}"
API_URL="${2:-http://localhost:8010}"
NUM_CONCURRENT="${3:-5}"
MODEL_SIZE="${4:-medium}"
LANGUAGE="${5:-th}"
POLL_INTERVAL="${6:-5}"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

# Check arguments
if [ -z "$FILE_NAME" ]; then
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  🔍 50 Concurrency Test Script (รันบน Server)               ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Usage:"
    echo "  bash scripts/test/run-50-concurrency-test.sh <file_name> [api_url] [num_concurrent] [model_size] [language] [poll_interval]"
    echo ""
    echo "Arguments:"
    echo "  file_name        - ชื่อไฟล์ใน uploads/ (เช่น v10-1.mp4)"
    echo "  api_url          - API URL (default: http://localhost:8010)"
    echo "  num_concurrent   - จำนวน concurrent requests (default: 5)"
    echo "  model_size       - ขนาดโมเดล (default: medium)"
    echo "  language         - ภาษา (default: th)"
    echo "  poll_interval    - ช่วงเวลาการตรวจสอบ (วินาที, default: 5)"
    echo ""
    echo "Examples:"
    echo "  # Basic usage"
    echo "  bash scripts/test/run-50-concurrency-test.sh v10-1.mp4"
    echo ""
    echo "  # Custom API URL"
    echo "  bash scripts/test/run-50-concurrency-test.sh v10-1.mp4 http://localhost:8010"
    echo ""
    echo "  # Custom concurrent count"
    echo "  bash scripts/test/run-50-concurrency-test.sh v10-1.mp4 http://localhost:8010 30"
    echo ""
    exit 1
fi

print_header "╔══════════════════════════════════════════════════════════════╗"
print_header "║  🚀 50 Concurrency Test (รันบน Server)                       ║"
print_header "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Configuration
FILE_PATH="uploads/${FILE_NAME}"
TEST_SCRIPT="scripts/test/test-50-concurrency.py"

print_status "Configuration:"
echo "  File Name: $FILE_NAME"
echo "  File Path: $FILE_PATH"
echo "  API URL: $API_URL"
echo "  Concurrent Requests: $NUM_CONCURRENT"
echo "  Model Size: $MODEL_SIZE"
echo "  Language: $LANGUAGE"
echo "  Poll Interval: ${POLL_INTERVAL}s"
echo "  Project Directory: $PROJECT_DIR"
echo ""

# Step 1: ตรวจสอบไฟล์
print_status "Step 1: ตรวจสอบไฟล์..."
if [ ! -f "$FILE_PATH" ]; then
    print_error "❌ ไฟล์ไม่พบ: $FILE_PATH"
    echo ""
    echo "🔍 ไฟล์ใน uploads directory:"
    ls -lh uploads/ 2>/dev/null | head -10 || echo "   (uploads directory ไม่มี หรือว่าง)"
    echo ""
    echo "💡 ตรวจสอบ path ที่ถูกต้อง:"
    echo "   find . -name \"$FILE_NAME\" -type f"
    exit 1
fi

# ตรวจสอบขนาดไฟล์
FILE_SIZE=$(stat -f%z "$FILE_PATH" 2>/dev/null || stat -c%s "$FILE_PATH" 2>/dev/null || echo "0")
FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))
print_success "✅ ไฟล์พบ: $FILE_PATH (${FILE_SIZE_MB} MB)"
echo ""

# Step 2: ตรวจสอบ API health
print_status "Step 2: ตรวจสอบ API health..."
HEALTH_RESPONSE=$(curl -s -f "${API_URL}/health" 2>&1 || echo "ERROR")
if echo "$HEALTH_RESPONSE" | grep -q "healthy\|status"; then
    print_success "✅ API is healthy"
else
    print_warning "⚠️  API health check failed"
    echo "   Response: $(echo "$HEALTH_RESPONSE" | head -1)"
    echo "   Continuing anyway..."
fi
echo ""

# Step 3: ตรวจสอบ test script
print_status "Step 3: ตรวจสอบ test script..."
if [ ! -f "$TEST_SCRIPT" ]; then
    print_error "❌ Test script ไม่พบ: $TEST_SCRIPT"
    exit 1
fi
print_success "✅ Test script พบ"
echo ""

# Step 4: แสดงสรุปและยืนยัน
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "📋 Test Summary"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "File: $FILE_NAME (${FILE_SIZE_MB} MB)"
echo "Path: $FILE_PATH"
echo "API: $API_URL"
echo "Concurrent: $NUM_CONCURRENT requests"
echo "Model: $MODEL_SIZE"
echo "Language: $LANGUAGE"
echo ""
print_warning "⚠️  การทดสอบจะส่ง $NUM_CONCURRENT requests พร้อมกัน"
print_warning "⚠️  อาจใช้เวลานาน ขึ้นอยู่กับขนาดไฟล์"
echo ""
read -p "เริ่มการทดสอบ? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "การทดสอบถูกยกเลิก"
    exit 0
fi
echo ""

# Step 4.5: Setup Python environment (สำหรับ persistent dependencies)
print_status "Step 4.5: Setting up Python environment..."
# Detect Python version dynamically
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.10")
PYTHON_SITE_PACKAGES="/workspace/.local/lib/python${PYTHON_VERSION}/site-packages"

export PYTHONUSERBASE="/workspace/.local"
export PATH="/workspace/.local/bin:$PATH"
export PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH"

echo "   Python version: ${PYTHON_VERSION}"
echo "   Installation path: ${PYTHON_SITE_PACKAGES}"
echo ""

# Check if aiohttp is installed
if ! env PYTHONUSERBASE="/workspace/.local" \
        PATH="/workspace/.local/bin:$PATH" \
        PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
        python3 -c "import aiohttp" 2>/dev/null; then
    print_warning "⚠️  aiohttp is not installed"
    echo ""
    echo "💡 Installing aiohttp..."
    env PYTHONUSERBASE="/workspace/.local" \
        PATH="/workspace/.local/bin:$PATH" \
        PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
        pip3 install --user --no-cache-dir aiohttp==3.9.1 || {
        print_error "❌ Failed to install aiohttp"
        echo ""
        echo "💡 Please run: bash scripts/pod/install-dependencies.sh"
        exit 1
    }
    print_success "✅ aiohttp installed"
    echo ""
else
    print_success "✅ aiohttp is available"
    echo ""
fi

# Step 5: รันการทดสอบ
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "🚀 เริ่มการทดสอบ..."
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# รัน test script ด้วย environment variables ที่ถูกต้อง
env PYTHONUSERBASE="/workspace/.local" \
    PATH="/workspace/.local/bin:$PATH" \
    PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
    python3 "$TEST_SCRIPT" \
    --api-url "$API_URL" \
    --file-path "$FILE_PATH" \
    --file-name "$FILE_NAME" \
    --num-concurrent "$NUM_CONCURRENT" \
    --model-size "$MODEL_SIZE" \
    --language "$LANGUAGE" \
    --poll-interval "$POLL_INTERVAL" || {
    print_error "❌ การทดสอบล้มเหลว"
    exit 1
}

echo ""
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_success "✅ การทดสอบเสร็จสิ้น!"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 ตรวจสอบรายงานผล:"
echo "   ls -lt concurrency_report_*.json | head -1"
echo ""
echo "💡 ดู HTML Monitor:"
echo "   cat static/concurrency-monitor.html"
echo ""
