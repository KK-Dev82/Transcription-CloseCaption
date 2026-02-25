#!/usr/bin/env python3
"""
ตรวจสอบ tasks ทั้งหมด: source (video_record vs upload), status
ใช้เพื่อ debug: ทำไมทุก task ถึง on_hold
"""
import os
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env.runpod")


def main():
    storage_type = os.getenv("STORAGE_TYPE", "sqlite").lower()
    if storage_type == "sqlite":
        from app.utils.sqlite_storage import SQLiteStorage
        storage = SQLiteStorage()
    else:
        from app.utils.json_storage import JSONStorage
        storage = JSONStorage()
    
    from app.services.redis_queue_service import get_redis_queue_service
    from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry
    
    all_list = storage.list_all_transcriptions()
    
    # สถิติ
    by_source = defaultdict(list)
    by_status = defaultdict(list)
    on_hold_tasks = []
    
    for t in all_list:
        tid = t.get("task_id")
        if not tid:
            continue
        source = t.get("source", "upload")
        status = t.get("status", "?")
        by_source[source].append({"task_id": tid[:8] + "...", "status": status})
        by_status[status].append({"task_id": tid[:8] + "...", "source": source})
        if status == "on_hold":
            on_hold_tasks.append({"task_id": tid, "source": source})
    
    # record_backlog
    queue_service = get_redis_queue_service()
    record_backlog = queue_service.get_record_backlog_count()
    
    print("=" * 60)
    print("📊 สรุป Tasks ทั้งหมด")
    print("=" * 60)
    print(f"รวม: {len(all_list)} tasks")
    print()
    print("📌 แยกตาม source:")
    for src, tasks in sorted(by_source.items()):
        print(f"   {src}: {len(tasks)} tasks")
        statuses = defaultdict(int)
        for x in tasks:
            statuses[x["status"]] += 1
        for st, cnt in sorted(statuses.items()):
            print(f"      - {st}: {cnt}")
    print()
    print("📌 แยกตาม status:")
    for st, tasks in sorted(by_status.items()):
        print(f"   {st}: {len(tasks)} tasks")
        sources = defaultdict(int)
        for x in tasks:
            sources[x["source"]] += 1
        for src, cnt in sorted(sources.items()):
            print(f"      - source={src}: {cnt}")
    print()
    print(f"📊 record_backlog: {record_backlog}")
    print(f"   (นับเฉพาะ queued+started ใน preprocess_video_record + queues_record)")
    print()
    
    # รายละเอียด record queues
    print("📦 Record queues:")
    pre_q = len(queue_service.preprocess_video_record_queue)
    pre_s = len(StartedJobRegistry(queue=queue_service.preprocess_video_record_queue))
    pre_f = len(FinishedJobRegistry(queue=queue_service.preprocess_video_record_queue))
    pre_fail = len(FailedJobRegistry(queue=queue_service.preprocess_video_record_queue))
    print(f"   preprocess_video_record: queued={pre_q}, started={pre_s}, finished={pre_f}, failed={pre_fail}")
    for gpu_key, q in queue_service.queues_record.items():
        q_len = len(q)
        started = len(StartedJobRegistry(queue=q))
        finished = len(FinishedJobRegistry(queue=q))
        failed = len(FailedJobRegistry(queue=q))
        print(f"   {gpu_key} (record): queued={q_len}, started={started}, finished={finished}, failed={failed}")
    print()
    
    # สรุป
    video_record_count = len(by_source.get("video_record", []))
    upload_count = len(by_source.get("upload", []))
    on_hold_count = len(on_hold_tasks)
    
    print("=" * 60)
    print("💡 สรุป")
    print("=" * 60)
    if video_record_count == 0:
        print("⚠️  ไม่มี task ที่เป็น source=video_record เลย!")
        print("   → ทุก request ส่งมาโดยไม่ระบุ source หรือ source=upload")
        print("   → Frontend/Client ต้องส่ง source: 'video_record' เมื่อเป็น Video Record")
    else:
        print(f"✅ มี {video_record_count} tasks เป็น video_record")
    
    if on_hold_count > 0 and record_backlog > 0:
        print(f"\n⏳ {on_hold_count} tasks on_hold เพราะ record_backlog={record_backlog} > 0")
        print("   (Upload tasks รอ Record เสร็จก่อน)")
    elif on_hold_count > 0 and record_backlog == 0:
        print(f"\n⚠️  {on_hold_count} tasks on_hold แต่ record_backlog=0!")
        print("   → อาจเป็น stale: _try_release_on_hold_tasks ยังไม่ถูกเรียก")
        print("   → ลอง Resume ผ่าน API: POST /api/v2/tasks/{{task_id}}/resume")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
