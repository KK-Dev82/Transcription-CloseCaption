#!/bin/bash
# Script สำหรับทดสอบ 50 Concurrency บน Pod
#
# วิธีใช้งาน:
#   bash scripts/test/run-50-concurrency-test.sh <file_name> [options]
#
# ตัวอย่าง:
#   bash scripts/test/run-50-concurrency-test.sh v10-1.mp4
#   bash scripts/test/run-50-concurrency-test.sh test-video-10min.mp4 --api-url http://80.15.7.37:41462

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
API_URL="${2:-http://80.15.7.37:41462}"
NUM_CONCURRENT="${3:-50}"
MODEL_SIZE="${4:-medium}"
LANGUAGE="${5:-th}"
POLL_INTERVAL="${6:-5}"

# Check arguments
if [ -z "$FILE_NAME" ]; then
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  🔍 50 Concurrency Test Script                               ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Usage:"
    echo "  bash scripts/test/run-50-concurrency-test.sh <file_name> [api_url] [num_concurrent] [model_size] [language] [poll_interval]"
    echo ""
    echo "Arguments:"
    echo "  file_name        - ชื่อไฟล์ใน uploads/ (เช่น v10-1.mp4)"
    echo "  api_url          - API URL (default: http://80.15.7.37:41462)"
    echo "  num_concurrent   - จำนวน concurrent requests (default: 50)"
    echo "  model_size       - ขนาดโมเดล (default: medium)"
    echo "  language         - ภาษา (default: th)"
    echo "  poll_interval    - ช่วงเวลาการตรวจสอบ (วินาที, default: 5)"
    echo ""
    echo "Examples:"
    echo "  # Basic usage"
    echo "  bash scripts/test/run-50-concurrency-test.sh v10-1.mp4"
    echo ""
    echo "  # Custom API URL"
    echo "  bash scripts/test/run-50-concurrency-test.sh v10-1.mp4 http://80.15.7.37:41462"
    echo ""
    echo "  # Custom concurrent count"
    echo "  bash scripts/test/run-50-concurrency-test.sh v10-1.mp4 http://80.15.7.37:41462 30"
    echo ""
    exit 1
fi

print_header "╔══════════════════════════════════════════════════════════════╗"
print_header "║  🚀 50 Concurrency Test                                      ║"
print_header "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Configuration
FILE_PATH="uploads/${FILE_NAME}"
SSH_HOST="pytorch-pod"
PROJECT_DIR="/workspace/transcription-service"
TEST_SCRIPT="scripts/test/test-50-concurrency.py"

print_status "Configuration:"
echo "  File Name: $FILE_NAME"
echo "  File Path: $FILE_PATH"
echo "  API URL: $API_URL"
echo "  Concurrent Requests: $NUM_CONCURRENT"
echo "  Model Size: $MODEL_SIZE"
echo "  Language: $LANGUAGE"
echo "  Poll Interval: ${POLL_INTERVAL}s"
echo ""

# Step 1: ตรวจสอบ SSH connection
print_status "Step 1: ตรวจสอบ SSH connection..."
if ! ssh -o ConnectTimeout=5 "$SSH_HOST" "echo 'SSH OK'" > /dev/null 2>&1; then
    print_error "❌ ไม่สามารถเชื่อมต่อ SSH ไปยัง $SSH_HOST ได้"
    echo ""
    echo "💡 ตรวจสอบ:"
    echo "   1. SSH config: cat ~/.ssh/config | grep pytorch-pod"
    echo "   2. SSH connection: ssh pytorch-pod"
    exit 1
fi
print_success "✅ SSH connection OK"
echo ""

# Step 2: ตรวจสอบไฟล์บน Pod
print_status "Step 2: ตรวจสอบไฟล์บน Pod..."
FILE_EXISTS=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && [ -f '$FILE_PATH' ] && echo 'yes' || echo 'no'")

if [ "$FILE_EXISTS" != "yes" ]; then
    print_error "❌ ไฟล์ไม่พบ: $FILE_PATH"
    echo ""
    echo "🔍 ตรวจสอบไฟล์ใน uploads directory:"
    ssh "$SSH_HOST" "cd $PROJECT_DIR && ls -lh uploads/ | head -10" || echo "   (ไม่สามารถ list files ได้)"
    echo ""
    echo "💡 วิธีแก้ไข:"
    echo "   1. Upload ไฟล์ไปยัง Pod:"
    echo "      scp $FILE_NAME $SSH_HOST:$PROJECT_DIR/uploads/"
    echo ""
    echo "   2. หรือตรวจสอบ path ที่ถูกต้อง:"
    echo "      ssh $SSH_HOST 'cd $PROJECT_DIR && find . -name \"$FILE_NAME\" -type f'"
    exit 1
fi

# ตรวจสอบขนาดไฟล์
FILE_SIZE=$(ssh "$SSH_HOST" "cd $PROJECT_DIR && stat -f%z '$FILE_PATH' 2>/dev/null || stat -c%s '$FILE_PATH' 2>/dev/null || echo '0'")
FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))
print_success "✅ ไฟล์พบ: $FILE_PATH (${FILE_SIZE_MB} MB)"
echo ""

# Step 3: ตรวจสอบ API health
print_status "Step 3: ตรวจสอบ API health..."
HEALTH_RESPONSE=$(curl -s -f "${API_URL}/health" 2>&1 || echo "ERROR")
if echo "$HEALTH_RESPONSE" | grep -q "healthy\|status"; then
    print_success "✅ API is healthy"
else
    print_warning "⚠️  API health check failed"
    echo "   Response: $(echo "$HEALTH_RESPONSE" | head -1)"
    echo "   Continuing anyway..."
fi
echo ""

# Step 4: ตรวจสอบ test script
print_status "Step 4: ตรวจสอบ test script..."
if ! ssh "$SSH_HOST" "cd $PROJECT_DIR && [ -f '$TEST_SCRIPT' ]" > /dev/null 2>&1; then
    print_error "❌ Test script ไม่พบ: $TEST_SCRIPT"
    echo ""
    echo "💡 ตรวจสอบว่า code ถูก push และ pull บน Pod แล้ว"
    exit 1
fi
print_success "✅ Test script พบ"
echo ""

# Step 5: แสดงสรุปและยืนยัน
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

# Step 6: รันการทดสอบ
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "🚀 เริ่มการทดสอบ..."
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# รัน test script บน Pod
ssh "$SSH_HOST" "cd $PROJECT_DIR && \
    python3 $TEST_SCRIPT \
        --api-url $API_URL \
        --file-path $FILE_PATH \
        --file-name \"$FILE_NAME\" \
        --num-concurrent $NUM_CONCURRENT \
        --model-size $MODEL_SIZE \
        --language $LANGUAGE \
        --poll-interval $POLL_INTERVAL" || {
    print_error "❌ การทดสอบล้มเหลว"
    exit 1
}

echo ""
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_success "✅ การทดสอบเสร็จสิ้น!"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 ตรวจสอบรายงานผล:"
echo "   ssh $SSH_HOST 'cd $PROJECT_DIR && ls -lt concurrency_report_*.json | head -1'"
echo ""
echo "💡 ดู HTML Monitor:"
echo "   ssh $SSH_HOST 'cd $PROJECT_DIR && cat static/concurrency-monitor.html'"
echo ""

