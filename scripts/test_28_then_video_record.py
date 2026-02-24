#!/usr/bin/env python3
"""
ทดสอบ: ส่ง 28 Tasks → รอ 30 วินาที → ส่ง 1 Task source=video_record
ตรวจสอบ Response และการลัดคิว
"""
import os
import sys
import time
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8010")
M4A_FILE = "uploads/2e8024e5-9ab8-4263-9375-24a0ffa4545c_3fe4b1ff-26e2-4883-a278-7ecad8b1fd5b_chapter_video_b41379a4-6100-4b29-8d60-87e97ee3da8c.m4a"
VIDEO_RECORD_FILE = "uploads/fe71418c-f9a6-40b3-82f2-a572a922c5da_394e26b2-367a-4237-8753-26fe2ce68d88_chapter_video_36d7d0df-a7b1-4318-af4c-765f23a516ba.mp4"

# โหลด env
for env_file in [PROJECT_ROOT / ".env.runpod", PROJECT_ROOT / ".env.runpod-2GPU"]:
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
        break

def main():
    abs_m4a = str((PROJECT_ROOT / M4A_FILE).resolve())
    abs_video = str((PROJECT_ROOT / VIDEO_RECORD_FILE).resolve())

    if not Path(abs_m4a).exists():
        print(f"❌ ไม่พบไฟล์: {M4A_FILE}")
        return 1
    if not Path(abs_video).exists():
        print(f"❌ ไม่พบไฟล์: {VIDEO_RECORD_FILE}")
        return 1

    url = f"{API_BASE}/api/transcribe-enhanced/start"
    payload = {"file_path": abs_m4a, "language": "th"}

    print("=" * 60)
    print("🧪 ทดสอบ 28 Tasks + Video Record ลัดคิว")
    print("=" * 60)
    print(f"📂 ไฟล์ 28 tasks: {M4A_FILE}")
    print(f"📂 ไฟล์ video_record: {VIDEO_RECORD_FILE}")
    print(f"📡 API: {API_BASE}")
    print()

    # ส่ง 28 tasks
    print("⏳ ส่ง 28 tasks...")
    task_ids_28 = []
    ok_count = 0
    err_429_count = 0
    other_err = 0
    t_start = time.time()
    for i in range(28):
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code in (200, 201):
                data = r.json()
                task_ids_28.append(data.get("task_id"))
                ok_count += 1
            elif r.status_code == 429:
                err_429_count += 1
                print(f"   [{i+1}] 429: {r.json().get('detail', r.text)[:80]}")
            else:
                other_err += 1
                print(f"   [{i+1}] {r.status_code}: {r.text[:80]}")
        except Exception as e:
            other_err += 1
            print(f"   [{i+1}] Exception: {e}")
    submit_28_time = time.time() - t_start
    print(f"✅ ส่งครบ: OK={ok_count}, 429={err_429_count}, อื่น={other_err} ใน {submit_28_time:.1f}s")
    print()

    # รอ 30 วินาที
    print("⏳ รอ 30 วินาที...")
    time.sleep(30)

    # ส่ง video_record
    print()
    print("⏳ ส่ง 1 task source=video_record...")
    payload_vr = {"file_path": abs_video, "language": "th", "source": "video_record"}
    video_record_task_id = None
    try:
        r = requests.post(url, json=payload_vr, timeout=30)
        if r.status_code in (200, 201):
            data = r.json()
            video_record_task_id = data.get("task_id")
            print(f"✅ Video Record ได้รับ task_id: {video_record_task_id[:8]}...")
        elif r.status_code == 429:
            print(f"❌ Video Record ได้ 429: {r.json().get('detail', r.text)}")
        else:
            print(f"❌ Video Record ได้ {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"❌ Video Record Exception: {e}")

    # ตรวจสอบ queue status
    print()
    print("📊 ตรวจสอบ queue status (หลังส่ง video_record)...")
    try:
        r = requests.get(f"{API_BASE}/api/transcribe/debug/queue", timeout=10)
        if r.status_code == 200:
            d = r.json()
            if "queues" in d:
                for k, v in d["queues"].items():
                    if isinstance(v, dict) and "length" in v:
                        print(f"   {k}: queued={v.get('length',0)}, started={v.get('started',0)}")
    except Exception as e:
        print(f"   ไม่สามารถดึง queue status: {e}")

    # ตรวจสอบว่า video_record เริ่ม process ก่อนหรือไม่ (ถ้ามี task อยู่)
    if ok_count > 0 or video_record_task_id:
        print()
        print("💡 ตรวจสอบการลัดคิว: ดู log worker-preprocess ว่า video_record ถูก process ก่อนหรือไม่")
        print("   tail -f /tmp/rq-worker-preprocess-0.log")

    print()
    print("=" * 60)
    print("📊 สรุป")
    print("=" * 60)
    print(f"   28 tasks: OK={ok_count}, 429={err_429_count}")
    print(f"   Video Record: ส่งแล้ว (ดู log เพื่อยืนยันการลัดคิว)")
    print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
