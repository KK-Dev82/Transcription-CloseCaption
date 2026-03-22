#!/usr/bin/env python3
"""
Test Plan: 26 Transcription Tasks — Queue Reject Verification
=============================================================

วัตถุประสงค์:
  1. ส่ง 26 tasks พร้อมกัน → 25 task ทำงาน, 1 task ถูก reject (HTTP 429)
  2. 25 tasks ที่ผ่านต้องเสร็จภายใน 25 นาที
  3. ผลลัพธ์ (จำนวนตัวอักษร) ต้องเท่ากันทุก task (เพราะใช้ไฟล์เดียวกัน)

วิธีใช้:
    python scripts/test_26_queue_reject.py [options]

Options:
    --url       BASE_URL (default: http://localhost:8010)
    --file      path ของ audio file
    --timeout   timeout นาที (default: 30)
    --poll      polling interval วินาที (default: 5)

ตัวอย่าง:
    python scripts/test_26_queue_reject.py
    python scripts/test_26_queue_reject.py --url http://localhost:8010
"""

import argparse
import json
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import statistics

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
AUDIO_FILE_DEFAULT = (
    "/workspace/transcription-service/uploads/"
    "a0f43cec-aed9-4dea-82d8-a7c11d59674e_260128_1020"
    " อนุฯ พัฒนาระบบ (บริหารราชการแผ่นดิน) 2.wav"
)

TOTAL_TASKS = 26
EXPECTED_ACCEPTED = 25
EXPECTED_REJECTED = 1
TARGET_MAX_MINUTES = 25
TERMINAL_STATES = {"completed", "failed", "cancelled", "error"}

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


def c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}"


def elapsed_str(start: float) -> str:
    s = time.time() - start
    m, sec = divmod(int(s), 60)
    return f"{m:02d}:{sec:02d}"


# ── API Client ────────────────────────────────────────────────────────────────
class APIClient:
    def __init__(self, base_url: str, timeout: int = 120):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def health(self) -> bool:
        try:
            r = self.session.get(f"{self.base}/health", timeout=5)
            return r.status_code < 500
        except Exception:
            return False

    def submit_no_retry(self, file_path: str) -> dict:
        """Submit 1 task — ไม่ retry on 429 (เพราะต้องการวัด reject)"""
        url = f"{self.base}/api/transcribe/"
        payload = {"file_path": file_path, "language": "th"}
        try:
            r = self.session.post(url, json=payload, timeout=self.timeout)
            return {
                "status_code": r.status_code,
                "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else {"detail": r.text},
            }
        except Exception as e:
            return {"status_code": 0, "body": {"detail": str(e)}}

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


# ══════════════════════════════════════════════════════════════════════════════
# Test: Submit 26 tasks concurrently
# ══════════════════════════════════════════════════════════════════════════════

def run_test(client: APIClient, file_path: str, poll_interval: float, timeout_minutes: float):
    print(f"\n{c(BOLD + CYAN, '╔══════════════════════════════════════════════════════════╗')}")
    print(f"{c(BOLD + CYAN, '║  Test: 26 Tasks → 25 Accepted + 1 Rejected (HTTP 429)   ║')}")
    print(f"{c(BOLD + CYAN, '╚══════════════════════════════════════════════════════════╝')}")
    print(f"  File     : {Path(file_path).name}")
    print(f"  Tasks    : {TOTAL_TASKS} (expect {EXPECTED_ACCEPTED} accepted, {EXPECTED_REJECTED} rejected)")
    print(f"  Target   : all {EXPECTED_ACCEPTED} done within {TARGET_MAX_MINUTES} min")
    print(f"  Criteria : character count must be identical across all completed tasks")
    print()

    # ── Step 1: Submit 26 tasks concurrently ──────────────────────────────────
    print(c(BOLD, "── Step 1: Submit 26 tasks simultaneously ──"))
    print()

    results_lock = threading.Lock()
    accepted: List[Dict] = []     # task_id, submit_time, idx
    rejected: List[Dict] = []     # status_code, detail, idx
    submit_errors: List[Dict] = []

    def do_submit(idx: int):
        t0 = time.time()
        resp = client.submit_no_retry(file_path)
        elapsed = time.time() - t0
        code = resp["status_code"]
        body = resp["body"]

        with results_lock:
            if code == 200:
                task_id = body.get("task_id", "unknown")
                slots_used = body.get("queue_slots_used", "?")
                slots_max = body.get("queue_slots_max", "?")
                accepted.append({
                    "idx": idx,
                    "task_id": task_id,
                    "submit_time": t0,
                    "status": "queued",
                    "progress": 0,
                    "done_time": None,
                    "wall_time": None,
                    "result_text": None,
                    "char_count": None,
                })
                print(f"  Task #{idx:02d}  {c(GREEN, 'ACCEPTED')}  task_id={task_id[:12]}...  "
                      f"slots={slots_used}/{slots_max}  ({elapsed:.1f}s)")
            elif code == 429:
                detail = body.get("detail", "Queue full")
                rejected.append({
                    "idx": idx,
                    "status_code": code,
                    "detail": detail,
                })
                print(f"  Task #{idx:02d}  {c(YELLOW, 'REJECTED 429')}  {detail[:60]}  ({elapsed:.1f}s)")
            else:
                detail = body.get("detail", str(body))
                submit_errors.append({
                    "idx": idx,
                    "status_code": code,
                    "detail": detail,
                })
                print(f"  Task #{idx:02d}  {c(RED, f'ERROR {code}')}  {detail[:60]}  ({elapsed:.1f}s)")

    # Strategy: Submit first 25 quickly in batches of 10 (to fill preprocess queue)
    # then submit task #26 which should be rejected because preprocess queue is full.
    #
    # Rate limit check order in the API:
    #   1. rate_limiter.acquire() — counts concurrent API requests (released on response)
    #   2. _check_preprocess_queue_limit() — counts queued+started in preprocess queue
    # The preprocess queue limit (MAX_PREPROCESS_QUEUE_SIZE=25) is the real bottleneck.
    # We need to fill it faster than 4 preprocess workers can drain it.
    submit_start = time.time()
    BATCH_SIZE = 10  # Larger batches to fill queue faster

    # Phase A: Submit first 25 tasks in large batches
    for batch_start in range(0, EXPECTED_ACCEPTED, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, EXPECTED_ACCEPTED)
        batch_threads = []
        for i in range(batch_start, batch_end):
            t = threading.Thread(target=do_submit, args=(i,), daemon=True)
            batch_threads.append(t)
        for t in batch_threads:
            t.start()
        for t in batch_threads:
            t.join(timeout=120)
        # Minimal pause — just enough for API to not crash
        if batch_end < EXPECTED_ACCEPTED:
            time.sleep(0.5)

    # Phase B: Submit task #26 (should be rejected if queue is full)
    print(f"\n  {c(BOLD, '→ Submitting task #25 (the 26th task — expect 429)...')}")
    do_submit(EXPECTED_ACCEPTED)  # idx=25

    submit_elapsed = time.time() - submit_start
    print(f"\n  Submit completed in {submit_elapsed:.1f}s")
    print(f"    Accepted : {len(accepted)}")
    print(f"    Rejected : {len(rejected)} (HTTP 429)")
    print(f"    Errors   : {len(submit_errors)}")

    # ── Step 1 Verification ───────────────────────────────────────────────────
    print(f"\n{c(BOLD, '── Step 1 Verification: Queue Reject ──')}")
    test1_pass = (len(accepted) == EXPECTED_ACCEPTED and len(rejected) >= EXPECTED_REJECTED)
    if test1_pass:
        print(f"  {c(GREEN, f'✓ PASS')}  {len(accepted)} accepted + {len(rejected)} rejected = {TOTAL_TASKS} total")
    else:
        print(f"  {c(RED, f'✗ FAIL')}  Expected {EXPECTED_ACCEPTED} accepted + {EXPECTED_REJECTED} rejected")
        print(f"           Got {len(accepted)} accepted + {len(rejected)} rejected + {len(submit_errors)} errors")
        if len(accepted) == 0:
            print(f"\n  {c(RED, 'No tasks accepted — aborting')}")
            return

    if not accepted:
        print(f"\n  {c(RED, 'No accepted tasks to monitor — aborting')}")
        return

    # ── Step 2: Monitor until all complete ────────────────────────────────────
    print(f"\n{c(BOLD, f'── Step 2: Wait for {len(accepted)} tasks to complete (timeout: {timeout_minutes} min) ──')}")
    print()

    wall_start = time.time()
    timeout_sec = timeout_minutes * 60
    total = len(accepted)

    header = f"  {'Elapsed':>7}  {'Done':>4}/{total:<4}  {'Queued':>6}  {'Running':>7}  {'Failed':>6}  {'Progress'}"
    print(header)
    print("  " + "─" * 70)

    last_print_done = -1

    while True:
        elapsed = time.time() - wall_start

        # Poll each pending task
        for info in accepted:
            if info["status"] in TERMINAL_STATES:
                continue
            task = client.get_task(info["task_id"])
            if not task:
                continue
            status = task.get("status", "unknown")
            progress = task.get("progress", 0)
            info["status"] = status
            info["progress"] = progress

            if status in TERMINAL_STATES and info["done_time"] is None:
                info["done_time"] = time.time()
                info["wall_time"] = info["done_time"] - info["submit_time"]

                # Extract result text
                result = task.get("result")
                if result and isinstance(result, dict):
                    text = result.get("full_text") or result.get("text") or ""
                    info["result_text"] = text
                    info["char_count"] = len(text)

        done_count = sum(1 for i in accepted if i["status"] in TERMINAL_STATES)
        completed = sum(1 for i in accepted if i["status"] == "completed")
        failed = sum(1 for i in accepted if i["status"] in ("failed", "error", "cancelled"))
        running = sum(1 for i in accepted if i["status"] in ("processing",))
        queued = total - done_count - running

        # Avg progress
        avg_progress = sum(i["progress"] for i in accepted) / total if total else 0

        if done_count != last_print_done or int(elapsed) % 15 == 0:
            m, s = divmod(int(elapsed), 60)
            bar_fill = int(avg_progress / 5)
            bar = "█" * bar_fill + "░" * (20 - bar_fill)
            print(
                f"  {m:02d}:{s:02d}     "
                f"{done_count:>4}/{total:<4}  "
                f"{queued:>6}  "
                f"{running:>7}  "
                f"{failed:>6}  "
                f"[{bar}] {avg_progress:.0f}%"
            )
            last_print_done = done_count

        if done_count >= total:
            break

        if elapsed > timeout_sec:
            print(f"\n  {c(RED, f'TIMEOUT after {timeout_minutes:.0f} min ({done_count}/{total} done)')}")
            break

        time.sleep(poll_interval)

    all_complete_sec = time.time() - wall_start
    all_complete_min = all_complete_sec / 60

    # ── Step 2 Verification: Completion within 25 min ─────────────────────────
    print(f"\n{c(BOLD, '── Step 2 Verification: Completion Time ──')}")
    completed_count = sum(1 for i in accepted if i["status"] == "completed")
    failed_count = sum(1 for i in accepted if i["status"] != "completed")

    print(f"  Completed : {completed_count}/{total}")
    print(f"  Failed    : {failed_count}/{total}")
    print(f"  Total time: {all_complete_min:.2f} min")

    test2_pass = (completed_count == EXPECTED_ACCEPTED and all_complete_min <= TARGET_MAX_MINUTES)
    if completed_count == EXPECTED_ACCEPTED and all_complete_min <= TARGET_MAX_MINUTES:
        print(f"  {c(GREEN, f'✓ PASS')}  All {completed_count} tasks completed in {all_complete_min:.1f} min (target ≤{TARGET_MAX_MINUTES})")
    elif completed_count == EXPECTED_ACCEPTED:
        print(f"  {c(RED, f'✗ FAIL')}  All {completed_count} tasks completed but took {all_complete_min:.1f} min (target ≤{TARGET_MAX_MINUTES})")
    else:
        print(f"  {c(RED, f'✗ FAIL')}  Only {completed_count}/{total} tasks completed")

    # Per-task timing
    durations = [i["wall_time"] for i in accepted if i["wall_time"] is not None and i["status"] == "completed"]
    if durations:
        print(f"\n  Per-task wall time:")
        print(f"    Min    : {min(durations)/60:.2f} min")
        print(f"    Median : {statistics.median(durations)/60:.2f} min")
        print(f"    Max    : {max(durations)/60:.2f} min")

    # ── Step 3 Verification: Character Count Consistency ──────────────────────
    print(f"\n{c(BOLD, '── Step 3 Verification: Character Count Consistency ──')}")

    completed_tasks = [i for i in accepted if i["status"] == "completed"]

    # Fetch full results for tasks that don't have text yet
    for info in completed_tasks:
        if info["char_count"] is None:
            task = client.get_task(info["task_id"])
            if task:
                result = task.get("result")
                if result and isinstance(result, dict):
                    text = result.get("full_text") or result.get("text") or ""
                    info["result_text"] = text
                    info["char_count"] = len(text)

    char_counts = [i["char_count"] for i in completed_tasks if i["char_count"] is not None]

    if not char_counts:
        print(f"  {c(RED, '✗ FAIL')}  No character counts available")
        test3_pass = False
    else:
        unique_counts = set(char_counts)
        min_chars = min(char_counts)
        max_chars = max(char_counts)
        median_chars = statistics.median(char_counts)

        print(f"  Tasks with results: {len(char_counts)}/{len(completed_tasks)}")
        print(f"  Character counts:")
        print(f"    Min    : {min_chars:,}")
        print(f"    Median : {int(median_chars):,}")
        print(f"    Max    : {max_chars:,}")

        if len(unique_counts) == 1:
            print(f"  {c(GREEN, f'✓ PASS')}  All {len(char_counts)} tasks produced identical output ({min_chars:,} chars)")
            test3_pass = True
        else:
            # Allow small variance (±0.5%) due to potential non-determinism
            variance_pct = (max_chars - min_chars) / median_chars * 100 if median_chars > 0 else 100
            if variance_pct <= 0.5:
                print(f"  {c(GREEN, f'✓ PASS')}  Variance is negligible ({variance_pct:.2f}%)")
                test3_pass = True
            else:
                print(f"  {c(RED, f'✗ FAIL')}  {len(unique_counts)} different character counts (variance: {variance_pct:.1f}%)")
                test3_pass = False

            # Show distribution
            print(f"\n  Distribution:")
            from collections import Counter
            counter = Counter(char_counts)
            for count, freq in counter.most_common(10):
                pct = freq / len(char_counts) * 100
                print(f"    {count:>8,} chars × {freq} tasks ({pct:.0f}%)")

    # ══════════════════════════════════════════════════════════════════════════
    # Final Summary
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{c(BOLD + CYAN, '══════════════════════════════════════════')}")
    print(f"{c(BOLD + CYAN, '  FINAL TEST RESULTS')}")
    print(f"{c(BOLD + CYAN, '══════════════════════════════════════════')}")
    print()

    tests = [
        ("Queue Reject (25 accepted + 1 rejected)", test1_pass),
        (f"Completion Time (≤{TARGET_MAX_MINUTES} min)", test2_pass),
        ("Character Count Consistency", test3_pass),
    ]

    all_pass = True
    for name, passed in tests:
        icon = c(GREEN, "✓ PASS") if passed else c(RED, "✗ FAIL")
        print(f"  {icon}  {name}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print(f"  {c(GREEN + BOLD, '★ ALL TESTS PASSED ★')}")
    else:
        print(f"  {c(RED + BOLD, '✗ SOME TESTS FAILED')}")

    # ── Save results to JSON ──────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = f"test_26_results_{ts}.json"

    output = {
        "test_time": ts,
        "config": {
            "total_tasks": TOTAL_TASKS,
            "expected_accepted": EXPECTED_ACCEPTED,
            "expected_rejected": EXPECTED_REJECTED,
            "target_max_minutes": TARGET_MAX_MINUTES,
            "file": file_path,
        },
        "results": {
            "test1_queue_reject": {
                "pass": test1_pass,
                "accepted": len(accepted),
                "rejected": len(rejected),
                "errors": len(submit_errors),
            },
            "test2_completion_time": {
                "pass": test2_pass,
                "completed": completed_count,
                "failed": failed_count,
                "total_minutes": round(all_complete_min, 2),
                "per_task_minutes": {
                    "min": round(min(durations) / 60, 2) if durations else None,
                    "median": round(statistics.median(durations) / 60, 2) if durations else None,
                    "max": round(max(durations) / 60, 2) if durations else None,
                },
            },
            "test3_char_consistency": {
                "pass": test3_pass,
                "unique_counts": len(set(char_counts)) if char_counts else 0,
                "char_counts": char_counts,
            },
            "all_pass": all_pass,
        },
        "accepted_tasks": [
            {
                "idx": i["idx"],
                "task_id": i["task_id"],
                "status": i["status"],
                "wall_time_sec": round(i["wall_time"], 2) if i["wall_time"] else None,
                "char_count": i["char_count"],
            }
            for i in sorted(accepted, key=lambda x: x["idx"])
        ],
        "rejected_tasks": rejected,
        "submit_errors": submit_errors,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  Results saved → {c(CYAN, out_file)}")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Test: 26 tasks → 25 accepted + 1 rejected")
    parser.add_argument("--url", default="http://localhost:8010", help="Base URL")
    parser.add_argument("--file", default=AUDIO_FILE_DEFAULT, help="Audio file path")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout (min)")
    parser.add_argument("--poll", type=float, default=5.0, help="Poll interval (s)")
    args = parser.parse_args()

    print(f"\n{c(BOLD, '╔══════════════════════════════════════════════════════════╗')}")
    print(f"{c(BOLD, '║  Transcription Service — 26 Task Queue Reject Test       ║')}")
    print(f"{c(BOLD, '╚══════════════════════════════════════════════════════════╝')}")
    print(f"  URL      : {args.url}")
    print(f"  File     : {Path(args.file).name}")
    print(f"  Timeout  : {args.timeout} min")
    print(f"  Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Pre-flight checks
    print(f"\n{c(BOLD, '── Pre-flight Checks ──')}")

    # 1. Check file exists
    if Path(args.file).exists():
        size_mb = Path(args.file).stat().st_size / 1024 / 1024
        print(f"  {c(GREEN, '✓')} File exists ({size_mb:.1f} MB)")
    else:
        print(f"  {c(RED, '✗')} File not found: {args.file}")
        sys.exit(1)

    # 2. Check service health
    client = APIClient(args.url)
    if client.health():
        print(f"  {c(GREEN, '✓')} Service is up at {args.url}")
    else:
        print(f"  {c(RED, '✗')} Service not reachable at {args.url}")
        sys.exit(1)

    # 3. Check queue is empty (clean state)
    dash = client.dashboard()
    if dash:
        active = dash.get("active_tasks", 0)
        if active == 0:
            print(f"  {c(GREEN, '✓')} Queue is empty (clean state)")
        else:
            print(f"  {c(YELLOW, '⚠')} {active} tasks already active — results may be affected")

    print()
    run_test(client, args.file, args.poll, args.timeout)


if __name__ == "__main__":
    main()
