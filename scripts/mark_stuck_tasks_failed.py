#!/usr/bin/env python3
"""
อัปเดต tasks ที่ค้าง (stuck) เป็น cancelled
ใช้เมื่อ tasks ถูก interrupt ก่อนจบ (เช่น workers restart)
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env.runpod")


def main():
    task_ids = sys.argv[1:] if len(sys.argv) > 1 else []
    if not task_ids:
        print("Usage: python scripts/mark_stuck_tasks_failed.py <task_id> [task_id2 ...]")
        print("Example: python scripts/mark_stuck_tasks_failed.py f29f1441-abc8-4b48-b6fe-3d77d8a3fe40 8dcaacdc-b922-4b66-9b11-60c4de7ec279")
        return 1

    from app.utils.sqlite_storage import SQLiteStorage
    storage = SQLiteStorage()

    for tid in task_ids:
        t = storage.load_transcription(tid)
        if not t:
            print(f"  {tid}: ไม่พบ")
            continue
        old_status = t.get("status")
        t["status"] = "cancelled"
        t["current_stage"] = "cancelled"
        t["current_stage_description"] = "Task ถูก interrupt ก่อนจบ (workers restart)"
        if "error_message" in t:
            del t["error_message"]
        t["updated_at"] = datetime.now(timezone.utc).isoformat()
        storage.save_transcription(tid, t)
        print(f"  {tid}: {old_status} → cancelled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
