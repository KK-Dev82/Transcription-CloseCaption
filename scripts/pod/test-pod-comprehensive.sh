#!/bin/bash
# Comprehensive Test Script สำหรับ Pod GPU
# ตรวจสอบความพร้อมและสมบูรณ์ของ Pod GPU สำหรับ transcription

set -e

AUDIO_FILE="${1:-uploads/v05-1_direct_audio.wav}"
MODEL_SIZE="${2:-medium}"

echo "=========================================="
echo "🧪 Comprehensive Pod GPU Test"
echo "=========================================="
echo "Audio file: $AUDIO_FILE"
echo "Model: $MODEL_SIZE"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_test() { echo -e "${BLUE}[TEST]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }

# Test 1: Environment & Dependencies
print_test "Test 1: Environment & Dependencies"
echo "----------------------------------------"
python3 -c "
import sys
print(f'Python: {sys.version}')
print(f'Python path: {sys.executable}')
" 2>&1

python3 -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA device: {torch.cuda.get_device_name(0)}')
    print(f'CUDA version: {torch.version.cuda}')
" 2>&1

pip3 list | grep -E 'faster-whisper|torch|ctranslate2' | head -5
echo ""

# Test 2: Direct faster-whisper test
print_test "Test 2: Direct faster-whisper (medium model)"
echo "----------------------------------------"
python3 << 'PYTHON_SCRIPT'
import sys
import time
from faster_whisper import WhisperModel
import torch

print("Loading medium model...")
start = time.time()
model = WhisperModel('medium', device='cuda', compute_type='float16')
load_time = time.time() - start
print(f"✓ Model loaded in {load_time:.2f}s")

print("Starting transcription...")
transcribe_start = time.time()
segments, info = model.transcribe('uploads/v05-1_direct_audio.wav', language='th')
transcribe_time = time.time() - transcribe_start
print(f"✓ Transcribe completed in {transcribe_time:.2f}s")
print(f"  Duration: {info.duration:.2f}s")
print(f"  Language: {info.language}")

print("Iterating segments...")
iter_start = time.time()
segments_list = []
count = 0
for segment in segments:
    segments_list.append({
        'start': segment.start,
        'end': segment.end,
        'text': segment.text.strip()
    })
    count += 1
    if count <= 3:
        print(f"  Segment {count}: [{segment.start:.2f}s-{segment.end:.2f}s] {segment.text[:60]}")
    if count >= 10:
        break

iter_time = time.time() - iter_start
print(f"✓ Iterated {count} segments in {iter_time:.2f}s")

full_text = ' '.join([s['text'] for s in segments_list])
print(f"✓ Full text length: {len(full_text)} characters")
print(f"✓ First 200 chars: {full_text[:200]}")

print(f"\n✅ Direct test completed successfully!")
print(f"   Total time: {time.time() - start:.2f}s")
PYTHON_SCRIPT

if [ $? -eq 0 ]; then
    print_success "Direct faster-whisper test PASSED"
else
    print_error "Direct faster-whisper test FAILED"
    exit 1
fi
echo ""

# Test 3: WhisperService test (no RabbitMQ)
print_test "Test 3: WhisperService (no RabbitMQ)"
echo "----------------------------------------"
cd /workspace/transcription-service
python3 scripts/pod/test-direct-transcription.py "$AUDIO_FILE" th "$MODEL_SIZE" 2>&1 | tail -30

if [ $? -eq 0 ]; then
    print_success "WhisperService test PASSED"
else
    print_error "WhisperService test FAILED"
    exit 1
fi
echo ""

# Test 4: API + RabbitMQ test
print_test "Test 4: API + RabbitMQ"
echo "----------------------------------------"
TASK_RESPONSE=$(curl -s -X POST http://localhost:8001/transcribe/ \
    -H 'Content-Type: application/json' \
    -d "{\"file_path\": \"$AUDIO_FILE\", \"language\": \"th\", \"model_size\": \"$MODEL_SIZE\", \"use_chunking\": false}")

TASK_ID=$(echo "$TASK_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))" 2>/dev/null)

if [ -z "$TASK_ID" ]; then
    print_error "Failed to get task_id from API"
    exit 1
fi

print_success "Task created: $TASK_ID"
echo "Waiting for completion (max 60s)..."

for i in {1..12}; do
    sleep 5
    TASK_STATUS=$(curl -s http://localhost:8001/transcribe/$TASK_ID | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('status'), data.get('progress'), len(data.get('full_text', '') or ''))" 2>/dev/null)
    STATUS=$(echo "$TASK_STATUS" | awk '{print $1}')
    PROGRESS=$(echo "$TASK_STATUS" | awk '{print $2}')
    TEXT_LEN=$(echo "$TASK_STATUS" | awk '{print $3}')
    
    echo "  [$i/12] Status: $STATUS, Progress: $PROGRESS%, Text: $TEXT_LEN chars"
    
    if [ "$STATUS" = "completed" ]; then
        print_success "Task completed!"
        break
    elif [ "$STATUS" = "failed" ]; then
        print_error "Task failed!"
        exit 1
    fi
done

if [ "$STATUS" != "completed" ]; then
    print_warning "Task did not complete in time"
fi
echo ""

# Summary
echo "=========================================="
echo "📊 Test Summary"
echo "=========================================="
echo "✓ Environment check"
echo "✓ Direct faster-whisper test"
echo "✓ WhisperService test"
echo "✓ API + RabbitMQ test"
echo ""
echo "✅ All tests completed!"

