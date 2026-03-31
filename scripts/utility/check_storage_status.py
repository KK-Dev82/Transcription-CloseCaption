#!/usr/bin/env python3
"""
Check Storage Status: เปรียบเทียบข้อมูลระหว่าง SQLite กับ Postgres

ใช้ตรวจสอบว่า:
- SQLite มีข้อมูลอะไรบ้าง
- Postgres มีข้อมูลอะไรบ้าง
- มีข้อมูลไหนที่ยังไม่ sync

Usage (รันบน transcription server):
  python3 scripts/utility/check_storage_status.py
  python3 scripts/utility/check_storage_status.py --task-id abc123
"""

import sqlite3
import json
import argparse
import os


def check_sqlite(sqlite_path: str, task_id: str = None):
    if not os.path.exists(sqlite_path):
        print(f"SQLite not found: {sqlite_path}")
        return

    conn = sqlite3.connect(sqlite_path, timeout=30)
    conn.row_factory = sqlite3.Row

    print("=" * 60)
    print(f"SQLite: {sqlite_path}")
    print("=" * 60)

    # Total counts
    cur = conn.execute("SELECT COUNT(*) as total FROM transcriptions")
    total = cur.fetchone()["total"]

    cur = conn.execute("SELECT status, COUNT(*) as cnt FROM transcriptions GROUP BY status ORDER BY cnt DESC")
    statuses = cur.fetchall()

    print(f"\nTotal tasks: {total}")
    for s in statuses:
        print(f"  {s['status']:<15} {s['cnt']:>5}")

    # Segments
    cur = conn.execute("SELECT COUNT(*) as total FROM segments")
    seg_total = cur.fetchone()["total"]
    print(f"\nTotal segments rows: {seg_total}")

    # Tasks with segments
    cur = conn.execute("""
        SELECT COUNT(DISTINCT t.task_id) as with_segs
        FROM transcriptions t
        JOIN segments s ON s.task_id = t.task_id
        WHERE t.status = 'completed'
    """)
    with_segs = cur.fetchone()["with_segs"]
    print(f"Completed tasks with segments: {with_segs}")

    # Specific task
    if task_id:
        print(f"\n--- Task: {task_id} ---")
        cur = conn.execute("SELECT * FROM transcriptions WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        if row:
            print(f"  Status: {row['status']}")
            print(f"  Progress: {row['progress']}")
            print(f"  FullText length: {len(row['full_text'] or '')}")
            print(f"  Created: {row['created_at']}")

            cur2 = conn.execute("SELECT COUNT(*) as cnt FROM segments WHERE task_id = ?", (task_id,))
            print(f"  Segments: {cur2.fetchone()['cnt']}")
        else:
            print("  Not found in SQLite")

    conn.close()


def check_postgres(task_id: str = None):
    """ตรวจ Postgres ผ่าน Transcription Service API (ถ้ารันอยู่)"""
    try:
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError

        base_url = "http://localhost:8010"

        # Check health
        try:
            resp = urlopen(Request(f"{base_url}/health"), timeout=5)
            print("\n" + "=" * 60)
            print(f"Transcription Service: {base_url} (running)")
            print("=" * 60)
        except Exception:
            print(f"\nTranscription Service not reachable at {base_url}")
            return

        # Get storage info
        try:
            resp = urlopen(Request(f"{base_url}/api/dashboard/storage-info"), timeout=5)
            info = json.loads(resp.read().decode())
            print(f"Storage type: {info.get('storage_type', 'unknown')}")
        except Exception:
            pass

        # Check specific task
        if task_id:
            try:
                resp = urlopen(Request(f"{base_url}/api/v2/tasks/{task_id}?format=full"), timeout=10)
                data = json.loads(resp.read().decode())
                print(f"\n--- Task: {task_id} (from current storage) ---")
                print(f"  Status: {data.get('status')}")
                print(f"  Progress: {data.get('progress')}")
                chunks = data.get("chunks") or data.get("segments") or []
                print(f"  Chunks: {len(chunks)}")
                full_text = data.get("full_text", "")
                print(f"  FullText length: {len(full_text)}")
            except HTTPError as e:
                print(f"  Task {task_id}: HTTP {e.code}")
            except Exception as e:
                print(f"  Error: {e}")

    except ImportError:
        print("\nCannot check Postgres (urllib not available)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check storage status")
    parser.add_argument("--sqlite-path", default="/home/athipc/deploy/storage/database.db")
    parser.add_argument("--task-id", default=None, help="Check specific task ID")
    args = parser.parse_args()

    check_sqlite(args.sqlite_path, args.task_id)
    check_postgres(args.task_id)
