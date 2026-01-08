#!/usr/bin/env python3
"""
Monitor multiple transcription jobs with real-time metrics
Shows: Time, Progress, CPU, GPU, RAM, Job ID
"""
import os
import sys
import time
import json
import redis
import requests
import subprocess
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('.env.runpod')
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

API_BASE = "http://localhost:8010/api"

def get_gpu_metrics():
    """Get GPU utilization and memory"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu', 
             '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(', ')
            if len(parts) >= 5:
                return {
                    'gpu_util': int(parts[0]),
                    'mem_util': int(parts[1]),
                    'mem_used': int(parts[2]),
                    'mem_total': int(parts[3]),
                    'temp': int(parts[4])
                }
    except:
        pass
    return {'gpu_util': 0, 'mem_util': 0, 'mem_used': 0, 'mem_total': 0, 'temp': 0}

def get_cpu_metrics():
    """Get CPU utilization"""
    try:
        result = subprocess.run(
            ['top', '-bn1'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'Cpu(s)' in line:
                    # Extract CPU usage percentage
                    parts = line.split(',')
                    for part in parts:
                        if '%id' in part:
                            idle = float(part.replace('%id', '').strip())
                            return 100.0 - idle
    except:
        pass
    return 0.0

def get_ram_metrics():
    """Get RAM usage"""
    try:
        result = subprocess.run(
            ['free', '-m'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'Mem:' in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        used = int(parts[2])
                        total = int(parts[1])
                        return {
                            'used_mb': used,
                            'total_mb': total,
                            'percent': (used / total) * 100.0
                        }
    except:
        pass
    return {'used_mb': 0, 'total_mb': 0, 'percent': 0.0}

def get_task_status(task_id, conn):
    """Get task status from API and Redis"""
    # Try API first
    try:
        response = requests.get(f"{API_BASE}/v2/tasks/{task_id}", timeout=5)
        if response.status_code == 200:
            task = response.json()
            return {
                'status': task.get('status', 'unknown'),
                'progress': task.get('progress', 0),
                'stage': task.get('current_stage', ''),
                'stage_desc': task.get('current_stage_description', ''),
                'created_at': task.get('created_at', ''),
                'completed_at': task.get('completed_at', '')
            }
    except:
        pass
    
    # Fallback to Redis
    total = int(conn.get(f"task:{task_id}:total_chunks") or 0)
    done = int(conn.get(f"task:{task_id}:done_chunks") or 0)
    
    if total > 0:
        progress = int((done / total) * 100)
        status = 'completed' if done == total else 'processing'
    else:
        progress = 0
        status = 'queued'
    
    return {
        'status': status,
        'progress': progress,
        'stage': '',
        'stage_desc': f"{done}/{total} chunks" if total > 0 else "waiting",
        'created_at': '',
        'completed_at': ''
    }

def main():
    if len(sys.argv) < 2:
        # Try to load from file
        if os.path.exists("/tmp/latest_task_ids.txt"):
            with open("/tmp/latest_task_ids.txt", "r") as f:
                task_ids = [line.strip() for line in f if line.strip()]
        else:
            print("Usage: python3 scripts/monitor_jobs.py <task_id1> [task_id2] ...")
            print("   Or: python3 scripts/monitor_jobs.py (will use /tmp/latest_task_ids.txt)")
            sys.exit(1)
    else:
        task_ids = sys.argv[1:]
    
    try:
        conn = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
        conn.ping()
    except Exception as e:
        print(f"❌ Cannot connect to Redis: {e}")
        sys.exit(1)
    
    print("=" * 85)
    print("=== ติดตาม Transcription Jobs ===")
    print("=" * 85)
    print(f"Jobs: {len(task_ids)}")
    print("")
    print("📊 Monitoring: Time | Progress | CPU | GPU | RAM | Job ID")
    print("   Press Ctrl+C to stop")
    print("")
    
    # เก็บ start times
    start_times = {}
    for task_id in task_ids:
        start_times[task_id] = time.time()
    
    check_count = 0
    
    try:
        while True:
            check_count += 1
            current_time = time.time()
            
            # Get system metrics
            gpu_metrics = get_gpu_metrics()
            cpu_percent = get_cpu_metrics()
            ram_metrics = get_ram_metrics()
            
            # Clear screen (move cursor up)
            if check_count > 1:
                lines_to_clear = len(task_ids) + 4  # jobs + header + metrics + separator
                print("\033[F" * lines_to_clear, end='')
            
            # Header
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Update #{check_count}")
            print(f"System: CPU {cpu_percent:.1f}% | GPU {gpu_metrics['gpu_util']}% | RAM {ram_metrics['percent']:.1f}% ({ram_metrics['used_mb']}/{ram_metrics['total_mb']}MB)")
            print("-" * 85)
            
            all_completed = True
            
            for i, task_id in enumerate(task_ids, 1):
                task_status = get_task_status(task_id, conn)
                status = task_status['status']
                progress = task_status['progress']
                
                elapsed = current_time - start_times[task_id]
                elapsed_str = f"{int(elapsed//60)}m {int(elapsed%60)}s"
                
                status_icon = "✅" if status == "completed" else "🔄" if status == "processing" else "⏳"
                
                print(f"{status_icon} Job {i}: {progress:3d}% | {elapsed_str:>8s} | {task_id[:36]}...")
                
                if status != "completed":
                    all_completed = False
            
            if all_completed:
                print("\n✅ All jobs completed!")
                break
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped by user")
    
    # สรุปผล
    print("\n" + "=" * 85)
    print("=== สรุปผลการทดสอบ ===")
    print("=" * 85)
    print("")
    
    for i, task_id in enumerate(task_ids, 1):
        task_status = get_task_status(task_id, conn)
        elapsed = time.time() - start_times[task_id]
        
        print(f"Job {i}: {task_id[:36]}...")
        print(f"   Status: {task_status['status'].upper()}")
        print(f"   Progress: {task_status['progress']}%")
        print(f"   Elapsed: {int(elapsed//60)}m {int(elapsed%60)}s ({int(elapsed)}s)")
        if task_status['completed_at']:
            print(f"   ✅ Completed")
        print()
    
    print("=" * 85)

if __name__ == "__main__":
    main()

