#!/usr/bin/env python3
"""
ตรวจสอบ task: source (priority), status, และ record_backlog
ใช้เพื่อ debug: ทำไม task ถึง on_hold ทั้งที่มีแค่ task เดียว
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env.runpod")


def main():
    task_id = sys.argv[1] if len(sys.argv) > 1 else "f9f6fe82-907f-4f8c-81ef-8185252f6f5b"
    
    storage_type = os.getenv("STORAGE_TYPE", "sqlite").lower()
    if storage_type == "sqlite":
        from app.utils.sqlite_storage import SQLiteStorage
        storage = SQLiteStorage()
    else:
        from app.utils.json_storage import JSONStorage
        storage = JSONStorage()
    
    from app.services.redis_queue_service import get_redis_queue_service
    
    # 1. โหลด task
    if storage_type == "sqlite":
        task = storage.load_transcription(task_id, skip_migration=True)
    else:
        task = storage.load_transcription(task_id)
    if not task:
        print(f"❌ ไม่พบ task: {task_id}")
        return 1
    
    print(f"📋 Task: {task_id}")
    print(f"   status: {task.get('status')}")
    print(f"   source: {task.get('source', 'upload')}  ← Priority (video_record=Record, upload=Upload)")
    print(f"   current_stage: {task.get('current_stage')}")
    print(f"   current_stage_description: {task.get('current_stage_description')}")
    print()
    
    # 2. record_backlog
    queue_service = get_redis_queue_service()
    record_backlog = queue_service.get_record_backlog_count()
    print(f"📊 record_backlog: {record_backlog}")
    print(f"   (นับเฉพาะ: queued + started ใน preprocess_video_record + queues_record)")
    print(f"   ไม่นับ: completed, failed, cancelled")
    print()
    
    # 3. รายละเอียดของ record queues
    from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry
    print("📦 Record queues breakdown:")
    pre_count = len(queue_service.preprocess_video_record_queue)
    pre_started = len(StartedJobRegistry(queue=queue_service.preprocess_video_record_queue))
    print(f"   preprocess_video_record: queued={pre_count}, started={pre_started}")
    for gpu_key, q in queue_service.queues_record.items():
        q_len = len(q)
        started = len(StartedJobRegistry(queue=q))
        finished = len(FinishedJobRegistry(queue=q))
        failed = len(FailedJobRegistry(queue=q))
        print(f"   {gpu_key} (record): queued={q_len}, started={started}, finished={finished}, failed={failed}")
    print()
    
    # 4. Redis keys สำหรับ task นี้
    print("🔑 Redis keys:")
    conn = queue_service.redis_conn
    for key in conn.scan_iter(match=f"task:{task_id}:*", count=100):
        k = key.decode() if isinstance(key, bytes) else key
        val = conn.get(key)
        if val:
            v = val.decode() if isinstance(val, bytes) else str(val)
            v = v[:80] + "..." if len(v) > 80 else v
        else:
            v = "(empty)"
        print(f"   {k}: {v}")
    print()
    
    # 5. สรุป
    source = task.get("source", "upload")
    if source == "upload" and record_backlog > 0:
        print("💡 สรุป: Task นี้เป็น source=upload → ถูก hold รอ Record เสร็จ (record_backlog > 0)")
        print("   หากไม่มี Record จริง อาจมี jobs ค้างใน record queues (stale)")
    elif source == "video_record":
        print("💡 สรุป: Task นี้เป็น source=video_record (Record) — ไม่ควรถูก hold")
    else:
        print("💡 สรุป: record_backlog=0 ควร release on_hold ได้")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
