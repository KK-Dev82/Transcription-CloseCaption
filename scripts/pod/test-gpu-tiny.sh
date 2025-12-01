#!/bin/bash
# Test script ตามคำแนะนำใหม่ - ทดสอบ tiny model บน GPU

set -e

AUDIO_FILE="${1:-uploads/v05-1_16k.wav}"

export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export CUDA_VISIBLE_DEVICES=0
export CT2_USE_CUDA_GRAPH=0  # ปิด CUDA Graph
export CT2_VERBOSE=1
export CUDA_LAUNCH_BLOCKING=1

echo "=========================================="
echo "Test: Tiny model on GPU"
echo "=========================================="
echo "Settings:"
echo "  - CT2_USE_CUDA_GRAPH=0"
echo "  - num_workers=1, cpu_threads=4"
echo "  - vad_filter=False"
echo "  - without_timestamps=True"
echo "  - beam_size=1, temperature=0.0"
echo ""

timeout 30 python3 << 'PYEOF'
from faster_whisper import WhisperModel
import time

print("Loading tiny model...")
start = time.time()
m = WhisperModel(
    "tiny",
    device="cuda",
    device_index=0,
    compute_type="float16",
    num_workers=1,
    cpu_threads=4
)
print(f"Model loaded in {time.time() - start:.2f}s")

print("Transcribing...")
transcribe_start = time.time()
segs, info = m.transcribe(
    "uploads/v05-1_16k.wav",
    language="th",
    vad_filter=False,
    without_timestamps=True,
    beam_size=1,
    temperature=0.0
)
transcribe_time = time.time() - transcribe_start
print(f"transcribe() completed in {transcribe_time:.2f}s")
print(f"Duration: {info.duration:.2f}s, Language: {info.language}")

print()
print("Checking segments...")
print(f"Type: {type(segs)}")
print(f"Is list: {isinstance(segs, list)}")

if isinstance(segs, list):
    print(f"✓ Returns LIST! Count: {len(segs)}")
    if len(segs) > 0:
        print(f"First segment: {segs[0].text[:80]}")
        print("✓ Test PASSED")
    else:
        print("⚠️ List is empty")
else:
    print("Still generator, trying first segment...")
    first = next(iter(segs))
    print(f"Got first: {first.text[:80]}")
    print("✓ Test PARTIAL (got first segment but still generator)")
PYEOF

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Test completed"
else
    echo ""
    echo "❌ Test failed or timeout"
    exit 1
fi

