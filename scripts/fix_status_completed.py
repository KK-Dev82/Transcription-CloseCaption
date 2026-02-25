#!/usr/bin/env python3
"""
แก้ tasks ที่มี completed_at แต่ status ยังเป็น processing (race condition)
- มี completed_at = aggregator เสร็จแล้ว
- status ไม่ใช่ completed = ถูก chunk completion overwrite

Usage:
  python scripts/fix_status_completed.py           # แก้ทั้งหมด (dry-run)
  python scripts/fix_status_completed.py --apply   # แก้จริง
"""

import os
import sys
import argparse
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env.runpod")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply fixes (default: dry-run)")
    parser.add_argument("--limit", type=int, default=0, help="Max tasks to fix (0=all)")
    args = parser.parse_args()

    storage_type = os.getenv("STORAGE_TYPE", "sqlite").lower()
    if storage_type != "sqlite":
        print("❌ ใช้ได้เฉพาะ STORAGE_TYPE=sqlite")
        sys.exit(1)

    print(f"🔍 ตรวจสอบ tasks ที่ completed_at มีแต่ status != completed")
    print(f"   Mode: {'APPLY' if args.apply else 'DRY-RUN'}\n")

    import sqlite3
    db_path = os.getenv("SQLITE_DB_PATH", str(project_root / "storage/database.db"))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cur = conn.execute("""
        SELECT task_id, status, progress, current_stage, completed_at, updated_at
        FROM transcriptions
        WHERE completed_at IS NOT NULL AND status != 'completed'
        ORDER BY updated_at DESC
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("✅ ไม่พบ tasks ที่ต้องแก้")
        return

    if args.limit:
        rows = rows[: args.limit]

    print(f"พบ {len(rows)} tasks ที่ต้องแก้:\n")
    for idx, row in enumerate(rows, 1):
        print(f"  {idx}. {row['task_id']}")
        print(f"     status={row['status']}, progress={row['progress']}%, completed_at={row['completed_at']}")

    if args.apply:
        print("\n⚠️  กำลังแก้ไข...")
        conn = sqlite3.connect(db_path)
        cur = conn.execute("""
            UPDATE transcriptions
            SET status = 'completed', current_stage = 'completed',
                current_stage_description = 'เสร็จสิ้น', progress = 100, stage_progress = 100
            WHERE completed_at IS NOT NULL AND status != 'completed'
        """)
        updated = cur.rowcount
        conn.commit()
        conn.close()
        print(f"✅ แก้ไข {updated} tasks แล้ว")
    else:
        print(f"\n💡 รันด้วย --apply เพื่อแก้ไขจริง")


if __name__ == "__main__":
    main()
