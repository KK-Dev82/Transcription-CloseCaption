#!/usr/bin/env python3
"""
ทดสอบ 25 tasks โดยใช้ไฟล์ที่มีอยู่ในเครื่อง (ไม่ผ่านการอัปโหลด)
- ใช้ file_path ตรงไปยังไฟล์ใน uploads/
- ส่งไปที่ /api/transcribe/ หรือ /api/transcribe-enhanced/start
"""

import os
import sys
import time
import requests
from pathlib import Path
from typing import List, Dict, Optional

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8010")
MODEL_SIZE = os.getenv("TEST_MODEL_SIZE", "Vinxscribe/biodatlab-whisper-th-medium-faster")
UPLOADS_DIR = project_root / "uploads"
NUM_TASKS = 25


def get_local_files(limit: int = NUM_TASKS) -> List[Path]:
    """ดึงไฟล์ audio/video จาก uploads/ (มีอยู่ในเครื่อง)"""
    if not UPLOADS_DIR.exists():
        raise FileNotFoundError(f"ไม่พบโฟลเดอร์ uploads: {UPLOADS_DIR}")
    
    exts = (".wav", ".mp3", ".mp4")
    files = []
    for ext in exts:
        files.extend(UPLOADS_DIR.glob(f"*{ext}"))
    
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    
    # ถ้ามีน้อยกว่า limit ให้วนใช้ไฟล์ซ้ำ
    result = []
    for i in range(limit):
        result.append(files[i % len(files)] if files else None)
    
    return [f for f in result if f is not None]


def submit_job(file_path: Path, job_index: int) -> Dict:
    """Submit transcription job ผ่าน API (ใช้ file_path โดยตรง)"""
    abs_path = str(file_path.resolve())
    url = f"{API_BASE_URL}/api/transcribe-enhanced/start"
    payload = {
        "file_path": abs_path,
        "language": "th",
        "model_size": MODEL_SIZE,
        "chunk_duration": 150,
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 429:
            return {
                "job_index": job_index,
                "status": "queue_full",
                "status_code": 429,
                "error": response.json().get("detail", "Queue Full"),
                "task_id": None,
                "file": file_path.name,
            }
        elif response.status_code in (200, 201):
            data = response.json()
            return {
                "job_index": job_index,
                "status": "queued",
                "status_code": response.status_code,
                "task_id": data.get("task_id"),
                "file": file_path.name,
            }
        else:
            return {
                "job_index": job_index,
                "status": "error",
                "status_code": response.status_code,
                "error": response.text[:200],
                "task_id": None,
                "file": file_path.name,
            }
    except Exception as e:
        return {
            "job_index": job_index,
            "status": "exception",
            "status_code": None,
            "error": str(e),
            "task_id": None,
            "file": file_path.name,
        }


def main():
    print("=" * 70)
    print("🧪 ทดสอบ 25 tasks (ใช้ไฟล์ local - ไม่ผ่านการอัปโหลด)")
    print("=" * 70)
    print()
    
    # 1. ดึงไฟล์จาก uploads
    files = get_local_files(NUM_TASKS)
    if not files:
        print(f"❌ ไม่พบไฟล์ใน {UPLOADS_DIR}")
        print("   ใส่ไฟล์ .wav, .mp3 หรือ .mp4 ลงใน uploads/ ก่อน")
        sys.exit(1)
    
    unique_count = len(set(str(f) for f in files))
    print(f"📁 ใช้ไฟล์จาก: {UPLOADS_DIR}")
    print(f"   จำนวน tasks: {NUM_TASKS}")
    print(f"   ไฟล์ไม่ซ้ำ: {unique_count} ไฟล์")
    if unique_count < NUM_TASKS:
        print(f"   (วนใช้ไฟล์ซ้ำเพื่อครบ {NUM_TASKS} tasks)")
    print()
    
    print(f"📌 API: {API_BASE_URL}/api/transcribe-enhanced/start")
    print(f"📌 Model: {MODEL_SIZE}")
    print()
    
    # 2. Submit tasks
    print("-" * 70)
    print("Step 1: Submit 25 tasks")
    print("-" * 70)
    
    submit_start = time.time()
    results = []
    
    for i in range(NUM_TASKS):
        file_path = files[i]
        r = submit_job(file_path, i + 1)
        results.append(r)
        
        status_icon = "✅" if r["status"] == "queued" else "⚠️" if r["status"] == "queue_full" else "❌"
        task_short = (r["task_id"] or "N/A")[:8] + "..." if r.get("task_id") else "N/A"
        print(f"  {i+1:2d}/25 {status_icon} {r['file'][:45]:<45} → {r['status']} {task_short}")
    
    submit_elapsed = time.time() - submit_start
    print()
    print(f"⏱️  Submit เสร็จใน {submit_elapsed:.2f}s")
    print()
    
    # 3. สรุป
    queued = [r for r in results if r["status"] == "queued"]
    queue_full = [r for r in results if r["status"] == "queue_full"]
    errors = [r for r in results if r["status"] not in ("queued", "queue_full")]
    
    print("=" * 70)
    print("สรุปผล")
    print("=" * 70)
    print(f"  Queued:     {len(queued)} tasks")
    print(f"  Queue Full: {len(queue_full)} tasks")
    print(f"  Errors:     {len(errors)} tasks")
    print()
    
    if queued:
        task_ids = [r["task_id"] for r in queued]
        print("Task IDs ที่ submit สำเร็จ:")
        for i, tid in enumerate(task_ids[:10]):
            print(f"  {i+1}. {tid}")
        if len(task_ids) > 10:
            print(f"  ... และอีก {len(task_ids)-10} tasks")
        print()
        print("ตรวจสอบสถานะ:")
        print(f"  curl {API_BASE_URL}/api/v2/tasks/<task_id>")
        print()
    
    if errors:
        print("Errors:")
        for r in errors[:5]:
            print(f"  Job {r['job_index']}: {r.get('error', r['status'])}")
    
    print()
    print("✅ เสร็จสิ้น")


if __name__ == "__main__":
    main()
