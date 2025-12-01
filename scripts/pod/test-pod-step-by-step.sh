#!/bin/bash
# Step-by-step test script สำหรับ Pod GPU
# แบ่งการทดสอบเป็นขั้นตอนเล็กๆ และ cleanup processes ทุกครั้ง

set -e

AUDIO_FILE="${1:-uploads/v05-1_direct_audio.wav}"
MODEL_SIZE="${2:-medium}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() { echo -e "${BLUE}[STEP]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

cleanup_processes() {
    echo "Cleaning up Python processes..."
    ps aux | grep python3 | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
    sleep 2
    GPU_PROCS=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | wc -l)
    if [ "$GPU_PROCS" -gt 0 ]; then
        echo "⚠️  Still $GPU_PROCS GPU processes running"
    else
        echo "✓ All processes cleaned"
    fi
}

# Step 1: Cleanup
print_step "Step 1: Cleanup existing processes"
cleanup_processes
echo ""

# Step 2: Environment check
print_step "Step 2: Environment check"
python3 -c "
import sys
print(f'Python: {sys.version.split()[0]}')
" 2>&1

python3 -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'Device: {torch.cuda.get_device_name(0)}')
" 2>&1
echo ""

# Step 3: Test model loading only
print_step "Step 3: Test model loading (timeout 30s)"
timeout 30 python3 << 'PYEOF'
from faster_whisper import WhisperModel
import time
print("Loading model...")
start = time.time()
model = WhisperModel('medium', device='cuda', compute_type='float16')
print(f"✓ Loaded in {time.time() - start:.2f}s")
print("✓ Model loading OK")
PYEOF

if [ $? -eq 0 ]; then
    print_success "Model loading passed"
else
    print_error "Model loading failed"
    cleanup_processes
    exit 1
fi
cleanup_processes
echo ""

# Step 4: Test transcribe only (no segments iteration)
print_step "Step 4: Test transcribe() call (timeout 30s)"
timeout 30 python3 << 'PYEOF'
from faster_whisper import WhisperModel
import time
print("Loading model...")
model = WhisperModel('medium', device='cuda', compute_type='float16')
print("Calling transcribe()...")
start = time.time()
segments, info = model.transcribe('uploads/v05-1_direct_audio.wav', language='th')
elapsed = time.time() - start
print(f"✓ transcribe() completed in {elapsed:.2f}s")
print(f"  Duration: {info.duration:.2f}s")
print(f"  Language: {info.language}")
print(f"  Segments type: {type(segments)}")
print("✓ transcribe() OK (not iterating segments yet)")
PYEOF

if [ $? -eq 0 ]; then
    print_success "transcribe() call passed"
else
    print_error "transcribe() call failed"
    cleanup_processes
    exit 1
fi
cleanup_processes
echo ""

# Step 5: Test segments iteration with limit
print_step "Step 5: Test segments iteration (timeout 15s, max 5 segments)"
timeout 15 python3 << 'PYEOF'
from faster_whisper import WhisperModel
import time
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Iteration timeout")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(10)

try:
    print("Loading model...")
    model = WhisperModel('medium', device='cuda', compute_type='float16')
    
    print("Transcribing...")
    segments, info = model.transcribe('uploads/v05-1_direct_audio.wav', language='th')
    
    print("Iterating segments (max 5)...")
    count = 0
    start = time.time()
    for segment in segments:
        print(f"  Segment {count+1}: [{segment.start:.2f}s-{segment.end:.2f}s] {segment.text[:50]}")
        count += 1
        if count >= 5:
            break
    
    elapsed = time.time() - start
    signal.alarm(0)
    print(f"✓ Iterated {count} segments in {elapsed:.2f}s")
    print("✓ Segments iteration OK")
except TimeoutError:
    signal.alarm(0)
    print(f"✗ TIMEOUT after {count} segments")
    raise
PYEOF

if [ $? -eq 0 ]; then
    print_success "Segments iteration passed"
else
    print_error "Segments iteration failed or timeout"
    cleanup_processes
    exit 1
fi
cleanup_processes
echo ""

# Summary
echo "=========================================="
echo "✅ All tests passed!"
echo "=========================================="
echo "✓ Environment OK"
echo "✓ Model loading OK"
echo "✓ transcribe() call OK"
echo "✓ Segments iteration OK"
echo ""
echo "Pod GPU is ready for transcription!"

