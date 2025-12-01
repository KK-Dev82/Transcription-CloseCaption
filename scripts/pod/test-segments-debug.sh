#!/bin/bash
# Debug script ตามคำแนะนำเพื่อหาสาเหตุ segments iteration timeout

set -e

AUDIO_FILE="${1:-uploads/v05-1_direct_audio.wav}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_test() { echo -e "${BLUE}[TEST]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

cleanup() {
    ps aux | grep python3 | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
    sleep 1
}

# Test 1: ยืนยันว่าค้างอยู่ตรงไหน (ใช้ islice)
print_test "Test 1: ตรวจสอบว่าค้างที่เฟรมแรกหรือไม่ (islice)"
echo "----------------------------------------"
timeout 15 python3 << 'PYEOF'
from faster_whisper import WhisperModel
from itertools import islice
import time

print("Loading model...")
model = WhisperModel('medium', device='cuda', compute_type='float16')
print("Transcribing...")
segments, info = model.transcribe('uploads/v05-1_direct_audio.wav', language='th')
print(f"transcribe() done: {info.duration}s, {info.language}")

print("Testing islice (first segment only)...")
start = time.time()
try:
    for i, seg in enumerate(islice(segments, 1)):
        print(f"✓ Got segment {i}: [{seg.start:.2f}s-{seg.end:.2f}s] {seg.text[:50]}")
        elapsed = time.time() - start
        print(f"  Time: {elapsed:.2f}s")
    print("✓ islice test PASSED - can get first segment")
except Exception as e:
    print(f"✗ islice test FAILED: {e}")
    raise
PYEOF

if [ $? -eq 0 ]; then
    print_success "Test 1 PASSED"
else
    print_error "Test 1 FAILED - ค้างตั้งแต่เฟรมแรก"
    cleanup
    exit 1
fi
cleanup
echo ""

# Test 2: เปิด debug mode
print_test "Test 2: เปิด CTranslate2 debug mode"
echo "----------------------------------------"
export CT2_VERBOSE=1
export CUDA_LAUNCH_BLOCKING=1

timeout 20 python3 << 'PYEOF'
import ctranslate2
from faster_whisper import WhisperModel
from itertools import islice
import time

print("Checking CTranslate2 CUDA version...")
try:
    ct2_cuda = ctranslate2.get_cuda_version()
    print(f"CT2 CUDA version: {ct2_cuda}")
except Exception as e:
    print(f"Error getting CT2 CUDA version: {e}")

print("\nLoading model with debug...")
model = WhisperModel('medium', device='cuda', compute_type='float16')
print("Transcribing...")
segments, info = model.transcribe('uploads/v05-1_direct_audio.wav', language='th')
print(f"transcribe() done")

print("Testing islice with debug...")
start = time.time()
for i, seg in enumerate(islice(segments, 1)):
    print(f"✓ Segment {i}: {seg.text[:50]}")
    print(f"  Time: {time.time() - start:.2f}s")
PYEOF

unset CT2_VERBOSE
unset CUDA_LAUNCH_BLOCKING

if [ $? -eq 0 ]; then
    print_success "Test 2 PASSED"
else
    print_error "Test 2 FAILED"
    cleanup
    exit 1
fi
cleanup
echo ""

# Test 3: ทดสอบ CPU mode
print_test "Test 3: ทดสอบ CPU mode (ตัดปัจจัย GPU)"
echo "----------------------------------------"
timeout 60 python3 << 'PYEOF'
from faster_whisper import WhisperModel
from itertools import islice
import time

print("Loading model (CPU)...")
model = WhisperModel('medium', device='cpu', compute_type='int8')
print("Transcribing (CPU)...")
segments, info = model.transcribe('uploads/v05-1_direct_audio.wav', language='th', vad_filter=False)
print(f"transcribe() done: {info.duration}s")

print("Testing islice (CPU)...")
start = time.time()
for i, seg in enumerate(islice(segments, 1)):
    print(f"✓ Segment {i}: [{seg.start:.2f}s-{seg.end:.2f}s] {seg.text[:50]}")
    print(f"  Time: {time.time() - start:.2f}s")
print("✓ CPU test PASSED")
PYEOF

if [ $? -eq 0 ]; then
    print_success "Test 3 PASSED - CPU works, problem is GPU-related"
else
    print_error "Test 3 FAILED - CPU also hangs, problem is elsewhere"
    cleanup
    exit 1
fi
cleanup
echo ""

# Test 4: ลด concurrency
print_test "Test 4: ลด concurrency (num_workers=1, cpu_threads=4)"
echo "----------------------------------------"
timeout 20 python3 << 'PYEOF'
from faster_whisper import WhisperModel
from itertools import islice
import time

print("Loading model (conservative settings)...")
model = WhisperModel(
    'medium',
    device='cuda',
    device_index=0,
    compute_type='float16',
    cpu_threads=4,
    num_workers=1
)

print("Transcribing (vad_filter=False, without_timestamps=True)...")
segments, info = model.transcribe(
    'uploads/v05-1_direct_audio.wav',
    language='th',
    vad_filter=False,
    word_timestamps=False,
    without_timestamps=True
)
print(f"transcribe() done")

print("Testing islice...")
start = time.time()
for i, seg in enumerate(islice(segments, 1)):
    print(f"✓ Segment {i}: {seg.text[:50]}")
    print(f"  Time: {time.time() - start:.2f}s")
print("✓ Conservative settings test PASSED")
PYEOF

if [ $? -eq 0 ]; then
    print_success "Test 4 PASSED"
else
    print_error "Test 4 FAILED"
    cleanup
    exit 1
fi
cleanup
echo ""

# Test 5: เช็ก ffmpeg และแปลงไฟล์
print_test "Test 5: แปลงไฟล์ด้วย ffmpeg (16k mono)"
echo "----------------------------------------"
if [ ! -f "${AUDIO_FILE%.*}_16k.wav" ]; then
    echo "Converting audio to 16k mono..."
    ffmpeg -y -i "$AUDIO_FILE" -ac 1 -ar 16000 -f wav "${AUDIO_FILE%.*}_16k.wav" 2>&1 | tail -5
    print_success "File converted"
else
    print_success "File already exists"
fi

timeout 20 python3 << PYEOF
from faster_whisper import WhisperModel
from itertools import islice
import time

print("Loading model...")
model = WhisperModel('medium', device='cuda', compute_type='float16', num_workers=1)

print("Transcribing converted file...")
segments, info = model.transcribe(
    '${AUDIO_FILE%.*}_16k.wav',
    language='th',
    vad_filter=False,
    word_timestamps=False
)
print(f"transcribe() done")

print("Testing islice...")
start = time.time()
for i, seg in enumerate(islice(segments, 1)):
    print(f"✓ Segment {i}: {seg.text[:50]}")
    print(f"  Time: {time.time() - start:.2f}s")
PYEOF

if [ $? -eq 0 ]; then
    print_success "Test 5 PASSED"
else
    print_error "Test 5 FAILED"
    cleanup
    exit 1
fi
cleanup
echo ""

# Test 6: ปิดฟีเจอร์ที่กินเวลา
print_test "Test 6: ปิดฟีเจอร์ที่กินเวลา (beam=1, temp=0)"
echo "----------------------------------------"
timeout 20 python3 << PYEOF
from faster_whisper import WhisperModel
from itertools import islice
import time

print("Loading model...")
model = WhisperModel('medium', device='cuda', compute_type='float16', num_workers=1)

print("Transcribing (minimal settings)...")
segments, info = model.transcribe(
    '${AUDIO_FILE%.*}_16k.wav',
    language='th',
    vad_filter=False,
    word_timestamps=False,
    beam_size=1,
    temperature=0.0
)
print(f"transcribe() done")

print("Testing islice...")
start = time.time()
for i, seg in enumerate(islice(segments, 1)):
    print(f"✓ Segment {i}: {seg.text[:50]}")
    print(f"  Time: {time.time() - start:.2f}s")
PYEOF

if [ $? -eq 0 ]; then
    print_success "Test 6 PASSED"
else
    print_error "Test 6 FAILED"
    cleanup
    exit 1
fi
cleanup
echo ""

# Summary
echo "=========================================="
echo "✅ All debug tests completed!"
echo "=========================================="

