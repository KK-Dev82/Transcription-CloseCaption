#!/usr/bin/env python3
"""
แก้ tasks ที่ค้าง 90% — re-enqueue aggregator job

กรณี: chunks เสร็จหมด (done_chunks >= total_chunks) แต่ aggregator job fail (worker kill/restart)
→ Task ค้างที่ 90% (stage=merging) ไม่ไปต่อ

Usage:
  python scripts/fix_stuck_90_percent.py           # dry-run
  python scripts/fix_stuck_90_percent.py --apply
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
    print(f"🔧 Fix tasks ค้าง 90% (re-enqueue aggregator)\n")
    print(f"   Mode: {'APPLY' if apply else 'DRY-RUN'}\n")

    from app.utils.sqlite_storage import SQLiteStorage
    from redis import Redis

    storage = SQLiteStorage()
    conn = Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
    ttl = int(os.getenv("REDIS_CHUNK_TTL_SECONDS", "43200"))

    # หา tasks ที่: status=processing, progress ~90%, done_chunks >= total_chunks
    all_list = storage.list_all_transcriptions()
    to_fix = []
    for t in all_list:
        if t.get("status") not in ("processing", "on_hold"):
            continue
        progress = t.get("progress", 0)
        if progress < 80:  # 80% ขึ้นไปถือว่าอยู่ช่วง aggregator
            continue
        task_id = t.get("task_id")
        if not task_id:
            continue
        total_key = f"task:{task_id}:total_chunks"
        done_key = f"task:{task_id}:done_chunks"
        total = conn.get(total_key)
        done = conn.get(done_key)
        total = int(total) if total else 0
        done = int(done) if done else 0
        if total == 0:
            continue
        if done < total:
            continue  # chunks ยังไม่ครบ — ใช้ recover_after_restart แทน
        # done >= total — chunks เสร็จหมด, aggregator ควร run (หรือเคย run แล้ว fail)
        to_fix.append((task_id, total, done, progress, t))

    print(f"พบ {len(to_fix)} tasks ที่ค้าง 90% (chunks ครบ, aggregator ควร re-enqueue)\n")
    if not to_fix:
        print("✅ ไม่มี tasks ที่ต้องแก้")
        return 0

    for task_id, total, done, progress, t in to_fix[:20]:
        print(f"  {task_id[:36]}... progress={progress}% done={done}/{total}")

    if not apply:
        print("\n💡 รันด้วย --apply เพื่อ re-enqueue aggregator")
        return 0

    from app.services.redis_queue_service import get_redis_queue_service
    queue_service = get_redis_queue_service()

    # ดึง language, model_size, chunk_duration จาก chunks_metadata
    fixed = 0
    for task_id, total, done, progress, t in to_fix:
        meta_key = f"task:{task_id}:chunks_metadata"
        meta_str = conn.get(meta_key)
        if not meta_str:
            print(f"  ⚠️ Skip {task_id[:36]}... (no chunks_metadata)")
            continue
        import json
        meta = json.loads(meta_str)
        language = meta.get("language", "th")
        model_size = meta.get("model_size") or "base"
        chunk_duration = int(meta.get("chunk_duration", 150))

        aggregator_task_id = f"{task_id}_aggregator"
        try:
            queue_service.enqueue_aggregator(
                task_id=aggregator_task_id,
                language=language,
                model_size=model_size,
                chunk_duration=chunk_duration,
            )
            fixed += 1
            print(f"  ✅ Re-enqueued aggregator: {task_id[:36]}...")
        except Exception as e:
            print(f"  ❌ Failed {task_id[:36]}...: {e}")

    print(f"\n✅ Re-enqueued aggregator สำหรับ {fixed} tasks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
