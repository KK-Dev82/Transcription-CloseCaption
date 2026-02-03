#!/usr/bin/env python3
"""
Retry tasks ที่ค้าง (status=processing, updated_at เก่ากว่า N นาที):
ล้าง Redis + ตั้ง status=queued + enqueue preprocess ใหม่

Usage:
  python scripts/retry_stuck_tasks.py              # ค้าง > 30 นาที (default)
  python scripts/retry_stuck_tasks.py --min 60      # ค้าง > 60 นาที
  python scripts/retry_stuck_tasks.py --dry-run     # แค่แสดงรายการ ไม่ทำ
"""
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env.runpod")


def get_stuck_tasks(storage, min_stuck_minutes: float):
    """คืนรายการ (task_id, task_dict) ที่ status=processing และ updated_at เก่ากว่า min_stuck_minutes"""
    all_list = storage.list_all_transcriptions()
    now = datetime.now(timezone.utc)
    stuck = []
    for t in all_list:
        if t.get("status") != "processing":
            continue
        tid = t.get("task_id")
        up = t.get("updated_at") or t.get("created_at")
        if not up:
            stuck.append((tid, t))
            continue
        try:
            up = up.replace("Z", "+00:00")
            if "+" not in up:
                up = up + "+00:00"
            dt = datetime.fromisoformat(up)
            mins = (now - dt).total_seconds() / 60
            if mins >= min_stuck_minutes:
                stuck.append((tid, t))
        except Exception:
            stuck.append((tid, t))
    return stuck


def retry_one_task(task_id: str, task: dict, redis_client, queue_service, storage, dry_run: bool) -> bool:
    file_path = task.get("file_path")
    if not file_path:
        print(f"   ⚠️  {task_id}: no file_path, skip")
        return False
    language = task.get("language", "th")
    model_size = task.get("model_size") or os.getenv("WHISPER_MODEL", "Systran/faster-whisper-small")
    chunk_duration = int(task.get("chunk_duration", 150))

    if dry_run:
        print(f"   [dry-run] {task_id} progress={task.get('progress')}% -> would retry")
        return True

    prefix = f"task:{task_id}:"
    keys = list(redis_client.scan_iter(match=prefix + "*", count=500))
    if keys:
        redis_client.delete(*keys)
    task["status"] = "queued"
    task["progress"] = 0
    task["current_stage"] = None
    task["current_stage_description"] = None
    task["updated_at"] = datetime.now(timezone.utc).isoformat()
    if "error_message" in task:
        del task["error_message"]
    storage.save_transcription(task_id, task)
    queue_service.enqueue_preprocess(
        task_id=task_id,
        file_path=file_path,
        language=language,
        model_size=model_size,
        chunk_duration=chunk_duration,
    )
    return True


def main():
    ap = argparse.ArgumentParser(description="Retry stuck transcription tasks")
    ap.add_argument("--min", type=float, default=30, help="Consider stuck if no update for this many minutes (default 30)")
    ap.add_argument("--dry-run", action="store_true", help="Only list tasks, do not retry")
    args = ap.parse_args()

    from app.utils.sqlite_storage import SQLiteStorage
    from redis import Redis
    from app.services.redis_queue_service import get_redis_queue_service

    storage = SQLiteStorage()
    stuck = get_stuck_tasks(storage, args.min)
    if not stuck:
        print("ไม่มี task ค้าง (processing และไม่มีการอัปเดตเกิน %s นาที)" % args.min)
        return 0

    print("พบ task ค้าง %s รายการ (ไม่มีการอัปเดตเกิน %s นาที)" % (len(stuck), args.min))
    if args.dry_run:
        for tid, t in stuck:
            print("   ", tid, "progress=%s" % t.get("progress"))
        print("รันใหม่โดยไม่ใส่ --dry-run เพื่อ retry จริง")
        return 0

    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("❌ REDIS_URL not set")
        return 1
    r = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=10)
    q = get_redis_queue_service()

    ok = 0
    for tid, t in stuck:
        full = storage.load_transcription(tid)
        if not full:
            continue
        if retry_one_task(tid, full, r, q, storage, dry_run=False):
            ok += 1
            print("✅ Retry:", tid[:36])
    print("")
    print("Done. Retry แล้ว %s tasks — จะถูก preprocess แล้วส่งไป GPU ใหม่" % ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
