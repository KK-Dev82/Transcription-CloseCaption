#!/usr/bin/env python3
"""
ทดสอบ Transcription Service ด้วย Load Testing
ทดสอบด้วย 1, 5, และ 25 jobs
"""
import requests
import json
import time
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

API_BASE = "http://localhost:8010/api"

def submit_job(file_path: str, language: str = "th", model_size: str = "base") -> Optional[Dict]:
    """Submit a transcription job"""
    payload = {
        "file_path": file_path,
        "language": language,
        "model_size": model_size,
        "chunk_duration": 30
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/transcribe/",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Detail: {error_detail}")
            except:
                print(f"   Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def check_task_status(task_id: str, format: str = "minimal") -> Optional[Dict]:
    """
    Check transcription task status
    
    Args:
        task_id: Task ID to check
        format: Response format - "minimal" (fast polling), "progress" (detailed), or "full" (complete data)
    
    Returns:
        Task status data or None if error
    """
    try:
        response = requests.get(
            f"{API_BASE}/v2/tasks/{task_id}?format={format}",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return None

def wait_for_completion(task_ids: List[str], timeout_minutes: int = 60) -> Dict[str, Dict]:
    """Wait for all tasks to complete"""
    results = {task_id: {"status": "unknown", "completed_at": None} for task_id in task_ids}
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60
    
    print(f"\n⏳ รอให้ jobs เสร็จสิ้น (timeout: {timeout_minutes} นาที)...")
    print("=" * 80)
    
    completed_count = 0
    failed_count = 0
    
    while True:
        elapsed = time.time() - start_time
        
        if elapsed > timeout_seconds:
            print(f"\n⏰ Timeout! เกิน {timeout_minutes} นาที")
            break
        
        # Check all tasks
        for task_id in task_ids:
            if results[task_id]["status"] in ["completed", "failed"]:
                continue
            
            # Use minimal format for fast polling
            status_data = check_task_status(task_id, format="minimal")
            
            if status_data:
                status = status_data.get("status", "unknown")
                progress = status_data.get("progress", 0)
                updated_at = status_data.get("updated_at", "")
                
                # Log every check for debugging
                elapsed_str = f"{int(elapsed//60)}m {int(elapsed%60):02d}s"
                print(f"[{elapsed_str}] 🔍 Checking task {task_id[:8]}: status={status}, progress={progress}%")
                
                # Update results
                old_status = results[task_id].get("status", "unknown")
                old_progress = results[task_id].get("progress", 0)
                
                results[task_id]["status"] = status
                results[task_id]["progress"] = progress
                results[task_id]["data"] = status_data
                results[task_id]["updated_at"] = updated_at
                
                # Log status change
                if old_status != status or old_progress != progress:
                    print(f"   📝 Status changed: {old_status} ({old_progress}%) → {status} ({progress}%)")
                
                if status == "completed":
                    if results[task_id]["completed_at"] is None:
                        print(f"   ✅ Detected completion! Verifying with full endpoint...")
                        # Verify with full endpoint to get complete data
                        full_data = check_task_status(task_id, format="full")
                        if full_data:
                            results[task_id]["data"] = full_data
                            completed_at = full_data.get("completed_at")
                            full_text = full_data.get("results", {}).get("full_text", "")
                            print(f"   ✅ Verified: completed_at={completed_at}, text_length={len(full_text)}")
                            results[task_id]["completed_at"] = time.time()
                        completed_count += 1
                        elapsed_time = time.time() - start_time
                        elapsed_min = int(elapsed_time // 60)
                        elapsed_sec = int(elapsed_time % 60)
                        print(f"✅ Task {task_id[:8]} completed in {elapsed_min}m {elapsed_sec}s ({elapsed_time:.1f}s)")
                elif status == "failed":
                    if results[task_id]["completed_at"] is None:
                        print(f"   ❌ Detected failure! Getting error details...")
                        # Get error message from full endpoint
                        full_data = check_task_status(task_id, format="full")
                        if full_data:
                            results[task_id]["data"] = full_data
                            error = full_data.get("error_message") or full_data.get("error") or "Unknown error"
                        else:
                            error = status_data.get("error", "Unknown error")
                        print(f"   ❌ Error: {error}")
                        results[task_id]["completed_at"] = time.time()
                        failed_count += 1
                        elapsed_time = time.time() - start_time
                        elapsed_min = int(elapsed_time // 60)
                        elapsed_sec = int(elapsed_time % 60)
                        print(f"❌ Task {task_id[:8]} failed after {elapsed_min}m {elapsed_sec}s: {error}")
            else:
                # Log API error
                elapsed_str = f"{int(elapsed//60)}m {int(elapsed%60):02d}s"
                print(f"[{elapsed_str}] ⚠️  Failed to get status for task {task_id[:8]} (API error)")
        
        # Print progress (show every check)
        total = len(task_ids)
        pending = total - completed_count - failed_count
        
        if pending > 0:
            elapsed_str = f"{int(elapsed//60)}m {int(elapsed%60):02d}s"
            print(f"[{elapsed_str}] 📊 Status: {completed_count} completed, {failed_count} failed, {pending} pending")
            
            # Show individual task progress
            for task_id in task_ids:
                if results[task_id]["status"] not in ["completed", "failed"]:
                    status = results[task_id].get("status", "unknown")
                    progress = results[task_id].get("progress", 0)
                    print(f"   Task {task_id[:8]}: {status} ({progress}%)")
        
        # Check if all done
        if completed_count + failed_count == total:
            print("\n")
            break
        
        time.sleep(2)  # Poll every 2 seconds
    
    total_time = time.time() - start_time
    return results, total_time

def test_load(num_jobs: int, audio_file: str) -> Dict:
    """Test transcription with specified number of jobs"""
    print("\n" + "=" * 80)
    print(f"🧪 ทดสอบ Transcription: {num_jobs} jobs")
    print("=" * 80)
    print(f"📁 Audio file: {audio_file}")
    print(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if file exists
    if not Path(audio_file).exists():
        print(f"❌ File not found: {audio_file}")
        return {"success": False, "error": "File not found"}
    
    # Submit jobs
    print(f"📤 Submitting {num_jobs} jobs...")
    task_ids = []
    submission_times = []
    
    for i in range(num_jobs):
        print(f"   Job {i+1}/{num_jobs}...", end=" ", flush=True)
        submit_start = time.time()
        result = submit_job(audio_file)
        submit_end = time.time()
        
        if result and result.get("task_id"):
            task_id = result["task_id"]
            task_ids.append(task_id)
            submission_times.append(submit_end - submit_start)
            print(f"✅ {task_id[:8]}... ({submission_times[-1]:.2f}s)")
        else:
            print(f"❌ Failed")
        
        # Small delay between submissions
        if i < num_jobs - 1:
            time.sleep(0.5)
    
    if not task_ids:
        print("\n❌ No jobs submitted successfully!")
        return {"success": False, "error": "No jobs submitted"}
    
    print(f"\n✅ Submitted {len(task_ids)} jobs successfully")
    print(f"   Average submission time: {sum(submission_times)/len(submission_times):.2f}s")
    
    # Wait for completion
    results, total_time = wait_for_completion(task_ids, timeout_minutes=60)
    
    # Calculate statistics
    completed = [r for r in results.values() if r["status"] == "completed"]
    failed = [r for r in results.values() if r["status"] == "failed"]
    pending = [r for r in results.values() if r["status"] not in ["completed", "failed"]]
    
    completion_times = []
    for result in completed:
        if result.get("completed_at"):
            completion_times.append(result["completed_at"])
    
    avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 สรุปผลการทดสอบ")
    print("=" * 80)
    print(f"Total jobs: {num_jobs}")
    print(f"✅ Completed: {len(completed)}")
    print(f"❌ Failed: {len(failed)}")
    print(f"⏳ Pending: {len(pending)}")
    print(f"⏱️  Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    
    if completion_times:
        min_time = min(completion_times)
        max_time = max(completion_times)
        print(f"📈 Completion times:")
        print(f"   Min: {min_time:.1f}s")
        print(f"   Max: {max_time:.1f}s")
        print(f"   Avg: {avg_completion_time:.1f}s")
        if len(completion_times) > 1:
            throughput = len(completed) / max_time if max_time > 0 else 0
            print(f"   Throughput: {throughput:.2f} jobs/second")
    
    print("=" * 80)
    
    return {
        "success": True,
        "num_jobs": num_jobs,
        "total_jobs": len(task_ids),
        "completed": len(completed),
        "failed": len(failed),
        "pending": len(pending),
        "total_time": total_time,
        "results": results
    }

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/test_transcription_load.py <audio_file> [num_jobs]")
        print("\nExample:")
        print("  python3 scripts/test_transcription_load.py uploads/audio_xxx.wav 1")
        print("  python3 scripts/test_transcription_load.py uploads/audio_xxx.wav 5")
        print("  python3 scripts/test_transcription_load.py uploads/audio_xxx.wav 25")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    
    # Test with 1, 5, and 25 jobs
    test_configs = [1, 5, 25]
    
    if len(sys.argv) > 2:
        # Custom number of jobs
        test_configs = [int(sys.argv[2])]
    
    print("\n" + "=" * 80)
    print("🚀 Transcription Load Testing")
    print("=" * 80)
    print(f"Audio file: {audio_file}")
    print(f"Test configurations: {test_configs}")
    print("=" * 80)
    
    all_results = []
    
    for num_jobs in test_configs:
        result = test_load(num_jobs, audio_file)
        all_results.append(result)
        
        # Wait a bit between tests
        if num_jobs != test_configs[-1]:
            print("\n⏸️  Waiting 30 seconds before next test...\n")
            time.sleep(30)
    
    # Final summary
    print("\n" + "=" * 80)
    print("📋 สรุปผลการทดสอบทั้งหมด")
    print("=" * 80)
    
    for i, result in enumerate(all_results):
        if result.get("success"):
            num_jobs = result.get("num_jobs", 0)
            completed = result.get("completed", 0)
            failed = result.get("failed", 0)
            total_time = result.get("total_time", 0)
            
            print(f"\nTest {i+1}: {num_jobs} jobs")
            print(f"  ✅ Completed: {completed}/{num_jobs}")
            print(f"  ❌ Failed: {failed}/{num_jobs}")
            print(f"  ⏱️  Total time: {total_time/60:.1f} minutes")
            
            if completed > 0 and total_time > 0:
                throughput = completed / total_time
                print(f"  📈 Throughput: {throughput:.3f} jobs/second ({throughput*60:.2f} jobs/minute)")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
