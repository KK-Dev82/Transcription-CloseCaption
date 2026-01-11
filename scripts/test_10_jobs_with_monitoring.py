#!/usr/bin/env python3
"""
Script สำหรับทดสอบ 10 Transcription Jobs พร้อม Monitor CPU และ RAM
"""

import requests
import time
import json
from datetime import datetime, timezone
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import threading

API_BASE = "http://localhost:8010/api"

# Global variables สำหรับ monitoring
max_cpu = 0
max_mem_gb = 0
max_mem_percent = 0
monitoring = True

def monitor_resources(interval=5):
    """Monitor CPU และ RAM usage"""
    global max_cpu, max_mem_gb, max_mem_percent, monitoring
    
    while monitoring:
        cpu_percent = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        mem_gb = mem.used / (1024**3)
        mem_percent = mem.percent
        
        max_cpu = max(max_cpu, cpu_percent)
        max_mem_gb = max(max_mem_gb, mem_gb)
        max_mem_percent = max(max_mem_percent, mem_percent)
        
        time.sleep(interval)

def submit_job(file_path: str, model_size: str, job_index: int) -> Dict:
    """Submit transcription job"""
    payload = {
        "file_path": file_path,
        "language": "th",
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
        task_id = result.get("task_id")
        
        print(f"✅ Job #{job_index+1} submitted: {task_id[:8]}...")
        return {
            "job_index": job_index + 1,
            "task_id": task_id,
            "submitted_at": time.time(),
            "status": "submitted"
        }
    except Exception as e:
        print(f"❌ Job #{job_index+1} submission failed: {e}")
        return {
            "job_index": job_index + 1,
            "task_id": None,
            "error": str(e),
            "status": "failed"
        }

def check_job_status(task_id: str) -> Dict:
    """Check transcription job status"""
    try:
        response = requests.get(
            f"{API_BASE}/v2/tasks/{task_id}",
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        return None

def monitor_job(task_info: Dict, model_size: str) -> Dict:
    """Monitor single job until completion"""
    task_id = task_info["task_id"]
    job_index = task_info["job_index"]
    
    if not task_id:
        return {**task_info, "status": "failed", "error": "No task_id"}
    
    start_time = time.time()
    check_count = 0
    
    while True:
        check_count += 1
        task_data = check_job_status(task_id)
        
        if not task_data:
            time.sleep(2)
            continue
        
        status = task_data.get("status", "unknown")
        progress = task_data.get("progress", 0)
        
        if check_count % 10 == 0 or status in ["completed", "failed"]:
            elapsed = time.time() - start_time
            print(f"  Job #{job_index}: {status.upper()} ({progress}%) - {int(elapsed)}s")
        
        if status == "completed":
            completed_at = task_data.get("completed_at")
            created_at = task_data.get("created_at")
            
            total_time = None
            if completed_at and created_at:
                try:
                    created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    completed = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                    total_time = (completed - created).total_seconds()
                except:
                    pass
            
            elapsed_time = time.time() - start_time
            actual_time = total_time if total_time else elapsed_time
            
            print(f"✅ Job #{job_index} completed in {int(actual_time)}s")
            
            return {
                **task_info,
                "status": "completed",
                "total_time": actual_time,
                "progress": 100,
                "completed_at": completed_at
            }
        
        elif status == "failed":
            error = task_data.get("error_message", "Unknown error")
            elapsed_time = time.time() - start_time
            print(f"❌ Job #{job_index} failed after {int(elapsed_time)}s: {error}")
            
            return {
                **task_info,
                "status": "failed",
                "error": error,
                "total_time": elapsed_time
            }
        
        time.sleep(2)

def main():
    global monitoring, max_cpu, max_mem_gb, max_mem_percent
    
    # ใช้ไฟล์ตัวอย่าง
    file_path = "/workspace/transcription-service/uploads/160c549e-f820-4b2b-9720-4ecb2f500ed4_v30-1.wav"
    
    import os
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    
    model_size = "Vinxscribe/biodatlab-whisper-th-medium-faster"
    num_jobs = 10
    
    print("=" * 85)
    print(f"🚀 Starting {num_jobs} Transcription Jobs with Resource Monitoring")
    print("=" * 85)
    print(f"Model: {model_size}")
    print(f"File: {os.path.basename(file_path)}")
    print(f"API: {API_BASE}")
    print("")
    
    # Baseline measurement
    print("📊 Baseline Resources:")
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    print(f"  CPU: {cpu_percent:.1f}%")
    print(f"  Memory: {mem.used / (1024**3):.1f} GB / {mem.total / (1024**3):.1f} GB ({mem.percent:.1f}%)")
    print("")
    
    # Start monitoring thread
    monitor_thread = threading.Thread(target=monitor_resources, args=(5,), daemon=True)
    monitor_thread.start()
    
    # Phase 1: Submit all jobs
    print("📤 Phase 1: Submitting jobs...")
    print("")
    overall_start_time = time.time()
    
    jobs = []
    for i in range(num_jobs):
        job_info = submit_job(file_path, model_size, i)
        jobs.append(job_info)
        time.sleep(0.5)
    
    print("")
    print(f"✅ All {num_jobs} jobs submitted")
    print("")
    
    # Phase 2: Monitor all jobs
    print("📊 Phase 2: Monitoring jobs...")
    print("")
    
    results = []
    with ThreadPoolExecutor(max_workers=num_jobs) as executor:
        futures = {executor.submit(monitor_job, job, model_size): job for job in jobs if job.get("task_id")}
        
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"❌ Error monitoring job: {e}")
    
    # Stop monitoring
    monitoring = False
    time.sleep(2)  # Wait for monitoring thread to finish
    
    overall_end_time = time.time()
    total_time = overall_end_time - overall_start_time
    
    # Sort results by job_index
    results.sort(key=lambda x: x.get("job_index", 0))
    
    # Phase 3: Show results
    print("")
    print("=" * 85)
    print("📊 RESULTS")
    print("=" * 85)
    print("")
    
    completed_jobs = [r for r in results if r.get("status") == "completed"]
    failed_jobs = [r for r in results if r.get("status") == "failed"]
    
    print(f"✅ Completed: {len(completed_jobs)}/{num_jobs}")
    if failed_jobs:
        print(f"❌ Failed: {len(failed_jobs)}/{num_jobs}")
    print("")
    
    if completed_jobs:
        times = [r["total_time"] for r in completed_jobs]
        
        print("⏱️  Time Statistics:")
        print(f"  Total time (all jobs): {int(total_time)}s ({total_time/60:.2f} minutes)")
        print(f"  Min time: {min(times):.1f}s ({min(times)/60:.2f} minutes)")
        print(f"  Max time: {max(times):.1f}s ({max(times)/60:.2f} minutes)")
        print(f"  Avg time: {sum(times)/len(times):.1f}s ({sum(times)/len(times)/60:.2f} minutes)")
        print("")
        
        print("📋 Individual Job Times:")
        for result in completed_jobs:
            job_idx = result.get("job_index", "?")
            job_time = result.get("total_time", 0)
            task_id = result.get("task_id", "unknown")[:8]
            print(f"  Job #{job_idx:2d}: {job_time:.1f}s ({task_id}...)")
    
    # Resource usage summary
    print("")
    print("=" * 85)
    print("📊 Resource Usage Summary")
    print("=" * 85)
    
    cpu_limit = 600  # 6 cores * 100%
    mem_limit = 31  # GB
    
    print(f"Max CPU Usage: {max_cpu:.1f}% (Limit: {cpu_limit}%)")
    print(f"Max Memory Usage: {max_mem_gb:.1f} GB (Limit: {mem_limit} GB)")
    print("")
    
    cpu_ok = max_cpu <= cpu_limit
    mem_ok = max_mem_gb <= mem_limit
    
    if cpu_ok:
        print(f"✅ CPU: {max_cpu:.1f}% <= {cpu_limit}% (OK)")
    else:
        print(f"❌ CPU: {max_cpu:.1f}% > {cpu_limit}% (EXCEEDED!)")
    
    if mem_ok:
        print(f"✅ Memory: {max_mem_gb:.1f} GB <= {mem_limit} GB (OK)")
    else:
        print(f"❌ Memory: {max_mem_gb:.1f} GB > {mem_limit} GB (EXCEEDED!)")
    
    print("")
    print("=" * 85)
    
    # Final check
    if total_time < 600:
        print("✅ Test completed! Total time < 10 minutes")
    else:
        print(f"⚠️  Test completed but total time ({int(total_time/60):.1f} min) >= 10 minutes")
    
    print("=" * 85)

if __name__ == "__main__":
    main()
