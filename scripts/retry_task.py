#!/usr/bin/env python3
"""
Retry transcription task เดียว: ล้าง Redis + ตั้ง status=queued + enqueue preprocess ใหม่

Usage:
  python scripts/retry_task.py <task_id>
  python scripts/retry_task.py 4de703cf-8e20-4adc-a243-cd686c9cb4a4
  python scripts/retry_task.py 4de703cf-8e20-4adc-a243-cd686c9cb4a4 --dry-run
"""
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    for env_file in [project_root / ".env.runpod", project_root / ".env"]:
        if env_file.exists():
            load_dotenv(env_file)
            break
except ImportError:
    pass


def get_storage():
    """โหลด storage ตาม STORAGE_TYPE (sqlite หรือ json)"""
    storage_type = os.getenv("STORAGE_TYPE", "sqlite").lower()
    if storage_type == "sqlite":
        from app.utils.sqlite_storage import SQLiteStorage
        return SQLiteStorage()
    from app.utils.json_storage import JSONStorage
    return JSONStorage()


def retry_one_task(
    task_id: str,
    task: dict,
    redis_client,
    queue_service,
    storage,
    dry_run: bool,
) -> bool:
    file_path = task.get("file_path")
    if not file_path:
        print(f"⚠️  Task ไม่มี file_path — ข้าม")
        return False

    language = task.get("language", "th")
    model_size = task.get("model_size") or os.getenv("WHISPER_MODEL", "Systran/faster-whisper-small")
    chunk_duration = int(task.get("chunk_duration", 150))

    if dry_run:
        print(f"[dry-run] จะ retry task {task_id}")
        print(f"  file_path={file_path}")
        print(f"  status={task.get('status')}, progress={task.get('progress')}%")
        return True

    prefix = f"task:{task_id}:"
    keys = list(redis_client.scan_iter(match=prefix + "*", count=500))
    if keys:
        redis_client.delete(*keys)
        print(f"✅ ลบ Redis keys ของ task นี้: {len(keys)} keys")
    else:
        print("   ไม่มี Redis keys ของ task นี้")

    task["status"] = "queued"
    task["progress"] = 0
    task["current_stage"] = None
    task["current_stage_description"] = None
    task["updated_at"] = datetime.now(timezone.utc).isoformat()
    if "error_message" in task:
        del task["error_message"]
    storage.save_transcription(task_id, task)
    print("✅ อัปเดต storage: status=queued, progress=0")

    job_id = queue_service.enqueue_preprocess(
        task_id=task_id,
        file_path=file_path,
        language=language,
        model_size=model_size,
        chunk_duration=chunk_duration,
    )
    print(f"✅ ส่ง preprocess เข้าคิว: job_id={job_id}")
    return True


def main():
    ap = argparse.ArgumentParser(
        description="Retry transcription task เดียว (ล้าง Redis + enqueue preprocess ใหม่)"
    )
    ap.add_argument("task_id", help="Task ID ที่ต้องการ retry (เช่น 4de703cf-8e20-4adc-a243-cd686c9cb4a4)")
    ap.add_argument("--dry-run", action="store_true", help="แสดงว่าจะทำอะไร ไม่ลงมือทำ")
    args = ap.parse_args()

    task_id = args.task_id.strip()

    storage = get_storage()
    task = storage.load_transcription(task_id)
    if not task:
        print(f"❌ ไม่พบ task: {task_id}")
        return 1

    print(f"🔍 Task: {task_id}")
    print(f"   file_path: {task.get('file_path', 'N/A')}")
    print(f"   status: {task.get('status')}, progress: {task.get('progress')}%")
    print("")

    if args.dry_run:
        retry_one_task(task_id, task, None, None, storage, dry_run=True)
        print("รันใหม่โดยไม่ใส่ --dry-run เพื่อ retry จริง")
        return 0

    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("❌ REDIS_URL ไม่ได้ตั้งค่า")
        return 1

    from redis import Redis
    from app.services.redis_queue_service import get_redis_queue_service

    try:
        r = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=10)
    except Exception as e:
        print(f"❌ เชื่อมต่อ Redis ไม่ได้: {e}")
        return 1

    q = get_redis_queue_service()
    ok = retry_one_task(task_id, task, r, q, storage, dry_run=False)
    if not ok:
        return 1

    print("")
    print("Done. Task จะถูก preprocess แล้วส่ง chunk ไป GPU ใหม่")
    return 0


if __name__ == "__main__":
    sys.exit(main())
