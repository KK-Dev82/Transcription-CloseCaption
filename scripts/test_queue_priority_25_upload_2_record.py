#!/usr/bin/env python3
"""
ทดสอบ Queue Priority: 25 Upload + 2 Record (จำลอง timeline)
- นาทีที่ 0:  3 Uploads
- นาทีที่ 2:  1 Record
- นาทีที่ 3:  23 Uploads (รวม 26 Uploads)
- นาทีที่ 10: 1 Record (รวม 2 Records)

ต้องใช้ MAX_CONCURRENT_REQUESTS=25, MAX_CONCURRENT_RECORD_SLOTS=5 (เช่น .env.runpod-1GPU)
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

# ไฟล์ทดสอบ
UPLOAD_FILE = "uploads/audio_154b9abb-b177-40a4-87e0-72b5bbc809f2.wav"  # ~31 min
RECORD_FILE = "uploads/record_10min_test.wav"  # ~10 min


def ensure_record_file():
    """สร้างไฟล์ Record 10 นาที ถ้ายังไม่มี"""
    record_path = project_root / RECORD_FILE
    if record_path.exists():
        return record_path
    src = project_root / UPLOAD_FILE
    if not src.exists():
        raise FileNotFoundError(f"ไม่พบ {UPLOAD_FILE}")
    import subprocess
    record_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-t", "600", "-acodec", "copy", str(record_path)],
        capture_output=True,
        check=True,
    )
    return record_path


def send_upload(file_path: Path) -> dict:
    r = requests.post(
        f"{API_BASE}/api/transcribe/",
        json={"file_path": str(file_path.resolve()), "language": "th"},
        timeout=30,
    )
    return {"status_code": r.status_code, "task_id": r.json().get("task_id") if r.ok else None}


def send_record(file_path: Path) -> dict:
    r = requests.post(
        f"{API_BASE}/api/transcribe/",
        json={"file_path": str(file_path.resolve()), "language": "th", "source": "video_record"},
        timeout=30,
    )
    return {"status_code": r.status_code, "task_id": r.json().get("task_id") if r.ok else None}


def get_task_status(task_id: str) -> dict:
    try:
        r = requests.get(f"{API_BASE}/api/v2/tasks/{task_id}?format=progress", timeout=5)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def poll_until_done(task_ids: list, interval: float = 3, max_wait: int = 7200, completion_order: list = None) -> dict:
    """Poll until done; record completion_order when each task transitions to completed."""
    if completion_order is None:
        completion_order = []
    results = {tid: {"status": "pending", "elapsed": None, "created_at": None, "updated_at": None} for tid in task_ids}
    start = time.time()
    last_print = 0
    while time.time() - start < max_wait:
        all_done = True
        for tid in task_ids:
            if results[tid]["status"] in ("completed", "failed"):
                continue
            t = get_task_status(tid)
            status = t.get("status", "pending")
            prev_status = results[tid]["status"]
            results[tid]["status"] = status
            results[tid]["created_at"] = t.get("created_at")
            results[tid]["updated_at"] = t.get("updated_at")
            if status == "completed":
                results[tid]["elapsed"] = t.get("elapsed_seconds") or t.get("elapsed")
                if prev_status != "completed" and completion_order is not None:
                    completion_order.append((tid, time.time() - start))
            elif status == "failed":
                results[tid]["error"] = t.get("error_message", "")
            else:
                all_done = False
        if time.time() - last_print > 30:
            elapsed = time.time() - start
            pending = sum(1 for tid in task_ids if results[tid]["status"] not in ("completed", "failed"))
            print(f"  ⏳ รอ... {elapsed/60:.1f} นาที | เหลือ {pending} tasks")
            last_print = time.time()
        if all_done:
            break
        time.sleep(interval)
    return results


def wait_until_minute(t_start: float, minute: float) -> bool:
    """รอจนถึงนาทีที่กำหนด (จาก t_start). คืน True ถ้าถึงแล้ว."""
    elapsed = time.time() - t_start
    target_sec = minute * 60
    if elapsed < target_sec:
        wait_sec = target_sec - elapsed
        print(f"  ⏳ รอจนถึงนาทีที่ {minute} ({wait_sec:.0f} วินาที)...")
        time.sleep(wait_sec)
    return True


def main():
    print("=" * 70)
    print("🧪 ทดสอบ Queue Priority: 25 Upload + 2 Record (จำลอง timeline)")
    print("=" * 70)
    print(f"API: {API_BASE}")
    print("⚠️  ใช้ .env.runpod-1GPU หรือ MAX_CONCURRENT_REQUESTS=25, MAX_CONCURRENT_RECORD_SLOTS=5")
    print("Timeline:")
    print("  นาทีที่ 0:  3 Uploads")
    print("  นาทีที่ 2:  1 Record")
    print("  นาทีที่ 3:  23 Uploads (รวม 26 Uploads)")
    print("  นาทีที่ 10: 1 Record (รวม 2 Records)")
    print()

    upload_path = project_root / UPLOAD_FILE
    if not upload_path.exists():
        print(f"❌ ไม่พบ {UPLOAD_FILE}")
        return 1

    try:
        record_path = ensure_record_file()
    except Exception as e:
        print(f"❌ {e}")
        return 1

    print(f"📂 Upload (30 min): {UPLOAD_FILE}")
    print(f"📂 Record (10 min): {RECORD_FILE}")
    print()

    t_start = time.time()
    all_task_ids = []
    task_labels = {}  # task_id -> label
    submit_times = {}  # task_id -> (label, submit_offset_sec)

    # Step 1: นาทีที่ 0 — 3 Uploads
    print(f"Step 1: ส่ง 3 Uploads (นาทีที่ 0)")
    for i in range(3):
        result = send_upload(upload_path)
        if result["status_code"] in (200, 201):
            tid = result["task_id"]
            all_task_ids.append(tid)
            label = f"Upload {i+1}"
            task_labels[tid] = label
            submit_times[tid] = (label, time.time() - t_start)
            print(f"  ✅ {label}: {tid[:8]}...")
        else:
            print(f"  ❌ Upload {i+1}: {result['status_code']}")
        time.sleep(0.3)

    # Step 2: นาทีที่ 2 — 1 Record
    wait_until_minute(t_start, 2)
    print()
    print(f"Step 2: ส่ง 1 Record (นาทีที่ 2)")
    result = send_record(record_path)
    if result["status_code"] in (200, 201):
        tid = result["task_id"]
        all_task_ids.append(tid)
        task_labels[tid] = "Record 1"
        submit_times[tid] = ("Record 1", time.time() - t_start)
        print(f"  ✅ Record 1: {tid[:8]}...")
    else:
        print(f"  ❌ Record 1: {result['status_code']}")

    # Step 3: นาทีที่ 3 — 23 Uploads (รวม 26 Uploads)
    wait_until_minute(t_start, 3)
    print()
    print(f"Step 3: ส่ง 23 Uploads (นาทีที่ 3)")
    for i in range(23):
        result = send_upload(upload_path)
        idx = 4 + i
        if result["status_code"] in (200, 201):
            tid = result["task_id"]
            all_task_ids.append(tid)
            label = f"Upload {idx}"
            task_labels[tid] = label
            submit_times[tid] = (label, time.time() - t_start)
            print(f"  ✅ {label}: {tid[:8]}...")
        else:
            print(f"  ❌ Upload {idx}: {result['status_code']} (อาจได้ 429 ถ้าเกิน limit)")
        time.sleep(0.2)

    # Step 4: นาทีที่ 10 — 1 Record
    wait_until_minute(t_start, 10)
    print()
    print(f"Step 4: ส่ง 1 Record (นาทีที่ 10)")
    result = send_record(record_path)
    if result["status_code"] in (200, 201):
        tid = result["task_id"]
        all_task_ids.append(tid)
        task_labels[tid] = "Record 2"
        submit_times[tid] = ("Record 2", time.time() - t_start)
        print(f"  ✅ Record 2: {tid[:8]}...")
    else:
        print(f"  ❌ Record 2: {result['status_code']}")

    # Step 5: รอจนทุก task เสร็จ
    completion_order = []
    print()
    print("Step 5: รอจนทุก task เสร็จ...")
    done = poll_until_done(all_task_ids, interval=3, completion_order=completion_order)

    # Step 6: แสดงผล
    print()
    print("=" * 70)
    print("📊 ผลลัพธ์: เวลาในการแปลงเสียงเป็นข้อความ")
    print("=" * 70)

    record_times = []
    upload_times = []
    for tid in all_task_ids:
        r = done.get(tid, {})
        status = r.get("status", "?")
        elapsed = r.get("elapsed")
        label = task_labels.get(tid, tid[:8])
        if elapsed is not None:
            print(f"  {label}: {elapsed/60:.1f} นาที ({elapsed:.0f}s) - {status}")
            if "Record" in label:
                record_times.append(elapsed)
            else:
                upload_times.append(elapsed)
        else:
            print(f"  {label}: - ({status})")

    # Timeline: ลำดับการเสร็จ
    print()
    print("=" * 70)
    print("📅 ลำดับการแปลงเสร็จ (Record ควรเสร็จก่อน Upload หลายตัว)")
    print("=" * 70)
    for rank, (tid, completed_at_sec) in enumerate(completion_order, 1):
        label = task_labels.get(tid, tid[:8])
        submit_sec = submit_times.get(tid, (None, 0))[1]
        print(f"  #{rank:2} เสร็จที่ {completed_at_sec/60:.1f} นาที | submit ที่ {submit_sec/60:.1f} นาที | {label}")

    # วิเคราะห์ Record vs Upload
    print()
    print("=" * 70)
    print("🔍 วิเคราะห์")
    print("=" * 70)
    total_tasks = len(all_task_ids)
    record_1_rank = next((r for r, (tid, _) in enumerate(completion_order, 1) if task_labels.get(tid) == "Record 1"), None)
    record_2_rank = next((r for r, (tid, _) in enumerate(completion_order, 1) if task_labels.get(tid) == "Record 2"), None)
    if record_1_rank:
        print(f"  Record 1 เสร็จอันดับที่: {record_1_rank}/{total_tasks}")
    if record_2_rank:
        print(f"  Record 2 เสร็จอันดับที่: {record_2_rank}/{total_tasks}")
    if record_times and upload_times:
        avg_record = sum(record_times) / len(record_times) / 60
        avg_upload = sum(upload_times) / len(upload_times) / 60
        print(f"  Record เฉลี่ย: {avg_record:.1f} นาที")
        print(f"  Upload เฉลี่ย: {avg_upload:.1f} นาที")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
