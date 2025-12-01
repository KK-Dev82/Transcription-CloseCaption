#!/bin/bash

# Script to verify parallel processing is enabled
# Usage: bash scripts/pod/verify-parallel.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header "Parallel Processing Verification"
echo ""

# Check if transcription_chunk_queue exists
print_status "Checking transcription_chunk_queue..."
if bash scripts/pod/check-rabbitmq-queue.sh transcription_chunk_queue 2>/dev/null | grep -q "Queue:"; then
    print_status "✅ transcription_chunk_queue exists"
else
    print_warning "⚠️  transcription_chunk_queue not found - may need to restart services"
fi
echo ""

# Check video worker logs for chunk queue consumer
print_status "Checking Video Worker for chunk queue consumer..."
if tail -100 /tmp/video-worker.log 2>/dev/null | grep -q "transcription_chunk_queue"; then
    print_status "✅ Video Worker is listening to transcription_chunk_queue"
else
    print_warning "⚠️  Video Worker may not be listening to transcription_chunk_queue"
    print_warning "   Please restart services: bash scripts/pod/restart-pod.sh"
fi
echo ""

# Check if code has parallel processing
print_status "Checking code for parallel processing..."
if grep -q "send_chunk_transcription_task" app/services/transcription_service.py 2>/dev/null; then
    print_status "✅ Code has send_chunk_transcription_task"
else
    print_error "❌ Code does not have send_chunk_transcription_task"
fi

if grep -q "_process_chunk_transcription_task" app/workers/video_worker.py 2>/dev/null; then
    print_status "✅ Code has _process_chunk_transcription_task handler"
else
    print_error "❌ Code does not have _process_chunk_transcription_task handler"
fi
echo ""

# Check recent transcription logs
print_status "Checking recent transcription logs..."
if tail -50 /tmp/video-worker.log 2>/dev/null | grep -q "ส่ง.*chunks ไปยัง transcription_chunk_queue"; then
    print_status "✅ Recent transcription used parallel processing"
else
    print_warning "⚠️  Recent transcription may not have used parallel processing"
    print_warning "   This could mean:"
    print_warning "   1. Services need restart"
    print_warning "   2. Old code is still running"
fi
echo ""

print_header "Recommendations"
echo ""
echo "If parallel processing is not working:"
echo "  1. Restart services: bash scripts/pod/restart-pod.sh"
echo "  2. Check logs: bash scripts/pod/logs-pod.sh worker | grep chunk"
echo "  3. Verify queue: bash scripts/pod/check-rabbitmq-queue.sh transcription_chunk_queue"
echo ""

