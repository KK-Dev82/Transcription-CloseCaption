#!/usr/bin/env python3
"""
ทดสอบ Queue Priority: Upload 10 + Record 1 (Record เริ่มตอนนาทีที่ 4)
- MAX_CONCURRENT_REQUESTS=11 (Upload 10 + Record 1)
- ส่ง Upload 10 tasks (ไฟล์ ~30 นาที) ก่อน
- รอจนถึงนาทีที่ 4 แล้วส่ง Record 1 task (ไฟล์ ~10 นาที)
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

RECORD_START_MINUTE = 4  # ส่ง Record ตอนนาทีที่ 4


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


def poll_until_done(task_ids: list, interval: float = 3, max_wait: int = 3600, completion_order: list = None) -> dict:
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


def main():
    print("=" * 70)
    print("🧪 ทดสอบ Queue Priority: Upload 10 + Record 1 (Record เริ่มนาทีที่ 4)")
    print("=" * 70)
    print(f"API: {API_BASE}")
    print(f"MAX_CONCURRENT_REQUESTS=10 + Record 5 = 15 total (Record มี slot สำรอง)")
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
    print(f"⏳ Record จะส่งตอนนาทีที่ {RECORD_START_MINUTE}")
    print()

    # 1. ส่ง Upload 10 tasks + บันทึกเวลา submit
    t_start = time.time()
    submit_times = {}  # task_id -> (label, submit_offset_sec)
    print(f"Step 1: ส่ง Upload 10 tasks (เริ่ม {time.strftime('%H:%M:%S')})")
    upload_task_ids = []
    for i in range(10):
        result = send_upload(upload_path)
        if result["status_code"] in (200, 201):
            tid = result["task_id"]
            upload_task_ids.append(tid)
            submit_times[tid] = (f"Upload {i+1}", time.time() - t_start)
            print(f"  ✅ Upload {i+1}/10: {tid[:8]}...")
        else:
            print(f"  ❌ Upload {i+1}/10: {result['status_code']}")
        time.sleep(0.5)

    if len(upload_task_ids) < 10:
        print(f"❌ ได้ Upload แค่ {len(upload_task_ids)}/10")
        return 1

    # 2. รอจนถึงนาทีที่ 4
    wait_seconds = RECORD_START_MINUTE * 60 - (time.time() - t_start)
    if wait_seconds > 0:
        print()
        print(f"Step 2: รอจนถึงนาทีที่ {RECORD_START_MINUTE} ({wait_seconds:.0f} วินาที)...")
        time.sleep(wait_seconds)

    # 3. ส่ง Record
    record_submit_time = time.time()
    elapsed_min = (record_submit_time - t_start) / 60
    print()
    print(f"Step 3: ส่ง Record 1 task (นาทีที่ {elapsed_min:.1f})")
    record_result = send_record(record_path)
    if record_result["status_code"] in (200, 201):
        record_task_id = record_result["task_id"]
        submit_times[record_task_id] = ("Record", time.time() - t_start)
        print(f"  ✅ Record: {record_task_id[:8]}...")
    else:
        print(f"  ❌ Record: {record_result['status_code']}")
        return 1

    # 4. รอจนทุก task เสร็จ + บันทึกลำดับการเสร็จ
    all_task_ids = upload_task_ids + [record_task_id]
    completion_order = []
    print()
    print("Step 4: รอจนทุก task เสร็จ...")
    done = poll_until_done(all_task_ids, interval=3, completion_order=completion_order)

    # 5. แสดงผล + Timeline
    print()
    print("=" * 70)
    print("📊 ผลลัพธ์: เวลาในการแปลงเสียงเป็นข้อความ")
    print("=" * 70)

    upload_times = []
    record_time = None
    for i, tid in enumerate(all_task_ids):
        r = done.get(tid, {})
        status = r.get("status", "?")
        elapsed = r.get("elapsed")
        label = "Record (10 min)" if i == 10 else f"Upload {i+1} (30 min)"
        if elapsed is not None:
            print(f"  {label}: {elapsed/60:.1f} นาที ({elapsed:.0f}s) - {status}")
            if i == 10:
                record_time = elapsed
            else:
                upload_times.append(elapsed)

    # Timeline: เวลา submit, ลำดับการเสร็จ, created_at, updated_at
    print()
    print("=" * 70)
    print("📅 Timeline: เวลา submit vs ลำดับการแปลงเสร็จ")
    print("=" * 70)
    tid_to_label = {tid: (f"Upload {i+1}" if i < 10 else "Record") for i, tid in enumerate(all_task_ids)}
    for rank, (tid, completed_at_sec) in enumerate(completion_order, 1):
        label = tid_to_label.get(tid, tid[:8])
        submit_sec = submit_times.get(tid, (None, 0))[1]
        r = done.get(tid, {})
        created = r.get("created_at", "")[:19] if r.get("created_at") else "-"
        updated = r.get("updated_at", "")[:19] if r.get("updated_at") else "-"
        print(f"  #{rank:2} เสร็จที่ {completed_at_sec/60:.1f} นาที | submit ที่ {submit_sec/60:.1f} นาที | {label}")
        print(f"       created_at: {created} | updated_at: {updated}")

    # สรุปตามประเภท
    print()
    print("  📌 ลำดับการเสร็จ (Record vs Upload):")
    record_rank = next((r for r, (tid, _) in enumerate(completion_order, 1) if tid == record_task_id), None)
    if record_rank:
        print(f"     - Record เสร็จเป็นอันดับที่ {record_rank}/11")
        print(f"     - Upload ที่เสร็จก่อน Record: {record_rank - 1} ตัว")

    # วิเคราะห์
    print()
    print("=" * 70)
    print("🔍 วิเคราะห์")
    print("=" * 70)
    if record_time and upload_times:
        record_min = record_time / 60
        upload_min_sorted = sorted([t/60 for t in upload_times])
        if record_min < min(upload_min_sorted):
            print("  ✅ Record เสร็จก่อน Upload ทุกตัว = Record แซงคิวได้")
        else:
            completed_before_record = sum(1 for u in upload_times if u < record_time)
            print(f"  📌 Upload ที่เสร็จก่อน Record: {completed_before_record}/10")
            print(f"  📌 Record เสร็จใน {record_min:.1f} นาที (ส่งตอนนาทีที่ {RECORD_START_MINUTE})")
            print(f"  📌 elapsed = updated_at - created_at (เวลาตั้งแต่สร้าง task จนเสร็จ)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
