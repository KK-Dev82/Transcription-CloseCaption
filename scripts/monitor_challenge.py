#!/usr/bin/env python3
"""
Monitor challenge test - 25 jobs with 20 minute timeout
Refreshes every 5 seconds
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
    # Load task IDs
    if os.path.exists("/tmp/latest_task_ids.txt"):
        with open("/tmp/latest_task_ids.txt", "r") as f:
            task_ids = [line.strip() for line in f if line.strip()]
    else:
        print("❌ No task IDs found in /tmp/latest_task_ids.txt")
        sys.exit(1)
    
    try:
        conn = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
        conn.ping()
    except Exception as e:
        print(f"❌ Cannot connect to Redis: {e}")
        sys.exit(1)
    
    print("=" * 85)
    print("=== Challenge Test: 25 Jobs ===")
    print("=" * 85)
    print(f"Target: ≤ 18 minutes")
    print(f"Timeout: 20 minutes")
    print(f"Jobs: {len(task_ids)}")
    print("")
    print("📊 Monitoring: Refreshing every 5 seconds")
    print("   Press Ctrl+C to stop")
    print("")
    
    # เก็บ start times
    start_times = {}
    for task_id in task_ids:
        start_times[task_id] = time.time()
    
    start_time = time.time()
    timeout_seconds = 20 * 60  # 20 minutes
    target_seconds = 18 * 60   # 18 minutes
    check_count = 0
    
    try:
        while True:
            check_count += 1
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Check timeout
            if elapsed > timeout_seconds:
                print("\n⏰ Timeout reached (20 minutes)")
                break
            
            # Get system metrics
            gpu_metrics = get_gpu_metrics()
            cpu_percent = get_cpu_metrics()
            ram_metrics = get_ram_metrics()
            
            # Clear screen (move cursor up)
            if check_count > 1:
                lines_to_clear = len(task_ids) + 6  # jobs + header + metrics + separator + target
                print("\033[F" * lines_to_clear, end='')
            
            # Header
            elapsed_str = f"{int(elapsed//60)}m {int(elapsed%60)}s"
            target_str = f"{int(target_seconds//60)}m"
            remaining = timeout_seconds - elapsed
            remaining_str = f"{int(remaining//60)}m {int(remaining%60)}s"
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Update #{check_count} | Elapsed: {elapsed_str} | Target: ≤{target_str} | Remaining: {remaining_str}")
            print(f"System: CPU {cpu_percent:.1f}% | GPU {gpu_metrics['gpu_util']}% ({gpu_metrics['mem_util']}% mem) | RAM {ram_metrics['percent']:.1f}% ({ram_metrics['used_mb']}/{ram_metrics['total_mb']}MB) | Temp: {gpu_metrics['temp']}°C")
            print("-" * 85)
            
            all_completed = True
            completed_count = 0
            processing_count = 0
            queued_count = 0
            
            for i, task_id in enumerate(task_ids, 1):
                task_status = get_task_status(task_id, conn)
                status = task_status['status']
                progress = task_status['progress']
                
                job_elapsed = current_time - start_times[task_id]
                job_elapsed_str = f"{int(job_elapsed//60)}m {int(job_elapsed%60)}s"
                
                if status == "completed":
                    status_icon = "✅"
                    completed_count += 1
                elif status == "processing":
                    status_icon = "🔄"
                    processing_count += 1
                    all_completed = False
                else:
                    status_icon = "⏳"
                    queued_count += 1
                    all_completed = False
                
                # แสดงเฉพาะ progress ที่เปลี่ยน หรือทุก 10 jobs
                print(f"{status_icon} Job {i:2d}: {progress:3d}% | {job_elapsed_str:>8s} | {task_id[:32]}...")
            
            # Summary line
            print("-" * 85)
            print(f"Summary: ✅ {completed_count}/{len(task_ids)} completed | 🔄 {processing_count} processing | ⏳ {queued_count} queued")
            
            if all_completed:
                print("\n✅ All jobs completed!")
                break
            
            # Check if target time exceeded
            if elapsed > target_seconds and completed_count < len(task_ids):
                print(f"\n⚠️  Target time ({target_str}) exceeded! {completed_count}/{len(task_ids)} completed")
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped by user")
    
    # สรุปผล
    final_time = time.time() - start_time
    print("\n" + "=" * 85)
    print("=== สรุปผล Challenge Test ===")
    print("=" * 85)
    print(f"Total time: {int(final_time//60)}m {int(final_time%60)}s ({int(final_time)}s)")
    print(f"Target: ≤ 18 minutes ({target_seconds}s)")
    print("")
    
    # ตรวจสอบแต่ละ job
    completed_times = []
    for i, task_id in enumerate(task_ids, 1):
        task_status = get_task_status(task_id, conn)
        elapsed = time.time() - start_times[task_id]
        
        if task_status['status'] == 'completed':
            completed_times.append(elapsed)
            status_icon = "✅"
        else:
            status_icon = "❌"
        
        print(f"{status_icon} Job {i:2d}: {task_status['status'].upper()} | {int(elapsed//60)}m {int(elapsed%60)}s | {task_id[:32]}...")
    
    print("")
    if completed_times:
        max_time = max(completed_times)
        min_time = min(completed_times)
        avg_time = sum(completed_times) / len(completed_times)
        
        print("=" * 85)
        print("=== ⏱️  สถิติเวลา ===")
        print("=" * 85)
        print(f"Completed: {len(completed_times)}/{len(task_ids)} jobs")
        print(f"Max time: {int(max_time//60)}m {int(max_time%60)}s ({int(max_time)}s)")
        print(f"Min time: {int(min_time//60)}m {int(min_time%60)}s ({int(min_time)}s)")
        print(f"Avg time: {int(avg_time//60)}m {int(avg_time%60)}s ({int(avg_time)}s)")
        print("")
        
        if max_time <= target_seconds:
            print(f"✅ ผ่าน: Max time ({int(max_time//60)}m {int(max_time%60)}s) ≤ Target ({target_str})")
        else:
            print(f"❌ ไม่ผ่าน: Max time ({int(max_time//60)}m {int(max_time%60)}s) > Target ({target_str})")
        
        if final_time <= target_seconds:
            print(f"✅ ผ่าน: Total time ({int(final_time//60)}m {int(final_time%60)}s) ≤ Target ({target_str})")
        else:
            print(f"⚠️  Total time ({int(final_time//60)}m {int(final_time%60)}s) > Target ({target_str})")
    
    print("=" * 85)

if __name__ == "__main__":
    main()

