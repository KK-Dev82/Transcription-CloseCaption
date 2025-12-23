#!/usr/bin/env python3
"""
Test Stability Script - ตรวจสอบความเสถียรของระบบ transcription
เกณฑ์ผ่าน:
1. ผ่านงาน 30 นาที 10 งานติด ไม่มี fail/retry/queue ค้าง
2. เวลารวมแกว่งน้อย: p95 ไม่เกิน ~1.3× ของค่าเฉลี่ย
3. GPU ใช้เต็มจริง: GPU util สูงและต่อเนื่อง (>80%)
4. หน่วยความจำคงที่: RSS ของ worker ไม่โตต่อเนื่อง (no leak)
"""
import requests
import json
import time
import subprocess
import statistics
from datetime import datetime
from typing import List, Dict, Optional

API_URL = "http://localhost:8010"
VIDEO_URL = "https://korrakang.com/video/v30-1.mp4"
VIDEO_DURATION = 1800  # 30 minutes
NUM_JOBS = 10  # 10 งานติด

def get_ram_usage() -> float:
    """Get current RAM usage in GB"""
    try:
        ram_result = subprocess.run(['free', '-m'], capture_output=True, text=True)
        ram_lines = ram_result.stdout.split('\n')
        if len(ram_lines) >= 2:
            mem_line = ram_lines[1].split()
            if len(mem_line) >= 3:
                return float(mem_line[2]) / 1024
    except:
        pass
    return 0.0

def get_gpu_utilization() -> Dict[int, float]:
    """Get GPU utilization for each GPU"""
    gpu_utils = {}
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,utilization.gpu', '--format=csv,noheader,nounits'],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().split('\n'):
            if ',' in line:
                idx, util = line.split(',')
                gpu_utils[int(idx.strip())] = float(util.strip())
    except:
        pass
    return gpu_utils

def get_worker_rss(worker_name: str) -> float:
    """Get RSS memory usage for worker process in MB"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if worker_name in line and 'rq worker' in line:
                parts = line.split()
                if len(parts) >= 6:
                    return float(parts[5]) / 1024  # Convert KB to MB
    except:
        pass
    return 0.0

def send_transcription_request() -> Optional[str]:
    """Send transcription request and return task_id"""
    try:
        response = requests.post(
            f"{API_URL}/api/transcribe/",
            json={
                "file_url": VIDEO_URL,
                "language": "th",
                "model_size": "base"
            },
            timeout=120
        )
        if response.status_code == 200:
            result = response.json()
            return result.get('task_id')
    except Exception as e:
        print(f"❌ Error sending request: {e}")
    return None

def wait_for_task_completion(task_id: str, max_wait: int = 600) -> Dict:
    """Wait for task completion and return result"""
    start_time = time.time()
    check_interval = 5
    
    while True:
        try:
            response = requests.get(f"{API_URL}/api/tasks/{task_id}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', 'unknown')
                
                if status == 'completed':
                    return {
                        'status': 'completed',
                        'task_id': task_id,
                        'total_time': time.time() - start_time,
                        'data': data
                    }
                elif status in ['failed', 'error']:
                    return {
                        'status': 'failed',
                        'task_id': task_id,
                        'error': data.get('error', 'Unknown error'),
                        'total_time': time.time() - start_time
                    }
        except Exception as e:
            print(f"⚠️  Error checking status: {e}")
        
        if time.time() - start_time > max_wait:
            return {
                'status': 'timeout',
                'task_id': task_id,
                'total_time': max_wait
            }
        
        time.sleep(check_interval)

def main():
    print("=" * 70)
    print("🧪 Testing Transcription Stability")
    print("=" * 70)
    print(f"Video URL: {VIDEO_URL}")
    print(f"Video Duration: {VIDEO_DURATION} seconds (30 minutes)")
    print(f"Number of Jobs: {NUM_JOBS}")
    print()
    
    # Initial measurements
    initial_ram = get_ram_usage()
    initial_gpu_utils = get_gpu_utilization()
    initial_worker_rss = {}
    for i in range(2):  # Check GPU0 and GPU1 workers
        initial_worker_rss[i] = get_worker_rss(f"worker-gpu{i}")
    
    print(f"📊 Initial State:")
    print(f"   RAM: {initial_ram:.1f}GB")
    print(f"   GPU Utilization: {initial_gpu_utils}")
    print(f"   Worker RSS: {initial_worker_rss}")
    print()
    
    # Send all jobs
    print("📤 Sending transcription requests...")
    task_ids = []
    for i in range(NUM_JOBS):
        task_id = send_transcription_request()
        if task_id:
            task_ids.append(task_id)
            print(f"   Job {i+1}/{NUM_JOBS}: {task_id[:16]}...")
        else:
            print(f"   ❌ Job {i+1}/{NUM_JOBS}: Failed to send")
        time.sleep(2)  # Small delay between requests
    
    if not task_ids:
        print("❌ No tasks were sent successfully")
        return
    
    print(f"✅ Sent {len(task_ids)} tasks")
    print()
    
    # Monitor and wait for completion
    print("=" * 70)
    print("📊 Monitoring Task Progress")
    print("=" * 70)
    print()
    
    results = []
    gpu_util_samples = []  # List of GPU util dicts over time
    worker_rss_samples = []  # List of worker RSS dicts over time
    ram_samples = []
    
    start_time = time.time()
    check_interval = 10
    
    while len(results) < len(task_ids):
        # Sample metrics
        current_ram = get_ram_usage()
        current_gpu_utils = get_gpu_utilization()
        current_worker_rss = {}
        for i in range(2):
            current_worker_rss[i] = get_worker_rss(f"worker-gpu{i}")
        
        ram_samples.append(current_ram)
        gpu_util_samples.append(current_gpu_utils.copy())
        worker_rss_samples.append(current_worker_rss.copy())
        
        # Check completed tasks
        for task_id in task_ids:
            if any(r['task_id'] == task_id for r in results):
                continue
            
            try:
                response = requests.get(f"{API_URL}/api/tasks/{task_id}", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status', 'unknown')
                    
                    if status == 'completed':
                        elapsed = time.time() - start_time
                        processing_time = data.get('processing_time', 0)
                        results.append({
                            'task_id': task_id,
                            'status': 'completed',
                            'total_time': elapsed,
                            'processing_time': processing_time
                        })
                        print(f"✅ [{elapsed:.0f}s] Task {len(results)}/{len(task_ids)} completed: {task_id[:16]}...")
                    elif status in ['failed', 'error']:
                        results.append({
                            'task_id': task_id,
                            'status': 'failed',
                            'error': data.get('error', 'Unknown error')
                        })
                        print(f"❌ Task failed: {task_id[:16]}... - {data.get('error', 'Unknown error')}")
            except:
                pass
        
        # Print current status
        if len(gpu_util_samples) % 3 == 0:  # Every 30 seconds
            elapsed = time.time() - start_time
            avg_gpu0 = statistics.mean([g.get(0, 0) for g in gpu_util_samples[-3:]]) if gpu_util_samples else 0
            avg_gpu1 = statistics.mean([g.get(1, 0) for g in gpu_util_samples[-3:]]) if gpu_util_samples else 0
            print(f"[{elapsed:.0f}s] Completed: {len(results)}/{len(task_ids)} | "
                  f"GPU0: {avg_gpu0:.0f}% | GPU1: {avg_gpu1:.0f}% | "
                  f"RAM: {current_ram:.1f}GB")
        
        if len(results) >= len(task_ids):
            break
        
        time.sleep(check_interval)
    
    total_time = time.time() - start_time
    
    # Analyze results
    print()
    print("=" * 70)
    print("📊 Stability Analysis")
    print("=" * 70)
    print()
    
    # 1. Check completion rate
    completed = [r for r in results if r.get('status') == 'completed']
    failed = [r for r in results if r.get('status') == 'failed']
    
    print("1️⃣  Completion Rate:")
    print(f"   ✅ Completed: {len(completed)}/{NUM_JOBS}")
    print(f"   ❌ Failed: {len(failed)}/{NUM_JOBS}")
    if len(failed) > 0:
        for f in failed:
            print(f"      - {f.get('task_id', 'unknown')[:16]}...: {f.get('error', 'Unknown error')}")
    
    if len(completed) < NUM_JOBS:
        print(f"   ❌ FAIL: Not all jobs completed ({len(completed)}/{NUM_JOBS})")
    else:
        print(f"   ✅ PASS: All jobs completed")
    print()
    
    # 2. Check timing consistency (p95)
    if len(completed) >= 2:
        processing_times = [r.get('processing_time', 0) for r in completed if r.get('processing_time', 0) > 0]
        if processing_times:
            avg_time = statistics.mean(processing_times)
            p95_time = statistics.quantiles(processing_times, n=20)[18] if len(processing_times) >= 20 else max(processing_times)
            p95_ratio = p95_time / avg_time if avg_time > 0 else 0
            
            print("2️⃣  Timing Consistency:")
            print(f"   Average: {avg_time:.2f}s ({avg_time/60:.2f} min)")
            print(f"   P95: {p95_time:.2f}s ({p95_time/60:.2f} min)")
            print(f"   P95/Avg Ratio: {p95_ratio:.2f}×")
            
            if p95_ratio <= 1.3:
                print(f"   ✅ PASS: P95 ≤ 1.3× average (stable)")
            else:
                print(f"   ❌ FAIL: P95 > 1.3× average (unstable)")
            print()
    
    # 3. Check GPU utilization
    if gpu_util_samples:
        gpu0_utils = [g.get(0, 0) for g in gpu_util_samples if 0 in g]
        gpu1_utils = [g.get(1, 0) for g in gpu_util_samples if 1 in g]
        
        avg_gpu0 = statistics.mean(gpu0_utils) if gpu0_utils else 0
        avg_gpu1 = statistics.mean(gpu1_utils) if gpu1_utils else 0
        max_gpu0 = max(gpu0_utils) if gpu0_utils else 0
        max_gpu1 = max(gpu1_utils) if gpu1_utils else 0
        
        print("3️⃣  GPU Utilization:")
        print(f"   GPU0: Avg {avg_gpu0:.0f}%, Max {max_gpu0:.0f}%")
        print(f"   GPU1: Avg {avg_gpu1:.0f}%, Max {max_gpu1:.0f}%")
        
        if avg_gpu0 >= 80 and avg_gpu1 >= 80:
            print(f"   ✅ PASS: Both GPUs utilized >80%")
        elif avg_gpu0 >= 80 or avg_gpu1 >= 80:
            print(f"   ⚠️  WARNING: Only one GPU utilized >80%")
        else:
            print(f"   ❌ FAIL: GPUs not fully utilized")
        print()
    
    # 4. Check memory stability
    if ram_samples:
        max_ram = max(ram_samples)
        final_ram = ram_samples[-1] if ram_samples else initial_ram
        ram_increase = final_ram - initial_ram
        
        print("4️⃣  Memory Stability:")
        print(f"   Initial: {initial_ram:.1f}GB")
        print(f"   Peak: {max_ram:.1f}GB")
        print(f"   Final: {final_ram:.1f}GB")
        print(f"   Increase: {ram_increase:.1f}GB")
        
        if ram_increase < 2.0:
            print(f"   ✅ PASS: Memory increase < 2GB (no leak)")
        elif ram_increase < 5.0:
            print(f"   ⚠️  WARNING: Memory increase 2-5GB (possible leak)")
        else:
            print(f"   ❌ FAIL: Memory increase > 5GB (likely leak)")
        print()
    
    # Check worker RSS
    if worker_rss_samples:
        for i in range(2):
            worker_rss = [w.get(i, 0) for w in worker_rss_samples if i in w]
            if worker_rss:
                initial_rss = initial_worker_rss.get(i, 0)
                max_rss = max(worker_rss)
                final_rss = worker_rss[-1] if worker_rss else initial_rss
                rss_increase = final_rss - initial_rss
                
                print(f"   Worker GPU{i} RSS:")
                print(f"      Initial: {initial_rss:.1f}MB")
                print(f"      Peak: {max_rss:.1f}MB")
                print(f"      Final: {final_rss:.1f}MB")
                print(f"      Increase: {rss_increase:.1f}MB")
                
                if rss_increase < 500:
                    print(f"      ✅ PASS: RSS increase < 500MB")
                else:
                    print(f"      ⚠️  WARNING: RSS increase ≥ 500MB (possible leak)")
        print()
    
    # Summary
    print("=" * 70)
    print("📋 Summary")
    print("=" * 70)
    
    all_passed = (
        len(completed) == NUM_JOBS and
        (not processing_times or p95_ratio <= 1.3) and
        (not gpu_util_samples or (avg_gpu0 >= 80 and avg_gpu1 >= 80)) and
        (not ram_samples or ram_increase < 2.0)
    )
    
    if all_passed:
        print("✅ STABILITY TEST PASSED")
        print("   System is stable and ready for performance optimization")
    else:
        print("❌ STABILITY TEST FAILED")
        print("   Please fix issues before optimizing performance")
    
    print()

if __name__ == "__main__":
    main()

