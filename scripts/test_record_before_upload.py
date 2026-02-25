#!/usr/bin/env python3
"""
ทดสอบ: Record ทั้งหมด ควรเสร็จก่อน Upload
- Upload 2 ตัว → Record 1 → รอ 3 นาที → Upload 3 ตัว → Record 2
- คาดหวัง: ทุก Record เสร็จก่อน Upload ตัวแรก

Usage:
  python scripts/test_record_before_upload.py
  API_BASE_URL=https://xxx.proxy.runpod.net python scripts/test_record_before_upload.py
"""
import os
import sys
import time
import requests
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8010")
UPLOAD_FILE = "uploads/audio_154b9abb-b177-40a4-87e0-72b5bbc809f2.wav"
RECORD_FILE = "uploads/record_10min_test.wav"


def ensure_record_file():
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
        capture_output=True, check=True,
    )
    return record_path


def send_upload(path: Path) -> dict:
    r = requests.post(
        f"{API_BASE}/api/transcribe/",
        json={"file_path": str(path.resolve()), "language": "th"},
        timeout=30,
    )
    return {"ok": r.status_code in (200, 201), "task_id": r.json().get("task_id") if r.ok else None}


def send_record(path: Path) -> dict:
    r = requests.post(
        f"{API_BASE}/api/transcribe/",
        json={"file_path": str(path.resolve()), "language": "th", "source": "video_record"},
        timeout=30,
    )
    return {"ok": r.status_code in (200, 201), "task_id": r.json().get("task_id") if r.ok else None}


def get_status(task_id: str) -> dict:
    try:
        r = requests.get(f"{API_BASE}/api/v2/tasks/{task_id}?format=progress", timeout=5)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def poll_until_done(task_ids: list, labels: dict, completion_order: list, interval=3, max_wait=7200):
    results = {tid: {"status": "pending", "elapsed": None} for tid in task_ids}
    start = time.time()
    last_print = 0
    while time.time() - start < max_wait:
        all_done = True
        for tid in task_ids:
            if results[tid]["status"] in ("completed", "failed"):
                continue
            t = get_status(tid)
            status = t.get("status", "pending")
            prev = results[tid]["status"]
            results[tid]["status"] = status
            if status == "completed":
                results[tid]["elapsed"] = t.get("elapsed_seconds") or t.get("elapsed")
                if prev != "completed":
                    completion_order.append((tid, time.time() - start, labels.get(tid, "?")))
            elif status == "failed":
                results[tid]["error"] = t.get("error_message", "")
            else:
                all_done = False
        if time.time() - last_print > 30:
            pending = sum(1 for tid in task_ids if results[tid]["status"] not in ("completed", "failed"))
            print(f"  ⏳ รอ... {(time.time()-start)/60:.1f} นาที | เหลือ {pending} tasks")
            last_print = time.time()
        if all_done:
            break
        time.sleep(interval)
    return results


def wait_minutes(t_start: float, minutes: float):
    elapsed = time.time() - t_start
    target = minutes * 60
    if elapsed < target:
        wait = target - elapsed
        print(f"  ⏳ รอ {wait/60:.1f} นาที...")
        time.sleep(wait)


def main():
    print("=" * 70)
    print("🧪 ทดสอบ: Record ทั้งหมด ควรเสร็จก่อน Upload")
    print("=" * 70)
    print(f"API: {API_BASE}")
    print("Timeline: Upload 2 → Record 1 → รอ 3 นาที → Upload 3 → Record 2")
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

    labels = {}
    all_ids = []
    t_start = time.time()

    # Step 1: Upload 2 ตัว
    print("Step 1: ส่ง Upload 2 ตัว")
    for i in range(2):
        res = send_upload(upload_path)
        if res["ok"]:
            tid = res["task_id"]
            all_ids.append(tid)
            labels[tid] = f"Upload {i+1}"
            print(f"  ✅ {labels[tid]}: {tid[:8]}...")
        else:
            print(f"  ❌ Upload {i+1}: failed")
        time.sleep(0.3)

    # Step 2: Record 1
    print()
    print("Step 2: ส่ง Record 1")
    res = send_record(record_path)
    if res["ok"]:
        tid = res["task_id"]
        all_ids.append(tid)
        labels[tid] = "Record 1"
        print(f"  ✅ Record 1: {tid[:8]}...")
    else:
        print("  ❌ Record 1: failed")

    # Step 3: รอ 3 นาที
    print()
    print("Step 3: รอ 3 นาที...")
    wait_minutes(t_start, 3)

    # Step 4: Upload 3 ตัว
    print()
    print("Step 4: ส่ง Upload 3 ตัว")
    for i in range(3):
        res = send_upload(upload_path)
        if res["ok"]:
            tid = res["task_id"]
            all_ids.append(tid)
            labels[tid] = f"Upload {i+3}"
            print(f"  ✅ {labels[tid]}: {tid[:8]}...")
        else:
            print(f"  ❌ Upload {i+3}: failed")
        time.sleep(0.3)

    # Step 5: Record 2
    print()
    print("Step 5: ส่ง Record 2")
    res = send_record(record_path)
    if res["ok"]:
        tid = res["task_id"]
        all_ids.append(tid)
        labels[tid] = "Record 2"
        print(f"  ✅ Record 2: {tid[:8]}...")
    else:
        print("  ❌ Record 2: failed")

    # Step 6: รอจนเสร็จ
    completion_order = []
    print()
    print("Step 6: รอจนทุก task เสร็จ...")
    results = poll_until_done(all_ids, labels, completion_order)

    # Step 7: แสดงผลและวิเคราะห์
    print()
    print("=" * 70)
    print("📅 ลำดับการเสร็จ")
    print("=" * 70)
    for rank, (tid, sec, label) in enumerate(completion_order, 1):
        elapsed = results.get(tid, {}).get("elapsed")
        print(f"  #{rank:2} ที่ {sec/60:.1f} นาที | {label} | elapsed={elapsed/60:.1f}min" if elapsed else f"  #{rank:2} ที่ {sec/60:.1f} นาที | {label}")

    # ตรวจสอบ: Record ทั้งหมดเสร็จก่อน Upload ตัวแรกหรือไม่
    print()
    print("=" * 70)
    print("🔍 วิเคราะห์: Record เสร็จก่อน Upload หรือไม่")
    print("=" * 70)

    record_ranks = [r for r, (tid, _, _) in enumerate(completion_order, 1) if "Record" in labels.get(tid, "")]
    upload_ranks = [r for r, (tid, _, _) in enumerate(completion_order, 1) if "Upload" in labels.get(tid, "")]

    if record_ranks and upload_ranks:
        max_record_rank = max(record_ranks)
        min_upload_rank = min(upload_ranks)
        passed = max_record_rank < min_upload_rank
        print(f"  Record สูงสุดอันดับ: {max_record_rank}")
        print(f"  Upload แรกอันดับ: {min_upload_rank}")
        if passed:
            print("  ✅ Record ทั้งหมดเสร็จก่อน Upload ตัวแรก")
        else:
            print("  ❌ มี Upload เสร็จก่อน Record บางตัว")
    else:
        print("  ⚠️ ไม่มีข้อมูลเพียงพอ")

    print("=" * 70)
    ok = record_ranks and upload_ranks and max(record_ranks) < min(upload_ranks)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
