#!/usr/bin/env python3
"""
Script สำหรับทดสอบ transcription job พร้อมแสดง progress แบบ real-time
"""

import sys
import os
import requests
import time
from datetime import datetime

# เพิ่ม path สำหรับ import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_BASE = "http://localhost:8010/api"

def format_time(seconds):
    """Format seconds to MM:SS or HH:MM:SS"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}h {mins}m {secs}s"

def print_progress_bar(progress, width=50):
    """Print a progress bar"""
    filled = int(width * progress / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {progress}%"

def submit_job(file_path, language="th", model_size="Systran/faster-whisper-small"):
    """Submit a transcription job"""
    print("=" * 85)
    print("=== ส่ง Transcription Job ===")
    print("=" * 85)
    print(f"File: {file_path}")
    print(f"Language: {language}")
    print(f"Model: {model_size}")
    print("")
    
    payload = {
        "file_path": file_path,
        "language": language,
        "model_size": model_size
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/transcribe/",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        task_id = result.get("task_id")
        
        print(f"✅ Job submitted successfully!")
        print(f"   Task ID: {task_id}")
        print(f"   Status: {result.get('status', 'N/A')}")
        print("")
        
        return task_id
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error submitting job: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text[:500]}")
        return None

def monitor_job(task_id, target_time=None, timeout=None):
    """Monitor job progress with real-time updates"""
    print("=" * 85)
    print("=== 📊 Tracking Progress ===")
    print("=" * 85)
    if target_time:
        print(f"Target: ≤ {target_time}s")
    if timeout:
        print(f"Timeout: {timeout}s")
    print("")
    
    start_time = time.time()
    prev_progress = -1
    prev_status = None
    prev_stage = None
    check_count = 0
    
    # Stage descriptions
    stage_descriptions = {
        "queued": "รอคิว",
        "preprocessing": "เตรียมไฟล์และแยกเสียง",
        "extracting_audio": "กำลังแยกเสียงจากวิดีโอ",
        "chunking": "กำลังแบ่งไฟล์เป็นส่วนๆ",
        "transcribing": "กำลังแปลงข้อความ",
        "aggregating": "กำลังรวมผลลัพธ์",
        "finalizing": "กำลังจัดเก็บข้อมูล",
        "completed": "เสร็จสิ้น",
        "failed": "ล้มเหลว"
    }
    
    last_update_time = start_time
    
    try:
        while True:
            check_count += 1
            elapsed = time.time() - start_time
            elapsed_str = format_time(elapsed)
            
            try:
                response = requests.get(
                    f"{API_BASE}/v2/tasks/{task_id}?format=progress",
                    timeout=10
                )
                
                if response.status_code == 200:
                    task = response.json()
                    status = task.get("status", "unknown").lower()
                    progress = task.get("progress", 0)
                    stage = task.get("current_stage", "")
                    stage_desc = task.get("current_stage_description", "")
                    updated_at = task.get("updated_at", "")
                    
                    # แสดง progress เมื่อมีการเปลี่ยนแปลง
                    if (status != prev_status or 
                        progress != prev_progress or 
                        stage != prev_stage or
                        check_count % 10 == 0 or
                        time.time() - last_update_time >= 5):  # Update every 5 seconds minimum
                        
                        # Clear line and print progress
                        status_icon = {
                            "queued": "⏳",
                            "processing": "🔄",
                            "completed": "✅",
                            "failed": "❌"
                        }.get(status, "❓")
                        
                        status_text = {
                            "queued": "รอคิว",
                            "processing": "กำลังดำเนินการ",
                            "completed": "เสร็จสิ้น",
                            "failed": "ล้มเหลว"
                        }.get(status, status.upper())
                        
                        print(f"\r[{elapsed_str}] {status_icon} {status_text:15s} | {print_progress_bar(progress)}", end="", flush=True)
                        
                        if stage:
                            stage_text = stage_descriptions.get(stage, stage)
                            if stage_desc:
                                print(f" | {stage_text}", end="", flush=True)
                        
                        prev_status = status
                        prev_progress = progress
                        prev_stage = stage
                        last_update_time = time.time()
                    
                    # ตรวจสอบว่าเสร็จหรือล้มเหลว
                    if status == "completed":
                        print()  # New line
                        print("")
                        print("=" * 85)
                        print("=== ✅ COMPLETED ===")
                        print("=" * 85)
                        
                        completed_at = task.get("completed_at")
                        created_at = task.get("created_at")
                        
                        if created_at and completed_at:
                            try:
                                created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                completed = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                                total_time = (completed - created).total_seconds()
                                
                                print(f"Task ID: {task_id}")
                                print(f"⏱️  Total time: {format_time(total_time)} ({total_time:.2f}s)")
                                print(f"   ({total_time/60:.2f} minutes)")
                                if target_time:
                                    print(f"🎯 Target: ≤ {target_time}s")
                                    result_icon = "✅ PASSED" if total_time <= target_time else "❌ FAILED"
                                    print(f"📊 Result: {result_icon}")
                                print("")
                            except Exception as e:
                                print(f"⚠️  Error parsing time: {e}")
                        
                        # ดึงผลลัพธ์เต็ม
                        full_response = requests.get(
                            f"{API_BASE}/v2/tasks/{task_id}?format=full",
                            timeout=10
                        )
                        
                        if full_response.status_code == 200:
                            full_task = full_response.json()
                            result = full_task.get("result", {})
                            text = result.get("text", "")
                            segments = result.get("segments", [])
                            
                            print(f"📝 Transcription Result:")
                            print(f"   Text length: {len(text)} characters")
                            print(f"   Segments: {len(segments)} segments")
                            print("")
                            
                            if text:
                                print("📄 Text Preview (first 1000 characters):")
                                print("-" * 85)
                                preview = text[:1000] + ("..." if len(text) > 1000 else "")
                                print(preview)
                                print("-" * 85)
                                print("")
                                
                                # Quality check
                                print("=" * 85)
                                print("=== ✅ Quality Check ===")
                                print("=" * 85)
                                if len(text.strip()) > 100:
                                    print("✅ Text is not empty and has substantial content")
                                else:
                                    print("⚠️  Text seems too short or empty")
                                
                                if segments and len(segments) > 10:
                                    print(f"✅ Has {len(segments)} segments (good granularity)")
                                else:
                                    print(f"⚠️  Only {len(segments)} segments")
                                print("")
                        break
                        
                    elif status == "failed":
                        print()  # New line
                        print("")
                        print("=" * 85)
                        print("=== ❌ FAILED ===")
                        print("=" * 85)
                        error = task.get("error_message", task.get("error", "Unknown error"))
                        print(f"Task ID: {task_id}")
                        print(f"Error: {error}")
                        print("")
                        break
                
                else:
                    print(f"\n⚠️  Failed to get task status: {response.status_code}")
                    break
                    
            except requests.exceptions.RequestException as e:
                print(f"\n⚠️  Request error: {e}")
                time.sleep(2)
                continue
            
            # Timeout check
            if timeout and elapsed > timeout:
                print()  # New line
                print("")
                print(f"⚠️  TIMEOUT (> {format_time(timeout)})")
                print("")
                break
            
            time.sleep(2)  # Check every 2 seconds
            
    except KeyboardInterrupt:
        print()  # New line
        print("")
        print("⚠️  Monitoring interrupted by user")
        print("")
    
    print("=" * 85)
    return task

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/test_transcription_with_progress.py <file_path> [target_time_seconds] [timeout_seconds]")
        print("")
        print("Example:")
        print("  python3 scripts/test_transcription_with_progress.py /uploads/video.wav 120 300")
        print("  # Target: ≤ 120s, Timeout: 300s")
        sys.exit(1)
    
    file_path = sys.argv[1]
    target_time = int(sys.argv[2]) if len(sys.argv) > 2 else None
    timeout = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    # Submit job
    task_id = submit_job(
        file_path=file_path,
        language="th",
        model_size="Systran/faster-whisper-small"
    )
    
    if not task_id:
        print("❌ Failed to submit job")
        sys.exit(1)
    
    # Monitor job
    result = monitor_job(task_id, target_time=target_time, timeout=timeout)
    
    if result and result.get("status") == "completed":
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
