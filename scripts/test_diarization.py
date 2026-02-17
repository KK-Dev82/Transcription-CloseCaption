#!/usr/bin/env python3
"""
ทดสอบ Diarization Service (pyannote) แบบ standalone

วิธีใช้:
  1) ใช้ไฟล์เสียงที่มีอยู่:
     python3 scripts/test_diarization.py /path/to/audio.wav

  2) สร้างไฟล์ทดสอบ (ความเงียบ 10 วินาที) สำหรับทดสอบ pipeline โหลด:
     python3 scripts/test_diarization.py --create-test

  3) ใช้ env WAV_PATH:
     WAV_PATH=/path/to/audio.wav python3 scripts/test_diarization.py

ต้องตั้ง PYANNOTE_MODEL_DIR หรือ PYANNOTE_HF_TOKEN ใน .env.runpod
"""
import argparse
import os
import sys
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# โหลด .env.runpod
env_file = PROJECT_ROOT / ".env.runpod"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if "#" in v:
                v = v.split("#")[0].strip()
            if k and v and not v.startswith("$"):
                os.environ[k] = v
    print(f"✅ Loaded {env_file}")


def create_test_wav(path: Path, duration_sec: int = 10, sample_rate: int = 16000) -> Path:
    """สร้างไฟล์ WAV ความเงียบสำหรับทดสอบ"""
    path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = sample_rate * duration_sec
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(b"\x00\x00" * n_samples)
    print(f"📂 สร้างไฟล์ทดสอบ: {path} ({duration_sec}s)")
    return path


def main():
    parser = argparse.ArgumentParser(description="ทดสอบ Diarization Service")
    parser.add_argument("audio_path", nargs="?", help="Path to audio file (.wav)")
    parser.add_argument("--create-test", action="store_true", help="สร้างไฟล์ WAV เงียบสำหรับทดสอบ")
    args = parser.parse_args()

    wav_path = args.audio_path or os.getenv("WAV_PATH")
    if args.create_test:
        test_path = PROJECT_ROOT / "uploads" / "test_diarization_silence.wav"
        wav_path = str(create_test_wav(test_path))
    elif not wav_path:
        print("❌ ระบุ audio_path หรือ WAV_PATH หรือใช้ --create-test")
        print("   ตัวอย่าง: python3 scripts/test_diarization.py /path/to/audio.wav")
        sys.exit(1)

    wav_path = Path(wav_path).resolve()
    if not wav_path.exists():
        print(f"❌ ไม่พบไฟล์: {wav_path}")
        sys.exit(1)

    print(f"📂 ไฟล์: {wav_path}")
    print(f"📦 PYANNOTE_MODEL_DIR: {os.getenv('PYANNOTE_MODEL_DIR', '(ไม่ตั้ง)')}")
    print("🔄 กำลังรัน diarization...")
    print()

    try:
        from app.services.diarization_service import diarize
    except ImportError as e:
        print(f"❌ ไม่สามารถโหลด diarization_service ได้: {e}")
        print("   pip install pyannote.audio==3.3.2")
        sys.exit(1)

    try:
        segments = diarize(str(wav_path))
        print("=" * 60)
        print("📊 ผล Diarization:")
        print("=" * 60)
        print(f"จำนวน segments: {len(segments)}")
        if segments:
            print("\n5 segments แรก:")
            for s in segments[:5]:
                print(f"  {s['start']:.2f}s - {s['end']:.2f}s: {s['speaker']}")
        print()
        print("✅ ทดสอบ Diarization สำเร็จ")
    except Exception as e:
        print(f"❌ Diarization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
