#!/usr/bin/env python3
"""
Analyze Resource Logs (GPU, CPU, RAM)
Usage: python3 scripts/analyze_resources.py <log_directory>
"""
import sys
import os
import csv
from pathlib import Path
from datetime import datetime

def analyze_gpu_log(log_file):
    """Analyze GPU log"""
    if not os.path.exists(log_file):
        return None
    
    try:
        values = {
            'gpu_util': [],
            'mem_util': [],
            'power': [],
            'temp': [],
        }
        
        with open(log_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'utilization.gpu' in row and row['utilization.gpu']:
                    values['gpu_util'].append(float(row['utilization.gpu']))
                if 'utilization.memory' in row and row['utilization.memory']:
                    values['mem_util'].append(float(row['utilization.memory']))
                if 'power.draw' in row and row['power.draw']:
                    try:
                        values['power'].append(float(row['power.draw']))
                    except:
                        pass
                if 'temperature.gpu' in row and row['temperature.gpu']:
                    try:
                        values['temp'].append(float(row['temperature.gpu']))
                    except:
                        pass
        
        if not values['gpu_util']:
            return None
        
        stats = {
            'avg_gpu_util': sum(values['gpu_util']) / len(values['gpu_util']),
            'max_gpu_util': max(values['gpu_util']),
            'min_gpu_util': min(values['gpu_util']),
            'avg_mem_util': sum(values['mem_util']) / len(values['mem_util']) if values['mem_util'] else 0,
            'max_mem_util': max(values['mem_util']) if values['mem_util'] else 0,
            'avg_power': sum(values['power']) / len(values['power']) if values['power'] else 0,
            'max_power': max(values['power']) if values['power'] else 0,
            'avg_temp': sum(values['temp']) / len(values['temp']) if values['temp'] else 0,
            'max_temp': max(values['temp']) if values['temp'] else 0,
        }
        return stats
    except Exception as e:
        print(f"⚠️  Error analyzing GPU log: {e}")
        import traceback
        traceback.print_exc()
        return None

def analyze_cpu_log(log_file):
    """Analyze CPU log"""
    if not os.path.exists(log_file):
        return None
    
    try:
        cpu_values = []
        
        with open(log_file, 'r') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return None
            
            # Find CPU column (usually 2nd or 3rd)
            cpu_col_idx = None
            for i, col in enumerate(header):
                if 'cpu' in col.lower() or i == 1:
                    cpu_col_idx = i
                    break
            
            if cpu_col_idx is None:
                return None
            
            for row in reader:
                if len(row) > cpu_col_idx and row[cpu_col_idx]:
                    try:
                        cpu_values.append(float(row[cpu_col_idx]))
                    except:
                        pass
        
        if not cpu_values:
            return None
        
        stats = {
            'avg_cpu': sum(cpu_values) / len(cpu_values),
            'max_cpu': max(cpu_values),
        }
        return stats
    except Exception as e:
        print(f"⚠️  Error analyzing CPU log: {e}")
        return None

def analyze_mem_log(log_file):
    """Analyze Memory log"""
    if not os.path.exists(log_file):
        return None
    
    try:
        mem_values = []
        
        with open(log_file, 'r') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return None
            
            # Last column is usually percent
            percent_col_idx = len(header) - 1
            
            for row in reader:
                if len(row) > percent_col_idx and row[percent_col_idx]:
                    try:
                        mem_values.append(float(row[percent_col_idx]))
                    except:
                        pass
        
        if not mem_values:
            return None
        
        stats = {
            'avg_mem_percent': sum(mem_values) / len(mem_values),
            'max_mem_percent': max(mem_values),
            'min_mem_percent': min(mem_values),
        }
        return stats
    except Exception as e:
        print(f"⚠️  Error analyzing Memory log: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        log_dir = "/tmp/resource_logs"
        print(f"ℹ️  No directory specified, using default: {log_dir}")
    else:
        log_dir = sys.argv[1]
    
    log_path = Path(log_dir)
    if not log_path.exists():
        print(f"❌ Directory not found: {log_dir}")
        return
    
    print("=" * 85)
    print("=== Resource Log Analysis ===")
    print("=" * 85)
    print(f"📁 Directory: {log_dir}")
    print("")
    
    gpu_log = log_path / "gpu.log"
    cpu_log = log_path / "cpu.log"
    mem_log = log_path / "memory.log"
    summary_log = log_path / "summary.log"
    
    # Analyze GPU
    print("📊 GPU Analysis:")
    gpu_stats = analyze_gpu_log(gpu_log)
    if gpu_stats:
        print(f"   Avg GPU Utilization: {gpu_stats['avg_gpu_util']:.1f}%")
        print(f"   Max GPU Utilization: {gpu_stats['max_gpu_util']:.1f}%")
        print(f"   Min GPU Utilization: {gpu_stats['min_gpu_util']:.1f}%")
        print(f"   Avg Memory Utilization: {gpu_stats['avg_mem_util']:.1f}%")
        print(f"   Max Memory Utilization: {gpu_stats['max_mem_util']:.1f}%")
        print(f"   Avg Power Draw: {gpu_stats['avg_power']:.1f}W")
        print(f"   Max Power Draw: {gpu_stats['max_power']:.1f}W")
        print(f"   Avg Temperature: {gpu_stats['avg_temp']:.1f}°C")
        print(f"   Max Temperature: {gpu_stats['max_temp']:.1f}°C")
    else:
        print("   ⚠️  No GPU data")
    print("")
    
    # Analyze CPU
    print("📊 CPU Analysis:")
    cpu_stats = analyze_cpu_log(cpu_log)
    if cpu_stats and cpu_stats.get('avg_cpu') is not None:
        print(f"   Avg CPU Usage: {cpu_stats['avg_cpu']:.1f}%")
        print(f"   Max CPU Usage: {cpu_stats['max_cpu']:.1f}%")
    else:
        print("   ⚠️  No CPU data")
    print("")
    
    # Analyze Memory
    print("📊 Memory Analysis:")
    mem_stats = analyze_mem_log(mem_log)
    if mem_stats:
        print(f"   Avg Memory Usage: {mem_stats['avg_mem_percent']:.1f}%")
        print(f"   Max Memory Usage: {mem_stats['max_mem_percent']:.1f}%")
        print(f"   Min Memory Usage: {mem_stats['min_mem_percent']:.1f}%")
    else:
        print("   ⚠️  No Memory data")
    print("")
    
    # Show summary
    if summary_log.exists():
        print("=" * 85)
        print("=== Summary Log ===")
        print("=" * 85)
        with open(summary_log, 'r') as f:
            print(f.read())
    
    # Generate CSV report
    report_file = log_path / "analysis_report.csv"
    with open(report_file, 'w') as f:
        f.write("Metric,Value\n")
        if gpu_stats:
            f.write(f"Avg GPU Utilization (%),{gpu_stats['avg_gpu_util']:.2f}\n")
            f.write(f"Max GPU Utilization (%),{gpu_stats['max_gpu_util']:.2f}\n")
            f.write(f"Avg Memory Utilization (%),{gpu_stats['avg_mem_util']:.2f}\n")
            f.write(f"Max Memory Utilization (%),{gpu_stats['max_mem_util']:.2f}\n")
            f.write(f"Avg Power Draw (W),{gpu_stats['avg_power']:.2f}\n")
            f.write(f"Max Power Draw (W),{gpu_stats['max_power']:.2f}\n")
        if cpu_stats and cpu_stats.get('avg_cpu') is not None:
            f.write(f"Avg CPU Usage (%),{cpu_stats['avg_cpu']:.2f}\n")
            f.write(f"Max CPU Usage (%),{cpu_stats['max_cpu']:.2f}\n")
        if mem_stats:
            f.write(f"Avg Memory Usage (%),{mem_stats['avg_mem_percent']:.2f}\n")
            f.write(f"Max Memory Usage (%),{mem_stats['max_mem_percent']:.2f}\n")
    
    print(f"📄 Report saved to: {report_file}")

if __name__ == "__main__":
    main()
