#!/usr/bin/env python3
"""
Test Script: ทดสอบ Queue Limit (25 jobs) และวัดระยะเวลา
- Submit 26 jobs เพื่อทดสอบ Queue Limit
- Job ที่ 26 ควรได้ HTTP 429 (Queue Full)
- Monitor 25 jobs จนเสร็จ
- วัด Total Time, Min, Max, Avg
"""

import os
import sys
import time
import requests
import json
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8010")
MODEL_SIZE = "Vinxscribe/biodatlab-whisper-th-medium-faster"
# Use the same test file as other test scripts
TEST_FILE = "/workspace/transcription-service/uploads/160c549e-f820-4b2b-9720-4ecb2f500ed4_v30-1.wav"

def submit_job(job_index: int) -> Dict:
    """Submit a transcription job"""
    url = f"{API_BASE_URL}/api/transcribe/"
    payload = {
        "file_path": TEST_FILE,
        "language": "th",
        "model_size": MODEL_SIZE,
        "chunk_duration": 150
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 429:
            # Queue Full
            return {
                "job_index": job_index,
                "status": "queue_full",
                "status_code": 429,
                "error": response.json().get("detail", "Queue Full"),
                "task_id": None
            }
        elif response.status_code == 200:
            # Success
            data = response.json()
            return {
                "job_index": job_index,
                "status": "queued",
                "status_code": 200,
                "task_id": data.get("task_id"),
                "message": data.get("message", "")
            }
        else:
            # Error
            return {
                "job_index": job_index,
                "status": "error",
                "status_code": response.status_code,
                "error": response.text,
                "task_id": None
            }
    except Exception as e:
        return {
            "job_index": job_index,
            "status": "exception",
            "status_code": None,
            "error": str(e),
            "task_id": None
        }

def get_task_status(task_id: str) -> Dict:
    """Get task status"""
    url = f"{API_BASE_URL}/api/v2/tasks/{task_id}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "error", "status_code": response.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def wait_for_completion(task_id: str, timeout: int = 3600) -> Dict:
    """Wait for task to complete"""
    start_time = time.time()
    last_status = None
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            return {
                "task_id": task_id,
                "status": "timeout",
                "elapsed_time": elapsed
            }
        
        task_data = get_task_status(task_id)
        status = task_data.get("status", "unknown")
        progress = task_data.get("progress", 0)
        
        if status != last_status or progress % 10 == 0:
            print(f"  Task {task_id[:8]}...: {status} ({progress}%) - {elapsed:.1f}s")
            last_status = status
        
        if status == "completed":
            elapsed_time = time.time() - start_time
            return {
                "task_id": task_id,
                "status": "completed",
                "elapsed_time": elapsed_time,
                "progress": progress
            }
        elif status in ["failed", "cancelled"]:
            elapsed_time = time.time() - start_time
            return {
                "task_id": task_id,
                "status": status,
                "elapsed_time": elapsed_time,
                "error": task_data.get("error", "")
            }
        
        time.sleep(2)

def main():
    print("=" * 85)
    print("🧪 Test: Queue Limit (25 jobs) และวัดระยะเวลา")
    print("=" * 85)
    print()
    print(f"Configuration:")
    print(f"  API: {API_BASE_URL}")
    print(f"  Model: {MODEL_SIZE}")
    print(f"  Test File: {TEST_FILE}")
    print(f"  NUM_GPUS: {os.getenv('NUM_GPUS', '1')}")
    print(f"  GPU_WORKERS_PER_GPU: {os.getenv('GPU_WORKERS_PER_GPU', '8')}")
    print(f"  NUM_PREPROCESS_WORKERS: {os.getenv('NUM_PREPROCESS_WORKERS', '6')}")
    print(f"  NUM_CPU_WORKERS: {os.getenv('NUM_CPU_WORKERS', '4')}")
    print(f"  MAX_PREPROCESS_QUEUE_SIZE: {os.getenv('MAX_PREPROCESS_QUEUE_SIZE', '25')}")
    print()
    
    # Step 1: Submit 26 jobs
    print("=" * 85)
    print("Step 1: Submit 26 jobs")
    print("=" * 85)
    print()
    
    submit_start_time = time.time()
    submission_results = []
    
    for i in range(1, 27):
        print(f"Submitting job {i}/26...", end=" ", flush=True)
        result = submit_job(i)
        submission_results.append(result)
        
        if result["status"] == "queue_full":
            print(f"✅ Queue Full (HTTP 429): {result.get('error', 'Queue Full')}")
        elif result["status"] == "queued":
            print(f"✅ Queued (task_id: {result['task_id'][:8]}...)")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    submit_elapsed = time.time() - submit_start_time
    print()
    print(f"Submission completed in {submit_elapsed:.2f}s")
    print()
    
    # Analyze submission results
    queued_jobs = [r for r in submission_results if r["status"] == "queued"]
    queue_full_jobs = [r for r in submission_results if r["status"] == "queue_full"]
    error_jobs = [r for r in submission_results if r["status"] not in ["queued", "queue_full"]]
    
    print("=" * 85)
    print("Submission Results:")
    print("=" * 85)
    print(f"  Queued: {len(queued_jobs)} jobs")
    print(f"  Queue Full (HTTP 429): {len(queue_full_jobs)} jobs")
    print(f"  Errors: {len(error_jobs)} jobs")
    print()
    
    if len(queue_full_jobs) > 0:
        print(f"✅ Queue Limit Working: Job {queue_full_jobs[0]['job_index']} got HTTP 429")
    else:
        print(f"⚠️  Queue Limit Not Working: No jobs got HTTP 429")
    
    if len(queued_jobs) != 25:
        print(f"⚠️  Expected 25 queued jobs, but got {len(queued_jobs)}")
    
    print()
    
    # Step 2: Monitor 25 jobs until completion
    if len(queued_jobs) == 0:
        print("❌ No jobs to monitor. Exiting.")
        return
    
    print("=" * 85)
    print(f"Step 2: Monitor {len(queued_jobs)} jobs until completion")
    print("=" * 85)
    print()
    
    monitor_start_time = time.time()
    completion_results = []
    
    # Use ThreadPoolExecutor to monitor jobs in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(wait_for_completion, job["task_id"]): job["job_index"]
            for job in queued_jobs
        }
        
        for future in as_completed(futures):
            job_index = futures[future]
            try:
                result = future.result()
                completion_results.append(result)
                print(f"✅ Job {job_index} completed: {result['status']} ({result.get('elapsed_time', 0):.1f}s)")
            except Exception as e:
                print(f"❌ Job {job_index} error: {e}")
    
    monitor_elapsed = time.time() - monitor_start_time
    
    print()
    print("=" * 85)
    print("Completion Results:")
    print("=" * 85)
    
    completed_jobs = [r for r in completion_results if r["status"] == "completed"]
    failed_jobs = [r for r in completion_results if r["status"] == "failed"]
    
    print(f"  Completed: {len(completed_jobs)} jobs")
    print(f"  Failed: {len(failed_jobs)} jobs")
    print()
    
    if len(completed_jobs) > 0:
        elapsed_times = [r["elapsed_time"] for r in completed_jobs]
        total_time = monitor_elapsed
        min_time = min(elapsed_times)
        max_time = max(elapsed_times)
        avg_time = sum(elapsed_times) / len(elapsed_times)
        
        print("=" * 85)
        print("📊 Performance Metrics:")
        print("=" * 85)
        print()
        print(f"{'Metric':<40} {'Value':<25}")
        print("-" * 65)
        print(f"{'Total time (all jobs)':<40} {total_time:.1f}s ({total_time/60:.2f} min)")
        print(f"{'Min time (single job)':<40} {min_time:.1f}s ({min_time/60:.2f} min)")
        print(f"{'Max time (single job)':<40} {max_time:.1f}s ({max_time/60:.2f} min)")
        print(f"{'Avg time (single job)':<40} {avg_time:.1f}s ({avg_time/60:.2f} min)")
        print()
        print(f"Throughput: {len(completed_jobs) / (total_time / 60):.2f} jobs/min")
        print()
        print("=" * 85)
    
    print()
    print("✅ Test completed!")

if __name__ == "__main__":
    main()
