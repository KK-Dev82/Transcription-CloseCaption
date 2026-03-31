#!/usr/bin/env python3
"""
Backfill Script: SQLite segments → Postgres TranscriptionResults.SegmentsJson

ไม่ต้องติดตั้ง package เพิ่ม — ใช้แค่ Python built-in (sqlite3)
เรียก Backend API แทนการเชื่อม Postgres ตรง

Usage (รันบน transcription server):
  python3 backfill_segments_to_postgres.py --dry-run
  python3 backfill_segments_to_postgres.py
"""

import sqlite3
import json
import argparse
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ─── Config ───
SQLITE_PATH = "/home/athipc/deploy/storage/database.db"
BACKEND_URL = "http://10.200.22.56:5114"  # senate-backend internal


def get_segments(conn, task_id):
    cur = conn.execute(
        "SELECT idx, start_time, end_time, text, confidence "
        "FROM segments WHERE task_id = ? ORDER BY idx",
        (task_id,)
    )
    segments = []
    for row in cur.fetchall():
        seg = {
            "start_time": float(row[1]) if row[1] is not None else 0.0,
            "end_time": float(row[2]) if row[2] is not None else 0.0,
            "text": str(row[3]) if row[3] else "",
        }
        if row[4] is not None:
            seg["confidence"] = float(row[4])
        segments.append(seg)
    return segments


def call_backend_webhook(task_id, full_text, segments, total_duration):
    """ส่งผ่าน webhook/pod endpoint ที่มีอยู่แล้ว — ให้ Backend เก็บ result"""
    payload = {
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "full_text": full_text,
        "chunks": segments,
        "chunks_count": len(segments),
        "total_duration": total_duration or 0,
    }

    # ใช้ empty GUID เพราะ Flow B ไม่มี FileId
    url = f"{BACKEND_URL}/api/transcription/webhook/pod?fileId=00000000-0000-0000-0000-000000000000"

    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        resp = urlopen(req, timeout=30)
        return resp.status, json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return e.code, body
    except URLError as e:
        return 0, str(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sqlite-path", default=SQLITE_PATH)
    parser.add_argument("--backend-url", default=BACKEND_URL)
    parser.add_argument("--limit", type=int, default=0, help="จำกัดจำนวน tasks (0=ทั้งหมด)")
    args = parser.parse_args()

    global BACKEND_URL
    BACKEND_URL = args.backend_url.rstrip("/")

    conn = sqlite3.connect(args.sqlite_path, timeout=30)
    conn.row_factory = sqlite3.Row

    # ดึง completed tasks ที่มี segments
    cur = conn.execute("""
        SELECT t.task_id, t.full_text, t.total_duration, t.created_at,
               COUNT(s.id) as seg_count
        FROM transcriptions t
        JOIN segments s ON s.task_id = t.task_id
        WHERE t.status = 'completed' AND length(t.full_text) > 0
        GROUP BY t.task_id
        HAVING seg_count > 0
        ORDER BY t.created_at DESC
    """)
    tasks = [dict(row) for row in cur.fetchall()]

    print(f"Found {len(tasks)} completed tasks with segments in SQLite")
    print(f"Backend: {BACKEND_URL}")
    print(f"Dry run: {args.dry_run}")
    print()

    if args.limit > 0:
        tasks = tasks[:args.limit]
        print(f"Limited to {args.limit} tasks")

    updated = 0
    skipped = 0
    errors = 0

    for i, task in enumerate(tasks):
        task_id = task["task_id"]
        segments = get_segments(conn, task_id)

        if not segments:
            skipped += 1
            continue

        if args.dry_run:
            print(f"[DRY RUN] {i+1}/{len(tasks)} task={task_id[:16]}... "
                  f"segments={len(segments)}, text={len(task['full_text'] or '')} chars")
            updated += 1
            continue

        status, resp = call_backend_webhook(
            task_id,
            task["full_text"] or "",
            segments,
            task["total_duration"],
        )

        if status in (200, 201):
            updated += 1
            print(f"OK  {i+1}/{len(tasks)} task={task_id[:16]}... "
                  f"segments={len(segments)} → {resp}")
        elif status == 404:
            skipped += 1
            print(f"SKIP {i+1}/{len(tasks)} task={task_id[:16]}... "
                  f"(no matching job in Postgres)")
        else:
            errors += 1
            print(f"ERR {i+1}/{len(tasks)} task={task_id[:16]}... "
                  f"status={status} → {resp}")

    conn.close()

    print()
    print("=" * 50)
    print(f"Total:   {len(tasks)}")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Errors:  {errors}")
    print("=" * 50)


if __name__ == "__main__":
    main()
