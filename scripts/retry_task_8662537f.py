#!/usr/bin/env python3
"""
Retry task 8662537f-efdb-48ef-9887-6c507b038b77: ล้าง process ค้าง + enqueue preprocess ใหม่
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env.runpod")

TASK_ID = "8662537f-efdb-48ef-9887-6c507b038b77"

def main():
    # 1. โหลด task จาก storage
    from app.utils.sqlite_storage import SQLiteStorage
    storage = SQLiteStorage()
    task = storage.load_transcription(TASK_ID)
    if not task:
        print(f"❌ Task {TASK_ID} not found")
        return 1
    file_path = task.get("file_path")
    language = task.get("language", "th")
    model_size = task.get("model_size", "Vinxscribe/biodatlab-whisper-th-medium-faster")
    chunk_duration = int(task.get("chunk_duration", 150))
    if not file_path:
        print("❌ Task has no file_path")
        return 1
    print(f"Task: {TASK_ID}, file_path={file_path}, status={task.get('status')}")

    # 2. ล้าง Redis keys ของ task นี้
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("❌ REDIS_URL not set")
        return 1
    from redis import Redis
    r = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=10)
    prefix = f"task:{TASK_ID}:"
    keys = list(r.scan_iter(match=prefix + "*", count=500))
    if keys:
        r.delete(*keys)
        print(f"✅ Deleted {len(keys)} Redis keys for {TASK_ID}")
    else:
        print("   No Redis keys to delete for this task")

    # 3. อัปเดต storage: status=queued, progress=0, ล้าง stage
    task["status"] = "queued"
    task["progress"] = 0
    task["current_stage"] = None
    task["current_stage_description"] = None
    task["updated_at"] = datetime.now(timezone.utc).isoformat()
    if "error_message" in task:
        del task["error_message"]
    storage.save_transcription(TASK_ID, task)
    print("✅ Storage updated: status=queued, progress=0")

    # 4. Enqueue preprocess ใหม่
    from app.services.redis_queue_service import get_redis_queue_service
    q = get_redis_queue_service()
    job_id = q.enqueue_preprocess(
        task_id=TASK_ID,
        file_path=file_path,
        language=language,
        model_size=model_size,
        chunk_duration=chunk_duration,
    )
    print(f"✅ Preprocess enqueued: job_id={job_id}")
    print("")
    print("Done. Task จะถูก preprocess แล้วส่ง chunk ไป GPU ใหม่.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
