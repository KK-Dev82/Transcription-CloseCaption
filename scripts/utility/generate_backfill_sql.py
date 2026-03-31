#!/usr/bin/env python3
"""
Generate Backfill SQL: SQLite segments → Postgres TranscriptionResults

สร้างไฟล์ .sql ที่สามารถรันใน pgAdmin ได้โดยตรง
ไม่ต้องติดตั้ง package เพิ่ม — ใช้แค่ Python built-in (sqlite3, json)

Usage (รันบน transcription server 10.200.22.64):
  python3 scripts/utility/generate_backfill_sql.py
  python3 scripts/utility/generate_backfill_sql.py --meeting-id 6ebfc0c7-...
  python3 scripts/utility/generate_backfill_sql.py --output /tmp/backfill.sql

Output:
  ไฟล์ .sql ที่ copy ไปรันใน pgAdmin (Database: Senate, Server: 10.200.22.59)
"""

import sqlite3
import json
import argparse
import os
from datetime import datetime


def generate(sqlite_path: str, output_path: str, meeting_filter: str = None):
    conn = sqlite3.connect(sqlite_path, timeout=30)

    # ดึง completed tasks ที่มี segments
    tasks = conn.execute("""
        SELECT t.task_id, t.full_text, t.total_duration
        FROM transcriptions t
        JOIN segments s ON s.task_id = t.task_id
        WHERE t.status = 'completed' AND length(t.full_text) > 0
        GROUP BY t.task_id
        HAVING COUNT(s.id) > 0
        ORDER BY t.created_at DESC
    """).fetchall()

    print(f"Found {len(tasks)} completed tasks with segments in SQLite")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("-- ==========================================================\n")
        f.write("-- Backfill segments from SQLite to Postgres\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\n")
        f.write(f"-- Source: {sqlite_path}\n")
        f.write(f"-- Total tasks: {len(tasks)}\n")
        if meeting_filter:
            f.write(f"-- Meeting filter: {meeting_filter}\n")
        f.write("-- \n")
        f.write("-- Run in pgAdmin: Database=Senate, Server=10.200.22.59\n")
        f.write("-- Only updates rows where SegmentsJson is NULL or '[]'\n")
        f.write("-- ==========================================================\n\n")
        f.write("BEGIN;\n\n")

        count = 0
        skipped = 0

        for task in tasks:
            tid = task[0]
            full_text = task[1] or ""
            total_duration = task[2]

            # ดึง segments
            segs = conn.execute("""
                SELECT start_time, end_time, text, confidence
                FROM segments WHERE task_id = ? ORDER BY idx
            """, (tid,)).fetchall()

            if not segs:
                skipped += 1
                continue

            segments = []
            for s in segs:
                seg = {
                    "start_time": float(s[0] or 0),
                    "end_time": float(s[1] or 0),
                    "text": s[2] or "",
                }
                if s[3] is not None:
                    seg["confidence"] = float(s[3])
                segments.append(seg)

            seg_json = json.dumps(segments, ensure_ascii=False).replace("'", "''")
            word_count = len(full_text.split())
            safe_tid = tid.replace("'", "''")

            f.write(f"-- Task: {tid} ({len(segments)} segments, {word_count} words)\n")
            f.write(f'UPDATE transcription."TranscriptionResults"\n')
            f.write(f"SET \"SegmentsJson\" = '{seg_json}'::jsonb,\n")
            f.write(f'    "WordCount" = {word_count}\n')
            f.write(f'WHERE "TranscriptionJobId" = (\n')
            f.write(f"    SELECT \"Id\" FROM transcription.\"TranscriptionJobs\" WHERE \"TaskId\" = '{safe_tid}'\n")
            f.write(f')\n')
            f.write(f"AND (\"SegmentsJson\" IS NULL OR \"SegmentsJson\" = '[]');\n\n")
            count += 1

        f.write("COMMIT;\n")

    conn.close()

    file_size = os.path.getsize(output_path)
    print(f"Exported {count} UPDATE statements (skipped {skipped})")
    print(f"Output: {output_path} ({file_size // 1024}KB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate backfill SQL from SQLite")
    parser.add_argument("--sqlite-path", default="/home/athipc/deploy/storage/database.db",
                        help="Path to SQLite database")
    parser.add_argument("--output", "-o", default="/home/athipc/deploy/backfill_segments.sql",
                        help="Output SQL file path")
    parser.add_argument("--meeting-id", default=None,
                        help="Filter by meeting ID (not implemented in SQLite, for documentation)")
    args = parser.parse_args()

    generate(args.sqlite_path, args.output, args.meeting_id)
