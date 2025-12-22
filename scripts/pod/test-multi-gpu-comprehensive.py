#!/usr/bin/env python3
"""
Comprehensive Multi-GPU Test Script
ทดสอบ 1 request และ 5 requests พร้อมเก็บข้อมูล:
- เวลาที่ใช้
- ผลลัพธ์ข้อความ
- CPU, RAM, GPU Usages
- Model ที่ใช้
"""
import requests
import json
import time
import os
import subprocess
import threading
import psutil
from datetime import datetime
from typing import Dict, List, Optional

class SystemMonitor:
    """Monitor system resources"""
    def __init__(self):
        self.cpu_readings = []
        self.ram_readings = []
        self.gpu_readings_0 = []
        self.gpu_readings_1 = []
        self.monitoring = True
        
    def start_monitoring(self):
        """Start monitoring in background thread"""
        def monitor():
            while self.monitoring:
                try:
                    # CPU and RAM
                    cpu_percent = psutil.cpu_percent(interval=1)
                    ram = psutil.virtual_memory()
                    self.cpu_readings.append(cpu_percent)
                    self.ram_readings.append(ram.percent)
                    
                    # GPU
                    gpu_output = subprocess.check_output(
                        ["nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used,memory.total", 
                         "--format=csv,noheader,nounits"],
                        text=True,
                        timeout=2
                    )
                    for line in gpu_output.strip().split('\n'):
                        parts = line.split(',')
                        if len(parts) >= 4:
                            gpu_idx = int(parts[0].strip())
                            gpu_util = int(parts[1].strip())
                            mem_used = int(parts[2].strip())
                            mem_total = int(parts[3].strip())
                            mem_percent = (mem_used / mem_total) * 100 if mem_total > 0 else 0
                            
                            if gpu_idx == 0:
                                self.gpu_readings_0.append({
                                    'util': gpu_util,
                                    'mem_percent': mem_percent,
                                    'mem_used_mb': mem_used,
                                    'mem_total_mb': mem_total
                                })
                            elif gpu_idx == 1:
                                self.gpu_readings_1.append({
                                    'util': gpu_util,
                                    'mem_percent': mem_percent,
                                    'mem_used_mb': mem_used,
                                    'mem_total_mb': mem_total
                                })
                except Exception as e:
                    pass
                time.sleep(1)
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        return thread
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        time.sleep(2)  # Wait for last readings
    
    def get_stats(self) -> Dict:
        """Get statistics"""
        stats = {}
        
        if self.cpu_readings:
            stats['cpu'] = {
                'min': min(self.cpu_readings),
                'max': max(self.cpu_readings),
                'avg': sum(self.cpu_readings) / len(self.cpu_readings)
            }
        
        if self.ram_readings:
            stats['ram'] = {
                'min': min(self.ram_readings),
                'max': max(self.ram_readings),
                'avg': sum(self.ram_readings) / len(self.ram_readings)
            }
        
        if self.gpu_readings_0:
            stats['gpu_0'] = {
                'util': {
                    'min': min(r['util'] for r in self.gpu_readings_0),
                    'max': max(r['util'] for r in self.gpu_readings_0),
                    'avg': sum(r['util'] for r in self.gpu_readings_0) / len(self.gpu_readings_0)
                },
                'mem': {
                    'min': min(r['mem_percent'] for r in self.gpu_readings_0),
                    'max': max(r['mem_percent'] for r in self.gpu_readings_0),
                    'avg': sum(r['mem_percent'] for r in self.gpu_readings_0) / len(self.gpu_readings_0),
                    'used_mb_avg': sum(r['mem_used_mb'] for r in self.gpu_readings_0) / len(self.gpu_readings_0),
                    'total_mb': self.gpu_readings_0[0]['mem_total_mb'] if self.gpu_readings_0 else 0
                }
            }
        
        if self.gpu_readings_1:
            stats['gpu_1'] = {
                'util': {
                    'min': min(r['util'] for r in self.gpu_readings_1),
                    'max': max(r['util'] for r in self.gpu_readings_1),
                    'avg': sum(r['util'] for r in self.gpu_readings_1) / len(self.gpu_readings_1)
                },
                'mem': {
                    'min': min(r['mem_percent'] for r in self.gpu_readings_1),
                    'max': max(r['mem_percent'] for r in self.gpu_readings_1),
                    'avg': sum(r['mem_percent'] for r in self.gpu_readings_1) / len(self.gpu_readings_1),
                    'used_mb_avg': sum(r['mem_used_mb'] for r in self.gpu_readings_1) / len(self.gpu_readings_1),
                    'total_mb': self.gpu_readings_1[0]['mem_total_mb'] if self.gpu_readings_1 else 0
                }
            }
        
        return stats

def test_single_request(worker_url: str, file_path: str, monitor: SystemMonitor) -> Dict:
    """Test single request"""
    print("=" * 70)
    print("📊 Test 1: Single Request")
    print("=" * 70)
    print()
    
    monitor.start_monitoring()
    
    try:
        # Create task
        print("📝 Creating transcription task...")
        task_data = {
            "file_path": file_path,
            "language": "th",
            "model_size": "base",
            "use_chunking": True,
            "chunk_duration": 90
        }
        
        start_time = time.time()
        response = requests.post(
            f"{worker_url}/api/transcribe/",
            json=task_data,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        task_id = result.get("task_id")
        print(f"✅ Task created: {task_id}")
        print()
        
        # Monitor progress
        print("📊 Monitoring progress...")
        while True:
            status_resp = requests.get(f"{worker_url}/api/tasks/{task_id}", timeout=30)
            status_resp.raise_for_status()
            task_status = status_resp.json()
            
            current_status = task_status.get("status")
            progress = task_status.get("progress", 0)
            elapsed = time.time() - start_time
            
            print(f"[{time.strftime('%H:%M:%S')}] Status: {current_status} | Progress: {progress}% | Elapsed: {elapsed:.1f}s")
            
            if current_status in ["completed", "failed"]:
                total_time = time.time() - start_time
                monitor.stop_monitoring()
                
                if current_status == "failed":
                    error_msg = task_status.get("error_message", "Unknown error")
                    print(f"❌ Task failed: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "time": total_time
                    }
                
                # Get full result
                full_result = task_status
                text = full_result.get("full_text", "")
                chunks = full_result.get("chunks", [])
                model_size = task_status.get("model_size", "base")
                
                return {
                    "success": True,
                    "time": total_time,
                    "text": text,
                    "text_length": len(text),
                    "chunks_count": len(chunks),
                    "model_size": model_size,
                    "task_id": task_id
                }
            
            time.sleep(2)
    except Exception as e:
        monitor.stop_monitoring()
        print(f"❌ Error: {e}")
        return {
            "success": False,
            "error": str(e),
            "time": time.time() - start_time if 'start_time' in locals() else 0
        }

def test_multiple_requests(worker_url: str, file_path: str, num_requests: int, monitor: SystemMonitor) -> Dict:
    """Test multiple concurrent requests"""
    print("=" * 70)
    print(f"📊 Test 2: {num_requests} Concurrent Requests")
    print("=" * 70)
    print()
    
    monitor.start_monitoring()
    
    def create_and_monitor_task(request_num: int):
        try:
            task_data = {
                "file_path": file_path,
                "language": "th",
                "model_size": "base",
                "use_chunking": True,
                "chunk_duration": 90
            }
            
            response = requests.post(
                f"{worker_url}/api/transcribe/",
                json=task_data,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            task_id = result.get("task_id")
            
            start_time = time.time()
            while True:
                try:
                    status_resp = requests.get(f"{worker_url}/api/tasks/{task_id}", timeout=30)
                    status_resp.raise_for_status()
                    task_status = status_resp.json()
                    
                    current_status = task_status.get("status")
                    if current_status in ["completed", "failed"]:
                        elapsed = time.time() - start_time
                        if current_status == "failed":
                            return {
                                "request_num": request_num,
                                "success": False,
                                "error": task_status.get("error_message", "Unknown error"),
                                "time": elapsed
                            }
                        
                        text = task_status.get("full_text", "")
                        return {
                            "request_num": request_num,
                            "success": True,
                            "time": elapsed,
                            "text": text,
                            "text_length": len(text),
                            "model_size": task_status.get("model_size", "base")
                        }
                    time.sleep(1)
                except requests.exceptions.Timeout:
                    continue
        except Exception as e:
            return {
                "request_num": request_num,
                "success": False,
                "error": str(e),
                "time": 0
            }
    
    start_time = time.time()
    import concurrent.futures
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [
            executor.submit(create_and_monitor_task, i+1)
            for i in range(num_requests)
        ]
        
        results = []
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            if result.get("success"):
                print(f"  Request {result['request_num']}: ✅ Completed in {result['time']:.1f}s")
            else:
                print(f"  Request {result['request_num']}: ❌ Failed - {result.get('error', 'Unknown')}")
    
    total_time = time.time() - start_time
    monitor.stop_monitoring()
    
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    
    return {
        "total_time": total_time,
        "successful_count": len(successful),
        "failed_count": len(failed),
        "results": results,
        "avg_time": sum(r["time"] for r in successful) / len(successful) if successful else 0,
        "min_time": min(r["time"] for r in successful) if successful else 0,
        "max_time": max(r["time"] for r in successful) if successful else 0
    }

def analyze_text_quality(text: str) -> Dict:
    """Analyze text quality"""
    if not text:
        return {
            "readable": False,
            "length": 0,
            "word_count": 0,
            "has_thai": False,
            "sample": ""
        }
    
    # Simple heuristics
    words = text.split()
    has_thai = any('\u0e00' <= char <= '\u0e7f' for char in text)
    
    # Sample first 200 chars
    sample = text[:200] + "..." if len(text) > 200 else text
    
    return {
        "readable": len(text) > 10 and len(words) > 3,
        "length": len(text),
        "word_count": len(words),
        "has_thai": has_thai,
        "sample": sample
    }

def main():
    worker_url = "http://127.0.0.1:8010"
    file_path = "uploads/v30-1.mp4"
    
    print("=" * 70)
    print("🧪 Comprehensive Multi-GPU Test")
    print("=" * 70)
    print()
    print(f"Worker URL: {worker_url}")
    print(f"File: {file_path}")
    print()
    
    # Test 1: Single request
    monitor1 = SystemMonitor()
    result1 = test_single_request(worker_url, file_path, monitor1)
    stats1 = monitor1.get_stats()
    
    print()
    print("=" * 70)
    print("📊 Test 1 Results")
    print("=" * 70)
    print(f"Success: {result1.get('success', False)}")
    if result1.get("success"):
        print(f"Time: {result1['time']:.1f}s ({int(result1['time']//60)}m {int(result1['time']%60)}s)")
        print(f"Model: {result1.get('model_size', 'unknown')}")
        print(f"Text length: {result1.get('text_length', 0)} chars")
        print(f"Chunks: {result1.get('chunks_count', 0)}")
        
        text_quality = analyze_text_quality(result1.get("text", ""))
        print(f"Text quality: Readable={text_quality['readable']}, Words={text_quality['word_count']}, Has Thai={text_quality['has_thai']}")
        print(f"Sample text: {text_quality['sample']}")
    else:
        print(f"Error: {result1.get('error', 'Unknown')}")
    
    print()
    print("System Resources (Test 1):")
    if stats1.get('cpu'):
        print(f"  CPU: Min={stats1['cpu']['min']:.1f}%, Avg={stats1['cpu']['avg']:.1f}%, Max={stats1['cpu']['max']:.1f}%")
    if stats1.get('ram'):
        print(f"  RAM: Min={stats1['ram']['min']:.1f}%, Avg={stats1['ram']['avg']:.1f}%, Max={stats1['ram']['max']:.1f}%")
    if stats1.get('gpu_0'):
        print(f"  GPU 0: Util Avg={stats1['gpu_0']['util']['avg']:.1f}%, Mem Avg={stats1['gpu_0']['mem']['avg']:.1f}% ({stats1['gpu_0']['mem']['used_mb_avg']:.0f}MB/{stats1['gpu_0']['mem']['total_mb']:.0f}MB)")
    if stats1.get('gpu_1'):
        print(f"  GPU 1: Util Avg={stats1['gpu_1']['util']['avg']:.1f}%, Mem Avg={stats1['gpu_1']['mem']['avg']:.1f}% ({stats1['gpu_1']['mem']['used_mb_avg']:.0f}MB/{stats1['gpu_1']['mem']['total_mb']:.0f}MB)")
    
    print()
    time.sleep(5)  # Wait between tests
    
    # Test 2: 5 concurrent requests
    monitor2 = SystemMonitor()
    result2 = test_multiple_requests(worker_url, file_path, 5, monitor2)
    stats2 = monitor2.get_stats()
    
    print()
    print("=" * 70)
    print("📊 Test 2 Results")
    print("=" * 70)
    print(f"Total time: {result2['total_time']:.1f}s ({int(result2['total_time']//60)}m {int(result2['total_time']%60)}s)")
    print(f"Successful: {result2['successful_count']}/{5}")
    print(f"Failed: {result2['failed_count']}/{5}")
    if result2['successful_count'] > 0:
        print(f"Avg task time: {result2['avg_time']:.1f}s")
        print(f"Min task time: {result2['min_time']:.1f}s")
        print(f"Max task time: {result2['max_time']:.1f}s")
    
    # Analyze text quality from first successful result
    successful_results = [r for r in result2['results'] if r.get('success')]
    if successful_results:
        first_result = successful_results[0]
        text_quality = analyze_text_quality(first_result.get("text", ""))
        print(f"Text quality: Readable={text_quality['readable']}, Words={text_quality['word_count']}, Has Thai={text_quality['has_thai']}")
        print(f"Sample text: {text_quality['sample']}")
    
    print()
    print("System Resources (Test 2):")
    if stats2.get('cpu'):
        print(f"  CPU: Min={stats2['cpu']['min']:.1f}%, Avg={stats2['cpu']['avg']:.1f}%, Max={stats2['cpu']['max']:.1f}%")
    if stats2.get('ram'):
        print(f"  RAM: Min={stats2['ram']['min']:.1f}%, Avg={stats2['ram']['avg']:.1f}%, Max={stats2['ram']['max']:.1f}%")
    if stats2.get('gpu_0'):
        print(f"  GPU 0: Util Avg={stats2['gpu_0']['util']['avg']:.1f}%, Mem Avg={stats2['gpu_0']['mem']['avg']:.1f}% ({stats2['gpu_0']['mem']['used_mb_avg']:.0f}MB/{stats2['gpu_0']['mem']['total_mb']:.0f}MB)")
    if stats2.get('gpu_1'):
        print(f"  GPU 1: Util Avg={stats2['gpu_1']['util']['avg']:.1f}%, Mem Avg={stats2['gpu_1']['mem']['avg']:.1f}% ({stats2['gpu_1']['mem']['used_mb_avg']:.0f}MB/{stats2['gpu_1']['mem']['total_mb']:.0f}MB)")
    
    print()
    print("=" * 70)
    print("📈 Analysis & Recommendations")
    print("=" * 70)
    print()
    
    # Analyze for 25 requests
    if result1.get("success") and result2.get("successful_count", 0) > 0:
        single_time = result1["time"]
        avg_concurrent_time = result2["avg_time"]
        
        print("1. Capacity Analysis for 25 Requests (30-minute videos):")
        print(f"   - Single request time: {single_time:.1f}s")
        print(f"   - Avg concurrent time (5 requests): {avg_concurrent_time:.1f}s")
        
        # Estimate for 25 requests
        # Assuming linear scaling (worst case)
        estimated_time_linear = avg_concurrent_time * (25 / 5)
        # Assuming better scaling with 2 GPUs
        estimated_time_parallel = avg_concurrent_time * (25 / 5) * 0.6  # 40% improvement with parallel
        
        print(f"   - Estimated time (linear): {estimated_time_linear:.1f}s ({int(estimated_time_linear//60)}m)")
        print(f"   - Estimated time (with 2 GPUs): {estimated_time_parallel:.1f}s ({int(estimated_time_parallel//60)}m)")
        
        if estimated_time_parallel < 1800:  # 30 minutes
            print(f"   ✅ Feasible: Can complete 25 requests in ~{int(estimated_time_parallel//60)} minutes")
        else:
            print(f"   ⚠️  May need optimization: Estimated {int(estimated_time_parallel//60)} minutes")
        
        print()
        print("2. Live Streaming Transcription (RTMP Close Caption):")
        print("   Recommendation: Add 1 dedicated GPU for priority tasks")
        print("   Architecture:")
        print("     - GPU 0, 1: Batch transcription (VOD)")
        print("     - GPU 2: Live streaming (priority, low latency)")
        print("   Benefits:")
        print("     - Isolated resources for real-time processing")
        print("     - No interference with batch jobs")
        print("     - Lower latency for live streams")
        print("   Implementation:")
        print("     - Add worker GPU 2 (port 8012) with priority queue")
        print("     - Route live streaming requests to GPU 2")
        print("     - Use smaller chunk_duration (15-30s) for live streams")
    
    print()

if __name__ == "__main__":
    main()


