#!/usr/bin/env python3
"""
ทดสอบ Transcription + วัดเวลา + CPU
เป้าหมาย: เวลา < 3 นาที, CPU < 100%

วิธีใช้:
  source scripts/utility/load-env-by-gpu.sh  # โหลด env ตาม GPU
  python3 scripts/test_transcription_tune_1gpu.py
"""
import os
import sys
import time
import requests
import threading
from pathlib import Path
from collections import deque

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8010")
FILE_PATH = "uploads/2e8024e5-9ab8-4263-9375-24a0ffa4545c_3fe4b1ff-26e2-4883-a278-7ecad8b1fd5b_chapter_video_b41379a4-6100-4b29-8d60-87e97ee3da8c.m4a"
TARGET_TIME_SEC = 180  # 3 นาที
CPU_SAMPLES = deque(maxlen=120)  # เก็บ 2 นาที
cpu_monitor_running = False


def get_cpu_usage():
    """อ่าน CPU usage จาก /proc/stat"""
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.split()
        if len(parts) >= 5:
            user, nice, system, idle = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
            return (user + nice + system) / (user + nice + system + idle) * 100
    except Exception:
        pass
    return 0


def cpu_monitor_loop():
    """Background thread เก็บ CPU samples"""
    global cpu_monitor_running
    cpu_monitor_running = True
    prev = None
    while cpu_monitor_running:
        try:
            with open("/proc/stat") as f:
                line = f.readline()
            parts = line.split()
            if len(parts) >= 5:
                user, nice, system, idle = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                total = user + nice + system + idle
                if prev is not None:
                    used = (user + nice + system) - prev[0]
                    tot = total - prev[1]
                    if tot > 0:
                        CPU_SAMPLES.append(used / tot * 100)
                prev = (user + nice + system, total)
        except Exception:
            pass
        time.sleep(1)
    cpu_monitor_running = False


def main():
    abs_path = str((PROJECT_ROOT / FILE_PATH).resolve())
    if not Path(abs_path).exists():
        print(f"❌ ไม่พบไฟล์: {abs_path}")
        sys.exit(1)

    # โหลด .env.runpod-1GPU
    env_1gpu = PROJECT_ROOT / ".env.runpod-1GPU"
    if env_1gpu.exists():
        for line in env_1gpu.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip()
                if "#" in v:
                    v = v.split("#")[0].strip()
                if k and v and not v.startswith("$"):
                    os.environ[k] = v
        print(f"✅ Loaded {env_1gpu}")

    print("=" * 60)
    print("🧪 ทดสอบ Transcription (tune 1GPU)")
    print("=" * 60)
    print(f"📂 ไฟล์: {FILE_PATH}")
    print(f"📡 API: {API_BASE}")
    print(f"🎯 เป้าหมาย: เวลา < {TARGET_TIME_SEC}s, CPU < 100%")
    print(f"   NUM_PREPROCESS_WORKERS={os.getenv('NUM_PREPROCESS_WORKERS', '?')}")
    print(f"   GPU_WORKERS_PER_GPU={os.getenv('GPU_WORKERS_PER_GPU', '?')}")
    print(f"   WHISPER_BEAM_SIZE={os.getenv('WHISPER_BEAM_SIZE', '?')}")
    print(f"   CHUNK_DURATION={os.getenv('TRANSCRIPTION_CHUNK_DURATION', '150')}")
    print()

    # เริ่ม CPU monitor
    t_cpu = threading.Thread(target=cpu_monitor_loop, daemon=True)
    t_cpu.start()

    # ส่ง request
    url = f"{API_BASE}/api/transcribe-enhanced/start"
    payload = {
        "file_path": abs_path,
        "language": "th",
        "model_size": os.getenv("WHISPER_MODEL", "models--Vinxscribe--biodatlab-whisper-th-medium-faster"),
        "chunk_duration": int(os.getenv("TRANSCRIPTION_CHUNK_DURATION", "150")),
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
    except requests.exceptions.ConnectionError:
        print("❌ ไม่สามารถเชื่อมต่อ API ได้ - กรุณารัน start-pod.sh ก่อน")
        sys.exit(1)

    if r.status_code == 429:
        print("❌ Queue เต็ม (429)")
        sys.exit(1)
    if r.status_code not in (200, 201):
        print(f"❌ API error: {r.status_code} {r.text[:300]}")
        sys.exit(1)

    data = r.json()
    task_id = data.get("task_id")
    if not task_id:
        print("❌ ไม่ได้ task_id")
        sys.exit(1)

    print(f"✅ Task ส่งแล้ว: {task_id}")
    print("⏳ รอผล...")

    t_start = time.time()
    # ใช้ v2 tasks API (รองรับ SQLite storage)
    status_url = f"{API_BASE}/api/v2/tasks/{task_id}?format=full"
    last_status = ""
    while True:
        elapsed = time.time() - t_start
        if elapsed > 600:  # timeout 10 นาที
            print("❌ Timeout 10 นาที")
            break
        try:
            r = requests.get(status_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                # v2 API อาจมี data wrapper
                if "data" in data:
                    data = data["data"]
                status = data.get("status", "")
                progress = data.get("progress", 0)
                stage = data.get("current_stage", "")
                msg = f"[{elapsed:.0f}s] status={status} progress={progress}% stage={stage}"
                if msg != last_status:
                    print(msg)
                    last_status = msg
                if status == "completed":
                    total_time = time.time() - t_start
                    cpu_monitor_running = False
                    time.sleep(1.5)  # รอ sample สุดท้าย
                    avg_cpu = sum(CPU_SAMPLES) / len(CPU_SAMPLES) if CPU_SAMPLES else 0
                    max_cpu = max(CPU_SAMPLES) if CPU_SAMPLES else 0
                    print()
                    print("=" * 60)
                    print("📊 ผลลัพธ์")
                    print("=" * 60)
                    print(f"   เวลารวม: {total_time:.1f} วินาที ({total_time/60:.2f} นาที)")
                    print(f"   CPU เฉลี่ย: {avg_cpu:.1f}%")
                    print(f"   CPU สูงสุด: {max_cpu:.1f}%")
                    ok_time = "✅" if total_time < TARGET_TIME_SEC else "❌"
                    ok_cpu = "✅" if max_cpu < 100 else "❌"
                    print(f"   เป้าหมาย <3 นาที: {ok_time} ({total_time:.1f}s)")
                    print(f"   เป้าหมาย CPU<100%: {ok_cpu} (max={max_cpu:.1f}%)")
                    break
                elif status == "failed":
                    print(f"❌ Task failed: {data.get('error_message', '')}")
                    break
        except Exception as e:
            print(f"⚠️ Poll error: {e}")
        time.sleep(2)

    cpu_monitor_running = False


if __name__ == "__main__":
    main()
