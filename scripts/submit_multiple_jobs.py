#!/usr/bin/env python3
"""
Submit multiple transcription jobs
"""
import requests
import json
import time
import sys

API_BASE = "http://localhost:8010/api"

def submit_job(file_path, language="th", model_size="Systran/faster-whisper-small"):
    """Submit a transcription job"""
    payload = {
        "file_path": file_path,
        "language": language,
        "model_size": model_size
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/transcribe/",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        return result.get("task_id"), result
    except Exception as e:
        print(f"❌ Error submitting job: {e}")
        return None, None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/submit_multiple_jobs.py <file_path> [num_jobs]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    num_jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    print("=" * 85)
    print(f"=== ส่ง {num_jobs} Transcription Jobs ===")
    print("=" * 85)
    print(f"File: {file_path}")
    print("")
    
    task_ids = []
    
    for i in range(num_jobs):
        print(f"📤 Sending job {i+1}/{num_jobs}...", end=" ", flush=True)
        task_id, result = submit_job(file_path)
        
        if task_id:
            task_ids.append(task_id)
            print(f"✅ Task ID: {task_id[:36]}...")
        else:
            print("❌ Failed")
        
        # รอสักครู่ก่อนส่ง job ถัดไป
        if i < num_jobs - 1:
            time.sleep(1)
    
    print("")
    print("=" * 85)
    print("=== ✅ Jobs Submitted ===")
    print("=" * 85)
    print(f"Total: {len(task_ids)} jobs")
    print("")
    print("Task IDs:")
    for i, task_id in enumerate(task_ids, 1):
        print(f"  {i}. {task_id}")
    print("")
    print("=" * 85)
    print("")
    print("💡 ใช้คำสั่งนี้เพื่อติดตาม:")
    print(f"   python3 scripts/monitor_jobs.py {' '.join(task_ids)}")
    print("=" * 85)
    
    # บันทึก task_ids ลงไฟล์
    with open("/tmp/latest_task_ids.txt", "w") as f:
        f.write("\n".join(task_ids))
    
    return task_ids

if __name__ == "__main__":
    main()

