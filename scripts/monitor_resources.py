#!/usr/bin/env python3
"""
Resource Monitor Script
- Monitor CPU, RAM, GPU usage
- Log to /workspace/resource_usage.log
- Run in background during tests
"""

import os
import sys
import time
import psutil
import subprocess
from datetime import datetime
from pathlib import Path

LOG_FILE = "/workspace/resource_usage.log"
INTERVAL = 5  # seconds

def get_gpu_info():
    """Get GPU usage info using nvidia-smi"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            gpus = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 7:
                        gpus.append({
                            'index': parts[0],
                            'name': parts[1],
                            'gpu_util': parts[2],
                            'mem_util': parts[3],
                            'mem_used_mb': parts[4],
                            'mem_total_mb': parts[5],
                            'temp': parts[6]
                        })
            return gpus
    except Exception as e:
        pass
    return []

def get_process_info():
    """Get process info for RQ workers"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'cpu_percent']):
        try:
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            if 'rq worker' in cmdline or 'transcription' in cmdline.lower():
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': cmdline[:100],  # truncate
                    'memory_mb': proc.info['memory_info'].rss / 1024 / 1024,
                    'cpu_percent': proc.info['cpu_percent']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return processes

def monitor_loop():
    """Main monitoring loop"""
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"📊 Starting Resource Monitor")
    print(f"   Log file: {LOG_FILE}")
    print(f"   Interval: {INTERVAL}s")
    print()
    
    with open(LOG_FILE, 'a') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"Resource Monitor Started: {datetime.now().isoformat()}\n")
        f.write(f"{'='*80}\n")
    
    try:
        while True:
            timestamp = datetime.now().isoformat()
            
            # System resources
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_mb = memory.total / 1024 / 1024
            memory_used_mb = memory.used / 1024 / 1024
            memory_percent = memory.percent
            
            # GPU info
            gpus = get_gpu_info()
            
            # Process info
            processes = get_process_info()
            total_worker_memory = sum(p['memory_mb'] for p in processes)
            
            # Log to file
            with open(LOG_FILE, 'a') as f:
                f.write(f"\n[{timestamp}]\n")
                f.write(f"CPU: {cpu_percent:.1f}%\n")
                f.write(f"RAM: {memory_used_mb:.0f}MB / {memory_mb:.0f}MB ({memory_percent:.1f}%)\n")
                f.write(f"Worker Processes: {len(processes)} (Total RAM: {total_worker_memory:.0f}MB)\n")
                
                if gpus:
                    for gpu in gpus:
                        f.write(f"GPU {gpu['index']} ({gpu['name']}):\n")
                        f.write(f"  GPU Util: {gpu['gpu_util']}%\n")
                        f.write(f"  Mem Util: {gpu['mem_util']}%\n")
                        f.write(f"  Mem Used: {gpu['mem_used_mb']}MB / {gpu['mem_total_mb']}MB\n")
                        f.write(f"  Temp: {gpu['temp']}°C\n")
                else:
                    f.write("GPU: Not available\n")
                
                if processes:
                    f.write("Top Workers:\n")
                    for proc in sorted(processes, key=lambda x: x['memory_mb'], reverse=True)[:5]:
                        f.write(f"  PID {proc['pid']}: {proc['memory_mb']:.0f}MB ({proc['cpu_percent']:.1f}% CPU)\n")
                
                f.write("-" * 80 + "\n")
            
            # Print to console (every 30 seconds)
            if int(time.time()) % 30 < INTERVAL:
                print(f"[{timestamp}] CPU: {cpu_percent:.1f}% | RAM: {memory_percent:.1f}% ({memory_used_mb:.0f}MB) | Workers: {len(processes)} | GPU: {len(gpus)}")
                if gpus:
                    for gpu in gpus:
                        print(f"  GPU {gpu['index']}: {gpu['gpu_util']}% GPU, {gpu['mem_util']}% Mem, {gpu['mem_used_mb']}MB")
            
            time.sleep(INTERVAL)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping Resource Monitor...")
        with open(LOG_FILE, 'a') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Resource Monitor Stopped: {datetime.now().isoformat()}\n")
            f.write(f"{'='*80}\n")
        print("✅ Monitor stopped")

if __name__ == "__main__":
    monitor_loop()
