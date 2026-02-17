#!/usr/bin/env python3
"""
วัดเวลาจริง: Transcription เปรียบเทียบ ระหว่าง ไม่มี vs มี Diarization
สำหรับไฟล์ ~30 นาที
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WAV_PATH = os.getenv(
    "WAV_PATH",
    str(PROJECT_ROOT / "uploads" / "b4aa2077-cb43-4135-8007-7f9f6ed2302a_260128_1020 อนุฯ พัฒนาระบบ (บริหารราชการแผ่นดิน) 2.wav"),
)
API_BASE = os.getenv("API_BASE", "http://localhost:8010")
TIMEOUT = int(os.getenv("TIMEOUT", "600"))  # รอสูงสุด 10 นาที


def submit_job(enable_diarization: bool) -> str:
    url = f"{API_BASE}/api/transcribe-enhanced/start"
    payload = {
        "file_path": WAV_PATH,
        "language": "th",
        "enable_diarization": enable_diarization,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("task_id", "")


def wait_done(task_id: str) -> tuple[str, float]:
    """Poll until completed. Returns (status, elapsed_sec)"""
    url = f"{API_BASE}/api/v2/tasks/{task_id}?format=full"
    start = time.time()
    last_progress = -1
    while (time.time() - start) < TIMEOUT:
        try:
            r = requests.get(url, timeout=10)
            d = r.json()
        except Exception as e:
            print(f"  poll error: {e}")
            time.sleep(5)
            continue
        status = d.get("status") or d.get("data", {}).get("status", "")
        progress = d.get("progress") or d.get("data", {}).get("progress", 0)
        elapsed = time.time() - start
        if progress != last_progress:
            print(f"  [{elapsed:.0f}s] progress={progress}%")
            last_progress = progress
        if status in ("completed", "done"):
            return status, elapsed
        if status in ("failed", "error"):
            print("  ❌ Job failed")
            return status, elapsed
        time.sleep(5)
    return "timeout", time.time() - start


def main():
    if not Path(WAV_PATH).exists():
        print(f"❌ ไม่พบไฟล์: {WAV_PATH}")
        sys.exit(1)
    print(f"📂 ไฟล์: {WAV_PATH}")
    print(f"🌐 API: {API_BASE}")
    print()

    results = {}

    # 1) ไม่มี Diarization
    print("=" * 60)
    print("1️⃣ ทดสอบ: enable_diarization=False (baseline)")
    print("=" * 60)
    task_id = submit_job(enable_diarization=False)
    print(f"   task_id: {task_id}")
    status, elapsed = wait_done(task_id)
    results["without_diarization"] = {"status": status, "elapsed_sec": elapsed}
    print(f"   ผล: status={status}, เวลา={elapsed:.1f} วินาที ({elapsed/60:.2f} นาที)")
    print()

    # 2) มี Diarization
    print("=" * 60)
    print("2️⃣ ทดสอบ: enable_diarization=True")
    print("=" * 60)
    task_id = submit_job(enable_diarization=True)
    print(f"   task_id: {task_id}")
    status, elapsed = wait_done(task_id)
    results["with_diarization"] = {"status": status, "elapsed_sec": elapsed}
    print(f"   ผล: status={status}, เวลา={elapsed:.1f} วินาที ({elapsed/60:.2f} นาที)")
    print()

    # สรุป
    print("=" * 60)
    print("📊 สรุป")
    print("=" * 60)
    w = results["without_diarization"]
    d = results["with_diarization"]
    print(f"  ไม่มี Diarization: {w['elapsed_sec']:.1f}s ({w['elapsed_sec']/60:.2f} นาที) - {w['status']}")
    print(f"  มี Diarization:   {d['elapsed_sec']:.1f}s ({d['elapsed_sec']/60:.2f} นาที) - {d['status']}")
    overhead = d["elapsed_sec"] - w["elapsed_sec"]
    print(f"  Diarization overhead: +{overhead:.1f}s (+{overhead/60:.2f} นาที)")
    if w["elapsed_sec"] > 0:
        pct = (overhead / w["elapsed_sec"]) * 100
        print(f"  % เพิ่มขึ้น: +{pct:.0f}%")
    print()
    if d["elapsed_sec"] > 300:
        print("⚠️  มี Diarization ใช้เวลามากกว่า 5 นาที — อาจยังไม่เหมาะกับ Production")
    else:
        print("✅ มี Diarization ใช้เวลาน้อยกว่า 5 นาที")


if __name__ == "__main__":
    main()
