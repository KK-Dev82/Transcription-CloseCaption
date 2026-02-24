#!/usr/bin/env python3
"""
ทดสอบ 25 concurrent M4A transcription jobs
วัดเวลารวมตั้งแต่ส่ง job แรกจน job สุดท้ายเสร็จ

ใช้: python scripts/test_25_m4a_concurrent.py [--clear-queue] [--num-jobs N] [--file PATH]
     --clear-queue = clear Redis queues ก่อนทดสอบ
     --num-jobs N   = จำนวน jobs (default 25)
     --file PATH    = ไฟล์ audio/video (default M4A)
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
M4A_FILE = "uploads/2e8024e5-9ab8-4263-9375-24a0ffa4545c_3fe4b1ff-26e2-4883-a278-7ecad8b1fd5b_chapter_video_b41379a4-6100-4b29-8d60-87e97ee3da8c.m4a"
NUM_JOBS = 25
CPU_SAMPLES = deque(maxlen=600)
GPU_SAMPLES = deque(maxlen=600)
RAM_SAMPLES = deque(maxlen=600)  # % used
cpu_running = True


def ram_loop():
    """Sample RAM usage % ทุก 2 วินาที"""
    while cpu_running:
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


def gpu_loop():
    """Sample GPU utilization ทุก 2 วินาที (ใช้ max across GPUs)"""
    import subprocess
    while cpu_running:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if out.returncode == 0 and out.stdout.strip():
                utils = []
                for line in out.stdout.strip().split("\n"):
                    v = line.strip().replace("%", "").strip()
                    if v.isdigit():
                        utils.append(int(v))
                if utils:
                    GPU_SAMPLES.append(max(utils))
        except Exception:
            pass
        time.sleep(2)


def cpu_loop():
    prev = None
    while cpu_running:
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


def clear_queues():
    """Clear RQ queues ก่อนทดสอบ"""
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
        num_gpus = int(os.getenv("NUM_GPUS", "2"))
        queues = ["transcription_preprocess", "transcription_preprocess_video_record", "transcription_priority", "transcription_cpu", "transcription_aggregator"]
        queues += [f"transcription_gpu{i}" for i in range(num_gpus)]
        for q in queues:
            key = f"rq:queue:{q}"
            n = r.llen(key)
            if n:
                r.delete(key)
                print(f"   Cleared {q}: {n} jobs")
        print("✅ Queue ว่างแล้ว\n")
    except Exception as e:
        print(f"⚠️ ไม่สามารถ clear queue: {e}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clear-queue", action="store_true", help="Clear Redis queues ก่อนทดสอบ")
    ap.add_argument("--num-jobs", type=int, default=25, help="จำนวน jobs (default 25)")
    ap.add_argument("--file", type=str, default=None, help="ไฟล์ audio/video (relative to project root)")
    args = ap.parse_args()
    num_jobs = args.num_jobs
    audio_file = args.file or M4A_FILE

    abs_path = str((PROJECT_ROOT / audio_file).resolve())
    if not Path(abs_path).exists():
        print(f"❌ ไม่พบไฟล์: {audio_file}")
        sys.exit(1)

    # โหลด env
    for env_file in [PROJECT_ROOT / ".env.runpod", PROJECT_ROOT / ".env.runpod-2GPU"]:
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
        print("🗑️ Clearing queues...")
        clear_queues()

    print("=" * 60)
    print(f"🧪 ทดสอบ {num_jobs} Concurrent M4A Transcription")
    print("=" * 60)
    print(f"📂 ไฟล์: {audio_file}")
    print(f"📊 จำนวน jobs: {num_jobs}")
    print(f"📡 API: {API_BASE}")
    print(f"   NUM_GPUS={os.getenv('NUM_GPUS')}, GPU_WORKERS_PER_GPU={os.getenv('GPU_WORKERS_PER_GPU')}")
    print(f"   NUM_PREPROCESS_WORKERS={os.getenv('NUM_PREPROCESS_WORKERS')}, NUM_CPU_WORKERS={os.getenv('NUM_CPU_WORKERS')}")
    print()

    # ส่ง jobs พร้อมกัน
    print(f"⏳ ส่ง {num_jobs} jobs...")
    t_start = time.time()
    task_ids = []
    url = f"{API_BASE}/api/transcribe-enhanced/start"
    payload = {
        "file_path": abs_path,
        "language": "th",
    }
    if os.getenv("WHISPER_MODEL"):
        payload["model_size"] = os.getenv("WHISPER_MODEL")
    cd = os.getenv("TRANSCRIPTION_CHUNK_DURATION")
    if cd:
        payload["chunk_duration"] = int(cd)
    for i in range(num_jobs):
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code in (200, 201):
                task_ids.append(r.json().get("task_id"))
            elif r.status_code == 429:
                print(f"❌ Queue เต็มที่ job {i+1}")
                break
            else:
                print(f"❌ API error {r.status_code} ที่ job {i+1}")
        except Exception as e:
            print(f"❌ Exception job {i+1}: {e}")
            break
    submit_time = time.time() - t_start
    print(f"✅ ส่งครบ {len(task_ids)}/{num_jobs} jobs ใน {submit_time:.1f}s")
    if not task_ids:
        sys.exit(1)

    # เริ่ม CPU + GPU + RAM monitor
    t_cpu = threading.Thread(target=cpu_loop, daemon=True)
    t_cpu.start()
    t_gpu = threading.Thread(target=gpu_loop, daemon=True)
    t_gpu.start()
    t_ram = threading.Thread(target=ram_loop, daemon=True)
    t_ram.start()

    # รอทุก job เสร็จ
    print("⏳ รอทุก job เสร็จ...")
    status_url = f"{API_BASE}/api/v2/tasks/{{task_id}}?format=minimal"
    completed = set()
    last_print = 0
    while len(completed) < len(task_ids):
        for tid in task_ids:
            if tid in completed:
                continue
            try:
                r = requests.get(status_url.format(task_id=tid), timeout=10)
                if r.status_code == 200:
                    d = r.json()
                    if "data" in d:
                        d = d["data"]
                    if d.get("status") == "completed":
                        completed.add(tid)
                    elif d.get("status") == "failed":
                        completed.add(tid)
                        print(f"⚠️ Task {tid[:8]}... failed")
            except Exception:
                pass
        elapsed = time.time() - t_start
        if elapsed - last_print >= 10:
            print(f"   [{elapsed:.0f}s] เสร็จแล้ว {len(completed)}/{len(task_ids)}")
            last_print = elapsed
        if elapsed > 6000:  # timeout 100 นาที
            print("❌ Timeout 100 นาที")
            break
        time.sleep(3)

    global cpu_running
    cpu_running = False
    time.sleep(1.5)
    total_time = time.time() - t_start
    avg_cpu = sum(CPU_SAMPLES) / len(CPU_SAMPLES) if CPU_SAMPLES else 0
    max_cpu = max(CPU_SAMPLES) if CPU_SAMPLES else 0
    avg_gpu = sum(GPU_SAMPLES) / len(GPU_SAMPLES) if GPU_SAMPLES else 0
    max_gpu = max(GPU_SAMPLES) if GPU_SAMPLES else 0
    avg_ram = sum(RAM_SAMPLES) / len(RAM_SAMPLES) if RAM_SAMPLES else 0
    max_ram = max(RAM_SAMPLES) if RAM_SAMPLES else 0

    # ตรวจสอบ full_text length ของแต่ละ task
    lengths = []
    for tid in task_ids:
        try:
            r = requests.get(f"{API_BASE}/api/v2/tasks/{tid}?format=full", timeout=10)
            if r.status_code == 200:
                d = r.json()
                data = d.get("data", d)
                result = data.get("result", {})
                text = result.get("text", "") or data.get("full_text", "")
                lengths.append(len(text))
        except Exception:
            pass

    print()
    print("=" * 60)
    print("📊 ผลลัพธ์")
    print("=" * 60)
    print(f"   จำนวน jobs: {len(task_ids)}")
    print(f"   เสร็จสมบูรณ์: {len(completed)}")
    print(f"   เวลารวม: {total_time:.1f} วินาที ({total_time/60:.2f} นาที)")
    print(f"   CPU เฉลี่ย: {avg_cpu:.1f}% | สูงสุด: {max_cpu:.1f}%")
    print(f"   GPU เฉลี่ย: {avg_gpu:.1f}% | สูงสุด: {max_gpu:.1f}%")
    print(f"   RAM เฉลี่ย: {avg_ram:.1f}% | สูงสุด: {max_ram:.1f}%")
    if lengths:
        print(f"   full_text length: min={min(lengths)}, max={max(lengths)}, avg={sum(lengths)/len(lengths):.0f}")
        if len(set(lengths)) > 1:
            print(f"   ⚠️ ความยาวไม่ตรงกัน! (ควร ~18494 สำหรับไฟล์เดียวกัน)")
        else:
            print(f"   ✅ ความยาวตรงกันทุก task")
    print()


if __name__ == "__main__":
    main()
