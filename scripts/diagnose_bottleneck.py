#!/usr/bin/env python3
"""
Diagnose Bottleneck: วิเคราะห์ว่าช้าที่ไหน และส่วนไหนนำมาใช้ได้อีก
- ใช้ไฟล์ที่ระบุ
- Submit 1 job, รอจนเสร็จ
- อ่าน phase_timings จาก SQLite
- แสดง: Extract | Chunk (Convert) | GPU Transcribe | Merge | Thai/Fuzzy
- ระบุ Bottleneck + แนะนำการใช้ Resource เพิ่ม

Usage:
  python3 scripts/diagnose_bottleneck.py
  python3 scripts/diagnose_bottleneck.py "uploads/ไฟล์.mp3"
"""

import os
import sys
import time
import requests
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import psutil
except ImportError:
    psutil = None

# Load env
for f in [project_root / ".env.runpod", project_root / ".env"]:
    if f.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(f)
            break
        except ImportError:
            pass

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8010")
MODEL_SIZE = os.getenv("WHISPER_MODEL", "deepdml/faster-whisper-large-v3-turbo-ct2")

# Spec: Pod ใช้ RAM 62 GB จริง (252 = Server)
SPEC_RAM_GB = 62
SPEC_VCPU = 12
SPEC_GPUS = 2
SPEC_VRAM_GB = 20

# Default file
DEFAULT_FILE = "uploads/f3ae2ac4-6eb9-4565-bcb3-7cd8f9259220_260128_1020 อนุฯ พัฒนาระบบ (บริหารราชการแผ่นดิน) 2.mp3"

cpu_samples: List[float] = []
monitoring = True


def get_gpu_info() -> List[Dict]:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            gpus = []
            for line in r.stdout.strip().split("\n"):
                if line.strip():
                    p = [x.strip() for x in line.split(",")]
                    if len(p) >= 4:
                        gpus.append({
                            "index": int(p[0]) if p[0].isdigit() else 0,
                            "mem_used_mb": int(p[1]) if p[1].isdigit() else 0,
                            "mem_total_mb": int(p[2]) if p[2].isdigit() else 0,
                            "gpu_util": int(p[3]) if p[3].isdigit() else 0,
                        })
            return gpus
    except Exception:
        pass
    return []


def sample_cpu(interval: float = 2.0):
    global cpu_samples, monitoring
    while monitoring:
        try:
            if psutil:
                cpu_samples.append(psutil.cpu_percent(interval=min(1.0, interval)))
        except Exception:
            pass
        time.sleep(interval)


def submit_job(file_path: str) -> Optional[str]:
    url = f"{API_BASE}/api/transcribe/"
    payload = {
        "file_path": file_path,
        "language": "th",
        "model_size": MODEL_SIZE,
        "chunk_duration": 150,
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            return r.json().get("task_id")
        if r.status_code == 429:
            print("❌ Queue เต็ม (429)")
            return None
        print(f"❌ API error {r.status_code}: {r.text[:200]}")
        return None
    except Exception as e:
        print(f"❌ Request error: {e}")
        return None


def get_status(task_id: str) -> Optional[Dict]:
    try:
        r = requests.get(f"{API_BASE}/api/v2/tasks/{task_id}", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def load_phase_timings(task_id: str) -> Optional[Dict]:
    """โหลด phase_timings จาก SQLite"""
    storage_type = os.getenv("STORAGE_TYPE", "sqlite").lower()
    if storage_type == "sqlite":
        from app.utils.sqlite_storage import SQLiteStorage
        st = SQLiteStorage()
    else:
        from app.utils.json_storage import JSONStorage
        st = JSONStorage()
    task = st.load_transcription(task_id)
    return task.get("phase_timings") if task else None


def print_bottleneck_analysis(pt: Dict, total_e2e: float, cpu_avg: float, cpu_max: float):
    """วิเคราะห์ bottleneck และแนะนำ"""
    pre = pt.get("preprocess") or {}
    agg = pt.get("aggregator") or {}

    extract_t = pre.get("extract_time") or 0      # FFmpeg: แปลง/แยกเสียง (MP3→WAV)
    chunk_t = pre.get("chunk_time") or 0           # FFmpeg: แบ่ง chunk
    enqueue_t = pre.get("enqueue_time") or 0
    total_pre = pre.get("total_preprocess_time") or (extract_t + chunk_t + enqueue_t)

    wait_t = agg.get("wait_chunks_time") or 0     # รอ GPU transcribe chunks
    fetch_t = agg.get("fetch_chunks_time") or 0
    merge_t = agg.get("merge_time") or 0
    thai_t = agg.get("thai_processing_time") or 0
    fuzzy_t = agg.get("fuzzy_match_time") or 0

    # Chunk transcribe = รวมเวลาที่ GPU ทำ (ประมาณจาก wait + เวลาจริงของ chunks)
    # wait_chunks = aggregator รอจน chunks ครบ → แปลว่าเป็นเวลาที่ GPU กำลัง transcribe
    gpu_transcribe_t = wait_t  # ประมาณ

    print()
    print("=" * 75)
    print("📊 Phase Breakdown (ช้าที่ไหน)")
    print("=" * 75)
    print()
    print(f"{'Phase':<28} {'Time':>10} {'% of Total':>12}  หมายเหตุ")
    print("-" * 75)

    def row(name: str, sec: float, note: str = ""):
        pct = (sec / total_e2e * 100) if total_e2e > 0 else 0
        print(f"  {name:<26} {sec:>8.1f}s {pct:>10.1f}%  {note}")

    row("1. Extract/Convert", extract_t, "FFmpeg MP3→WAV 16k (CPU)")
    row("2. Chunk", chunk_t, "FFmpeg แบ่งเป็น chunks (CPU)")
    row("3. Enqueue", enqueue_t, "ส่ง chunks ลงคิว")
    row("4. GPU Transcribe", gpu_transcribe_t, "Whisper ทำ chunks (GPU)")
    row("5. Fetch chunks", fetch_t, "ดึงผลจาก Redis")
    row("6. Merge", merge_t, "รวมข้อความ")
    row("7. Thai/Fuzzy", thai_t + fuzzy_t, "Post-process (CPU)")

    print("-" * 75)
    row("Total Preprocess", total_pre, "")
    row("Total End-to-End", total_e2e, "")
    print()
    print("  หมายเหตุ:")
    print("    - Extract/Convert: FFmpeg แปลงไฟล์ (MP3/MP4→WAV 16k) ใช้ CPU เยอะ")
    print("    - Chunk: FFmpeg แบ่งไฟล์เป็นส่วนๆ ใช้ CPU")
    print("    - GPU Transcribe: Whisper แปลงเสียง→ข้อความ ใช้ GPU")
    print()

    # หา bottleneck
    phases = [
        ("Extract/Convert", extract_t, "CPU - FFmpeg decode MP3→WAV"),
        ("Chunk", chunk_t, "CPU - FFmpeg segment"),
        ("GPU Transcribe", gpu_transcribe_t, "GPU - Whisper"),
        ("Merge+Thai", merge_t + thai_t + fuzzy_t, "CPU - รวมข้อความ"),
    ]
    bottleneck = max(phases, key=lambda x: x[1])

    print("=" * 75)
    print("🎯 Bottleneck")
    print("=" * 75)
    print(f"  สูงสุด: {bottleneck[0]} ({bottleneck[1]:.1f}s = {(bottleneck[1]/total_e2e*100) if total_e2e else 0:.1f}%)")
    print(f"  สาเหตุ: {bottleneck[2]}")
    print()

    # แนะนำ
    print("=" * 75)
    print("💡 แนะนำ: ส่วนไหนนำมาใช้ได้อีก")
    print("=" * 75)
    print()

    if bottleneck[0] in ("Extract/Convert", "Chunk"):
        print("  ⚠️  Bottleneck อยู่ที่ CPU (Convert/Chunk):")
        print("     - FFMPEG_EXTRACT_THREADS: ลดจาก 4 → 2 (ลดการแย่ง CPU ระหว่าง job)")
        print("     - NUM_PREPROCESS_WORKERS: ลดจาก 8 → 4 (ถ้า CPU 100%)")
        print("     - ไฟล์ MP3: แปลงเป็น WAV 16k Mono ล่วงหน้าถ้าได้ → ข้าม Extract")
        print()
    if gpu_transcribe_t > total_e2e * 0.5:
        print("  📌 Bottleneck อยู่ที่ GPU Transcribe:")
        print("     - CHUNK_INFLIGHT_LIMIT_PER_JOB: เพิ่ม (ให้ GPU ได้ chunks มากขึ้น)")
        print("     - CHUNK_ENQUEUE_WINDOW_SIZE: เพิ่ม (ส่ง chunks เข้าคิวเร็วขึ้น)")
        print("     - GPU_WORKERS_PER_GPU: ตรวจสอบว่า GPU-Util สูงหรือไม่")
        print()

    if cpu_avg > 80 or (cpu_max and cpu_max > 95):
        print("  ⚠️  CPU ใกล้เต็ม (หรือเต็ม):")
        print("     - ลด NUM_PREPROCESS_WORKERS")
        print("     - ลด FFMPEG_EXTRACT_THREADS")
        print("     - ตรวจว่า Chunk เยอะเกินหรือไม่ (chunk_duration เล็กลง = chunks เยอะขึ้น)")
        print()

    print("  📋 Resource ที่ยังใช้ได้ (Spec: 62GB RAM, 12 vCPU, 2×20GB VRAM):")
    print("     - RAM/VRAM เหลือ → GPU workers เพิ่มได้")
    print("     - CPU เหลือ → Preprocess workers เพิ่มได้ (แต่ระว้งแย่งกัน)")
    print("=" * 75)


def main():
    global monitoring

    file_path = sys.argv[1] if len(sys.argv) >= 2 else DEFAULT_FILE
    # Resolve path
    if not Path(file_path).is_absolute():
        file_path = str(project_root / file_path)

    # ถ้า default ไม่มี ลองหา mp3/wav ใน uploads
    if not Path(file_path).exists():
        uploads = project_root / "uploads"
        if uploads.exists():
            for f in list(uploads.glob("*.mp3")) + list(uploads.glob("*.wav")) + list(uploads.glob("*.mp4")):
                file_path = str(f)
                print(f"   (ใช้ไฟล์จาก uploads: {f.name})")
                break

    if not Path(file_path).exists():
        print(f"❌ ไม่พบไฟล์: {file_path}")
        print("   ใส่ไฟล์ใน uploads/ หรือส่ง path เป็น argument")
        sys.exit(1)

    print("=" * 75)
    print("🔍 Diagnose Bottleneck - วิเคราะห์ว่าช้าที่ไหน")
    print("=" * 75)
    print()
    print(f"File: {os.path.basename(file_path)}")
    print(f"Spec: {SPEC_RAM_GB} GB RAM | {SPEC_VCPU} vCPU | {SPEC_GPUS}×{SPEC_VRAM_GB}GB VRAM")
    print()

    # เริ่ม CPU monitor
    if psutil:
        t = threading.Thread(target=sample_cpu, args=(2.0,), daemon=True)
        t.start()
        time.sleep(0.5)

    # Submit
    print("📤 Submitting job...")
    task_id = submit_job(file_path)
    if not task_id:
        monitoring = False
        sys.exit(1)
    print(f"   Task ID: {task_id[:16]}...")
    print()

    # Monitor
    print("📊 Monitoring... (รอจนเสร็จ)")
    start = time.time()
    while time.time() - start < 7200:  # 2 hr max
        data = get_status(task_id)
        if data:
            st = data.get("status", "")
            prog = data.get("progress", 0)
            if st == "completed":
                elapsed = time.time() - start
                print(f"   ✅ Completed ใน {elapsed:.1f}s ({elapsed/60:.2f} min)")
                break
            elif st in ("failed", "cancelled"):
                print(f"   ❌ {st}: {data.get('error_message', '')}")
                monitoring = False
                sys.exit(1)
            if int(time.time()) % 30 < 3 and prog > 0:
                print(f"   ... {st} ({prog}%)")
        time.sleep(3)

    monitoring = False
    time.sleep(2)

    # โหลด phase_timings
    pt = load_phase_timings(task_id)
    if not pt:
        print("❌ โหลด phase_timings ไม่ได้ (task อาจยังไม่บันทึก)")
        sys.exit(1)

    total_e2e = None
    agg = pt.get("aggregator") or {}
    if "total_end_to_end_time" in agg:
        total_e2e = float(agg["total_end_to_end_time"])
    if total_e2e is None and agg.get("t_aggregator_start") and agg.get("t_aggregator_end"):
        # ประมาณจาก preprocess
        pre = pt.get("preprocess") or {}
        total_pre = pre.get("total_preprocess_time") or 0
        total_agg = agg.get("total_aggregator_time") or 0
        total_e2e = total_pre + total_agg

    if total_e2e is None:
        total_e2e = time.time() - start

    cpu_avg = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
    cpu_max = max(cpu_samples) if cpu_samples else 0

    # พิมพ์วิเคราะห์
    print_bottleneck_analysis(pt, total_e2e, cpu_avg, cpu_max)

    # GPU สรุป
    gpus = get_gpu_info()
    if gpus:
        print()
        print("📊 GPU (หลังจบ):")
        for g in gpus:
            used_gb = g["mem_used_mb"] / 1024
            total_gb = g["mem_total_mb"] / 1024
            free = total_gb - used_gb
            print(f"   GPU {g['index']}: {used_gb:.1f}/{total_gb:.1f} GB ใช้ | เหลือ ~{free:.1f} GB")
    if psutil:
        mem = psutil.virtual_memory()
        used_gb = mem.used / (1024**3)
        print(f"   RAM: {used_gb:.1f}/{SPEC_RAM_GB} GB ใช้ | เหลือ ~{max(0, SPEC_RAM_GB - used_gb):.1f} GB")
    print()


if __name__ == "__main__":
    main()
