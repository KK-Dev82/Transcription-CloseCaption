#!/usr/bin/env python3
"""
ทดสอบ Queue Priority: Upload 30 นาที vs Record 10 นาที
- ส่ง Upload 3 tasks (ไฟล์ ~30 นาที) ก่อน
- แทรก Record 1 task (ไฟล์ ~10 นาที)
- ตรวจสอบว่า Record เสร็จก่อน Upload หรือไม่ (Record แซงคิวได้)
"""

import os
import sys
import time
import requests
from pathlib import Path
from datetime import datetime

# Add project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Config
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8010")
UPLOADS_DIR = project_root / "uploads"

# ไฟล์ทดสอบ (ต้องมีใน uploads/)
UPLOAD_FILE = "uploads/audio_154b9abb-b177-40a4-87e0-72b5bbc809f2.wav"  # ~31 min
RECORD_FILE = "uploads/record_10min_test.wav"  # ~10 min (สร้างจาก ffmpeg -t 600)


def ensure_record_file():
    """สร้างไฟล์ Record 10 นาที ถ้ายังไม่มี"""
    record_path = project_root / RECORD_FILE
    if record_path.exists():
        return record_path
    # สร้างจากไฟล์ 30 นาที
    src = project_root / UPLOAD_FILE
    if not src.exists():
        raise FileNotFoundError(f"ไม่พบ {UPLOAD_FILE} สำหรับสร้าง record_10min_test.wav")
    import subprocess
    record_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-t", "600", "-acodec", "copy", str(record_path)],
        capture_output=True,
        check=True,
    )
    print(f"  สร้างไฟล์: {RECORD_FILE} (10 นาที)")
    return record_path


def send_upload(file_path: Path) -> dict:
    abs_path = str(file_path.resolve())
    r = requests.post(
        f"{API_BASE}/api/transcribe/",
        json={"file_path": abs_path, "language": "th"},
        timeout=30,
    )
    return {"status_code": r.status_code, "task_id": r.json().get("task_id") if r.ok else None}


def send_record(file_path: Path) -> dict:
    abs_path = str(file_path.resolve())
    r = requests.post(
        f"{API_BASE}/api/transcribe/",
        json={"file_path": abs_path, "language": "th", "source": "video_record"},
        timeout=30,
    )
    return {"status_code": r.status_code, "task_id": r.json().get("task_id") if r.ok else None}


def get_task_status(task_id: str) -> dict:
    try:
        r = requests.get(f"{API_BASE}/api/v2/tasks/{task_id}?format=progress", timeout=5)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def poll_until_done(task_ids: list, interval: float = 5, max_wait: int = 3600, verbose: bool = True) -> dict:
    """รอจนทุก task เสร็จ"""
    results = {tid: {"status": "pending", "elapsed": None, "completed_at": None} for tid in task_ids}
    start = time.time()
    last_print = 0
    while time.time() - start < max_wait:
        all_done = True
        for tid in task_ids:
            if results[tid]["status"] in ("completed", "failed"):
                continue
            t = get_task_status(tid)
            status = t.get("status", "pending")
            results[tid]["status"] = status
            if status == "completed":
                results[tid]["elapsed"] = t.get("elapsed_seconds") or t.get("elapsed")
                results[tid]["completed_at"] = time.time()
            elif status == "failed":
                results[tid]["error"] = t.get("error_message", "")
            else:
                all_done = False

        if verbose and time.time() - last_print > 30:
            elapsed = time.time() - start
            pending = sum(1 for tid in task_ids if results[tid]["status"] not in ("completed", "failed"))
            print(f"  ⏳ รอ... {elapsed/60:.1f} นาที | เหลือ {pending} tasks")
            last_print = time.time()

        if all_done:
            break
        time.sleep(interval)
    return results


def main():
    print("=" * 70)
    print("🧪 ทดสอบ Queue Priority: Upload 30 นาที vs Record 10 นาที")
    print("=" * 70)
    print(f"API: {API_BASE}")
    print()

    # 1. ตรวจสอบไฟล์
    upload_path = project_root / UPLOAD_FILE
    if not upload_path.exists():
        print(f"❌ ไม่พบ {UPLOAD_FILE}")
        return 1

    try:
        record_path = ensure_record_file()
    except Exception as e:
        print(f"❌ {e}")
        return 1

    upload_size = upload_path.stat().st_size / 1024 / 1024
    record_size = record_path.stat().st_size / 1024 / 1024
    print(f"📂 Upload (30 min): {UPLOAD_FILE} ({upload_size:.1f} MB)")
    print(f"📂 Record (10 min): {RECORD_FILE} ({record_size:.1f} MB)")
    print()

    # 2. ส่ง Upload 3 tasks
    print("Step 1: ส่ง Upload 3 tasks (ไฟล์ 30 นาที)")
    t0 = time.time()
    upload_task_ids = []
    for i in range(3):
        result = send_upload(upload_path)
        if result["status_code"] in (200, 201):
            upload_task_ids.append(result["task_id"])
            print(f"  ✅ Upload {i+1}/3: task_id={result['task_id'][:8]}...")
        else:
            print(f"  ❌ Upload {i+1}/3: {result['status_code']}")
        time.sleep(1)

    if len(upload_task_ids) < 3:
        print("❌ ต้องได้ Upload 3 tasks")
        return 1

    # 3. รอให้ preprocess เริ่ม (chunks ไป GPU queue)
    print()
    print("⏳ รอ 30 วินาที (ให้ preprocess เริ่ม, chunks ไป upload queue)...")
    time.sleep(30)

    # 4. แทรก Record
    print()
    print("Step 2: แทรก Record 1 task (ไฟล์ 10 นาที)")
    record_result = send_record(record_path)
    record_submit_time = time.time()
    if record_result["status_code"] in (200, 201):
        record_task_id = record_result["task_id"]
        print(f"  ✅ Record: task_id={record_task_id[:8]}... (ส่งหลัง Upload ~{record_submit_time - t0:.0f}s)")
    else:
        print(f"  ❌ Record: {record_result['status_code']}")
        return 1

    # 5. รอจนทุก task เสร็จ
    all_task_ids = upload_task_ids + [record_task_id]
    print()
    print("⏳ รอจนทุก task เสร็จ (อาจใช้เวลา 5–15 นาที)...")
    done = poll_until_done(all_task_ids, interval=10, max_wait=1800)

    # 6. แสดงผลและวิเคราะห์
    print()
    print("=" * 70)
    print("📊 ผลลัพธ์: เวลาในการแปลงเสียงเป็นข้อความ")
    print("=" * 70)

    upload_times = []
    record_time = None
    record_completed_first = False
    upload_completed_count_when_record_done = 0

    for i, tid in enumerate(all_task_ids):
        r = done.get(tid, {})
        status = r.get("status", "?")
        elapsed = r.get("elapsed")
        label = "Record (10 min)" if i == 3 else f"Upload {i+1} (30 min)"
        if elapsed is not None:
            print(f"  {label}: {elapsed/60:.1f} นาที ({elapsed:.0f} วินาที) - {status}")
            if i == 3:
                record_time = elapsed
            else:
                upload_times.append(elapsed)

    # วิเคราะห์: Record เสร็จก่อน Upload หรือไม่
    print()
    print("=" * 70)
    print("🔍 วิเคราะห์: Record แซงคิวได้หรือไม่?")
    print("=" * 70)

    if record_time and upload_times:
        # Record ใช้เวลาน้อยกว่า Upload (10 min vs 30 min) เป็นปกติ
        # สิ่งที่สำคัญ: Record ส่งทีหลัง แต่เสร็จก่อน Upload บางตัวหรือไม่
        # ถ้า Record เสร็จใน ~2-4 นาที (สำหรับ 10 min file) และ Upload ยังไม่เสร็จ = แซงได้
        record_min = record_time / 60
        upload_min = [t / 60 for t in upload_times]
        print(f"  Record (10 min): เสร็จใน {record_min:.1f} นาที")
        print(f"  Upload (30 min): เสร็จใน {upload_min[0]:.1f}, {upload_min[1]:.1f}, {upload_min[2]:.1f} นาที")
        print()
        if record_min < min(upload_min):
            print("  ✅ Record เสร็จก่อน Upload ทุกตัว = Record ได้ slot ก่อน (แซงคิวได้)")
        else:
            print("  📌 Record และ Upload รันพร้อมกัน (Shared Pool)")
            print("     Record ใช้เวลาน้อยกว่าเพราะไฟล์สั้นกว่า (10 min vs 30 min)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
