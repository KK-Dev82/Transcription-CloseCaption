#!/usr/bin/env python3
"""
ทดสอบ 25 Chunk Group tasks
ส่ง 25 requests โดยใช้ชุด chunks เดียวกัน (9 ไฟล์) เพื่อวัดเวลาและระบบ

Usage:
  python scripts/test_25_chunk_group.py           # ส่งเท่านั้น
  python scripts/test_25_chunk_group.py --wait    # ส่งแล้วรอจนทุก task เสร็จ
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env.runpod")


def poll_until_all_done(task_ids: list, interval: float = 10, max_wait: int = 3600) -> dict:
    """รอจนทุก task เสร็จ (completed/failed/cancelled)"""
    from app.utils.sqlite_storage import SQLiteStorage
    storage = SQLiteStorage()
    start = time.time()
    while (time.time() - start) < max_wait:
        done = 0
        for tid in task_ids:
            t = storage.load_transcription(tid)
            if t and t.get("status") in ("completed", "failed", "cancelled"):
                done += 1
        print(f"  {done}/{len(task_ids)} เสร็จ... ({int(time.time()-start)}s)")
        if done >= len(task_ids):
            break
        time.sleep(interval)
    return {"done": done, "total": len(task_ids), "elapsed": time.time() - start}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true", help="รอจนทุก task เสร็จ")
    parser.add_argument("-n", "--num", type=int, default=25, help="จำนวน tasks (default: 25)")
    args = parser.parse_args()

    from app.api.transcribe import start_transcription, TranscriptionRequest

    chunk_dir = Path("uploads/0e692d52-364e-424a-8f1a-4903c30cdaeb_3fe4b1ff-26e2-4883-a278-7ecad8b1fd5b_chapter_video_b41379a4-6100-4b29-8d60-87e97ee3da8c")
    if not chunk_dir.exists():
        print("ไม่พบโฟลเดอร์ chunks - รัน split_wav_to_chunks.py ก่อน")
        return 1

    chunks = sorted(chunk_dir.glob("chunk_*.wav"))
    file_paths = [str(p).replace("\\", "/") for p in chunks]
    if not file_paths:
        print("ไม่พบ chunks")
        return 1

    NUM_TASKS = args.num
    print("=" * 70)
    print(f"ทดสอบ {NUM_TASKS} Chunk Group tasks")
    print("=" * 70)
    print(f"Chunks: {len(file_paths)} ไฟล์ (240s แต่ละไฟล์)")
    print()

    task_ids = []
    t_start = time.time()

    for i in range(NUM_TASKS):
        req = TranscriptionRequest(file_paths=file_paths, chunk_group=True, language="th")
        try:
            result = asyncio.run(start_transcription(req))
            task_ids.append(result["task_id"])
            print(f"  {i+1:2d}/{NUM_TASKS}: {result['task_id'][:8]}...")
        except Exception as e:
            print(f"  {i+1:2d}/{NUM_TASKS}: ERROR {e}")
            if "429" in str(e) or "Queue" in str(e):
                print("  Queue เต็ม - หยุดส่ง")
                break

    t_enqueue = time.time() - t_start
    print()
    print(f"ส่ง {len(task_ids)} tasks ใน {t_enqueue:.1f}s")
    print()

    if args.wait and task_ids:
        print("รอจนทุก task เสร็จ (poll ทุก 10s)...")
        r = poll_until_all_done(task_ids)
        print()
        print("=" * 70)
        print("สรุป")
        print("=" * 70)
        print(f"เสร็จ: {r['done']}/{r['total']} tasks")
        print(f"เวลารวม (ส่ง + รอเสร็จ): {r['elapsed']:.1f}s ({r['elapsed']/60:.1f} นาที)")
    else:
        print("Task IDs:")
        for tid in task_ids[:5]:
            print(f"  {tid}")
        if len(task_ids) > 5:
            print(f"  ... และอีก {len(task_ids)-5} tasks")
        print()
        print("ดูสถานะ: GET /api/v2/tasks/{task_id}")
        print("รอจนเสร็จ: python scripts/test_25_chunk_group.py --wait")
    return 0


if __name__ == "__main__":
    sys.exit(main())
