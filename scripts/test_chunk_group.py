#!/usr/bin/env python3
"""
ทดสอบ Chunk Group API
เปรียบเทียบ: flow ปกติ vs chunk_group
วัด CPU usage และเวลา
"""
import json
import os
import sys
import time
from pathlib import Path

# เพิ่ม project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ใช้ requests ถ้ามี
try:
    import requests
except ImportError:
    requests = None

API_BASE = os.getenv("API_BASE", "http://localhost:8001")


def get_chunk_paths(chunk_dir: str) -> list[str]:
    """ดึง paths ของ chunks เรียงตามลำดับ"""
    base = Path(chunk_dir)
    if not base.exists():
        raise FileNotFoundError(f"ไม่พบโฟลเดอร์: {chunk_dir}")
    chunks = sorted(base.glob("chunk_*.wav"))
    # ใช้ path แบบ relative จาก workspace (uploads/xxx/chunk_0000.wav)
    return [str(c.relative_to(Path.cwd())) if c.is_relative_to(Path.cwd()) else str(c) for c in chunks]


def start_transcription_chunk_group(file_paths: list[str], language: str = "th") -> dict:
    """ส่ง chunk group ไป API"""
    url = f"{API_BASE}/api/transcribe/"
    payload = {
        "file_paths": file_paths,
        "chunk_group": True,
        "language": language,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def start_transcription_normal(file_path: str, language: str = "th") -> dict:
    """ส่งไฟล์เดี่ยวไป API (flow ปกติ)"""
    url = f"{API_BASE}/api/transcribe/"
    payload = {
        "file_path": file_path,
        "language": language,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def get_task_status(task_id: str) -> dict:
    """ดึงสถานะ task"""
    url = f"{API_BASE}/api/v2/tasks/{task_id}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def poll_until_done(task_id: str, poll_interval: float = 2.0, max_wait: int = 600) -> dict:
    """รอจน task เสร็จ"""
    start = time.time()
    while (time.time() - start) < max_wait:
        data = get_task_status(task_id)
        status = data.get("status", "")
        if status in ("completed", "failed", "cancelled"):
            return data
        time.sleep(poll_interval)
    raise TimeoutError(f"Task {task_id} ไม่เสร็จภายใน {max_wait}s")


def main():
    if not requests:
        print("ต้องติดตั้ง requests: pip install requests")
        return 1

    # โฟลเดอร์ chunks ที่สร้างไว้
    chunk_dir = Path("uploads/0e692d52-364e-424a-8f1a-4903c30cdaeb_3fe4b1ff-26e2-4883-a278-7ecad8b1fd5b_chapter_video_b41379a4-6100-4b29-8d60-87e97ee3da8c")
    if not chunk_dir.exists():
        print(f"ไม่พบโฟลเดอร์ chunks: {chunk_dir}")
        print("รัน split_wav_to_chunks.py ก่อน")
        return 1

    chunks = sorted(chunk_dir.glob("chunk_*.wav"))
    file_paths = [str(p).replace("\\", "/") for p in chunks]
    if not file_paths:
        print("ไม่พบไฟล์ chunk ในโฟลเดอร์")
        return 1

    print("=" * 60)
    print("ทดสอบ Chunk Group API")
    print("=" * 60)
    print(f"Chunks: {len(file_paths)} ไฟล์")
    for i, p in enumerate(file_paths[:3]):
        print(f"  {i}: {p}")
    if len(file_paths) > 3:
        print(f"  ... และอีก {len(file_paths)-3} ไฟล์")
    print()

    # ทดสอบ Chunk Group
    print("1. ส่ง Chunk Group request...")
    t0 = time.time()
    try:
        result = start_transcription_chunk_group(file_paths)
        task_id = result["task_id"]
        print(f"   Task ID: {task_id}")
        print(f"   Response: {json.dumps(result, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"   Error: {e}")
        return 1

    print("\n2. รอ task เสร็จ (poll ทุก 2 วินาที)...")
    try:
        final = poll_until_done(task_id)
        elapsed = time.time() - t0
        print(f"   Status: {final.get('status')}")
        print(f"   เวลารวม (API call + รอเสร็จ): {elapsed:.1f} วินาที")
        if final.get("status") == "completed":
            text = final.get("full_text", final.get("text", ""))
            print(f"   ความยาวข้อความ: {len(text)} ตัวอักษร")
    except Exception as e:
        print(f"   Error: {e}")
        return 1

    print("\n" + "=" * 60)
    print("ทดสอบเสร็จ")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
