#!/usr/bin/env python3
"""
ตรวจสอบ tasks ที่ status=processing แต่ไม่มี job รัน — ทำไมไม่มีการแปลงเสียง

วิธีใช้:
  python3 scripts/diagnose_stuck_processing.py
  # หรือ (จาก project root):
  ./scripts/diagnose_stuck.sh
"""
import os
import sys
import json
from pathlib import Path

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
    from redis import Redis
    
    all_list = storage.list_all_transcriptions()
    processing = [t for t in all_list if t.get("status") == "processing"]
    
    print(f"📋 Tasks ที่ status=processing: {len(processing)}")
    print()
    
    redis_url = os.getenv("REDIS_URL")
    conn = Redis.from_url(redis_url, decode_responses=True)
    queue_svc = get_redis_queue_service()
    
    for t in processing[:10]:  # ตรวจแค่ 10 ตัวแรก
        tid = t.get("task_id")
        if not tid:
            continue
        print(f"--- Task {tid[:8]}... ---")
        print(f"   stage: {t.get('current_stage')}")
        print(f"   progress: {t.get('progress')}%")
        
        # Redis keys
        on_hold = conn.get(f"task:{tid}:on_hold")
        in_on_hold_set = conn.sismember("tasks:on_hold", tid)
        paused = conn.get(f"task:{tid}:paused")
        total_chunks = conn.get(f"task:{tid}:total_chunks")
        done_chunks = conn.get(f"task:{tid}:done_chunks")
        inflight = conn.get(f"task:{tid}:inflight_chunks")
        chunks_meta = conn.get(f"task:{tid}:chunks_metadata")
        
        print(f"   Redis: on_hold={on_hold}, in_tasks_on_hold={in_on_hold_set}, paused={paused}")
        print(f"   Redis: total_chunks={total_chunks}, done={done_chunks}, inflight={inflight}")
        
        if chunks_meta:
            meta = json.loads(chunks_meta)
            next_idx = meta.get("next_chunk_index", 0)
            total = meta.get("total_chunks", 0)
            print(f"   chunks_metadata: next_chunk_index={next_idx}/{total}")
        
        # ตรวจสอบว่ามี chunk jobs ใน queue หรือไม่
        from rq.job import Job
        
        job_ids_to_check = [f"{tid}_preprocess", f"{tid}_aggregator", tid]
        if total_chunks:
            n = int(total_chunks)
            for i in range(min(n, 5)):
                job_ids_to_check.append(f"{tid}_chunk_{i}")
        
        for jid in job_ids_to_check[:8]:
            try:
                job = Job.fetch(jid, connection=queue_svc.redis_conn)
                st = job.get_status()
                print(f"   Job {jid}: status={st}")
            except Exception as e:
                if "No such job" not in str(e):
                    print(f"   Job {jid}: {e}")
        
        print()
    
    # สรุป queue
    from rq.registry import StartedJobRegistry
    print("📦 Queue summary:")
    print(f"   preprocess: queued={len(queue_svc.preprocess_queue)}, started={len(StartedJobRegistry(queue=queue_svc.preprocess_queue))}")
    for k, q in queue_svc.queues_upload.items():
        print(f"   {k}: queued={len(q)}, started={len(StartedJobRegistry(queue=q))}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
