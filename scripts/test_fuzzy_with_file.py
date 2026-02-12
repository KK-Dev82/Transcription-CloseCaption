#!/usr/bin/env python3
"""
ทดสอบ Fuzzy match กับไฟล์ WAV ผ่าน full pipeline (preprocess → chunks → aggregator + Fuzzy)
ส่ง job ไป API แล้ว monitor จนเสร็จ พร้อมดู log Thai/Fuzzy
"""
import os
import sys
import time
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# โหลด .env.runpod
env_file = PROJECT_ROOT / ".env.runpod"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

API_BASE = os.getenv("API_BASE", "http://localhost:8010")
FILE_PATH = "uploads/0ac3e39b-23ba-47e3-a696-aafebfe9b8f3_S25690212009646C02.wav"
FULL_PATH = PROJECT_ROOT / FILE_PATH


def main():
    if not FULL_PATH.exists():
        print(f"❌ ไม่พบไฟล์: {FULL_PATH}")
        sys.exit(1)

    print("=" * 60)
    print("🧪 ทดสอบ Fuzzy Match กับ File Transcription")
    print("=" * 60)
    print(f"📂 ไฟล์: {FILE_PATH}")
    print(f"🌐 API: {API_BASE}")
    print(f"✅ FUZZY_MATCH_ENABLED_FOR_TRANSCRIPTION={os.getenv('FUZZY_MATCH_ENABLED_FOR_TRANSCRIPTION', 'true')}")
    print()

    # ส่ง job
    try:
        r = requests.post(
            f"{API_BASE}/api/transcribe/",
            json={"file_path": FILE_PATH, "language": "th"},
            timeout=30
        )
        r.raise_for_status()
        data = r.json()
        task_id = data.get("task_id")
        print(f"✅ ส่ง job สำเร็จ: task_id={task_id}")
    except Exception as e:
        print(f"❌ ส่ง job ไม่สำเร็จ: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"   Response: {e.response.text[:300]}")
        sys.exit(1)

    print()
    print("📋 Monitor progress (Ctrl+C เพื่อหยุด):")
    print("   python scripts/check_task_status.py", task_id)
    print()
    print("📋 ดู log Fuzzy/Thai แบบ real-time:")
    print("   tail -F /tmp/rq-worker-cpu-*.log 2>/dev/null | grep -E 'Fuzzy|Thai|merging|Processed|🔤|🇹🇭' --line-buffered")
    print()
    print("⏳ รอจนเสร็จ (poll ทุก 5 วินาที)...")
    print()

    start = time.time()
    last_progress = -1
    while True:
        try:
            r = requests.get(f"{API_BASE}/api/v2/tasks/{task_id}?format=minimal", timeout=10)
            if r.status_code != 200:
                time.sleep(5)
                continue
            d = r.json()
            status = d.get("status", "")
            progress = d.get("progress", 0)
            stage = d.get("current_stage") or d.get("current_stage_description") or ""

            if progress != last_progress or status == "completed" or status == "failed":
                elapsed = int(time.time() - start)
                print(f"   [{elapsed}s] status={status}, progress={progress}%, stage={stage}")
                last_progress = progress

            if status == "completed":
                print()
                print("=" * 60)
                print("✅ เสร็จสิ้น!")
                full_text = d.get("full_text", "")
                print(f"📝 full_text (ตัวแรก 500 chars): {full_text[:500]}...")
                print()
                sys.exit(0)

            if status == "failed":
                print()
                print("❌ ล้มเหลว:", d.get("error_message", "unknown"))
                sys.exit(1)

        except Exception as e:
            print(f"   ⚠️ Poll error: {e}")
        time.sleep(5)


if __name__ == "__main__":
    main()
