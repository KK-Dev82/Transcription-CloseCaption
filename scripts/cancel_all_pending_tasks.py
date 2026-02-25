#!/usr/bin/env python3
"""
Cancel tasks ทั้งหมดที่ยังไม่เสร็จ (queued, processing, on_hold)
- ยกเลิก jobs ใน Redis (preprocess, chunks, aggregator)
- ลบ Redis keys
- อัปเดต status เป็น cancelled ใน storage

รองรับ STORAGE_TYPE=sqlite และ json (โหลด storage ตาม env)
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
for env_file in [Path(__file__).parent.parent / ".env.runpod", Path(__file__).parent.parent / ".env"]:
    if env_file.exists():
        load_dotenv(env_file)
        break


def get_storage():
    """โหลด storage ตาม STORAGE_TYPE (sqlite หรือ json)"""
    storage_type = os.getenv("STORAGE_TYPE", "sqlite").lower()
    if storage_type == "sqlite":
        from app.utils.sqlite_storage import SQLiteStorage
        return SQLiteStorage()
    from app.utils.json_storage import JSONStorage
    return JSONStorage()


def main():
    from app.services.redis_queue_service import get_redis_queue_service

    storage = get_storage()
    queue_service = get_redis_queue_service()
    storage_type = os.getenv("STORAGE_TYPE", "sqlite").lower()
    print(f"📦 Storage: {storage_type}")

    # หา tasks ที่ยังไม่เสร็จ
    all_list = storage.list_all_transcriptions()
    to_cancel = [
        t for t in all_list
        if t.get("status") in ("queued", "processing", "pending", "on_hold")
    ]

    if not to_cancel:
        print("ไม่มี tasks ที่ต้อง cancel")
        return 0

    print(f"Cancel {len(to_cancel)} tasks (Redis + Storage)...")
    total_jobs = 0
    total_keys = 0
    for t in to_cancel:
        tid = t.get("task_id")
        if not tid:
            continue
        old_status = t.get("status", "?")
        # Cancel jobs ใน Redis
        try:
            result = queue_service.cancel_task(tid)
            total_jobs += result.get("cancelled_jobs", 0)
            total_keys += result.get("redis_keys_deleted", 0)
        except Exception as e:
            print(f"  ⚠️ Redis cancel {tid[:8]}...: {e}")
        # อัปเดต storage (SQLite ใช้ skip_migration เพื่อป้องกัน recursion)
        from app.utils.sqlite_storage import SQLiteStorage
        if isinstance(storage, SQLiteStorage):
            full = storage.load_transcription(tid, skip_migration=True)
        else:
            full = storage.load_transcription(tid)
        if full:
            full["status"] = "cancelled"
            full["current_stage"] = "cancelled"
            full["current_stage_description"] = "ยกเลิกโดยผู้ใช้ (restart preparation)"
            if "error_message" in full:
                del full["error_message"]
            full["updated_at"] = datetime.now(timezone.utc).isoformat()
            storage.save_transcription(tid, full)
        print(f"  ✅ {tid[:8]}... {old_status} → cancelled")
    print(f"Done: {len(to_cancel)} tasks cancelled ({total_jobs} jobs, {total_keys} Redis keys)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
