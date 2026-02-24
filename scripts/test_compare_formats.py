#!/usr/bin/env python3
"""
เปรียบเทียบ Transcription: M4A vs WAV vs MP4
วัดเวลา + CPU + ตัวอย่างข้อความ (ไม่มีการ convert ฝั่งเรา - แต่ MP4 ต้อง extract)
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
FILES = [
    ("M4A", "uploads/2e8024e5-9ab8-4263-9375-24a0ffa4545c_3fe4b1ff-26e2-4883-a278-7ecad8b1fd5b_chapter_video_b41379a4-6100-4b29-8d60-87e97ee3da8c.m4a"),
    ("WAV", "uploads/f09d2850-371d-42c2-bf16-56cb49e00701_3fe4b1ff-26e2-4883-a278-7ecad8b1fd5b_chapter_video_b41379a4-6100-4b29-8d60-87e97ee3da8c.wav"),
    ("MP4", "uploads/3a7808ed-c011-4a2e-beed-9f319fe8bb89_3fe4b1ff-26e2-4883-a278-7ecad8b1fd5b_chapter_video_b41379a4-6100-4b29-8d60-87e97ee3da8c.mp4"),
]
CPU_SAMPLES = deque(maxlen=300)
cpu_monitor_running = False


def cpu_monitor_loop():
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


def run_one(label: str, file_path: str) -> dict:
    global CPU_SAMPLES
    CPU_SAMPLES.clear()
    abs_path = str((PROJECT_ROOT / file_path).resolve())
    if not Path(abs_path).exists():
        return {"label": label, "error": f"ไม่พบไฟล์: {file_path}"}

    url = f"{API_BASE}/api/transcribe-enhanced/start"
    payload = {
        "file_path": abs_path,
        "language": "th",
        "model_size": os.getenv("WHISPER_MODEL", "models--Vinxscribe--biodatlab-whisper-th-medium-faster"),
        "chunk_duration": int(os.getenv("TRANSCRIPTION_CHUNK_DURATION", "240")),
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
    except Exception as e:
        return {"label": label, "error": str(e)}

    if r.status_code != 200 and r.status_code != 201:
        return {"label": label, "error": f"API {r.status_code}: {r.text[:200]}"}

    task_id = r.json().get("task_id")
    if not task_id:
        return {"label": label, "error": "ไม่มี task_id"}

    status_url = f"{API_BASE}/api/v2/tasks/{task_id}?format=full"
    t_start = time.time()
    full_text = ""
    while True:
        elapsed = time.time() - t_start
        if elapsed > 600:
            return {"label": label, "error": "Timeout 10 นาที", "task_id": task_id}
        try:
            r = requests.get(status_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if "data" in data:
                    data = data["data"]
                status = data.get("status", "")
                full_text = data.get("full_text", "") or data.get("text", "")
                if status == "completed":
                    break
                elif status == "failed":
                    return {"label": label, "error": data.get("error_message", "failed"), "task_id": task_id}
        except Exception as e:
            pass
        time.sleep(2)

    total_time = time.time() - t_start
    time.sleep(1.5)
    avg_cpu = sum(CPU_SAMPLES) / len(CPU_SAMPLES) if CPU_SAMPLES else 0
    max_cpu = max(CPU_SAMPLES) if CPU_SAMPLES else 0
    return {
        "label": label,
        "time_sec": total_time,
        "cpu_avg": avg_cpu,
        "cpu_max": max_cpu,
        "text_preview": full_text[:500] if full_text else "",
        "text_len": len(full_text),
    }


def main():
    env_file = PROJECT_ROOT / ".env.runpod-1GPU"
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
        print(f"✅ Loaded {env_file}\n")

    print("=" * 70)
    print("🧪 เปรียบเทียบ Transcription: M4A vs WAV vs MP4")
    print("=" * 70)
    print("   M4A: ข้าม extract, create_chunks ใช้ PyAV decode")
    print("   WAV:  ข้าม extract, create_chunks ใช้ wave fast path")
    print("   MP4:  ต้อง extract (FFmpeg) + create_chunks")
    print()

    global cpu_monitor_running
    t_cpu = threading.Thread(target=cpu_monitor_loop, daemon=True)
    t_cpu.start()

    results = []
    for label, file_path in FILES:
        print(f"⏳ กำลังทดสอบ {label}...")
        r = run_one(label, file_path)
        results.append(r)
        if "error" in r:
            print(f"   ❌ {r['error']}")
        else:
            print(f"   ✅ {r['time_sec']:.1f}s, CPU max={r['cpu_max']:.1f}%")

    cpu_monitor_running = False
    time.sleep(2)

    print()
    print("=" * 70)
    print("📊 สรุปผล")
    print("=" * 70)
    print(f"{'Format':<8} {'เวลา (s)':<12} {'CPU avg':<10} {'CPU max':<10} {'ความยาวข้อความ':<12}")
    print("-" * 70)
    for r in results:
        if "error" in r:
            print(f"{r['label']:<8} ERROR: {r['error'][:40]}")
        else:
            print(f"{r['label']:<8} {r['time_sec']:<12.1f} {r['cpu_avg']:<10.1f}% {r['cpu_max']:<10.1f}% {r['text_len']:<12}")
    print()

    # เปรียบเทียบข้อความ (ถ้าทั้ง 3 สำเร็จ)
    ok_results = [r for r in results if "error" not in r and r.get("text_len", 0) > 0]
    if len(ok_results) >= 2:
        print("=" * 70)
        print("📝 ตัวอย่างข้อความ (200 ตัวอักษรแรก)")
        print("=" * 70)
        for r in ok_results:
            preview = (r.get("text_preview", "") or "")[:200]
            print(f"\n--- {r['label']} ---")
            print(preview + ("..." if len(preview) >= 200 else ""))
        print()


if __name__ == "__main__":
    main()
