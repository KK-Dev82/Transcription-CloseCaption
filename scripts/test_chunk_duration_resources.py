#!/usr/bin/env python3
"""
ทดสอบ Chunk Duration 90 vs 150 vs 240 — วัด CPU, GPU, RAM usage ต่อ 1 ไฟล์ .wav

เปรียบเทียบ resource usage ระหว่าง chunk_duration ต่างๆ:
- 90s  → total_chunks เยอะ → Preprocess + Aggregator หนักขึ้น, GPU parallel มากขึ้น
- 150s → ค่า default
- 240s → total_chunks น้อย → Preprocess + Aggregator เบาลง, GPU ใช้เวลาต่อ chunk นานขึ้น

Usage:
  python scripts/test_chunk_duration_resources.py [--file PATH] [--clear-queue]
  --file PATH: ไฟล์ WAV (หรือ MP4/M4A) — default: ค้นหาใน uploads/
  --clear-queue: ล้าง queue ก่อนทดสอบ

Requires: API server + RQ workers ต้องรันอยู่
"""
import os
import sys
import time
import argparse
import requests
import threading
from pathlib import Path
from collections import deque

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8010")
CHUNK_DURATIONS = [90, 150, 240]

# Global samples — reset ระหว่างแต่ละ run
CPU_SAMPLES = deque(maxlen=600)
GPU_SAMPLES = deque(maxlen=600)
GPU_MEM_SAMPLES = deque(maxlen=600)
RAM_SAMPLES = deque(maxlen=600)
monitor_running = True


def reset_samples():
    """เคลียร์ samples ก่อน run ใหม่"""
    CPU_SAMPLES.clear()
    GPU_SAMPLES.clear()
    GPU_MEM_SAMPLES.clear()
    RAM_SAMPLES.clear()


def cpu_loop():
    prev = None
    while monitor_running:
        try:
            with open("/proc/stat") as f:
                parts = f.readline().split()
            if len(parts) >= 5:
                u, n, s, i = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                tot = u + n + s + i
                if prev:
                    used = (u + n + s) - prev[0]
                    t = tot - prev[1]
                    if t > 0:
                        CPU_SAMPLES.append(used / t * 100)
                prev = ((u + n + s), tot)
        except Exception:
            pass
        time.sleep(1)


def gpu_loop():
    import subprocess
    while monitor_running:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if out.returncode == 0 and out.stdout.strip():
                for line in out.stdout.strip().split("\n"):
                    parts = line.split(", ")
                    if len(parts) >= 3:
                        util = parts[0].strip().replace("%", "").strip()
                        mem_used = parts[1].strip().replace(" MiB", "").strip()
                        if util.isdigit():
                            GPU_SAMPLES.append(int(util))
                        if mem_used.isdigit():
                            GPU_MEM_SAMPLES.append(int(mem_used))
        except Exception:
            pass
        time.sleep(2)


def ram_loop():
    while monitor_running:
        try:
            with open("/proc/meminfo") as f:
                lines = f.read()
            mem_total = mem_avail = 0
            for line in lines.split("\n"):
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_avail = int(line.split()[1])
            if mem_total > 0:
                used_pct = (mem_total - mem_avail) / mem_total * 100
                RAM_SAMPLES.append(used_pct)
        except Exception:
            pass
        time.sleep(2)


def run_single_test(abs_path: str, chunk_duration: int) -> dict:
    """รัน transcription 1 ครั้งด้วย chunk_duration ที่กำหนด"""
    reset_samples()

    url = f"{API_BASE}/api/transcribe-enhanced/start"
    payload = {
        "file_path": abs_path,
        "language": "th",
        "use_chunking": True,
        "chunk_duration": chunk_duration,
    }
    if os.getenv("WHISPER_MODEL"):
        payload["model_size"] = os.getenv("WHISPER_MODEL")

    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code not in (200, 201):
            return {"error": f"API {r.status_code}: {r.text[:100]}", "chunk_duration": chunk_duration}
        task_id = r.json().get("task_id")
    except Exception as e:
        return {"error": str(e), "chunk_duration": chunk_duration}

    t_start = time.time()
    status_url = f"{API_BASE}/api/v2/tasks/{{task_id}}?format=minimal"
    while True:
        try:
            r = requests.get(status_url.format(task_id=task_id), timeout=10)
            if r.status_code == 200:
                d = r.json()
                data = d.get("data", d)
                status = data.get("status")
                if status == "completed":
                    break
                elif status == "failed":
                    return {
                        "error": data.get("error_message", "failed")[:100],
                        "chunk_duration": chunk_duration,
                        "elapsed": time.time() - t_start,
                    }
        except Exception:
            pass
        if time.time() - t_start > 3600:
            return {"error": "timeout 60min", "chunk_duration": chunk_duration, "elapsed": 3600}
        time.sleep(2)

    elapsed = time.time() - t_start

    # คำนวณ stats จาก samples
    avg_cpu = sum(CPU_SAMPLES) / len(CPU_SAMPLES) if CPU_SAMPLES else 0
    max_cpu = max(CPU_SAMPLES) if CPU_SAMPLES else 0
    avg_gpu = sum(GPU_SAMPLES) / len(GPU_SAMPLES) if GPU_SAMPLES else 0
    max_gpu = max(GPU_SAMPLES) if GPU_SAMPLES else 0
    avg_gpu_mem = sum(GPU_MEM_SAMPLES) / len(GPU_MEM_SAMPLES) if GPU_MEM_SAMPLES else 0
    max_gpu_mem = max(GPU_MEM_SAMPLES) if GPU_MEM_SAMPLES else 0
    avg_ram = sum(RAM_SAMPLES) / len(RAM_SAMPLES) if RAM_SAMPLES else 0
    max_ram = max(RAM_SAMPLES) if RAM_SAMPLES else 0

    return {
        "chunk_duration": chunk_duration,
        "elapsed": elapsed,
        "task_id": task_id,
        "avg_cpu": avg_cpu,
        "max_cpu": max_cpu,
        "avg_gpu": avg_gpu,
        "max_gpu": max_gpu,
        "avg_gpu_mem": avg_gpu_mem,
        "max_gpu_mem": max_gpu_mem,
        "avg_ram": avg_ram,
        "max_ram": max_ram,
    }


def main():
    ap = argparse.ArgumentParser(description="ทดสอบ chunk_duration 90 vs 150 vs 240 — วัด resource usage")
    ap.add_argument("--file", type=str, default=None, help="ไฟล์ WAV/MP4/M4A")
    ap.add_argument("--clear-queue", action="store_true", help="ล้าง queue ก่อนทดสอบ")
    args = ap.parse_args()

    # หาไฟล์
    audio_file = args.file
    if audio_file:
        abs_path = str(Path(audio_file).resolve()) if Path(audio_file).is_absolute() else str((PROJECT_ROOT / audio_file).resolve())
    else:
        candidates = [
            PROJECT_ROOT / "uploads",
            PROJECT_ROOT,
        ]
        found = None
        for base in candidates:
            if not base.exists():
                continue
            for ext in ["*.wav", "*.WAV", "*.m4a", "*.mp4"]:
                for f in base.glob(ext):
                    found = f
                    break
                if found:
                    break
            if found:
                break
        if not found or not found.exists():
            print("❌ ไม่พบไฟล์ WAV/MP4/M4A")
            print("   ใช้: python scripts/test_chunk_duration_resources.py --file path/to/file.wav")
            sys.exit(1)
        abs_path = str(found.resolve())
        try:
            audio_file = str(found.relative_to(PROJECT_ROOT))
        except ValueError:
            audio_file = found.name

    if not Path(abs_path).exists():
        print(f"❌ ไม่พบไฟล์: {abs_path}")
        sys.exit(1)

    # โหลด env
    for env_file in [PROJECT_ROOT / ".env.runpod", PROJECT_ROOT / ".env.runpod-1GPU", PROJECT_ROOT / ".env"]:
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip()
                    if "#" in v:
                        v = v.split("#")[0].strip()
                    if k and v and not v.startswith("$"):
                        os.environ[k] = v
            break

    if args.clear_queue:
        try:
            import redis
            r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
            queues = ["transcription_preprocess", "transcription_preprocess_video_record", "transcription_cpu"]
            queues += [f"transcription_gpu{i}" for i in range(4)]
            for q in queues:
                key = f"rq:queue:{q}"
                if r.llen(key):
                    r.delete(key)
                    print(f"   Cleared {q}")
            print("   ✅ Queue cleared")
        except ImportError:
            print("   ⚠️ redis not installed, skip clear")
        except Exception as e:
            print(f"   Clear queue: {e}")

    print("=" * 70)
    print("🧪 ทดสอบ Chunk Duration: 90 vs 150 vs 240 — Resource Usage ต่อ 1 ไฟล์")
    print("=" * 70)
    print(f"📂 ไฟล์: {audio_file}")
    print(f"📡 API: {API_BASE}")
    print(f"   chunk_durations: {CHUNK_DURATIONS}")
    print()

    # เริ่ม monitor (รันตลอดทั้ง 3 tests)
    global monitor_running
    monitor_running = True
    t_cpu = threading.Thread(target=cpu_loop, daemon=True)
    t_cpu.start()
    t_gpu = threading.Thread(target=gpu_loop, daemon=True)
    t_gpu.start()
    t_ram = threading.Thread(target=ram_loop, daemon=True)
    t_ram.start()

    results = []
    for cd in CHUNK_DURATIONS:
        print(f"⏳ รัน chunk_duration={cd}s...")
        res = run_single_test(abs_path, cd)
        results.append(res)
        if "error" in res:
            print(f"   ❌ {res['error']}")
        else:
            print(f"   ✅ เสร็จใน {res['elapsed']:.1f}s | CPU max {res['max_cpu']:.0f}% | GPU VRAM max {res['max_gpu_mem']:.0f} MB")
        time.sleep(3)  # พักระหว่าง run

    monitor_running = False
    time.sleep(2)

    # สรุปตารางเปรียบเทียบ
    print()
    print("=" * 70)
    print("📊 สรุปเปรียบเทียบ Chunk Duration")
    print("=" * 70)
    print()

    ok_results = [r for r in results if "error" not in r]
    if not ok_results:
        print("❌ ไม่มี run ที่สำเร็จ")
        return

    # Header
    print(f"{'chunk_duration':<14} {'เวลา(s)':<10} {'CPU avg':<10} {'CPU max':<10} {'GPU avg':<10} {'GPU max':<10} {'VRAM max':<12} {'RAM max':<10}")
    print("-" * 100)
    for r in ok_results:
        print(f"{r['chunk_duration']}s{'':<10} {r['elapsed']:<10.1f} {r['avg_cpu']:<10.1f} {r['max_cpu']:<10.1f} {r['avg_gpu']:<10.1f} {r['max_gpu']:<10.1f} {r['max_gpu_mem']:<12.0f} {r['max_ram']:<10.1f}")

    # Failed runs
    failed = [r for r in results if "error" in r]
    if failed:
        print()
        for r in failed:
            print(f"   chunk_duration={r['chunk_duration']}s: ❌ {r['error']}")

    print()
    print("💡 หมายเหตุ:")
    print("   - chunk_duration เล็กลง (90s) → total_chunks เยอะ → Preprocess + Aggregator หนักขึ้น")
    print("   - chunk_duration ใหญ่ขึ้น (240s) → total_chunks น้อย → Preprocess + Aggregator เบาลง")
    print("   - GPU VRAM มักใกล้เคียงกัน (ขึ้นกับ model size)")
    print("   - CPU/RAM สูงสุดมักเกิดจาก Preprocess (extract+chunk) และ Aggregator (fetch+merge)")
    print()


if __name__ == "__main__":
    main()
