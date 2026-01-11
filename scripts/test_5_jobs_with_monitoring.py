#!/usr/bin/env python3
"""
Test Script: ทดสอบ 5 Jobs พร้อมติดตาม GPU, SQLite, Redis
- Submit 5 jobs
- Monitor GPU usage
- Monitor SQLite updates
- Monitor Redis updates
- Track resource usage
"""

import os
import sys
import time
import requests
import json
import sqlite3
import redis
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8010")
MODEL_SIZE = "Vinxscribe/biodatlab-whisper-th-medium-faster"
TEST_FILE = "/workspace/transcription-service/uploads/160c549e-f820-4b2b-9720-4ecb2f500ed4_v30-1.wav"

# Load environment
env_file = "config/.env.runpod"
if not os.path.exists(env_file):
    env_file = ".env.runpod"

if os.path.exists(env_file):
    from dotenv import load_dotenv
    load_dotenv(env_file)

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
DB_PATH = Path("storage/database.db")

def get_gpu_info():
    """Get GPU usage info"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,utilization.gpu,utilization.memory,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            gpus = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 5:
                        gpus.append({
                            'index': parts[0],
                            'gpu_util': parts[1],
                            'mem_util': parts[2],
                            'mem_used_mb': parts[3],
                            'mem_total_mb': parts[4]
                        })
            return gpus
    except:
        pass
    return []

def check_sqlite_task(task_id: str) -> Dict:
    """Check task in SQLite"""
    if not DB_PATH.exists():
        return {"error": "Database not found"}
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT status, progress, full_text, current_stage, error_message,
                   created_at, updated_at, completed_at,
                   (SELECT COUNT(*) FROM segments WHERE segments.task_id = transcriptions.task_id) as segments_count
            FROM transcriptions
            WHERE task_id = ?
        """, (task_id,))
        task = cursor.fetchone()
        
        if task:
            return {
                "status": task['status'],
                "progress": task['progress'],
                "has_full_text": bool(task['full_text']),
                "full_text_length": len(task['full_text']) if task['full_text'] else 0,
                "segments_count": task['segments_count'],
                "stage": task['current_stage'],
                "error": task['error_message'],
                "created_at": task['created_at'],
                "updated_at": task['updated_at'],
                "completed_at": task['completed_at']
            }
        else:
            return {"error": "Task not found"}
    finally:
        conn.close()

def check_redis_task(task_id: str) -> Dict:
    """Check task in Redis"""
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        total_key = f"task:{task_id}:total_chunks"
        done_key = f"task:{task_id}:done_chunks"
        total_chunks = r.get(total_key)
        done_chunks = r.get(done_key)
        
        # Check chunk results
        chunk_results = []
        for i in range(20):
            chunk_key = f"task:{task_id}:chunk:{i}"
            if r.exists(chunk_key):
                chunk_results.append(i)
        
        return {
            "total_chunks": int(total_chunks) if total_chunks else None,
            "done_chunks": int(done_chunks) if done_chunks else None,
            "chunk_results_count": len(chunk_results),
            "chunk_results": chunk_results[:10]  # First 10
        }
    except Exception as e:
        return {"error": str(e)}

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
            return {
                "job_index": job_index,
                "status": "queue_full",
                "status_code": 429,
                "error": response.json().get("detail", "Queue Full"),
                "task_id": None
            }
        elif response.status_code == 200:
            data = response.json()
            return {
                "job_index": job_index,
                "status": "queued",
                "status_code": 200,
                "task_id": data.get("task_id"),
                "message": data.get("message", "")
            }
        else:
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
    """Get task status from API"""
    url = f"{API_BASE_URL}/api/v2/tasks/{task_id}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "error", "status_code": response.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def monitor_task_with_details(task_id: str, job_index: int, check_interval: int = 10) -> Dict:
    """Monitor task with detailed SQLite and Redis checks"""
    start_time = time.time()
    last_status = None
    last_progress = 0
    check_count = 0
    gpu_usage_samples = []
    sqlite_updates = []
    redis_updates = []
    
    print(f"\n📊 Monitoring Job {job_index} (Task: {task_id[:8]}...)")
    print("-" * 85)
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > 3600:  # 1 hour timeout
            return {
                "task_id": task_id,
                "status": "timeout",
                "elapsed_time": elapsed
            }
        
        # Check API status
        task_data = get_task_status(task_id)
        status = task_data.get("status", "unknown")
        progress = task_data.get("progress", 0)
        
        # Check SQLite (every check_interval seconds)
        if check_count % (check_interval // 2) == 0:
            sqlite_data = check_sqlite_task(task_id)
            if "error" not in sqlite_data:
                sqlite_updates.append({
                    "timestamp": time.time(),
                    "status": sqlite_data.get("status"),
                    "progress": sqlite_data.get("progress"),
                    "has_full_text": sqlite_data.get("has_full_text"),
                    "segments_count": sqlite_data.get("segments_count")
                })
        
        # Check Redis (every check_interval seconds)
        if check_count % (check_interval // 2) == 0:
            redis_data = check_redis_task(task_id)
            if "error" not in redis_data:
                redis_updates.append({
                    "timestamp": time.time(),
                    "total_chunks": redis_data.get("total_chunks"),
                    "done_chunks": redis_data.get("done_chunks"),
                    "chunk_results_count": redis_data.get("chunk_results_count")
                })
        
        # Check GPU (every 10 seconds)
        if check_count % 2 == 0:
            gpus = get_gpu_info()
            if gpus:
                for gpu in gpus:
                    gpu_usage_samples.append({
                        "timestamp": time.time(),
                        "gpu_index": gpu['index'],
                        "gpu_util": gpu['gpu_util'],
                        "mem_util": gpu['mem_util'],
                        "mem_used_mb": gpu['mem_used_mb']
                    })
        
        # Print status updates
        if status != last_status or progress != last_progress:
            if progress % 10 == 0 or status != last_status:
                sqlite_info = ""
                redis_info = ""
                gpu_info = ""
                
                if sqlite_updates:
                    latest_sqlite = sqlite_updates[-1]
                    sqlite_info = f" | SQLite: {latest_sqlite['status']} ({latest_sqlite['progress']}%)"
                    if latest_sqlite.get('has_full_text'):
                        sqlite_info += f" | Text: {latest_sqlite.get('full_text_length', 0)} chars"
                    if latest_sqlite.get('segments_count', 0) > 0:
                        sqlite_info += f" | Segments: {latest_sqlite['segments_count']}"
                
                if redis_updates:
                    latest_redis = redis_updates[-1]
                    if latest_redis.get('total_chunks'):
                        redis_info = f" | Redis: {latest_redis['done_chunks']}/{latest_redis['total_chunks']} chunks"
                
                if gpu_usage_samples:
                    latest_gpu = gpu_usage_samples[-1]
                    gpu_info = f" | GPU{latest_gpu['gpu_index']}: {latest_gpu['gpu_util']}% ({latest_gpu['mem_used_mb']}MB)"
                
                print(f"  [{elapsed:.0f}s] {status} ({progress}%){sqlite_info}{redis_info}{gpu_info}")
                last_status = status
                last_progress = progress
        
        if status == "completed":
            elapsed_time = time.time() - start_time
            
            # Final checks
            final_sqlite = check_sqlite_task(task_id)
            final_redis = check_redis_task(task_id)
            
            return {
                "task_id": task_id,
                "status": "completed",
                "elapsed_time": elapsed_time,
                "progress": progress,
                "sqlite_final": final_sqlite,
                "redis_final": final_redis,
                "gpu_samples": len(gpu_usage_samples),
                "sqlite_updates": len(sqlite_updates),
                "redis_updates": len(redis_updates)
            }
        elif status in ["failed", "cancelled"]:
            elapsed_time = time.time() - start_time
            return {
                "task_id": task_id,
                "status": status,
                "elapsed_time": elapsed_time,
                "error": task_data.get("error", ""),
                "sqlite_final": check_sqlite_task(task_id),
                "redis_final": check_redis_task(task_id)
            }
        
        time.sleep(2)
        check_count += 1

def main():
    num_jobs = 5
    
    print("=" * 85)
    print(f"🧪 Test: 5 Jobs พร้อมติดตาม GPU, SQLite, Redis")
    print("=" * 85)
    print()
    print(f"Configuration:")
    print(f"  API: {API_BASE_URL}")
    print(f"  Model: {MODEL_SIZE}")
    print(f"  Test File: {TEST_FILE}")
    print(f"  GPU_WORKERS_PER_GPU: {os.getenv('GPU_WORKERS_PER_GPU', '5')}")
    print(f"  NUM_PREPROCESS_WORKERS: {os.getenv('NUM_PREPROCESS_WORKERS', '6')}")
    print(f"  NUM_CPU_WORKERS: {os.getenv('NUM_CPU_WORKERS', '4')}")
    print()
    
    # Check GPU
    gpus = get_gpu_info()
    print(f"GPU Detection: {len(gpus)} GPU(s) found")
    for gpu in gpus:
        print(f"  GPU {gpu['index']}: {gpu['mem_total_mb']}MB total")
    print()
    
    if not os.path.exists(TEST_FILE):
        print(f"❌ Error: Test file not found at {TEST_FILE}")
        sys.exit(1)
    
    # Step 1: Submit jobs
    print("=" * 85)
    print("Step 1: Submit 5 jobs")
    print("=" * 85)
    print()
    
    submitted_jobs = []
    for i in range(1, num_jobs + 1):
        print(f"Submitting job {i}/{num_jobs}...", end=" ", flush=True)
        result = submit_job(i)
        submitted_jobs.append(result)
        
        if result["status"] == "queue_full":
            print(f"✅ Queue Full (HTTP 429)")
        elif result["status"] == "queued":
            print(f"✅ Queued (task_id: {result['task_id'][:8]}...)")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    queued_jobs = [r for r in submitted_jobs if r["status"] == "queued"]
    print()
    print(f"Queued: {len(queued_jobs)} jobs")
    print()
    
    if len(queued_jobs) == 0:
        print("❌ No jobs to monitor. Exiting.")
        return
    
    # Step 2: Monitor with detailed tracking
    print("=" * 85)
    print(f"Step 2: Monitor {len(queued_jobs)} jobs (with GPU, SQLite, Redis tracking)")
    print("=" * 85)
    print()
    
    completion_results = []
    
    with ThreadPoolExecutor(max_workers=len(queued_jobs)) as executor:
        futures = {
            executor.submit(monitor_task_with_details, job["task_id"], job["job_index"]): job["job_index"]
            for job in queued_jobs
        }
        
        for future in as_completed(futures):
            job_index = futures[future]
            try:
                result = future.result()
                completion_results.append(result)
            except Exception as e:
                print(f"❌ Job {job_index} error: {e}")
    
    # Step 3: Summary
    print()
    print("=" * 85)
    print("📊 Final Results Summary")
    print("=" * 85)
    print()
    
    completed_jobs = [r for r in completion_results if r["status"] == "completed"]
    failed_jobs = [r for r in completion_results if r["status"] == "failed"]
    
    print(f"Completed: {len(completed_jobs)} jobs")
    print(f"Failed: {len(failed_jobs)} jobs")
    print()
    
    if completed_jobs:
        print("✅ Completed Jobs Details:")
        for job in completed_jobs:
            print(f"\n  Task: {job['task_id'][:12]}...")
            print(f"    Time: {job['elapsed_time']:.1f}s")
            
            sqlite = job.get('sqlite_final', {})
            if "error" not in sqlite:
                print(f"    SQLite: {sqlite.get('status')} | Text: {sqlite.get('full_text_length', 0)} chars | Segments: {sqlite.get('segments_count', 0)}")
            
            redis = job.get('redis_final', {})
            if "error" not in redis:
                if redis.get('total_chunks'):
                    print(f"    Redis: {redis['done_chunks']}/{redis['total_chunks']} chunks done")
        
        print()
        print("📈 Monitoring Stats:")
        for job in completed_jobs:
            print(f"  Task {job['task_id'][:12]}...: {job.get('gpu_samples', 0)} GPU samples, {job.get('sqlite_updates', 0)} SQLite checks, {job.get('redis_updates', 0)} Redis checks")
    
    print()
    print("=" * 85)
    print("✅ Test completed!")
    print()
    print("💡 Check resource usage logs at: /workspace/resource_usage.log")

if __name__ == "__main__":
    main()
