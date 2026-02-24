#!/usr/bin/env python3
"""
ทดสอบ Full-file (ไม่แบ่ง chunk) vs Chunk — วัด CPU, GPU, RAM usage
Spec: 5 vCPU, 1 GPU 20GB RTX 4000 Ada

Usage:
  python scripts/test_fullfile_vs_chunk_resources.py [--file PATH] [--use-chunking]
  --file PATH: ไฟล์ MP4 หรือ WAV (default: ใช้ไฟล์ที่มี)
  --use-chunking: ทดสอบแบบ chunk (default: ทดสอบ full-file)
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
# ไฟล์ default: MP4 ~30 นาที
MP4_FILE = "uploads/2e8024e5-9ab8-4263-9375-24a0ffa4545c_3fe4b1ff-26e2-4883-a278-7ecad8b1fd5b_chapter_video_b41379a4-6100-4b29-8d60-87e97ee3da8c.m4a"
WAV_FILE = None  # ใช้ถ้ามี

CPU_SAMPLES = deque(maxlen=600)
GPU_SAMPLES = deque(maxlen=600)
GPU_MEM_SAMPLES = deque(maxlen=600)  # MB used
RAM_SAMPLES = deque(maxlen=600)
monitor_running = True


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=str, default=None, help="ไฟล์ MP4/WAV/M4A")
    ap.add_argument("--use-chunking", action="store_true", help="ใช้ chunk mode (default: full-file)")
    ap.add_argument("--clear-queue", action="store_true", help="Clear queue ก่อนทดสอบ")
    args = ap.parse_args()

    audio_file = args.file or MP4_FILE
    abs_path = str((PROJECT_ROOT / audio_file).resolve())
    if not Path(abs_path).exists():
        print(f"❌ ไม่พบไฟล์: {audio_file}")
        sys.exit(1)

    # โหลด env
    for env_file in [PROJECT_ROOT / ".env.runpod", PROJECT_ROOT / ".env.runpod-1GPU"]:
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
            for q in ["transcription_preprocess", "transcription_preprocess_video_record", "transcription_cpu", "transcription_gpu0", "transcription_gpu1"]:
                key = f"rq:queue:{q}"
                if r.llen(key):
                    r.delete(key)
                    print(f"   Cleared {q}")
            print("   ✅ Queue cleared")
        except ImportError:
            print("   ⚠️ redis not installed, skip clear")
        except Exception as e:
            print(f"   Clear queue: {e}")

    use_chunking = args.use_chunking
    mode = "chunk" if use_chunking else "full-file"

    print("=" * 60)
    print(f"🧪 ทดสอบ {mode.upper()} — วัด CPU, GPU, RAM")
    print("=" * 60)
    print(f"📂 ไฟล์: {audio_file}")
    print(f"📡 API: {API_BASE}")
    print(f"   use_chunking={use_chunking}")
    print(f"   Spec: 5 vCPU, 1 GPU 20GB RTX 4000 Ada")
    print()

    # เริ่ม monitor
    t_cpu = threading.Thread(target=cpu_loop, daemon=True)
    t_cpu.start()
    t_gpu = threading.Thread(target=gpu_loop, daemon=True)
    t_gpu.start()
    t_ram = threading.Thread(target=ram_loop, daemon=True)
    t_ram.start()

    # ส่ง task
    url = f"{API_BASE}/api/transcribe-enhanced/start"
    payload = {
        "file_path": abs_path,
        "language": "th",
        "use_chunking": use_chunking,
    }
    print(f"⏳ ส่ง task (use_chunking={use_chunking})...")
    t_start = time.time()
    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code not in (200, 201):
            print(f"❌ API error {r.status_code}: {r.text[:200]}")
            sys.exit(1)
        data = r.json()
        task_id = data.get("task_id")
        print(f"✅ Task ID: {task_id[:8]}...")
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

    # รอเสร็จ
    status_url = f"{API_BASE}/api/v2/tasks/{{task_id}}?format=minimal"
    print("⏳ รอเสร็จ...")
    while True:
        try:
            r = requests.get(status_url.format(task_id=task_id), timeout=10)
            if r.status_code == 200:
                d = r.json()
                data = d.get("data", d)
                status = data.get("status")
                progress = data.get("progress", 0)
                elapsed = time.time() - t_start
                if status == "completed":
                    print(f"✅ เสร็จใน {elapsed:.1f}s")
                    break
                elif status == "failed":
                    print(f"❌ Failed: {data.get('error_message', '')[:100]}")
                    break
                if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                    print(f"   [{elapsed:.0f}s] {status} {progress}%")
        except Exception:
            pass
        if time.time() - t_start > 3600:
            print("❌ Timeout 60 นาที")
            break
        time.sleep(3)

    global monitor_running
    monitor_running = False
    time.sleep(2)

    total_time = time.time() - t_start
    avg_cpu = sum(CPU_SAMPLES) / len(CPU_SAMPLES) if CPU_SAMPLES else 0
    max_cpu = max(CPU_SAMPLES) if CPU_SAMPLES else 0
    avg_gpu = sum(GPU_SAMPLES) / len(GPU_SAMPLES) if GPU_SAMPLES else 0
    max_gpu = max(GPU_SAMPLES) if GPU_SAMPLES else 0
    avg_gpu_mem = sum(GPU_MEM_SAMPLES) / len(GPU_MEM_SAMPLES) if GPU_MEM_SAMPLES else 0
    max_gpu_mem = max(GPU_MEM_SAMPLES) if GPU_MEM_SAMPLES else 0
    avg_ram = sum(RAM_SAMPLES) / len(RAM_SAMPLES) if RAM_SAMPLES else 0
    max_ram = max(RAM_SAMPLES) if RAM_SAMPLES else 0

    print()
    print("=" * 60)
    print("📊 ผลลัพธ์ Resource Usage")
    print("=" * 60)
    print(f"   เวลารวม: {total_time:.1f}s ({total_time/60:.2f} นาที)")
    print(f"   CPU: เฉลี่ย {avg_cpu:.1f}% | สูงสุด {max_cpu:.1f}%")
    print(f"   GPU: เฉลี่ย {avg_gpu:.1f}% | สูงสุด {max_gpu:.1f}%")
    print(f"   GPU VRAM: เฉลี่ย {avg_gpu_mem:.0f} MB | สูงสุด {max_gpu_mem:.0f} MB")
    print(f"   RAM: เฉลี่ย {avg_ram:.1f}% | สูงสุด {max_ram:.1f}%")
    print()
    if max_gpu_mem > 0:
        room_20gb = 20 * 1024  # 20GB in MB
        remaining = room_20gb - max_gpu_mem
        print(f"   💡 VRAM 20GB: ใช้ {max_gpu_mem:.0f} MB, เหลือ ~{remaining:.0f} MB")
        if remaining > 2000:
            est_concurrent = int(remaining / (max_gpu_mem or 1))
            print(f"   💡 ประมาณ: 1 GPU รองรับได้ {max(1, est_concurrent)} ไฟล์พร้อมกัน (full-file)")
    print()


if __name__ == "__main__":
    main()
