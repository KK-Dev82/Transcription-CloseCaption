#!/usr/bin/env python3
"""
วิเคราะห์ Bottleneck: ใช้เวลาไปกับอะไรมากเกินไป
- ดึง phase_timings จาก tasks ล่าสุด
- แสดง % ของแต่ละ phase
- แนะนำการ optimize เพื่อลดเวลา (เป้า: ลด 12s/ไฟล์ จาก 60s → 48s)

Usage:
  python scripts/analyze_bottleneck.py           # 10 tasks ล่าสุด
  python scripts/analyze_bottleneck.py --limit 20
"""

import os
import sys
from pathlib import Path
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
        return __import__("datetime").datetime.fromisoformat(s)
    except Exception:
        return None


def get_duration_seconds(task: Dict) -> Optional[float]:
    pt = task.get("phase_timings") or {}
    agg = pt.get("aggregator") or {}
    if "total_end_to_end_time" in agg:
        return float(agg["total_end_to_end_time"])
    created = _parse_iso(task.get("created_at"))
    completed = _parse_iso(task.get("completed_at"))
    if created and completed:
        return (completed - created).total_seconds()
    return None


def load_recent_tasks(limit: int = 10) -> List[Dict]:
    """โหลด task ที่ completed จาก storage"""
    storage_type = os.getenv("STORAGE_TYPE", "sqlite").lower()
    if storage_type == "sqlite":
        from app.utils.sqlite_storage import SQLiteStorage
        storage = SQLiteStorage()
    else:
        from app.utils.json_storage import JSONStorage
        storage = JSONStorage()

    all_list = storage.list_all_transcriptions()
    completed = [t for t in all_list if t.get("status") == "completed"]
    results = []
    for t in completed[: limit * 3]:
        task_id = t.get("task_id")
        if not task_id:
            continue
        full = storage.load_transcription(task_id)
        if not full or full.get("status") != "completed":
            continue
        dur = get_duration_seconds(full)
        if dur is None:
            continue
        results.append(full)
        if len(results) >= limit:
            break

    results.sort(key=lambda x: (x.get("updated_at") or ""), reverse=True)
    return results[:limit]


def main():
    import argparse
    p = argparse.ArgumentParser(description="วิเคราะห์ bottleneck จาก phase_timings")
    p.add_argument("--limit", type=int, default=10, help="จำนวน task (default 10)")
    args = p.parse_args()

    print("โหลด tasks ล่าสุดจาก storage...")
    tasks = load_recent_tasks(limit=args.limit)

    if not tasks:
        print("❌ ไม่พบ task ที่ completed หรือมี phase_timings")
        print("   รัน transcription 1-2 งานก่อน แล้วรันสคริปต์นี้อีกครั้ง")
        return

    # รวม phase timings
    totals = {
        "extract": 0.0, "chunk": 0.0, "enqueue": 0.0, "total_preprocess": 0.0,
        "wait_chunks": 0.0, "fetch_chunks": 0.0, "merge": 0.0,
        "thai_processing": 0.0, "fuzzy_match": 0.0,
        "total_aggregator": 0.0, "total_e2e": 0.0
    }
    count = 0

    for task in tasks:
        pt = task.get("phase_timings") or {}
        pre = pt.get("preprocess") or {}
        agg = pt.get("aggregator") or {}
        total_e2e = get_duration_seconds(task)
        if total_e2e is None or total_e2e <= 0:
            continue

        extract = pre.get("extract_time") or 0
        chunk_t = pre.get("chunk_time") or 0
        enqueue = pre.get("enqueue_time") or 0
        total_pre = pre.get("total_preprocess_time") or (extract + chunk_t + enqueue)

        wait = agg.get("wait_chunks_time") or 0
        fetch = agg.get("fetch_chunks_time") or 0
        merge = agg.get("merge_time") or 0
        thai = agg.get("thai_processing_time") or 0
        fuzzy = agg.get("fuzzy_match_time") or 0
        total_agg = agg.get("total_aggregator_time") or (wait + fetch + merge)

        totals["extract"] += extract
        totals["chunk"] += chunk_t
        totals["enqueue"] += enqueue
        totals["total_preprocess"] += total_pre
        totals["wait_chunks"] += wait
        totals["fetch_chunks"] += fetch
        totals["merge"] += merge
        totals["thai_processing"] += thai
        totals["fuzzy_match"] += fuzzy
        totals["total_aggregator"] += total_agg
        totals["total_e2e"] += total_e2e
        count += 1

    if count == 0:
        print("❌ ไม่มี task ที่มี phase_timings ครบ")
        return

    n = count
    avg_e2e = totals["total_e2e"] / n

    print()
    print("=" * 70)
    print("📊 Phase Breakdown (เฉลี่ยจาก {} tasks, ~{:.1f}s/task)".format(n, avg_e2e))
    print("=" * 70)
    print()
    print(f"{'Phase':<28} {'เวลาเฉลี่ย':>12} {'% ของ Total':>12}  หมายเหตุ")
    print("-" * 70)

    def row(name: str, sec_sum: float, note: str = ""):
        avg_sec = sec_sum / n
        pct = (avg_sec / avg_e2e * 100) if avg_e2e > 0 else 0
        print(f"  {name:<26} {avg_sec:>8.1f}s {pct:>10.1f}%  {note}")

    row("1. Extract/Convert", totals["extract"], "FFmpeg/WAV (CPU)")
    row("2. Chunk", totals["chunk"], "แบ่ง chunks (CPU)")
    row("3. Enqueue", totals["enqueue"], "ส่งลงคิว")
    row("4. GPU Transcribe (wait)", totals["wait_chunks"], "รอ GPU ทำ chunks — ตัวหลัก")
    row("5. Fetch chunks", totals["fetch_chunks"], "ดึงผลจาก Redis")
    row("6. Merge", totals["merge"], "รวมข้อความ")
    row("7. Thai processing", totals["thai_processing"], "PyThaiNLP + Attacut")
    row("8. Fuzzy match", totals["fuzzy_match"], "แก้ชื่อคน/คำศัพท์")

    print()
    print("=" * 70)
    print("💡 แนะนำการ Optimize (เป้า: ลด 12s/ไฟล์ จาก 60s → 48s)")
    print("=" * 70)
    print()

    pre_pct = (totals["total_preprocess"] / n) / avg_e2e * 100 if avg_e2e > 0 else 0
    wait_pct = (totals["wait_chunks"] / n) / avg_e2e * 100 if avg_e2e > 0 else 0
    agg_pct = ((totals["fetch_chunks"] + totals["merge"] + totals["thai_processing"] + totals["fuzzy_match"]) / n) / avg_e2e * 100 if avg_e2e > 0 else 0

    if wait_pct > 70:
        print("  🔴 GPU Transcribe (wait_chunks) ใช้เวลามากที่สุด ({:.0f}%)".format(wait_pct))
        print("     → เพิ่ม GPU_WORKERS_PER_GPU (ถ้า CPU พอ)")
        print("     → ลด chunk_duration → chunks เยอะขึ้น → GPU parallel มากขึ้น")
        print("     → ใช้โมเดลเล็กกว่า (small แทน large) ถ้ายอมรับความแม่นยำลด")
        print()

    if pre_pct > 15:
        print("  🟡 Preprocess ใช้เวลา {:.0f}%".format(pre_pct))
        print("     → ใช้ WAV 16kHz mono แทน M4A/MP3 (ลด extract)")
        print("     → เพิ่ม NUM_PREPROCESS_WORKERS (ถ้า CPU พอ)")
        print()

    if (totals["thai_processing"] / n) > 5:
        print("  🟡 Thai processing ใช้เวลา {:.1f}s/ไฟล์".format(totals["thai_processing"] / n))
        print("     → พิจารณาปิด enable_thai_processing ถ้าไม่จำเป็น")
        print()

    if (totals["fuzzy_match"] / n) > 2:
        print("  🟡 Fuzzy match ใช้เวลา {:.1f}s/ไฟล์".format(totals["fuzzy_match"] / n))
        print("     → ตั้ง FUZZY_MATCH_ENABLED_FOR_TRANSCRIPTION=false")
        print()

    if agg_pct > 15 and wait_pct < 70:
        print("  🟡 Aggregator (fetch+merge+thai) ใช้เวลา {:.0f}%".format(agg_pct))
        print("     → ลด chunk_duration = chunks เยอะขึ้น = fetch loop มากขึ้น (trade-off)")
        print("     → ปิด Thai/Fuzzy ถ้าไม่จำเป็น")
        print()

    print("  📌 สรุป: รันสคริปต์นี้หลังทดสอบเพื่อดู phase ที่ใช้เวลามาก")
    print("     python scripts/analyze_bottleneck.py --limit 10")
    print()


if __name__ == "__main__":
    main()
