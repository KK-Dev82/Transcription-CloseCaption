#!/bin/bash
# Script สำหรับตรวจสอบสถานะ Transcription Task
#
# วิธีใช้งาน:
#   bash scripts/pod/check-transcription-status.sh [task-id]
#
# ตัวอย่าง:
#   bash scripts/pod/check-transcription-status.sh b4544c2d-82b3-4a41-a340-18834e345a76

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${CYAN}$1${NC}"
}

TASK_ID="${1}"

if [ -z "$TASK_ID" ]; then
    print_error "❌ Task ID is required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/check-transcription-status.sh <task-id>"
    echo ""
    echo "Example:"
    echo "  bash scripts/pod/check-transcription-status.sh b4544c2d-82b3-4a41-a340-18834e345a76"
    exit 1
fi

API_URL="${2:-http://localhost:8001}"

echo "📊 Checking Transcription Status"
echo "📅 $(date)"
echo ""
print_status "Task ID: $TASK_ID"
print_status "API URL: $API_URL"
echo ""

# Check API health
print_status "Checking API health..."
if ! curl -f -s --max-time 5 "$API_URL/health" > /dev/null 2>&1; then
    print_error "❌ API is not responding at $API_URL"
    exit 1
fi
print_success "✅ API is healthy"
echo ""

# Get task status
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Task Status"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Try /transcribe/{task_id} endpoint first
RESPONSE=$(curl -s "$API_URL/transcribe/$TASK_ID" 2>/dev/null || echo "")

# If that fails, try /api/transcription/{task_id} (legacy)
if [ -z "$RESPONSE" ] || echo "$RESPONSE" | grep -q "404\|Not Found" 2>/dev/null; then
    RESPONSE=$(curl -s "$API_URL/api/transcription/$TASK_ID" 2>/dev/null || echo "")
fi

if [ -z "$RESPONSE" ]; then
    print_error "❌ Could not fetch task status"
    exit 1
fi

# Parse response
STATUS=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('status', 'unknown'))" 2>/dev/null || echo "unknown")
PROGRESS=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('progress', 0))" 2>/dev/null || echo "0")
FILE_PATH=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('file_path', 'N/A'))" 2>/dev/null || echo "N/A")
ERROR_MSG=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('error_message', ''))" 2>/dev/null || echo "")

echo "Status: $STATUS"
echo "Progress: $PROGRESS%"
echo "File Path: $FILE_PATH"

if [ -n "$ERROR_MSG" ] && [ "$ERROR_MSG" != "None" ]; then
    print_error "Error: $ERROR_MSG"
fi

echo ""
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check Video Worker logs
print_status "Checking Video Worker logs for this task..."
if [ -f "/tmp/video-worker.log" ]; then
    TASK_LOGS=$(grep -i "$TASK_ID" /tmp/video-worker.log 2>/dev/null | tail -10 || echo "")
    if [ -n "$TASK_LOGS" ]; then
        print_success "✅ Found logs for this task:"
        echo "$TASK_LOGS"
    else
        print_warning "⚠️  No logs found for this task in Video Worker"
        print_status "💡 Checking recent Video Worker activity..."
        tail -n 20 /tmp/video-worker.log | grep -i "transcription\|task\|processing" | tail -5 || echo "No recent activity"
    fi
else
    print_warning "⚠️  Video Worker log file not found"
fi

echo ""

# Check storage
print_status "Checking storage..."
if [ -f "storage/transcriptions/$TASK_ID.json" ]; then
    print_success "✅ Task file found in storage"
    STORAGE_STATUS=$(python3 -c "import json; data=json.load(open('storage/transcriptions/$TASK_ID.json')); print(data.get('status', 'unknown'))" 2>/dev/null || echo "unknown")
    print_status "Storage status: $STORAGE_STATUS"
else
    print_warning "⚠️  Task file not found in storage"
fi

echo ""

# Summary
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Summary"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

case "$STATUS" in
    completed|success)
        print_success "✅ Transcription completed!"
        ;;
    processing)
        print_status "⏳ Transcription in progress ($PROGRESS%)"
        print_status "💡 Monitor progress: tail -f /tmp/video-worker.log | grep $TASK_ID"
        ;;
    failed|error)
        print_error "❌ Transcription failed"
        ;;
    pending)
        print_warning "⏳ Task is pending"
        print_status "💡 Check Video Worker logs: tail -f /tmp/video-worker.log"
        ;;
    *)
        print_warning "⚠️  Unknown status: $STATUS"
        ;;
esac

echo ""

