#!/usr/bin/env python3
"""
อัปเดต tasks ทั้งหมดที่ยังไม่เสร็จ (queued, processing) เป็น cancelled
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env.runpod")


def main():
    from app.utils.sqlite_storage import SQLiteStorage
    import sqlite3

    storage = SQLiteStorage()
    db_path = os.getenv("SQLITE_DB_PATH", "storage/database.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT task_id, status FROM transcriptions WHERE status IN ('queued', 'processing')"
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("ไม่มี tasks ที่ต้อง cancel")
        return 0

    print(f"Cancel {len(rows)} tasks...")
    for tid, old_status in rows:
        t = storage.load_transcription(tid)
        if not t:
            continue
        t["status"] = "cancelled"
        t["current_stage"] = "cancelled"
        t["current_stage_description"] = "ยกเลิกโดยผู้ใช้ (restart preparation)"
        if "error_message" in t:
            del t["error_message"]
        t["updated_at"] = datetime.now(timezone.utc).isoformat()
        storage.save_transcription(tid, t)
        print(f"  {tid[:8]}... {old_status} → cancelled")
    print(f"Done: {len(rows)} tasks cancelled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
