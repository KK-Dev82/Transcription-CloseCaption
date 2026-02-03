#!/usr/bin/env python3
"""
ทดสอบ transcription ด้วยไฟล์ WAV ตัวเดียว
ใช้ path เดียวกับ /api/transcription และ live-chunk FE-CC (WhisperService + model จาก env)

วิธีใช้:
  1) รันโดยตรง (ต้องมี dependencies + GPU ใน env):
     # ถ้ารันแล้วเจอ libcudnn not found ให้ set LD_LIBRARY_PATH ก่อน (หรือรัน scripts/utility/setup-cudnn-env.sh):
     export LD_LIBRARY_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib:/usr/lib/x86_64-linux-gnu:/usr/local/cuda-12.1/lib64:/usr/local/lib/python3.10/dist-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}"
     python3 scripts/test_transcription_single_file.py

  2) ทดสอบผ่าน API (เมื่อ Main API รันอยู่ที่ localhost:8010):
     ./scripts/test_transcription_single_file_via_api.sh
     หรือ
     curl -s -X POST http://localhost:8010/api/internal/transcribe \\
       -H "Content-Type: application/json" \\
       -d '{"audio_path":"/workspace/transcription-service/uploads/f89a1ae1-08f0-4e84-bb33-808b331a5c8c_S20260115009049C02.wav","model_size":"Vinxscribe/biodatlab-whisper-th-medium-faster","language":"th","use_thai_processor":true}'
"""
import os
import sys
from pathlib import Path

WAV_PATH = "/workspace/transcription-service/uploads/f89a1ae1-08f0-4e84-bb33-808b331a5c8c_S20260115009049C02.wav"

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
            # ตัด inline comment (# ...) ออกจากค่า
            if "#" in v:
                v = v.split("#")[0].strip()
            if k and v and not v.startswith("$"):
                os.environ[k] = v
    print(f"✅ Loaded {env_file}")


def main():
    if not Path(WAV_PATH).exists():
        print(f"❌ ไม่พบไฟล์: {WAV_PATH}")
        sys.exit(1)

    model_size = os.getenv("CC_MODEL_SIZE") or os.getenv("WHISPER_MODEL", "Vinxscribe/biodatlab-whisper-th-medium-faster")
    language = os.getenv("CC_LANGUAGE", "th")
    if model_size.startswith("models--"):
        parts = model_size.replace("models--", "").split("--", 1)
        if len(parts) == 2:
            model_size = f"{parts[0]}/{parts[1]}"

    print(f"📂 ไฟล์: {WAV_PATH}")
    print(f"📦 Model: {model_size}")
    print(f"🌍 Language: {language}")
    print("🔄 กำลัง transcribe (ใช้ WhisperService เหมือน /transcription และ FE-CC)...")
    print()

    try:
        from app.services.whisper_service import WhisperService
    except Exception as e:
        print(f"❌ ไม่สามารถโหลด WhisperService ได้: {e}")
        print()
        print("💡 แนะนำ: ทดสอบผ่าน API แทน (เมื่อ Main API รันอยู่):")
        print(f"   curl -s -X POST http://localhost:8010/api/internal/transcribe \\")
        print(f"     -H 'Content-Type: application/json' \\")
        print(f"     -d '{{\"audio_path\":\"{WAV_PATH}\",\"model_size\":\"{model_size}\",\"language\":\"{language}\",\"use_thai_processor\":true}}'")
        sys.exit(1)

    whisper = WhisperService()
    result = whisper.transcribe_file(
        audio_path=WAV_PATH,
        model_size=model_size,
        language=language,
        use_thai_processor=(language == "th"),
    )

    text = (result.get("text") or "").strip()
    segments = result.get("segments", [])
    print("=" * 60)
    print("📝 ผลลัพธ์ (text):")
    print("=" * 60)
    print(text[:2000] + ("..." if len(text) > 2000 else ""))
    print()
    print(f"📊 จำนวน segments: {len(segments)}")
    print(f"📏 ความยาวข้อความ: {len(text)} ตัวอักษร")
    print("✅ ทดสอบ transcription สำเร็จ (path เดียวกับ /transcription และ live-chunk FE-CC)")


if __name__ == "__main__":
    main()
