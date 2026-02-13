#!/usr/bin/env python3
"""
ทดสอบ transcription: วัดเวลา เนื้อหา และรูปแบบ Segment
ใช้ path + model ตาม .env.runpod
"""
import os
import sys
import time
import json
from pathlib import Path

WAV_PATH = "/workspace/transcription-service/uploads/b4aa2077-cb43-4135-8007-7f9f6ed2302a_260128_1020 อนุฯ พัฒนาระบบ (บริหารราชการแผ่นดิน) 2.wav"

# โหลด .env.runpod ก่อน import app
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
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

provider = os.getenv("WHISPER_PROVIDER", "faster-whisper")
model_display = os.getenv("TRANSCRIPTION_TYPHOON_MODEL") if provider == "nemo-typhoon" else (os.getenv("WHISPER_MODEL") or "medium")
if model_display and model_display.startswith("models--"):
    parts = model_display.replace("models--", "").split("--", 1)
    if len(parts) == 2:
        model_display = f"{parts[0]}/{parts[1]}"

def main():
    if not Path(WAV_PATH).exists():
        print(f"❌ ไม่พบไฟล์: {WAV_PATH}")
        sys.exit(1)

    # ตรวจสอบความยาวไฟล์ (โดยประมาณ)
    size_mb = Path(WAV_PATH).stat().st_size / (1024 * 1024)
    try:
        import wave
        with wave.open(WAV_PATH, 'rb') as w:
            frames = w.getnframes()
            rate = w.getframerate()
            duration_sec = frames / float(rate)
        print(f"📂 ไฟล์: {Path(WAV_PATH).name}")
        print(f"   ขนาด: {size_mb:.1f} MB | ความยาว: {duration_sec:.1f} วินาที ({duration_sec/60:.1f} นาที)")
    except Exception:
        print(f"📂 ไฟล์: {Path(WAV_PATH).name} ({size_mb:.1f} MB)")

    print(f"📦 Provider: {provider}")
    print(f"📦 Model: {model_display}")
    print("⏱️  เริ่มวัดเวลา...")
    start = time.time()

    try:
        from app.services.whisper_service import WhisperService
        whisper = WhisperService()
        result = whisper.transcribe_file(
            audio_path=WAV_PATH,
            model_size=model_display,
            language="th",
            use_thai_processor=True,
        )
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

    elapsed = time.time() - start
    text = (result.get("text") or "").strip()
    segments = result.get("segments", [])
    proc_time = result.get("processing_time")

    print()
    print("=" * 70)
    print("⏱️  เวลาที่ใช้")
    print("=" * 70)
    print(f"   เวลา total: {elapsed:.2f} วินาที ({elapsed/60:.1f} นาที)")
    if proc_time:
        print(f"   processing_time จาก result: {proc_time:.2f} วินาที")
    if 'duration_sec' in dir() and duration_sec > 0:
        rtf = elapsed / duration_sec
        print(f"   Real-Time Factor (RTF): {rtf:.2f}x (1x = realtime)")

    print()
    print("=" * 70)
    print("📝 เนื้อหา (ตัวอย่าง 1500 ตัวอักษรแรก)")
    print("=" * 70)
    print(text[:1500] + ("..." if len(text) > 1500 else ""))

    print()
    print("=" * 70)
    print("📊 Segment")
    print("=" * 70)
    print(f"   จำนวน segments: {len(segments)}")
    if segments:
        seg0 = segments[0]
        print(f"   รูปแบบ segment (ตัวอย่าง segment แรก): {json.dumps(seg0, ensure_ascii=False, indent=2)}")
        if len(segments) > 1:
            print(f"\n   ตัวอย่าง segment ที่ 2: {json.dumps(segments[1], ensure_ascii=False)}")
        if len(segments) > 2:
            print(f"   ตัวอย่าง segment สุดท้าย: {json.dumps(segments[-1], ensure_ascii=False)}")

    print()
    print(f"📏 ความยาวข้อความรวม: {len(text)} ตัวอักษร")
    print("✅ ทดสอบเสร็จสิ้น")

if __name__ == "__main__":
    main()
