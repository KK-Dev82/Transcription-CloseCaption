#!/usr/bin/env python3
"""
Load Test: Capacity Assessment for 25 Concurrent 30-min Videos
==============================================================

วัตถุประสงค์: ประเมินว่า 2× RTX 4000 Ada สามารถรองรับ 25 งาน 30 นาที
ให้เสร็จภายใน 18-20 นาทีได้หรือไม่

วิธีใช้:
    python scripts/load_test_capacity.py [options]

Options:
    --url       BASE_URL ของ service (default: http://localhost:8000)
    --file      path ของ audio file (absolute หรือ relative จาก /workspace)
    --n         จำนวน concurrent tasks (default: 25)
    --phase     single = benchmark 1 task, batch = ทดสอบ N tasks (default: both)
    --poll      polling interval วินาที (default: 5)
    --timeout   timeout นาที (default: 30)
    --out       output JSON file (default: load_test_results_<timestamp>.json)

ตัวอย่าง:
    python scripts/load_test_capacity.py
    python scripts/load_test_capacity.py --n 10 --phase batch
    python scripts/load_test_capacity.py --url http://localhost:8000 --n 25
"""

import argparse
import json
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import statistics

# ── dependencies ─────────────────────────────────────────────────────────────
try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

# ── constants ─────────────────────────────────────────────────────────────────
AUDIO_FILE_DEFAULT = (
    "/workspace/transcription-service/uploads/"
    "a0f43cec-aed9-4dea-82d8-a7c11d59674e_260128_1020"
    " อนุฯ พัฒนาระบบ (บริหารราชการแผ่นดิน) 2.wav"
)
AUDIO_DURATION_SECONDS = 1856.0   # จาก ffprobe (31 นาที)
CHUNK_DURATION = 240               # seconds per chunk (จาก .env.runpod)
TARGET_MAX_MINUTES = 20            # เป้าหมาย: เสร็จภายใน 20 นาที

GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
CYAN    = "\033[96m"
BOLD    = "\033[1m"
RESET   = "\033[0m"

TERMINAL_STATES = {"completed", "failed", "cancelled", "error"}


# ═════════════════════════════════════════════════════════════════════════════
# Helper utilities
# ═════════════════════════════════════════════════════════════════════════════

def _c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed(start: float) -> str:
    s = time.time() - start
    m, s = divmod(int(s), 60)
    return f"{m:02d}:{s:02d}"


def _p(items: list, pct: float) -> float:
    if not items:
        return 0.0
    sorted_items = sorted(items)
    idx = max(0, int(len(sorted_items) * pct / 100) - 1)
    return sorted_items[idx]


def estimate_chunks(audio_seconds: float, chunk_duration: int) -> int:
    import math
    return math.ceil(audio_seconds / chunk_duration)


def get_audio_duration(file_path: str) -> Optional[float]:
    """ดึง duration จาก ffprobe หรือใช้ค่าที่ตั้งไว้"""
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", file_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            dur = float(data["format"]["duration"])
            return dur
    except Exception:
        pass
    return None


# ═════════════════════════════════════════════════════════════════════════════
# API helpers
# ═════════════════════════════════════════════════════════════════════════════

class APIClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def health(self) -> bool:
        try:
            r = self.session.get(f"{self.base}/health", timeout=5)
            return r.status_code < 500
        except Exception:
            return False

    def submit(self, file_path: str, retries: int = 5, backoff: float = 2.0) -> Optional[Dict]:
        """Submit ไฟล์ไป transcription (retry on 429)"""
        url = f"{self.base}/api/transcribe/"
        payload = {"file_path": file_path, "language": "th"}
        for attempt in range(retries):
            try:
                r = self.session.post(url, json=payload, timeout=self.timeout)
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 429:
                    wait = backoff * (2 ** attempt)
                    print(f"  {_c(YELLOW, f'429 queue full, retrying in {wait:.0f}s (attempt {attempt+1}/{retries})')}")
                    time.sleep(wait)
                    continue
                # other error
                print(f"  {_c(RED, f'Submit failed {r.status_code}: {r.text[:100]}')}")
                return None
            except Exception as e:
                print(f"  {_c(RED, f'Submit error: {e}')}")
                if attempt < retries - 1:
                    time.sleep(backoff)
        return None

    def get_task(self, task_id: str) -> Optional[Dict]:
        try:
            r = self.session.get(f"{self.base}/api/v2/tasks/{task_id}", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None

    def dashboard(self) -> Optional[Dict]:
        try:
            r = self.session.get(f"{self.base}/api/monitoring/dashboard-summary", timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Phase 1: Single-file RTF Benchmark
# ═════════════════════════════════════════════════════════════════════════════

def benchmark_single(client: APIClient, file_path: str, audio_duration: float) -> Dict:
    print(f"\n{_c(BOLD+CYAN, '═══ Phase 1: Single-file RTF Benchmark ═══')}")
    print(f"  File: {Path(file_path).name}")
    print(f"  Duration: {audio_duration/60:.1f} min ({audio_duration:.0f}s)")
    print(f"  Chunks: {estimate_chunks(audio_duration, CHUNK_DURATION)} × {CHUNK_DURATION}s")

    start_time = time.time()
    resp = client.submit(file_path)
    if not resp:
        return {"error": "Failed to submit task", "skipped": True}

    task_id = resp["task_id"]
    print(f"  Submitted → task_id: {task_id}")
    print(f"  Waiting for completion...\n")

    prev_status = ""
    prev_progress = -1
    while True:
        elapsed = time.time() - start_time
        task = client.get_task(task_id)
        if not task:
            time.sleep(5)
            continue

        status = task.get("status", "unknown")
        progress = task.get("progress", 0)
        stage = task.get("current_stage_description") or task.get("current_stage", "")

        if status != prev_status or progress != prev_progress:
            bar_fill = int(progress / 5)
            bar = "█" * bar_fill + "░" * (20 - bar_fill)
            print(f"  [{_elapsed(start_time)}] [{bar}] {progress:3d}%  {status}  {stage[:40]}")
            prev_status = status
            prev_progress = progress

        if status in TERMINAL_STATES:
            break
        time.sleep(5)

    wall_time = time.time() - start_time
    rtf = audio_duration / wall_time if wall_time > 0 else 0

    print()
    if status == "completed":
        print(f"  {_c(GREEN, '✓ COMPLETED')}")
    else:
        print(f"  {_c(RED, f'✗ {status.upper()}')}")

    print(f"  Wall time  : {wall_time/60:.2f} min ({wall_time:.1f}s)")
    print(f"  RTF        : {_c(BOLD, f'{rtf:.1f}×')} real-time")
    print(f"  Audio/min  : {audio_duration/60:.1f} min of audio in {wall_time/60:.1f} min")

    return {
        "task_id": task_id,
        "status": status,
        "wall_time_seconds": round(wall_time, 2),
        "rtf": round(rtf, 2),
        "audio_duration_seconds": audio_duration,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Phase 2: Concurrent Load Test
# ═════════════════════════════════════════════════════════════════════════════

def run_concurrent(
    client: APIClient,
    file_path: str,
    audio_duration: float,
    n: int,
    poll_interval: float,
    timeout_minutes: float,
) -> Dict:
    print(f"\n{_c(BOLD+CYAN, f'═══ Phase 2: {n} Concurrent Tasks ═══')}")
    chunks_per_video = estimate_chunks(audio_duration, CHUNK_DURATION)
    total_audio_min = n * audio_duration / 60
    print(f"  Files      : {n} × {audio_duration/60:.1f} min = {total_audio_min:.0f} min total audio")
    print(f"  Chunks     : {n} × {chunks_per_video} = {n*chunks_per_video} chunks")
    print(f"  Target     : all done within {TARGET_MAX_MINUTES} min")
    print()

    # ── submit all tasks (with stagger to avoid thundering herd) ────────────
    print(f"  Submitting {n} tasks...")
    submit_start = time.time()

    tasks: Dict[str, Dict] = {}   # task_id → {submit_time, status, done_time, ...}
    submit_lock = threading.Lock()
    errors: List[str] = []

    def do_submit(idx: int):
        t0 = time.time()
        resp = client.submit(file_path)
        if resp:
            tid = resp["task_id"]
            with submit_lock:
                tasks[tid] = {
                    "idx": idx,
                    "task_id": tid,
                    "submit_time": t0,
                    "status": "queued",
                    "progress": 0,
                    "done_time": None,
                    "wall_time": None,
                    "rtf": None,
                }
        else:
            with submit_lock:
                errors.append(f"Task {idx} submit failed")

    # Submit in batches of 5 to avoid slamming the rate limiter
    batch_size = 5
    for batch_start in range(0, n, batch_size):
        batch = range(batch_start, min(batch_start + batch_size, n))
        threads = [threading.Thread(target=do_submit, args=(i,), daemon=True) for i in batch]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if batch_start + batch_size < n:
            time.sleep(0.5)   # small pause between batches

    submit_elapsed = time.time() - submit_start
    submitted = len(tasks)
    print(f"  Submitted  : {submitted}/{n} tasks in {submit_elapsed:.1f}s")
    if errors:
        for e in errors[:5]:
            print(f"  {_c(RED, f'  ✗ {e}')}")

    if submitted == 0:
        return {"error": "No tasks submitted", "n": n}

    wall_start = time.time()   # t=0 after all submitted
    timeout_sec = timeout_minutes * 60
    dashboard_snapshots: List[Dict] = []

    # ── polling loop ─────────────────────────────────────────────────────────
    print(f"\n  Polling every {poll_interval}s (timeout: {timeout_minutes} min)...\n")
    header = f"  {'Elapsed':>7}  {'Done':>4}/{submitted:<4}  {'Queued':>6}  {'Running':>7}  {'Failed':>6}  {'GPU workers':>11}"
    print(header)
    print("  " + "─" * (len(header) - 2))

    first_complete_time: Optional[float] = None
    all_complete_time: Optional[float] = None
    last_print_done = -1

    while True:
        elapsed = time.time() - wall_start

        # poll each pending task
        for tid, info in list(tasks.items()):
            if info["status"] in TERMINAL_STATES:
                continue
            task = client.get_task(tid)
            if not task:
                continue
            status = task.get("status", "unknown")
            progress = task.get("progress", 0)
            info["status"] = status
            info["progress"] = progress

            if status in TERMINAL_STATES and info["done_time"] is None:
                info["done_time"] = time.time()
                info["wall_time"] = info["done_time"] - info["submit_time"]
                info["rtf"] = audio_duration / info["wall_time"] if info["wall_time"] > 0 else 0
                if first_complete_time is None:
                    first_complete_time = info["done_time"] - wall_start

        done_count = sum(1 for i in tasks.values() if i["status"] in TERMINAL_STATES)
        completed = sum(1 for i in tasks.values() if i["status"] == "completed")
        failed = sum(1 for i in tasks.values() if i["status"] in ("failed", "error", "cancelled"))
        running = sum(1 for i in tasks.values() if i["status"] in ("processing",))
        queued = submitted - done_count - running

        # dashboard snapshot
        dash = client.dashboard()
        gpu_busy = dash["workers"]["busy"] if dash else "?"
        gpu_total = dash["workers"]["total"] if dash else "?"
        if dash:
            snap = {
                "elapsed_sec": round(elapsed),
                "done": done_count,
                "running": running,
                "queued": queued,
                "workers_busy": dash["workers"]["busy"],
                "workers_total": dash["workers"]["total"],
                "queue_depth_pre": dash.get("queue", {}).get("depth_preprocess", 0),
                "queue_depth_gpu": dash.get("queue", {}).get("depth_transcription", 0),
            }
            dashboard_snapshots.append(snap)

        if done_count != last_print_done:
            m, s = divmod(int(elapsed), 60)
            print(
                f"  {m:02d}:{s:02d}     "
                f"{done_count:>4}/{submitted:<4}  "
                f"{queued:>6}  "
                f"{running:>7}  "
                f"{failed:>6}  "
                f"{gpu_busy}/{gpu_total}"
            )
            last_print_done = done_count

        if done_count >= submitted:
            all_complete_time = elapsed
            break

        if elapsed > timeout_sec:
            print(f"\n  {_c(RED, f'TIMEOUT after {timeout_minutes} min ({done_count}/{submitted} done)')}")
            all_complete_time = elapsed
            break

        time.sleep(poll_interval)

    # ── results ──────────────────────────────────────────────────────────────
    print(f"\n{_c(BOLD, '  ── Results ──')}")

    durations = [i["wall_time"] for i in tasks.values() if i["wall_time"] is not None]
    rtfs = [i["rtf"] for i in tasks.values() if i["rtf"] is not None]

    all_complete_min = all_complete_time / 60 if all_complete_time else 0
    first_complete_min = first_complete_time / 60 if first_complete_time else 0

    passed = all_complete_time is not None and all_complete_min <= TARGET_MAX_MINUTES
    icon = _c(GREEN, "✓ PASSED") if passed else _c(RED, "✗ FAILED")

    print(f"  Time to first completion : {first_complete_min:.2f} min")
    print(f"  Time to ALL completion   : {_c(BOLD, f'{all_complete_min:.2f} min')}")
    print(f"  Target (≤{TARGET_MAX_MINUTES} min)            : {icon}")
    print()
    print(f"  Completed : {completed}/{submitted}")
    print(f"  Failed    : {failed}/{submitted}")
    print()

    if durations:
        print(f"  Per-task wall time:")
        print(f"    Min    : {min(durations)/60:.2f} min")
        print(f"    Median : {statistics.median(durations)/60:.2f} min")
        print(f"    p95    : {_p(durations, 95)/60:.2f} min")
        print(f"    Max    : {max(durations)/60:.2f} min")
    if rtfs:
        print(f"  RTF (per task):")
        print(f"    Min    : {min(rtfs):.1f}×")
        print(f"    Median : {statistics.median(rtfs):.1f}×")
        print(f"    Max    : {max(rtfs):.1f}×")

    # Throughput
    total_audio_min = submitted * audio_duration / 60
    if all_complete_time and all_complete_time > 0:
        throughput = total_audio_min / (all_complete_time / 60)
        print(f"\n  Throughput : {_c(BOLD, f'{throughput:.1f}× real-time')} ({total_audio_min:.0f} min audio in {all_complete_min:.1f} min)")

    # Bottleneck hint
    print(f"\n{_c(BOLD, '  ── Bottleneck Analysis ──')}")
    if durations and all_complete_time:
        single_time = min(durations)
        queue_wait = all_complete_min - (single_time / 60)
        if queue_wait > 2:
            print(f"  {_c(YELLOW, f'Queue wait dominates: ~{queue_wait:.1f} min extra vs fastest task')}")
            print(f"  → Consider: more GPU workers (GPU_WORKERS_PER_GPU), larger preprocess pool")
        else:
            print(f"  {_c(GREEN, 'No significant queueing overhead detected')}")

    return {
        "n": submitted,
        "completed": completed,
        "failed": failed,
        "first_complete_min": round(first_complete_min, 2),
        "all_complete_min": round(all_complete_min, 2),
        "target_min": TARGET_MAX_MINUTES,
        "passed_target": passed,
        "per_task_wall_time_min": {
            "min": round(min(durations)/60, 2) if durations else None,
            "median": round(statistics.median(durations)/60, 2) if durations else None,
            "p95": round(_p(durations, 95)/60, 2) if durations else None,
            "max": round(max(durations)/60, 2) if durations else None,
        },
        "rtf": {
            "min": round(min(rtfs), 2) if rtfs else None,
            "median": round(statistics.median(rtfs), 2) if rtfs else None,
            "max": round(max(rtfs), 2) if rtfs else None,
        },
        "throughput_x_realtime": round(total_audio_min / all_complete_min, 2) if all_complete_min else None,
        "dashboard_snapshots": dashboard_snapshots,
        "tasks": [
            {k: v for k, v in t.items() if k != "done_time"}
            for t in tasks.values()
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# Theoretical estimate (no service needed)
# ═════════════════════════════════════════════════════════════════════════════

def print_theoretical_estimate(n: int, audio_duration: float, gpu_workers: int = 6,
                                preprocess_workers: int = 4, rtf_low: float = 20.0,
                                rtf_high: float = 40.0):
    chunks_per = estimate_chunks(audio_duration, CHUNK_DURATION)
    total_chunks = n * chunks_per

    print(f"\n{_c(BOLD+CYAN, '═══ Theoretical Capacity Estimate ═══')}")
    print(f"  Config     : 2× RTX 4000 Ada, GPU workers={gpu_workers}, preprocess={preprocess_workers}")
    print(f"  Audio      : {n} × {audio_duration/60:.1f} min = {n * audio_duration/60:.0f} min total")
    print(f"  Chunks     : {n} × {chunks_per} = {total_chunks} chunks @ {CHUNK_DURATION}s each")
    print()

    for rtf in [rtf_low, rtf_high]:
        secs_per_chunk = CHUNK_DURATION / rtf
        gpu_rounds = total_chunks / gpu_workers
        gpu_time = gpu_rounds * secs_per_chunk
        preprocess_rounds = n / preprocess_workers
        preprocess_time = preprocess_rounds * 20   # ~20s per file
        # pipeline: preprocess overlaps with GPU
        pipeline_time = max(preprocess_time, gpu_time) + 30  # +30s for aggregation
        label = "optimistic" if rtf == rtf_high else "conservative"
        ok = "✓" if pipeline_time / 60 <= TARGET_MAX_MINUTES else "✗"
        print(f"  RTF={rtf:.0f}× ({label})")
        print(f"    Per-chunk GPU time : {secs_per_chunk:.1f}s")
        print(f"    Total GPU time     : {gpu_time/60:.1f} min ({gpu_rounds:.0f} rounds × {secs_per_chunk:.1f}s)")
        print(f"    Preprocess time    : {preprocess_time/60:.1f} min")
        print(f"    Pipeline total     : {_c(BOLD, f'{pipeline_time/60:.1f} min')}  {ok}")
        print()

    print(f"  Target: ≤{TARGET_MAX_MINUTES} min  |  Model: medium-faster (float16, beam_size=2, batched=true)")


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Load test: 25 concurrent 30-min video capacity")
    parser.add_argument("--url",     default="http://localhost:8000",       help="Base URL")
    parser.add_argument("--file",    default=AUDIO_FILE_DEFAULT,             help="Audio file path")
    parser.add_argument("--n",       type=int, default=25,                   help="Concurrent tasks")
    parser.add_argument("--phase",   choices=["single","batch","both","estimate"], default="both")
    parser.add_argument("--poll",    type=float, default=5.0,                help="Poll interval (s)")
    parser.add_argument("--timeout", type=float, default=30.0,               help="Timeout (min)")
    parser.add_argument("--out",     default=None,                           help="Output JSON file")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = args.out or f"load_test_results_{ts}.json"

    print(f"\n{_c(BOLD, '╔══════════════════════════════════════════════════╗')}")
    print(f"{_c(BOLD, '║  Transcription Service — Capacity Load Test      ║')}")
    print(f"{_c(BOLD, '╚══════════════════════════════════════════════════╝')}")
    print(f"  URL       : {args.url}")
    print(f"  File      : {Path(args.file).name}")
    print(f"  Tasks     : {args.n}")
    print(f"  Phase     : {args.phase}")
    print(f"  Time      : {ts}")

    # ── estimate only (no service needed) ────────────────────────────────────
    if args.phase == "estimate":
        dur = get_audio_duration(args.file) or AUDIO_DURATION_SECONDS
        print_theoretical_estimate(args.n, dur)
        return

    # ── resolve audio duration ────────────────────────────────────────────────
    dur = get_audio_duration(args.file)
    if dur:
        print(f"  Duration  : {dur/60:.1f} min (ffprobe)")
    else:
        dur = AUDIO_DURATION_SECONDS
        print(f"  Duration  : {dur/60:.1f} min (default, ffprobe unavailable)")
    print_theoretical_estimate(args.n, dur)

    # ── service check ─────────────────────────────────────────────────────────
    client = APIClient(args.url)
    print(f"\nChecking service at {args.url}...")
    if not client.health():
        print(_c(RED, f"ERROR: Service not reachable at {args.url}"))
        print("Start the service first, or use --phase estimate for theoretical numbers only.")
        sys.exit(1)
    print(_c(GREEN, "Service is up."))

    # ── verify file exists on server ─────────────────────────────────────────
    if not Path(args.file).exists():
        print(_c(RED, f"ERROR: Audio file not found: {args.file}"))
        print("Update --file to point to a file accessible by the service.")
        sys.exit(1)

    results = {
        "test_time": ts,
        "url": args.url,
        "file": args.file,
        "audio_duration_seconds": dur,
        "n": args.n,
        "phase": args.phase,
        "theoretical": None,
        "single": None,
        "batch": None,
    }

    # Theoretical
    chunks_per = estimate_chunks(dur, CHUNK_DURATION)
    results["theoretical"] = {
        "chunks_per_video": chunks_per,
        "total_chunks": args.n * chunks_per,
        "gpu_workers": 6,
        "preprocess_workers": 4,
    }

    # ── Phase 1: single ───────────────────────────────────────────────────────
    if args.phase in ("single", "both"):
        results["single"] = benchmark_single(client, args.file, dur)

    # ── Phase 2: batch ────────────────────────────────────────────────────────
    if args.phase in ("batch", "both"):
        results["batch"] = run_concurrent(
            client, args.file, dur, args.n, args.poll, args.timeout
        )

    # ── save results ──────────────────────────────────────────────────────────
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  Results saved → {_c(CYAN, out_file)}")

    # ── final verdict ─────────────────────────────────────────────────────────
    if results.get("batch"):
        b = results["batch"]
        print(f"\n{_c(BOLD, '═══ FINAL VERDICT ═══')}")
        done_min = b.get("all_complete_min", 0)
        passed = b.get("passed_target", False)
        if passed:
            msg = f"PASSED — All {b['completed']} tasks completed in {done_min:.1f} min (target: ≤{TARGET_MAX_MINUTES} min)"
            print(f"  {_c(GREEN+BOLD, msg)}")
        else:
            msg = f"FAILED — Tasks completed in {done_min:.1f} min (target: ≤{TARGET_MAX_MINUTES} min)"
            print(f"  {_c(RED+BOLD, msg)}")
            print(f"\n  Recommendations:")
            if done_min > 0:
                shortfall = done_min - TARGET_MAX_MINUTES
                print(f"    • Shortfall: {shortfall:.1f} min — need ~{shortfall/done_min*100:.0f}% more throughput")
            print(f"    • Increase GPU_WORKERS_PER_GPU (current: 3)")
            print(f"    • Switch to large-v3-turbo model (faster RTF) — see .env.runpod-2GPU")
            print(f"    • Reduce WHISPER_CHUNK_LENGTH or TRANSCRIPTION_CHUNK_DURATION")
            print(f"    • Increase NUM_PREPROCESS_WORKERS (current: 4)")


if __name__ == "__main__":
    main()
