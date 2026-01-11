#!/usr/bin/env python3
"""
Benchmark Script: เปรียบเทียบประสิทธิภาพระหว่าง 2 models (Simplified Version)
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
        "display_name": "Vinxscribe Medium (Thai)"
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
        "model_size": model_size
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
        
        # แสดง progress เมื่อเปลี่ยน >= 10%
        if progress >= last_progress + 10:
            stage = task.get("current_stage", "N/A")
            print(f"      [{int(elapsed)}s] {progress}% | {stage}")
            last_progress = progress
        
        if status == "completed":
            return task
        elif status == "failed":
            error = task.get("error_message", "Unknown error")
            raise Exception(f"Task failed: {error}")
        
        time.sleep(3)

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
        
        return {
            "total_time": total_time,
        }
    except Exception as e:
        print(f"      ⚠️  Error calculating timing: {e}")
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
    
    results = []
    start_wall_time = time.time()
    
    # ส่ง jobs ทั้งหมดพร้อมกัน
    task_ids = []
    print(f"\n📤 Submitting {num_jobs} jobs...")
    for i in range(1, num_jobs + 1):
        try:
            task_id = submit_job(TEST_FILE, model_id, language="th")
            task_ids.append(task_id)
            print(f"   Job {i}: {task_id}")
        except Exception as e:
            print(f"   ❌ Job {i} failed to submit: {e}")
            task_ids.append(None)
    
    # รอจนทุก job เสร็จ
    print(f"\n⏳ Waiting for {num_jobs} jobs to complete...")
    completed_count = 0
    
    for i, task_id in enumerate(task_ids, 1):
        if task_id is None:
            results.append({
                "task_id": f"failed_submit_{i}",
                "status": "failed",
                "error": "Failed to submit",
                "job_number": i,
                "total_time": 0
            })
            continue
        
        try:
            print(f"\n   Job {i}/{num_jobs} ({task_id[:8]}...):")
            task = wait_for_completion(task_id, timeout=600)
            
            timing = calculate_timing(task)
            timing["task_id"] = task_id
            timing["status"] = task.get("status")
            timing["job_number"] = i
            
            total_time = timing.get("total_time", 0)
            print(f"      ✅ Completed in {int(total_time//60)}m {int(total_time%60)}s ({int(total_time)}s)")
            
            results.append(timing)
            completed_count += 1
            
        except Exception as e:
            print(f"      ❌ Failed: {e}")
            results.append({
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
                "job_number": i,
                "total_time": 0
            })
    
    end_wall_time = time.time()
    total_wall_time = end_wall_time - start_wall_time
    
    print(f"\n✅ Completed {completed_count}/{num_jobs} jobs")
    print(f"   Total wall time: {int(total_wall_time//60)}m {int(total_wall_time%60)}s")
    
    return results

def calculate_statistics(results: List[Dict]) -> Dict:
    """คำนวณสถิติ"""
    successful_results = [r for r in results if r.get("total_time", 0) > 0]
    
    if not successful_results:
        return {}
    
    total_times = [r["total_time"] for r in successful_results]
    
    stats = {
        "num_jobs": len(results),
        "successful_jobs": len(successful_results),
        "failed_jobs": len(results) - len(successful_results),
        "total_wall_time": max([r["total_time"] for r in results if r.get("total_time", 0) > 0]) if successful_results else 0,  # max time
        "min_time": min(total_times) if total_times else 0,
        "max_time": max(total_times) if total_times else 0,
        "avg_time": sum(total_times) / len(total_times) if total_times else 0,
    }
    
    return stats

def print_comparison(model1_stats: Dict, model2_stats: Dict, model1_name: str, model2_name: str):
    """แสดงผลการเปรียบเทียบ"""
    print("")
    print("=" * 85)
    print("📊 BENCHMARK RESULTS COMPARISON")
    print("=" * 85)
    print("")
    
    # สร้างตารางเปรียบเทียบ
    print(f"{'Metric':<45} {model1_name[:18]:<20} {model2_name[:20]}")
    print("-" * 85)
    
    metrics = [
        ("Successful Jobs", "successful_jobs", "jobs"),
        ("Failed Jobs", "failed_jobs", "jobs"),
        ("Total Wall Time (max of 5 jobs)", "total_wall_time", "seconds"),
        ("Min Transcription Time", "min_time", "seconds"),
        ("Max Transcription Time", "max_time", "seconds"),
        ("Avg Transcription Time", "avg_time", "seconds"),
    ]
    
    for metric_name, key, unit in metrics:
        val1 = model1_stats.get(key, 0)
        val2 = model2_stats.get(key, 0)
        
        if unit == "seconds":
            val1_str = f"{int(val1//60)}m {int(val1%60)}s ({int(val1)}s)" if val1 > 60 else f"{int(val1)}s"
            val2_str = f"{int(val2//60)}m {int(val2%60)}s ({int(val2)}s)" if val2 > 60 else f"{int(val2)}s"
        else:
            val1_str = str(int(val1))
            val2_str = str(int(val2))
        
        print(f"{metric_name:<45} {val1_str:<20} {val2_str}")
        
        # แสดง % difference
        if val1 > 0 and val2 > 0 and unit == "seconds":
            diff_pct = ((val2 - val1) / val1) * 100
            diff_sign = "+" if diff_pct > 0 else ""
            diff_color = "🔴" if diff_pct > 10 else "🟡" if diff_pct > 5 else "🟢"
            print(f"  {diff_color} Difference: {diff_sign}{diff_pct:.1f}%")
    
    print("")
    print("=" * 85)

def main():
    """Main function"""
    print("=" * 85)
    print("🚀 Model Benchmark Tool")
    print("=" * 85)
    print("")
    print("Testing 5 jobs per model (concurrent):")
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
            print(f"Total wall time (max of 5 jobs): {int(stats.get('total_wall_time', 0)//60)}m {int(stats.get('total_wall_time', 0)%60)}s")
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
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n💾 Results saved to: {output_file}")

if __name__ == "__main__":
    main()
