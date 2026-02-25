#!/usr/bin/env python3
"""
ทดสอบ Queue Priority: ส่ง Upload 3 ก่อน แล้วแทรก Record
- ใช้ MAX_CONCURRENT_REQUESTS=3 (ตั้งใน .env.runpod)
- ใช้ไฟล์ .wav จาก uploads/ ใน project
- ตรวจสอบว่า Record ไปคิว record และแซง Upload ได้
"""

import os
import sys
import time
import requests
from pathlib import Path

# Add project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Config
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8010")
UPLOADS_DIR = project_root / "uploads"


def get_wav_file() -> Path:
    """ดึงไฟล์ .wav จาก uploads/ (ใช้ไฟล์สั้นที่สุดเพื่อทดสอบเร็ว)"""
    if not UPLOADS_DIR.exists():
        raise FileNotFoundError(f"ไม่พบ uploads/: {UPLOADS_DIR}")
    wavs = list(UPLOADS_DIR.glob("*.wav"))
    if not wavs:
        raise FileNotFoundError(f"ไม่พบไฟล์ .wav ใน {UPLOADS_DIR}")
    # เลือกไฟล์ที่เล็กที่สุด (ทดสอบเร็ว)
    return min(wavs, key=lambda p: p.stat().st_size)


def send_upload(file_path: Path) -> dict:
    """ส่ง Upload task (ไม่ใส่ source)"""
    abs_path = str(file_path.resolve())
    r = requests.post(
        f"{API_BASE}/api/transcribe/",
        json={"file_path": abs_path, "language": "th"},
        timeout=30,
    )
    return {"status_code": r.status_code, "data": r.json() if r.ok else r.text, "task_id": r.json().get("task_id") if r.ok else None}


def send_record(file_path: Path) -> dict:
    """ส่ง Record task (source=video_record)"""
    abs_path = str(file_path.resolve())
    r = requests.post(
        f"{API_BASE}/api/transcribe/",
        json={"file_path": abs_path, "language": "th", "source": "video_record"},
        timeout=30,
    )
    return {"status_code": r.status_code, "data": r.json() if r.ok else r.text, "task_id": r.json().get("task_id") if r.ok else None}


def get_task_status(task_id: str) -> dict:
    """ดึงสถานะ task จาก API (format=progress มี elapsed_seconds)"""
    try:
        r = requests.get(f"{API_BASE}/api/v2/tasks/{task_id}?format=progress", timeout=5)
        if r.ok:
            d = r.json()
            # progress format มี elapsed_seconds
            if "elapsed_seconds" in d:
                d["elapsed"] = d["elapsed_seconds"]
            return d
        return {}
    except Exception:
        return {}


def poll_until_done(task_ids: list, interval: float = 5, max_wait: int = 600) -> dict:
    """รอจนทุก task เสร็จ แล้วคืน elapsed ต่อ task"""
    import time
    results = {tid: {"status": "pending", "elapsed": None} for tid in task_ids}
    start = time.time()
    while time.time() - start < max_wait:
        all_done = True
        for tid in task_ids:
            if results[tid]["status"] in ("completed", "failed"):
                continue
            t = get_task_status(tid)
            status = t.get("status", "pending")
            results[tid]["status"] = status
            if status == "completed":
                # ใช้ elapsed_seconds จาก API ถ้ามี
                elapsed = t.get("elapsed_seconds") or t.get("elapsed")
                if elapsed is not None:
                    results[tid]["elapsed"] = float(elapsed)
                else:
                    created = t.get("created_at", "")
                    updated = t.get("updated_at", "")
                    if created and updated:
                        try:
                            from datetime import datetime
                            c = datetime.fromisoformat(created.replace("Z", "+00:00"))
                            u = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                            results[tid]["elapsed"] = (u - c).total_seconds()
                        except Exception:
                            pass
            elif status == "failed":
                results[tid]["error"] = t.get("error_message", "")
            else:
                all_done = False
        if all_done:
            break
        time.sleep(interval)
    return results


def get_queue_status() -> dict:
    """ดึง queue status จาก debug endpoint"""
    try:
        r = requests.get(f"{API_BASE}/api/transcribe/debug/queue", timeout=5)
        return r.json().get("queues", {}) if r.ok else {}
    except Exception as e:
        return {"error": str(e)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ทดสอบ Queue Priority: Upload 3 → แทรก Record")
    parser.add_argument("--wait", action="store_true", help="รอจนทุก task เสร็จ แล้วแสดงเวลา")
    args = parser.parse_args()
    print("=" * 60)
    print("🧪 ทดสอบ Queue Priority: Upload 3 → แทรก Record")
    print("=" * 60)
    print(f"API: {API_BASE}")
    print(f"MAX_CONCURRENT_REQUESTS=4 (Upload 3 + Record 1)")
    print()

    # 1. ดึงไฟล์ .wav
    try:
        wav_file = get_wav_file()
        print(f"📂 ใช้ไฟล์: {wav_file.name} ({wav_file.stat().st_size / 1024 / 1024:.2f} MB)")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    # 2. ส่ง Upload 3 tasks
    print()
    print("Step 1: ส่ง Upload 3 tasks")
    upload_task_ids = []
    for i in range(3):
        result = send_upload(wav_file)
        if result["status_code"] in (200, 201):
            tid = result.get("task_id", "")
            upload_task_ids.append(tid)
            print(f"  ✅ Upload {i+1}/3: task_id={tid[:8]}...")
        elif result["status_code"] == 429:
            print(f"  ⚠️ Upload {i+1}/3: 429 Rate Limited (คิวเต็ม)")
        else:
            print(f"  ❌ Upload {i+1}/3: {result['status_code']} - {result.get('data', '')[:80]}")
        time.sleep(0.5)

    if not upload_task_ids:
        print("❌ ไม่มี Upload สำเร็จ")
        return 1

    # 3. รอให้ preprocess เริ่ม (chunks ไป GPU queue)
    print()
    print("⏳ รอ 15 วินาที (ให้ preprocess เริ่ม, chunks ไป upload queue)...")
    time.sleep(15)

    # 4. ตรวจสอบ queue ก่อนแทรก Record
    q_before = get_queue_status()
    print()
    print("📊 Queue status ก่อนแทรก Record:")
    for k in ["upload_gpu0", "upload_gpu1", "record_gpu0", "record_gpu1", "preprocess", "preprocess_video_record"]:
        v = q_before.get(k, {})
        if isinstance(v, dict):
            ln = v.get("length", 0)
            st = v.get("started", 0)
            print(f"  {k}: queued={ln}, started={st}")
        elif k in q_before:
            print(f"  {k}: {q_before[k]}")

    # 5. แทรก Record
    print()
    print("Step 2: แทรก Record 1 task")
    record_result = send_record(wav_file)
    if record_result["status_code"] in (200, 201):
        record_tid = record_result.get("task_id", "")
        print(f"  ✅ Record: task_id={record_tid[:8]}...")
    elif record_result["status_code"] == 429:
        print(f"  ⚠️ Record: 429 Rate Limited (คิวเต็ม - Record ควรได้ slot พิเศษที่ preprocess)")
    else:
        print(f"  ❌ Record: {record_result['status_code']} - {record_result.get('data', '')[:80]}")

    # 6. รอแล้วตรวจสอบ queue อีกครั้ง
    print()
    print("⏳ รอ 10 วินาที...")
    time.sleep(10)

    q_after = get_queue_status()
    print()
    print("📊 Queue status หลังแทรก Record:")
    for k in ["upload_gpu0", "upload_gpu1", "record_gpu0", "record_gpu1", "preprocess", "preprocess_video_record"]:
        v = q_after.get(k, {})
        if isinstance(v, dict):
            ln = v.get("length", 0)
            st = v.get("started", 0)
            print(f"  {k}: queued={ln}, started={st}")

    # 7. Optional: รอจนเสร็จและแสดงเวลา
    all_task_ids = upload_task_ids + ([record_result.get("task_id")] if record_result.get("task_id") else [])
    if args.wait and all_task_ids:
        print()
        print("⏳ รอจนทุก task เสร็จ (--wait)...")
        done = poll_until_done(all_task_ids, interval=5, max_wait=600)
        print()
        print("📊 เวลาในการแปลงเสียงเป็นข้อความ:")
        total_elapsed = 0
        for i, tid in enumerate(all_task_ids):
            r = done.get(tid, {})
            status = r.get("status", "?")
            elapsed = r.get("elapsed")
            label = "Record" if i == 3 else f"Upload {i+1}"
            if elapsed is not None:
                print(f"  {label}: {elapsed:.1f} วินาที ({status})")
                total_elapsed += elapsed
            else:
                print(f"  {label}: - ({status})")
        if len([e for t in all_task_ids for e in [done.get(t, {}).get("elapsed")] if e]) > 0:
            avg = total_elapsed / len(all_task_ids)
            print(f"  เฉลี่ย: {avg:.1f} วินาที/ไฟล์")

    print()
    print("=" * 60)
    print("💡 ตรวจสอบ:")
    print("  - Record ควรไป record_gpu0/1 (ไม่ใช่ upload_gpu0/1)")
    print("  - Worker log: tail -f /tmp/rq-worker-gpu0-w0.log")
    print("  - ใช้ --wait เพื่อรอจนเสร็จและดูเวลา")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
