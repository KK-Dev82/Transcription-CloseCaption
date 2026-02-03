#!/usr/bin/env python3
"""
วิเคราะห์ Performance จาก Storage (phase_timings) และจาก Logs
- ดึง task ที่ completed แล้วที่มี phase_timings (preprocess + aggregator)
- แสดง Total End-to-End, แบ่งตาม phase (Extract, Chunk, Wait chunks, Fetch, Merge, Thai)
- รองรับงานที่ใช้เวลานาน (เช่น 300+ นาที)
Usage:
  python scripts/analyze_performance.py              # วิเคราะห์ 50 task ล่าสุดที่ completed
  python scripts/analyze_performance.py --limit 20 # จำกัด 20 task
  python scripts/analyze_performance.py --min-minutes 200  # เฉพาะงานที่ใช้เวลา >= 200 นาที
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    for f in [project_root / ".env.runpod", project_root / ".env"]:
        if f.exists():
            load_dotenv(f)
            break
except ImportError:
    pass


def _parse_iso(s: Optional[str]):
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        if "+" not in s and s[-1] != "Z":
            s = s + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def get_duration_seconds(task: Dict) -> Optional[float]:
    """คำนวณระยะเวลารวมจาก phase_timings หรือ created_at -> completed_at"""
    pt = task.get("phase_timings") or {}
    agg = pt.get("aggregator") or {}
    if "total_end_to_end_time" in agg:
        return float(agg["total_end_to_end_time"])
    created = _parse_iso(task.get("created_at"))
    completed = _parse_iso(task.get("completed_at"))
    if created and completed:
        return (completed - created).total_seconds()
    return None


def format_seconds(s: float) -> str:
    if s >= 3600:
        return f"{s/3600:.2f}h ({s/60:.1f} min)"
    return f"{s/60:.2f} min"


def analyze_from_storage(limit: int = 50, min_minutes: Optional[float] = None) -> List[Dict]:
    """โหลด task ที่ completed จาก storage แล้วดึง performance จาก phase_timings"""
    storage_type = os.getenv("STORAGE_TYPE", "sqlite").lower()
    if storage_type == "sqlite":
        from app.utils.sqlite_storage import SQLiteStorage
        storage = SQLiteStorage()
    else:
        from app.utils.json_storage import JSONStorage
        storage = JSONStorage()

    all_list = storage.list_all_transcriptions()
    completed = [t for t in all_list if t.get("status") == "completed"]
    # โหลด full task เพื่อได้ phase_timings (list_all อาจไม่มี phase_timings_json)
    results = []
    for t in completed[: limit * 2]:  # โหลดเกินก่อน แล้ว filter ตาม duration
        task_id = t.get("task_id")
        if not task_id:
            continue
        full = storage.load_transcription(task_id)
        if not full or full.get("status") != "completed":
            continue
        dur = get_duration_seconds(full)
        if dur is not None and min_minutes is not None and (dur / 60) < min_minutes:
            continue
        results.append(full)
        if len(results) >= limit:
            break

    # เรียงตาม duration ลดลง (งานที่ใช้เวลานานสุดอยู่ก่อน)
    results.sort(key=lambda x: get_duration_seconds(x) or 0, reverse=True)
    return results[:limit]


def print_performance_report(tasks: List[Dict]):
    """พิมพ์สรุป performance แต่ละ task"""
    if not tasks:
        print("ไม่พบ task ที่มี phase_timings / completed")
        return

    print("=" * 70)
    print("Performance Report (จาก Storage – phase_timings)")
    print("=" * 70)

    for i, task in enumerate(tasks, 1):
        task_id = (task.get("task_id") or "")[:36]
        pt = task.get("phase_timings") or {}
        pre = pt.get("preprocess") or {}
        agg = pt.get("aggregator") or {}
        total_e2e = get_duration_seconds(task)
        if total_e2e is None:
            continue

        print(f"\n--- Task {i}: {task_id} ---")
        print(f"  Total End-to-End: {format_seconds(total_e2e)} ({total_e2e:.1f}s)")
        print(f"  File: {(task.get('file_path') or task.get('file_name') or 'N/A')[:60]}")

        if pre:
            extract = pre.get("extract_time") or 0
            chunk_t = pre.get("chunk_time") or 0
            enqueue = pre.get("enqueue_time") or 0
            total_pre = pre.get("total_preprocess_time") or (extract + chunk_t + enqueue)
            print(f"  Preprocess: total {total_pre:.1f}s  (extract: {extract:.1f}s, chunk: {chunk_t:.1f}s, enqueue: {enqueue:.1f}s)")
            if total_e2e and total_e2e > 0:
                print(f"    → Preprocess %: {(total_pre / total_e2e) * 100:.1f}%")

        if agg:
            wait = agg.get("wait_chunks_time") or 0
            fetch = agg.get("fetch_chunks_time") or 0
            merge = agg.get("merge_time") or 0
            thai = agg.get("thai_processing_time") or 0
            total_agg = agg.get("total_aggregator_time") or (wait + fetch + merge)
            print(f"  Aggregator: total {total_agg:.1f}s  (wait_chunks: {wait:.1f}s, fetch: {fetch:.1f}s, merge: {merge:.1f}s, thai: {thai:.1f}s)")
            if total_e2e and total_e2e > 0:
                print(f"    → Wait chunks %: {(wait / total_e2e) * 100:.1f}%  |  Fetch %: {(fetch / total_e2e) * 100:.1f}%  |  Merge %: {(merge / total_e2e) * 100:.1f}%")

        created = task.get("created_at") or ""
        completed = task.get("completed_at") or ""
        if created:
            print(f"  Created: {created[:19]}")
        if completed:
            print(f"  Completed: {completed[:19]}")

    # สรุปรวม
    durations = [get_duration_seconds(t) for t in tasks if get_duration_seconds(t) is not None]
    if durations:
        total_min = sum(durations) / 60
        avg_min = (sum(durations) / len(durations)) / 60
        print("\n" + "=" * 70)
        print("สรุป:")
        print(f"  จำนวน task: {len(durations)}")
        print(f"  เวลารวม: {total_min:.1f} นาที ({total_min/60:.2f} ชม.)")
        print(f"  เวลาเฉลี่ยต่อ task: {avg_min:.1f} นาที")
        if len(durations) >= 1:
            print(f"  งานที่ใช้เวลานานสุด: {max(durations)/60:.1f} นาที")
            print(f"  งานที่ใช้เวลาสั้นสุด: {min(durations)/60:.1f} นาที")


def parse_logs_for_performance(log_dir: Path, pattern_minutes: str = r"(\d+\.?\d*)\s*minutes?") -> List[Dict]:
    """ดึงบรรทัดที่เกี่ยวกับ Total End-to-End / minutes จาก logs"""
    found = []
    for log_file in sorted(log_dir.glob("transcription.log*"), reverse=True)[:3]:
        if not log_file.is_file():
            continue
        try:
            text = log_file.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if "Total End-to-End" in line or "Total end-to-end" in line:
                    # e.g. "   🎯 Total End-to-End: 18000.00s (300.00 minutes)"
                    m = re.search(r"([\d.]+)\s*s\s*\(([\d.]+)\s*minutes?\)", line)
                    if m:
                        found.append({"file": log_file.name, "line": line.strip(), "seconds": float(m.group(1)), "minutes": float(m.group(2))})
                if "minutes)" in line and ("Extract:" in line or "Wait chunks:" in line or "Merge:" in line):
                    found.append({"file": log_file.name, "line": line.strip()})
        except Exception as e:
            print(f"  (อ่าน {log_file.name} ไม่ได้: {e})")
    return found


def main():
    import argparse
    p = argparse.ArgumentParser(description="Analyze transcription performance from storage and logs")
    p.add_argument("--limit", type=int, default=50, help="จำนวน task สูงสุดที่วิเคราะห์ (default 50)")
    p.add_argument("--min-minutes", type=float, default=None, help="แสดงเฉพาะงานที่ใช้เวลา >= N นาที")
    p.add_argument("--logs", action="store_true", help="สแกน logs สำหรับ Total End-to-End / minutes ด้วย")
    args = p.parse_args()

    print("โหลด task ที่ completed จาก storage...")
    tasks = analyze_from_storage(limit=args.limit, min_minutes=args.min_minutes)
    print_performance_report(tasks)

    if args.logs:
        logs_dir = project_root / "logs"
        if logs_dir.exists():
            print("\n" + "=" * 70)
            print("จาก Logs (transcription.log*) – บรรทัด Total End-to-End / minutes")
            print("=" * 70)
            entries = parse_logs_for_performance(logs_dir)
            for e in entries[:30]:
                if "seconds" in e:
                    print(f"  [{e['file']}] {e['seconds']:.0f}s ({e['minutes']:.1f} min)")
                print(f"  {e.get('line', '')}")
        else:
            print("\n(ไม่มีโฟลเดอร์ logs หรือไม่เปิด --logs)")


if __name__ == "__main__":
    main()
