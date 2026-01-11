#!/usr/bin/env python3
"""
Benchmark Script: เปรียบเทียบประสิทธิภาพระหว่าง 2 models
- Vinxscribe/biodatlab-whisper-th-medium-faster
- Systran/faster-whisper-small
"""

import requests
import time
import os
import sys
from datetime import datetime
from typing import List, Dict
import json

API_BASE = "http://localhost:8010/api"
TEST_FILE = "/workspace/transcription-service/uploads/f8f3d293-ba60-41c5-9054-09725a3a22fb_v30-1.wav"

MODELS = [
    {
        "name": "Vinxscribe/biodatlab-whisper-th-medium-faster",
        "model_id": "Vinxscribe/biodatlab-whisper-th-medium-faster",
        "display_name": "Vinxscribe Medium (Thai-optimized)"
    },
    {
        "name": "Systran/faster-whisper-small",
        "model_id": "Systran/faster-whisper-small",
        "display_name": "Systran Small"
    }
]

def submit_job(file_path: str, model_size: str, language: str = "th") -> str:
    """ส่ง transcription job"""
    url = f"{API_BASE}/transcribe/"
    
    payload = {
        "file_path": file_path,
        "language": language,
        "model_size": model_size  # ใช้ model_size แทน model
    }
    
    response = requests.post(url, json=payload, timeout=30)
    if response.status_code != 200:
        raise Exception(f"Failed to submit job: {response.status_code} - {response.text}")
    
    data = response.json()
    return data.get("task_id")

def get_task_status(task_id: str) -> Dict:
    """ดึงสถานะ task"""
    url = f"{API_BASE}/v2/tasks/{task_id}?format=full"
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        return {}
    return response.json()

def wait_for_completion(task_id: str, timeout: int = 600) -> Dict:
    """รอจน task เสร็จ"""
    start_time = time.time()
    last_progress = -1
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise TimeoutError(f"Task {task_id} timeout after {timeout}s")
        
        task = get_task_status(task_id)
        status = task.get("status", "").lower()
        progress = task.get("progress", 0)
        
        # แสดง progress เมื่อเปลี่ยน
        if progress != last_progress:
            stage = task.get("current_stage", "N/A")
            print(f"   [{int(elapsed)}s] {status.upper()} - {progress}% | {stage}")
            last_progress = progress
        
        if status == "completed":
            return task
        elif status == "failed":
            error = task.get("error_message", "Unknown error")
            raise Exception(f"Task failed: {error}")
        
        time.sleep(2)

def calculate_timing(task: Dict) -> Dict:
    """คำนวณเวลาที่ใช้"""
    created_at = task.get("created_at")
    completed_at = task.get("completed_at")
    
    if not created_at or not completed_at:
        return {}
    
    try:
        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        completed = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
        total_time = (completed - created).total_seconds()
        
        # ดึง phase timings ถ้ามี
        result = task.get("result", {})
        phase_timings = result.get("phase_timings", {})
        
        return {
            "total_time": total_time,
            "preprocess_time": phase_timings.get("total_preprocess_time", 0),
            "aggregator_time": phase_timings.get("total_aggregator_time", 0),
            "transcription_time": phase_timings.get("total_transcription_time", 0),
        }
    except Exception as e:
        print(f"   ⚠️  Error calculating timing: {e}")
        return {}

def run_benchmark(model_config: Dict, num_jobs: int = 5) -> List[Dict]:
    """รัน benchmark สำหรับ model หนึ่ง"""
    model_name = model_config["name"]
    model_id = model_config["model_id"]
    display_name = model_config["display_name"]
    
    print("")
    print("=" * 85)
    print(f"📊 Testing Model: {display_name}")
    print(f"   Model ID: {model_id}")
    print(f"   Jobs: {num_jobs}")
    print("=" * 85)
    print("")
    
    results = []
    
    for i in range(1, num_jobs + 1):
        print(f"\n{'='*85}")
        print(f"Job {i}/{num_jobs}")
        print(f"{'='*85}")
        
        try:
            # ตั้งค่า WHISPER_MODEL environment variable
            # Note: ต้อง restart workers เพื่อให้ใช้ model ใหม่
            # แต่ในกรณีนี้เราจะใช้ model parameter ใน API request
            
            # ส่ง job (ใช้ model_size parameter)
            print(f"📤 Submitting job {i}...")
            task_id = submit_job(TEST_FILE, model_id, language="th")
            print(f"   Task ID: {task_id}")
            print(f"   Model: {model_id}")
            
            # รอจนเสร็จ
            print(f"⏳ Waiting for completion...")
            task = wait_for_completion(task_id, timeout=600)
            
            # คำนวณเวลา
            timing = calculate_timing(task)
            timing["task_id"] = task_id
            timing["status"] = task.get("status")
            timing["job_number"] = i
            
            # แสดงผลลัพธ์
            total_time = timing.get("total_time", 0)
            print(f"✅ Job {i} completed in {int(total_time//60)}m {int(total_time%60)}s ({int(total_time)}s)")
            
            if timing.get("transcription_time"):
                print(f"   Transcription time: {timing['transcription_time']:.2f}s")
            if timing.get("preprocess_time"):
                print(f"   Preprocess time: {timing['preprocess_time']:.2f}s")
            if timing.get("aggregator_time"):
                print(f"   Aggregator time: {timing['aggregator_time']:.2f}s")
            
            results.append(timing)
            
        except Exception as e:
            print(f"❌ Job {i} failed: {e}")
            results.append({
                "task_id": f"failed_{i}",
                "status": "failed",
                "error": str(e),
                "job_number": i,
                "total_time": 0
            })
    
    return results

def calculate_statistics(results: List[Dict]) -> Dict:
    """คำนวณสถิติ"""
    successful_results = [r for r in results if r.get("total_time", 0) > 0]
    
    if not successful_results:
        return {}
    
    total_times = [r["total_time"] for r in successful_results]
    transcription_times = [r.get("transcription_time", r["total_time"]) for r in successful_results if r.get("transcription_time")]
    
    stats = {
        "num_jobs": len(results),
        "successful_jobs": len(successful_results),
        "failed_jobs": len(results) - len(successful_results),
        "total_wall_time": max(total_times) if total_times else 0,  # เวลารวมของ 5 jobs (max time)
        "min_time": min(total_times) if total_times else 0,
        "max_time": max(total_times) if total_times else 0,
        "avg_time": sum(total_times) / len(total_times) if total_times else 0,
    }
    
    if transcription_times:
        stats["min_transcription_time"] = min(transcription_times)
        stats["max_transcription_time"] = max(transcription_times)
        stats["avg_transcription_time"] = sum(transcription_times) / len(transcription_times)
    
    return stats

def print_comparison(model1_results: Dict, model2_results: Dict, model1_name: str, model2_name: str):
    """แสดงผลการเปรียบเทียบ"""
    print("")
    print("=" * 85)
    print("📊 BENCHMARK RESULTS COMPARISON")
    print("=" * 85)
    print("")
    
    # สร้างตารางเปรียบเทียบ
    print(f"{'Metric':<40} {model1_name[:20]:<22} {model2_name[:22]}")
    print("-" * 85)
    
    metrics = [
        ("Successful Jobs", "successful_jobs", "jobs"),
        ("Failed Jobs", "failed_jobs", "jobs"),
        ("Total Wall Time (5 jobs)", "total_wall_time", "seconds"),
        ("Min Transcription Time", "min_time", "seconds"),
        ("Max Transcription Time", "max_time", "seconds"),
        ("Avg Transcription Time", "avg_time", "seconds"),
    ]
    
    for metric_name, key, unit in metrics:
        val1 = model1_results.get(key, 0)
        val2 = model2_results.get(key, 0)
        
        if unit == "seconds":
            val1_str = f"{int(val1//60)}m {int(val1%60)}s" if val1 > 60 else f"{int(val1)}s"
            val2_str = f"{int(val2//60)}m {int(val2%60)}s" if val2 > 60 else f"{int(val2)}s"
        else:
            val1_str = str(int(val1))
            val2_str = str(int(val2))
        
        print(f"{metric_name:<40} {val1_str:<22} {val2_str}")
        
        # แสดง % difference
        if val1 > 0 and val2 > 0 and unit == "seconds":
            diff_pct = ((val2 - val1) / val1) * 100
            diff_sign = "+" if diff_pct > 0 else ""
            print(f"{'  → Difference':<40} {diff_sign}{diff_pct:.1f}%")
    
    print("")
    print("=" * 85)
    
    # แสดงรายละเอียดแต่ละ job
    print("")
    print("📋 Detailed Job Results:")
    print("")
    
    for i in range(1, 6):
        job1 = next((r for r in model1_results.get("job_details", []) if r.get("job_number") == i), {})
        job2 = next((r for r in model2_results.get("job_details", []) if r.get("job_number") == i), {})
        
        time1 = job1.get("total_time", 0)
        time2 = job2.get("total_time", 0)
        
        time1_str = f"{int(time1//60)}m {int(time1%60)}s" if time1 > 60 else f"{int(time1)}s"
        time2_str = f"{int(time2//60)}m {int(time2%60)}s" if time2 > 60 else f"{int(time2)}s"
        
        status1 = "✅" if job1.get("status") == "completed" else "❌"
        status2 = "✅" if job2.get("status") == "completed" else "❌"
        
        print(f"Job {i}: {status1} {time1_str:<15} vs {status2} {time2_str}")

def main():
    """Main function"""
    print("=" * 85)
    print("🚀 Model Benchmark Tool")
    print("=" * 85)
    print("")
    print("Testing 5 jobs per model:")
    print(f"  1. {MODELS[0]['display_name']}")
    print(f"  2. {MODELS[1]['display_name']}")
    print("")
    print(f"Test file: {TEST_FILE}")
    print("")
    
    # ตรวจสอบว่าไฟล์ test อยู่
    if not os.path.exists(TEST_FILE):
        print(f"❌ Error: Test file not found: {TEST_FILE}")
        sys.exit(1)
    
    all_results = {}
    
    # ทดสอบแต่ละ model
    for model_config in MODELS:
        model_name = model_config["name"]
        display_name = model_config["display_name"]
        
        try:
            # รัน benchmark (ใช้ model_size parameter ใน API request)
            print(f"\n📝 Note: Using model_size='{model_id}' in API request")
            print(f"   Workers will use the model specified in model_size parameter")
            
            # รัน benchmark
            job_results = run_benchmark(model_config, num_jobs=5)
            stats = calculate_statistics(job_results)
            stats["job_details"] = job_results
            all_results[model_name] = stats
            
            # แสดงสถิติ
            print("")
            print("=" * 85)
            print(f"📊 Statistics for {display_name}")
            print("=" * 85)
            print(f"Successful jobs: {stats.get('successful_jobs', 0)}/5")
            print(f"Total wall time (5 jobs): {int(stats.get('total_wall_time', 0)//60)}m {int(stats.get('total_wall_time', 0)%60)}s")
            print(f"Min time: {int(stats.get('min_time', 0))}s")
            print(f"Max time: {int(stats.get('max_time', 0))}s")
            print(f"Avg time: {stats.get('avg_time', 0):.1f}s")
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error testing {display_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # แสดงการเปรียบเทียบ
    if len(all_results) == 2:
        model1_name = MODELS[0]['display_name']
        model2_name = MODELS[1]['display_name']
        print_comparison(
            all_results[MODELS[0]['name']],
            all_results[MODELS[1]['name']],
            model1_name,
            model2_name
        )
    
    # บันทึกผลลัพธ์เป็น JSON
    output_file = f"/tmp/benchmark_results_{int(time.time())}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Results saved to: {output_file}")

if __name__ == "__main__":
    main()
