#!/usr/bin/env python3
"""
Recover tasks หลัง restart workers — re-enqueue chunks ที่หาย (job fail เมื่อ worker ถูก kill)

Usage:
  python scripts/recover_after_restart.py           # dry-run
  python scripts/recover_after_restart.py --apply
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from dotenv import load_dotenv
load_dotenv(project_root / ".env.runpod")


def main():
    apply = "--apply" in sys.argv
    print(f"🔧 Recover tasks หลัง restart (mode: {'APPLY' if apply else 'DRY-RUN'})\n")

    from app.utils.sqlite_storage import SQLiteStorage
    from redis import Redis

    storage = SQLiteStorage()
    conn = Redis.from_url(os.getenv("REDIS_URL"), decode_responses=False)
    ttl = int(os.getenv("REDIS_CHUNK_TTL_SECONDS", "43200"))

    # หา processing tasks ที่มี chunks_metadata
    all_list = storage.list_all_transcriptions()
    to_fix = []
    for t in all_list:
        if t.get("status") not in ("processing", "on_hold"):
            continue
        task_id = t.get("task_id")
        if not task_id:
            continue
        meta_key = f"task:{task_id}:chunks_metadata"
        if not conn.exists(meta_key):
            continue
        total_key = f"task:{task_id}:total_chunks"
        done_key = f"task:{task_id}:done_chunks"
        total = conn.get(total_key)
        done = conn.get(done_key)
        total = int(total) if total else 0
        done = int(done) if done else 0
        if total == 0 or done >= total:
            continue
        # มี chunks ที่ยังไม่เสร็จ
        to_fix.append((task_id, total, done, t.get("progress", 0)))

    print(f"พบ {len(to_fix)} tasks ที่มี chunks ค้าง\n")
    if not to_fix:
        print("✅ ไม่มี tasks ที่ต้อง recover")
        return 0

    for task_id, total, done, progress in to_fix[:20]:
        print(f"  {task_id[:36]}... progress={progress}% done={done}/{total}")

    if not apply:
        print("\n💡 รันด้วย --apply เพื่อ re-enqueue chunks")
        return 0

    from app.services.redis_queue_service import get_redis_queue_service
    queue_service = get_redis_queue_service()
    from app.services.stuck_task_monitor import StuckTaskMonitor
    monitor = StuckTaskMonitor()
    monitor.stuck_threshold_seconds = 10  # ใช้ threshold สั้นเพื่อให้ fix ได้

    fixed = 0
    for task_id, total, done, _ in to_fix:
        if monitor.fix_stuck_task(task_id, "recover_after_restart"):
            fixed += 1
            print(f"✅ Fixed {task_id[:36]}...")

    print(f"\n✅ Re-enqueued chunks สำหรับ {fixed} tasks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
