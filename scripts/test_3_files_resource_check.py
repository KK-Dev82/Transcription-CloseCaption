#!/usr/bin/env python3
"""
Test Script: ทดสอบ 3 Files และตรวจสอบการใช้งานทรัพยากร (Resource Usage)
- Submit 3 transcription jobs
- Monitor CPU, RAM, GPU (VRAM) แบบ real-time
- สรุป: ใช้ไปเท่าไร vs เหลือเท่าไร (spec: 12 vCPU, 62GB RAM, 2x RTX 4000 Ada 20GB)

Usage:
  python3 scripts/test_3_files_resource_check.py
  python3 scripts/test_3_files_resource_check.py uploads/file1.wav uploads/file2.wav uploads/file3.wav
"""

import os
import sys
import time
import requests
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    import psutil
except ImportError:
    print("❌ pip install psutil ก่อนรันสคริปต์")
    sys.exit(1)

# Load env
env_file = ".env.runpod"
if os.path.exists(env_file):
    from dotenv import load_dotenv
    load_dotenv(env_file)

# Config
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8010")
MODEL_SIZE = os.getenv("WHISPER_MODEL", "deepdml/faster-whisper-large-v3-turbo-ct2")

# Spec: Pod = 12 vCPU, 62 GB RAM (252 = Server RAM), 2x RTX 4000 Ada 20GB
SPEC = {
    "vCPU": 12,
    "RAM_GB": 62,  # RAM จริงของ Pod
    "GPUS": 2,
    "VRAM_GB_PER_GPU": 20,
}

# Resource tracking
resource_samples: List[Dict] = []
monitoring_active = True


def get_gpu_info() -> List[Dict]:
    """Get GPU usage from nvidia-smi"""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            gpus = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 7:
                        try:
                            gpus.append({
                                "index": int(parts[0]),
                                "name": parts[1],
                                "gpu_util": int(parts[2]) if parts[2].isdigit() else 0,
                                "mem_util": int(parts[3]) if parts[3].isdigit() else 0,
                                "mem_used_mb": int(parts[4]) if parts[4].isdigit() else 0,
                                "mem_total_mb": int(parts[5]) if parts[5].isdigit() else 0,
                                "temp": parts[6],
                            })
                        except (ValueError, IndexError):
                            pass
            return gpus
    except Exception:
        pass
    return []


def sample_resources(interval: float = 2.0):
    """Sample CPU, RAM, GPU every interval seconds"""
    global resource_samples, monitoring_active
    while monitoring_active:
        try:
            cpu_percent = psutil.cpu_percent(interval=min(1.0, interval))
            mem = psutil.virtual_memory()
            gpus = get_gpu_info()

            sample = {
                "ts": time.time(),
                "cpu_percent": cpu_percent,
                "ram_used_gb": mem.used / (1024 ** 3),
                "ram_total_gb": mem.total / (1024 ** 3),
                "ram_percent": mem.percent,
                "gpus": gpus,
            }
            resource_samples.append(sample)
        except Exception:
            pass
        time.sleep(interval)


def submit_job(file_path: str, job_index: int) -> Dict:
    """Submit transcription job"""
    url = f"{API_BASE_URL}/api/transcribe/"
    payload = {
        "file_path": file_path,
        "language": "th",
        "model_size": MODEL_SIZE,
        "chunk_duration": 150,
    }
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 429:
            return {"job_index": job_index, "status": "queue_full", "task_id": None}
        elif response.status_code == 200:
            data = response.json()
            return {
                "job_index": job_index,
                "status": "queued",
                "task_id": data.get("task_id"),
            }
        else:
            return {"job_index": job_index, "status": "error", "error": response.text, "task_id": None}
    except Exception as e:
        return {"job_index": job_index, "status": "exception", "error": str(e), "task_id": None}


def get_task_status(task_id: str) -> Optional[Dict]:
    """Get task status from API"""
    try:
        r = requests.get(f"{API_BASE_URL}/api/v2/tasks/{task_id}", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def monitor_job(task_id: str, job_index: int) -> Dict:
    """Monitor job until completion"""
    start = time.time()
    while time.time() - start < 3600:
        data = get_task_status(task_id)
        if data:
            status = data.get("status", "unknown")
            progress = data.get("progress", 0)
            if status == "completed":
                return {
                    "job_index": job_index,
                    "task_id": task_id,
                    "status": "completed",
                    "elapsed": time.time() - start,
                    "progress": 100,
                }
            elif status in ["failed", "cancelled"]:
                return {
                    "job_index": job_index,
                    "task_id": task_id,
                    "status": status,
                    "elapsed": time.time() - start,
                    "error": data.get("error_message", ""),
                }
        time.sleep(2)
    return {"job_index": job_index, "task_id": task_id, "status": "timeout", "elapsed": 3600}


def print_resource_summary(samples: List[Dict]):
    """Print resource usage summary vs spec"""
    if not samples:
        return

    cpu_max = max(s["cpu_percent"] for s in samples)
    ram_max_gb = max(s["ram_used_gb"] for s in samples)
    ram_max_pct = max(s["ram_percent"] for s in samples)

    gpu_mem_max = [0.0] * SPEC["GPUS"]
    gpu_util_max = [0] * SPEC["GPUS"]
    for s in samples:
        for g in s.get("gpus", []):
            idx = g["index"]
            if idx < len(gpu_mem_max):
                gpu_mem_max[idx] = max(gpu_mem_max[idx], g["mem_used_mb"] / 1024)
                gpu_util_max[idx] = max(gpu_util_max[idx], g["gpu_util"])

    print()
    print("=" * 70)
    print("📊 Resource Usage Summary (3 Files Test)")
    print("=" * 70)
    print()
    print("Spec: 12 vCPU | 62 GB RAM | 2x RTX 4000 Ada 20GB")
    print("-" * 70)
    print()
    print("CPU:")
    print(f"  ใช้สูงสุด:  {cpu_max:.1f}%  (100% = ครบ {SPEC['vCPU']} cores)")
    print(f"  เหลือ:      ~{max(0, 100 - cpu_max):.0f}%  (headroom)")
    print()
    print("RAM:")
    print(f"  ใช้สูงสุด:  {ram_max_gb:.1f} GB  (limit: {SPEC['RAM_GB']} GB)")
    print(f"  เหลือ:      ~{max(0, SPEC['RAM_GB'] - ram_max_gb):.1f} GB")
    print(f"  ใช้เป็น %:  {ram_max_pct:.1f}%")
    print()
    print("GPU (VRAM):")
    for i in range(SPEC["GPUS"]):
        used = gpu_mem_max[i] if i < len(gpu_mem_max) else 0
        total = SPEC["VRAM_GB_PER_GPU"]
        free = max(0, total - used)
        util = gpu_util_max[i] if i < len(gpu_util_max) else 0
        print(f"  GPU {i}: ใช้ {used:.1f} GB / {total} GB  | เหลือ ~{free:.1f} GB  | GPU Util สูงสุด: {util}%")
    print()
    print("-" * 70)
    print("สรุป: RAM และ VRAM เหลือพอหรือไม่ → ถ้าเหลือเยอะ อาจเพิ่ม workers ได้")
    print("      CPU 100% → ลด NUM_PREPROCESS_WORKERS ได้")
    print("=" * 70)


def main():
    global monitoring_active

    # หาไฟล์ทดสอบ (รองรับ argument หรือ auto-detect)
    test_files: List[str] = []
    if len(sys.argv) >= 2:
        for arg in sys.argv[1:4]:  # รับได้ถึง 3 ไฟล์
            p = Path(arg)
            if p.is_absolute() and p.exists():
                test_files.append(str(p))
            elif (Path(project_root) / arg).exists():
                test_files.append(str((Path(project_root) / arg).resolve()))
            else:
                print(f"⚠️  ไฟล์ไม่พบ: {arg}")

    if not test_files:
        candidates = [
            "/workspace/transcription-service/uploads/160c549e-f820-4b2b-9720-4ecb2f500ed4_v30-1.wav",
            "/workspace/transcription-service/uploads/f8f3d293-ba60-41c5-9054-09725a3a22fb_v30-1.wav",
            "uploads/160c549e-f820-4b2b-9720-4ecb2f500ed4_v30-1.wav",
        ]
        for p in candidates:
            ap = Path(p)
            if not ap.is_absolute():
                ap = Path(project_root) / p
            if ap.exists():
                test_files.append(str(ap.resolve()))
                break

    if not test_files:
        # ลองค้นหาใน uploads
        uploads = Path(project_root) / "uploads"
        if uploads.exists():
            for f in list(uploads.glob("*.wav"))[:3] + list(uploads.glob("*.mp4"))[:3]:
                test_files.append(str(f))
        if not test_files:
            print("❌ ไม่พบไฟล์ทดสอบใน uploads/")
            print("   ใส่ไฟล์ .wav หรือ .mp4 ลงใน uploads/ ก่อนรัน")
            print("   หรือแก้ script ให้ชี้ไปที่ file_path ที่มีอยู่")
            sys.exit(1)

    # ใช้ไฟล์แรก 3 ครั้ง (หรือใช้ 3 ไฟล์ต่างกันถ้ามี)
    files_to_use = (test_files * 3)[:3]

    print("=" * 70)
    print("🧪 Test: 3 Files - Resource Usage Check")
    print("=" * 70)
    print()
    print(f"Spec: {SPEC['vCPU']} vCPU | {SPEC['RAM_GB']} GB RAM | {SPEC['GPUS']}x RTX 4000 Ada {SPEC['VRAM_GB_PER_GPU']}GB")
    print()
    print("Configuration:")
    print(f"  API: {API_BASE_URL}")
    print(f"  Model: {MODEL_SIZE}")
    print(f"  Files: {[os.path.basename(f) for f in files_to_use]}")
    print()

    # Baseline
    cpu0 = psutil.cpu_percent(interval=1)
    mem0 = psutil.virtual_memory()
    gpus0 = get_gpu_info()
    print("📊 Baseline (ก่อนส่ง job):")
    print(f"  CPU: {cpu0:.1f}%")
    print(f"  RAM: {mem0.used/(1024**3):.1f} GB / {mem0.total/(1024**3):.1f} GB")
    for g in gpus0:
        print(f"  GPU {g['index']}: {g['mem_used_mb']} MB / {g['mem_total_mb']} MB, Util: {g['gpu_util']}%")
    print()

    # เริ่ม monitor thread
    monitor_thread = threading.Thread(target=sample_resources, args=(2.0,), daemon=True)
    monitor_thread.start()
    time.sleep(0.5)

    # Submit 3 jobs
    print("📤 Submitting 3 jobs...")
    jobs = []
    for i, fp in enumerate(files_to_use):
        r = submit_job(fp, i + 1)
        jobs.append(r)
        if r["status"] == "queued":
            print(f"  Job {i+1}: ✅ {r['task_id'][:12]}...")
        else:
            print(f"  Job {i+1}: ❌ {r.get('status', 'error')} {r.get('error', '')}")
        time.sleep(0.3)

    queued = [j for j in jobs if j.get("task_id")]
    if not queued:
        print("\n❌ ไม่มี job ถูกส่ง สำเร็จ")
        monitoring_active = False
        return

    # Monitor จนเสร็จ
    print()
    print("📊 Monitoring... (กด Ctrl+C เพื่อหยุด)")
    start = time.time()
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(monitor_job, j["task_id"], j["job_index"]): j for j in queued}
        for f in as_completed(futures):
            try:
                res = f.result()
                status = res.get("status", "?")
                elapsed = res.get("elapsed", 0)
                print(f"  Job {res['job_index']}: {status} ({elapsed:.0f}s)")
            except Exception as e:
                print(f"  Error: {e}")
    total_time = time.time() - start

    monitoring_active = False
    time.sleep(2.5)

    # สรุป job
    print()
    print("=" * 70)
    print("⏱️  Time Summary")
    print("=" * 70)
    print(f"  Total: {total_time:.1f}s ({total_time/60:.2f} min)")
    print()

    # สรุป resource
    print_resource_summary(resource_samples)

    print()
    print("💡 หมายเหตุ:")
    print("   - ถ้า CPU 100% ตลอด → ลด NUM_PREPROCESS_WORKERS (เช่น 8→4)")
    print("   - ถ้า RAM/VRAM เหลือเยอะ → อาจเพิ่ม GPU workers ได้")
    print("   - ถ้าใช้เวลานาน → ตรวจสอบ queue / preprocess bottleneck")


if __name__ == "__main__":
    main()
