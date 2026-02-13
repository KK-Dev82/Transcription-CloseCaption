#!/usr/bin/env python3
"""
Test: แปลง WAV 3 ครั้ง วัดเวลาทั้งหมดและ Performance
ใช้ไฟล์ WAV 16k mono ที่พร้อมใช้ (ไม่ต้อง Convert)
"""

import os
import sys
import time
import requests
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load env
for f in [project_root / ".env.runpod", project_root / ".env"]:
    if f.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(f)
            break
        except ImportError:
            pass

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8010")
MODEL = os.getenv("WHISPER_MODEL", "deepdml/faster-whisper-large-v3-turbo-ct2")

# ไฟล์ WAV ที่ตรวจสอบแล้ว: 16kHz mono, พร้อมใช้
WAV_FILE = "uploads/b4aa2077-cb43-4135-8007-7f9f6ed2302a_260128_1020 อนุฯ พัฒนาระบบ (บริหารราชการแผ่นดิน) 2.wav"


def submit():
    fp = project_root / WAV_FILE
    if not fp.exists():
        print(f"❌ ไม่พบไฟล์: {fp}")
        return None
    try:
        r = requests.post(
            f"{API_BASE}/api/transcribe/",
            json={
                "file_path": str(fp.resolve()),
                "language": "th",
                "model_size": MODEL,
                "chunk_duration": 150,
            },
            timeout=30,
        )
        if r.status_code == 200:
            return r.json().get("task_id")
        print(f"  API {r.status_code}: {r.text[:150]}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def wait_done(task_id: str, timeout: int = 3600):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{API_BASE}/api/v2/tasks/{task_id}", timeout=10)
            if r.status_code == 200:
                d = r.json()
                if d.get("status") == "completed":
                    return d
                if d.get("status") in ("failed", "cancelled"):
                    return d
        except Exception:
            pass
        time.sleep(3)
    return None


def main():
    fp = project_root / WAV_FILE
    if not fp.exists():
        print(f"❌ ไม่พบไฟล์: {fp}")
        sys.exit(1)

    print("=" * 70)
    print("🧪 Test: แปลง WAV 3 ครั้ง — วัดเวลาทั้งหมด")
    print("=" * 70)
    print()
    print("ไฟล์: b4aa2077-cb43-4135-8007-7f9f6ed2302a_260128_1020...wav")
    print("Format: 16 kHz mono, 16-bit PCM (~31 min) — พร้อมใช้ ไม่ต้อง Convert")
    print()

    times = []
    total_start = time.time()

    for i in range(1, 4):
        print(f"📤 Run {i}/3: Submitting...", end=" ", flush=True)
        task_id = submit()
        if not task_id:
            print("❌ ล้มเหลว")
            continue
        print(f"OK ({task_id[:12]}...)")

        run_start = time.time()
        result = wait_done(task_id)
        run_elapsed = time.time() - run_start

        if result and result.get("status") == "completed":
            times.append(run_elapsed)
            print(f"   ✅ เสร็จใน {run_elapsed:.1f}s ({run_elapsed/60:.2f} min)")
        else:
            print(f"   ❌ {result.get('status', 'timeout')} ({run_elapsed:.1f}s)")

    total_elapsed = time.time() - total_start

    print()
    print("=" * 70)
    print("📊 สรุปผล")
    print("=" * 70)
    print(f"  สำเร็จ: {len(times)}/3")
    if times:
        print(f"  เวลารวมทั้ง 3 ครั้ง: {total_elapsed:.1f}s ({total_elapsed/60:.2f} min)")
        print(f"  เฉลี่ยต่อครั้ง: {sum(times)/len(times):.1f}s")
        print(f"  เร็วที่สุด: {min(times):.1f}s")
        print(f"  ช้าที่สุด: {max(times):.1f}s")
    print()
    print("  หมายเหตุ: WAV 16k mono ข้าม Extract/Convert → ใช้ CPU น้อยกว่า MP3")
    print("=" * 70)


if __name__ == "__main__":
    main()
