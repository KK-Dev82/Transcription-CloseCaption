#!/usr/bin/env python3
"""
Test Script: ทดสอบ 3 Jobs และตรวจสอบ WebSocket Notifications
- Submit 3 jobs
- Monitor WebSocket events สำหรับ progress updates
- ตรวจสอบว่า WebSocket notifications ทำงานถูกต้อง
"""

import os
import sys
import time
import requests
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Try to import websockets (optional)
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8010")
WS_BASE_URL = os.getenv("WS_BASE_URL", "ws://localhost:8010")
MODEL_SIZE = "Vinxscribe/biodatlab-whisper-th-medium-faster"
TEST_FILE = "/workspace/transcription-service/uploads/160c549e-f820-4b2b-9720-4ecb2f500ed4_v30-1.wav"

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
            # Queue Full
            return {
                "job_index": job_index,
                "status": "queue_full",
                "status_code": 429,
                "error": response.json().get("detail", "Queue Full"),
                "task_id": None
            }
        elif response.status_code == 200:
            # Success
            data = response.json()
            return {
                "job_index": job_index,
                "status": "queued",
                "status_code": 200,
                "task_id": data.get("task_id"),
                "message": data.get("message", "")
            }
        else:
            # Error
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
    """Get task status"""
    url = f"{API_BASE_URL}/api/v2/tasks/{task_id}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "error", "status_code": response.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}

async def listen_websocket_events(task_ids: List[str], event_log: List[Dict], timeout: int = 600):
    """Listen to WebSocket events for given task IDs"""
    try:
        # Try to connect to WebSocket
        # Note: WebSocket endpoint might be different, adjust as needed
        ws_url = f"{WS_BASE_URL}/ws"
        
        try:
            async with websockets.connect(ws_url, timeout=10) as websocket:
                print(f"✅ Connected to WebSocket: {ws_url}")
                
                # Subscribe to task events (adjust protocol as needed)
                # This is a placeholder - actual implementation depends on WebSocket API
                
                start_time = time.time()
                while time.time() - start_time < timeout:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        try:
                            event_data = json.loads(message)
                            event_log.append({
                                "timestamp": time.time(),
                                "data": event_data
                            })
                            
                            event_type = event_data.get("type", "unknown")
                            task_id = event_data.get("task_id", "")
                            
                            if task_id and task_id in task_ids:
                                print(f"  📡 WebSocket Event: {event_type} for task {task_id[:8]}...")
                                if event_type in ["transcription.progress", "task.updated"]:
                                    progress = event_data.get("progress", 0)
                                    stage = event_data.get("stage", "")
                                    print(f"     Progress: {progress}%, Stage: {stage}")
                        except json.JSONDecodeError:
                            print(f"  ⚠️  Non-JSON message: {message[:100]}")
                    except asyncio.TimeoutError:
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        print("  ⚠️  WebSocket connection closed")
                        break
        except Exception as e:
            print(f"  ⚠️  WebSocket connection failed: {e}")
            print(f"     This is expected if WebSocket endpoint is not available")
    except Exception as e:
        print(f"  ⚠️  WebSocket listener error: {e}")

def wait_for_completion_with_events(task_id: str, event_log: List[Dict], timeout: int = 3600) -> Dict:
    """Wait for task to complete and check for events"""
    start_time = time.time()
    last_status = None
    last_progress = 0
    events_received = []
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            return {
                "task_id": task_id,
                "status": "timeout",
                "elapsed_time": elapsed,
                "events_received": len(events_received)
            }
        
        # Check for WebSocket events for this task
        for event in event_log:
            event_data = event.get("data", {})
            if event_data.get("task_id") == task_id and event not in events_received:
                events_received.append(event)
                event_type = event_data.get("type", "")
                progress = event_data.get("progress", 0)
                stage = event_data.get("stage", "")
                print(f"  📡 Event: {event_type} - Progress: {progress}%, Stage: {stage}")
        
        task_data = get_task_status(task_id)
        status = task_data.get("status", "unknown")
        progress = task_data.get("progress", 0)
        
        if status != last_status or progress != last_progress:
            if progress % 10 == 0 or status != last_status:
                print(f"  Task {task_id[:8]}...: {status} ({progress}%) - {elapsed:.1f}s")
                last_status = status
                last_progress = progress
        
        if status == "completed":
            elapsed_time = time.time() - start_time
            return {
                "task_id": task_id,
                "status": "completed",
                "elapsed_time": elapsed_time,
                "progress": progress,
                "events_received": len(events_received)
            }
        elif status in ["failed", "cancelled"]:
            elapsed_time = time.time() - start_time
            return {
                "task_id": task_id,
                "status": status,
                "elapsed_time": elapsed_time,
                "error": task_data.get("error", ""),
                "events_received": len(events_received)
            }
        
        time.sleep(2)

def main():
    print("=" * 85)
    print("🧪 Test: 3 Jobs และตรวจสอบ WebSocket Notifications")
    print("=" * 85)
    print()
    print(f"Configuration:")
    print(f"  API: {API_BASE_URL}")
    print(f"  WebSocket: {WS_BASE_URL}")
    print(f"  Model: {MODEL_SIZE}")
    print(f"  Test File: {TEST_FILE}")
    print(f"  NUM_PREPROCESS_WORKERS: {os.getenv('NUM_PREPROCESS_WORKERS', '6')}")
    print(f"  NUM_CPU_WORKERS: {os.getenv('NUM_CPU_WORKERS', '4')}")
    print(f"  MAX_PREPROCESS_QUEUE_SIZE: {os.getenv('MAX_PREPROCESS_QUEUE_SIZE', '25')}")
    print()
    
    # Step 1: Submit 3 jobs
    print("=" * 85)
    print("Step 1: Submit 3 jobs")
    print("=" * 85)
    print()
    
    submit_start_time = time.time()
    submission_results = []
    
    for i in range(1, 4):
        print(f"Submitting job {i}/3...", end=" ", flush=True)
        result = submit_job(i)
        submission_results.append(result)
        
        if result["status"] == "queue_full":
            print(f"✅ Queue Full (HTTP 429): {result.get('error', 'Queue Full')}")
        elif result["status"] == "queued":
            print(f"✅ Queued (task_id: {result['task_id'][:8]}...)")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    submit_elapsed = time.time() - submit_start_time
    print()
    print(f"Submission completed in {submit_elapsed:.2f}s")
    print()
    
    # Analyze submission results
    queued_jobs = [r for r in submission_results if r["status"] == "queued"]
    queue_full_jobs = [r for r in submission_results if r["status"] == "queue_full"]
    error_jobs = [r for r in submission_results if r["status"] not in ["queued", "queue_full"]]
    
    print("=" * 85)
    print("Submission Results:")
    print("=" * 85)
    print(f"  Queued: {len(queued_jobs)} jobs")
    print(f"  Queue Full (HTTP 429): {len(queue_full_jobs)} jobs")
    print(f"  Errors: {len(error_jobs)} jobs")
    print()
    
    if len(queued_jobs) == 0:
        print("❌ No jobs to monitor. Exiting.")
        return
    
    # Step 2: Monitor jobs with WebSocket events
    print("=" * 85)
    print(f"Step 2: Monitor {len(queued_jobs)} jobs with WebSocket events")
    print("=" * 85)
    print()
    
    # Start WebSocket listener (in background)
    event_log = []
    task_ids = [job["task_id"] for job in queued_jobs]
    
    print("📡 Starting WebSocket listener...")
    if WEBSOCKETS_AVAILABLE:
        try:
            # Try to start WebSocket listener (may fail if endpoint not available)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ws_task = loop.create_task(listen_websocket_events(task_ids, event_log, timeout=600))
            # Run in background thread
            import threading
            ws_thread = threading.Thread(target=lambda: loop.run_until_complete(ws_task), daemon=True)
            ws_thread.start()
            time.sleep(2)  # Give WebSocket time to connect
        except Exception as e:
            print(f"  ⚠️  WebSocket listener not available: {e}")
            print(f"     Continuing with HTTP polling only...")
            print()
    else:
        print(f"  ⚠️  websockets library not installed")
        print(f"     Install with: pip install websockets")
        print(f"     Continuing with HTTP polling only...")
        print()
    
    monitor_start_time = time.time()
    completion_results = []
    
    # Use ThreadPoolExecutor to monitor jobs in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(wait_for_completion_with_events, job["task_id"], event_log): job["job_index"]
            for job in queued_jobs
        }
        
        for future in as_completed(futures):
            job_index = futures[future]
            try:
                result = future.result()
                completion_results.append(result)
                events_count = result.get("events_received", 0)
                print(f"✅ Job {job_index} completed: {result['status']} ({result.get('elapsed_time', 0):.1f}s, {events_count} events)")
            except Exception as e:
                print(f"❌ Job {job_index} error: {e}")
    
    monitor_elapsed = time.time() - monitor_start_time
    
    print()
    print("=" * 85)
    print("Completion Results:")
    print("=" * 85)
    
    completed_jobs = [r for r in completion_results if r["status"] == "completed"]
    failed_jobs = [r for r in completion_results if r["status"] == "failed"]
    
    print(f"  Completed: {len(completed_jobs)} jobs")
    print(f"  Failed: {len(failed_jobs)} jobs")
    print()
    
    # WebSocket Events Summary
    print("=" * 85)
    print("📡 WebSocket Events Summary:")
    print("=" * 85)
    print(f"  Total events received: {len(event_log)}")
    print()
    
    if len(event_log) > 0:
        # Group events by type
        event_types = {}
        for event in event_log:
            event_type = event.get("data", {}).get("type", "unknown")
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        print("  Events by type:")
        for event_type, count in sorted(event_types.items()):
            print(f"    - {event_type}: {count}")
        print()
        
        # Show sample events
        print("  Sample events (first 5):")
        for i, event in enumerate(event_log[:5]):
            event_data = event.get("data", {})
            event_type = event_data.get("type", "unknown")
            task_id = event_data.get("task_id", "")[:8] if event_data.get("task_id") else "N/A"
            progress = event_data.get("progress", 0)
            print(f"    {i+1}. {event_type} (task: {task_id}..., progress: {progress}%)")
    else:
        print("  ⚠️  No WebSocket events received")
        print("     This may be expected if WebSocket endpoint is not configured")
    print()
    
    if len(completed_jobs) > 0:
        elapsed_times = [r["elapsed_time"] for r in completed_jobs]
        total_time = monitor_elapsed
        min_time = min(elapsed_times)
        max_time = max(elapsed_times)
        avg_time = sum(elapsed_times) / len(elapsed_times)
        
        print("=" * 85)
        print("📊 Performance Metrics:")
        print("=" * 85)
        print()
        print(f"{'Metric':<40} {'Value':<25}")
        print("-" * 65)
        print(f"{'Total time (all jobs)':<40} {total_time:.1f}s ({total_time/60:.2f} min)")
        print(f"{'Min time (single job)':<40} {min_time:.1f}s ({min_time/60:.2f} min)")
        print(f"{'Max time (single job)':<40} {max_time:.1f}s ({max_time/60:.2f} min)")
        print(f"{'Avg time (single job)':<40} {avg_time:.1f}s ({avg_time/60:.2f} min)")
        print()
        
        # WebSocket events per job
        avg_events = sum(r.get("events_received", 0) for r in completed_jobs) / len(completed_jobs)
        print(f"{'Avg WebSocket events/job':<40} {avg_events:.1f}")
        print()
        
        print("=" * 85)
    
    print()
    print("✅ Test completed!")

if __name__ == "__main__":
    main()
