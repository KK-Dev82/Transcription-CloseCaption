#!/usr/bin/env python3
"""
Test script สำหรับตรวจสอบ segments iteration โดยตรง
"""

import sys
import time
import signal
from faster_whisper import WhisperModel

def timeout_handler(signum, frame):
    raise TimeoutError("Test timeout")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)  # 30 seconds timeout

try:
    print("=" * 60)
    print("Testing faster-whisper segments iteration")
    print("=" * 60)
    
    print("\n1. Loading model...")
    start = time.time()
    model = WhisperModel('medium', device='cuda', compute_type='float16')
    print(f"   ✓ Loaded in {time.time() - start:.2f}s")
    
    print("\n2. Starting transcription...")
    transcribe_start = time.time()
    segments, info = model.transcribe('uploads/v05-1_direct_audio.wav', language='th')
    transcribe_time = time.time() - transcribe_start
    print(f"   ✓ Transcribe completed in {transcribe_time:.2f}s")
    print(f"   Duration: {info.duration:.2f}s, Language: {info.language}")
    
    print("\n3. Testing segments iteration...")
    print("   (This is where it usually hangs)")
    iter_start = time.time()
    
    # Try to get first segment
    print("   Trying to get first segment...")
    first_seg = next(segments, None)
    
    if first_seg is None:
        print("   ❌ No segments found!")
        sys.exit(1)
    
    print(f"   ✓ First segment: [{first_seg.start:.2f}s-{first_seg.end:.2f}s] {first_seg.text[:50]}")
    
    # Continue iterating
    count = 1
    segments_list = [first_seg]
    
    print("   Continuing iteration...")
    for segment in segments:
        segments_list.append(segment)
        count += 1
        if count <= 5:
            print(f"   Segment {count}: [{segment.start:.2f}s-{segment.end:.2f}s] {segment.text[:50]}")
        if count >= 20:
            break
    
    iter_time = time.time() - iter_start
    print(f"\n   ✓ Iterated {count} segments in {iter_time:.2f}s")
    
    full_text = ' '.join([s.text.strip() for s in segments_list])
    print(f"   ✓ Text length: {len(full_text)} characters")
    print(f"   ✓ First 150 chars: {full_text[:150]}")
    
    signal.alarm(0)
    print("\n✅ Test PASSED!")
    sys.exit(0)
    
except TimeoutError as e:
    print(f"\n❌ TIMEOUT: {e}")
    signal.alarm(0)
    sys.exit(1)
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    signal.alarm(0)
    sys.exit(1)

