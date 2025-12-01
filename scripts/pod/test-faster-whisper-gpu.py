#!/usr/bin/env python3
"""
Test script สำหรับทดสอบ faster-whisper บน GPU
ใช้เพื่อตรวจสอบว่า GPU transcription ทำงานได้และไม่ค้าง

Usage:
    python3 scripts/pod/test-faster-whisper-gpu.py [audio_file] [model_size]

Examples:
    python3 scripts/pod/test-faster-whisper-gpu.py uploads/v05-1_16k.wav tiny
    python3 scripts/pod/test-faster-whisper-gpu.py temp/sample_16k.wav medium
"""

import os
import sys
import time
from pathlib import Path

# ตั้งค่า environment variables ก่อน import faster_whisper
os.environ.setdefault("CT2_USE_CUDA_GRAPH", "0")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

from faster_whisper import WhisperModel

def main():
    # Parse arguments
    audio_file = sys.argv[1] if len(sys.argv) > 1 else "/workspace/transcription-service/temp/sample_16k.wav"
    model_size = os.environ.get("WHISPER_MODEL", "tiny") if len(sys.argv) <= 2 else sys.argv[2]
    
    # Check if audio file exists
    audio_path = Path(audio_file)
    if not audio_path.exists():
        print(f"❌ Audio file not found: {audio_file}")
        print(f"   Current directory: {os.getcwd()}")
        print(f"   Looking for: {audio_path.absolute()}")
        sys.exit(1)
    
    print("=" * 60)
    print("🧪 Testing faster-whisper on GPU")
    print("=" * 60)
    print(f"📁 Audio file: {audio_file}")
    print(f"📦 Model: {model_size}")
    print(f"🖥️  Device: cuda")
    print(f"⚙️  Compute type: float16")
    print(f"🔧 CT2_USE_CUDA_GRAPH: {os.getenv('CT2_USE_CUDA_GRAPH', '0')}")
    print("")
    
    # Load model
    print("📥 Loading model...")
    load_start = time.time()
    try:
        model = WhisperModel(
            model_size,
            device="cuda",
            compute_type="float16",
            num_workers=1,
            cpu_threads=4
        )
        load_time = time.time() - load_start
        print(f"✅ Model loaded in {load_time:.2f}s")
        print("")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Transcribe
    print("🎤 Transcribing...")
    transcribe_start = time.time()
    try:
        segments, info = model.transcribe(
            str(audio_path),
            language="th",
            vad_filter=False,  # เริ่ม false ก่อน
            without_timestamps=True,
            beam_size=1,
            temperature=0.0
        )
        transcribe_time = time.time() - transcribe_start
        print(f"✅ transcribe() completed in {transcribe_time:.2f}s")
        print("")
    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Check segments
    print("=" * 60)
    print("📊 Results")
    print("=" * 60)
    print(f"Duration: {getattr(info, 'duration', 'N/A'):.2f}s" if hasattr(info, 'duration') else "Duration: N/A")
    print(f"Language: {getattr(info, 'language', 'N/A')}")
    print(f"Segments type: {type(segments)}")
    print(f"Is list: {isinstance(segments, list)}")
    print("")
    
    if isinstance(segments, list):
        print(f"✅ Returns LIST! Count: {len(segments)}")
        if len(segments) > 0:
            first_text = segments[0].get("text", "") if isinstance(segments[0], dict) else getattr(segments[0], "text", "")
            print(f"First segment: {first_text[:80]}")
            print("")
            print("✅ Test PASSED - GPU transcription working correctly!")
        else:
            print("⚠️  List is empty")
    else:
        print("⚠️  Still returns GENERATOR (expected list with without_timestamps=True)")
        print("Trying to get first segment...")
        try:
            first = next(iter(segments))
            first_text = getattr(first, "text", "")
            print(f"First segment: {first_text[:80]}")
            print("")
            print("✅ Test PARTIAL - Got first segment but still generator")
        except StopIteration:
            print("❌ Generator is empty")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error iterating generator: {e}")
            sys.exit(1)
    
    print("")
    print("=" * 60)
    print("✅ Test completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()

