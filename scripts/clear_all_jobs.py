#!/usr/bin/env python3
"""
Script สำหรับยกเลิก (cancel) jobs ทั้งหมดที่อยู่ในสถานะ QUEUED หรือ PROCESSING
และ clear queues ใน Redis
"""

import sys
import os
from pathlib import Path

# เพิ่ม project root เพื่อ import app
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

import requests
import redis
from dotenv import load_dotenv

# โหลด environment variables
load_dotenv('.env.runpod')

API_BASE = "http://localhost:8010/api"
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

def clear_redis_queues():
    """Clear all RQ queues in Redis"""
    print("=" * 85)
    print("=== Clearing Redis Queues ===")
    print("=" * 85)
    print("")
    
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        
        num_gpus = int(os.getenv('NUM_GPUS', '2'))
        queues = [
            'transcription_preprocess',
            'transcription_priority',
            'transcription_preprocess_video_record',
            'transcription_cpu',
            'transcription_aggregator'
        ] + [f'transcription_gpu{i}' for i in range(num_gpus)]
        queues += [f'transcription_gpu_record_{i}' for i in range(num_gpus)]
        queues += [f'transcription_gpu_upload_{i}' for i in range(num_gpus)]
        
        total_cleared = 0
        for queue_name in queues:
            queue_key = f"rq:queue:{queue_name}"
            length = r.llen(queue_key)
            if length > 0:
                r.delete(queue_key)
                print(f"✅ Cleared {queue_name}: {length} jobs")
                total_cleared += length
            else:
                print(f"✅ {queue_name}: already empty")
        
        # Clear scheduled jobs
        scheduled_key = "rq:scheduled"
        scheduled_count = r.zcard(scheduled_key)
        if scheduled_count > 0:
            r.delete(scheduled_key)
            print(f"✅ Cleared scheduled jobs: {scheduled_count}")
            total_cleared += scheduled_count
        
        # Clear started jobs registry
        started_key = "rq:started"
        started_count = r.zcard(started_key)
        if started_count > 0:
            r.delete(started_key)
            print(f"✅ Cleared started jobs: {started_count}")
        
        print("")
        print(f"📊 Total cleared from queues: {total_cleared} jobs")
        print("")
        
    except Exception as e:
        print(f"❌ Error clearing Redis queues: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def update_task_status_to_failed(task_id, reason="Cancelled by admin"):
    """Update task status to failed"""
    try:
        from datetime import datetime, timezone
        
        # Try SQLite storage first
        try:
            from app.utils.sqlite_storage import SQLiteStorage
            storage = SQLiteStorage()
            
            # Load current task
            task = storage.load_transcription(task_id, skip_migration=True)
            
            if task:
                # Update status
                task["status"] = "failed"
                task["error_message"] = reason
                task["updated_at"] = datetime.now(timezone.utc).isoformat()
                task["current_stage"] = "cancelled"
                task["current_stage_description"] = reason
                task["progress"] = 0
                
                # Save updated task
                storage.save_transcription(task_id, task)
                return True
        except Exception as sqlite_error:
            # Fallback to JSON storage
            pass
        
        # Try JSON storage as fallback
        try:
            from app.utils.json_storage import JSONStorage
            json_storage = JSONStorage()
            task_dir = json_storage.storage_dir / "transcriptions" / task_id
            metadata_path = task_dir / "metadata.json"
            
            if metadata_path.exists():
                import json
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    task_data = json.load(f)
                
                task_data["status"] = "failed"
                task_data["error_message"] = reason
                task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                task_data["current_stage"] = "cancelled"
                task_data["current_stage_description"] = reason
                
                json_storage.save_transcription(task_id, task_data)
                return True
        except Exception as json_error:
            pass
        
        # If both fail, try direct SQLite update
        try:
            from app.utils.sqlite_storage import SQLiteStorage
            storage = SQLiteStorage()
            
            # Direct SQL update as last resort
            conn = storage._get_connection()
            conn.execute("""
                UPDATE transcriptions 
                SET status = ?, 
                    error_message = ?, 
                    updated_at = ?,
                    current_stage = ?,
                    current_stage_description = ?,
                    progress = 0
                WHERE task_id = ?
            """, (
                "failed",
                reason,
                datetime.now(timezone.utc).isoformat(),
                "cancelled",
                reason,
                task_id
            ))
            conn.commit()
            return True
        except Exception as direct_error:
            return False
        
    except Exception as e:
        return False

def cancel_all_jobs():
    """Cancel all QUEUED and PROCESSING jobs"""
    print("=" * 85)
    print("=== Cancelling All QUEUED and PROCESSING Jobs ===")
    print("=" * 85)
    print("")
    
    try:
        # ดึง tasks ทั้งหมด (ใช้ pagination)
        all_tasks = []
        limit = 100
        offset = 0
        
        while True:
            response = requests.get(
                f"{API_BASE}/v2/tasks/",
                params={"limit": limit, "offset": offset, "sort": "created_at", "order": "desc"},
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"⚠️  Failed to get tasks: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
            
            data = response.json()
            tasks = data.get("tasks", [])
            
            if not tasks:
                break
            
            all_tasks.extend(tasks)
            
            # ถ้าได้ tasks น้อยกว่า limit แสดงว่าเป็นหน้าสุดท้าย
            if len(tasks) < limit:
                break
            
            offset += limit
        
        tasks = all_tasks
        
        # รวม queued, pending, processing — ทั้งหมดที่ยังไม่เสร็จ
        queued = [t for t in tasks if t.get("status", "").lower() in ("queued", "pending")]
        processing = [t for t in tasks if t.get("status", "").lower() == "processing"]
        
        total_to_cancel = len(queued) + len(processing)
        
        print(f"📊 Found:")
        print(f"   QUEUED/PENDING: {len(queued)} jobs")
        print(f"   PROCESSING: {len(processing)} jobs")
        print(f"   Total to cancel: {total_to_cancel} jobs")
        print("")
        
        if total_to_cancel == 0:
            print("✅ No jobs to cancel")
            return True
        
        # Cancel QUEUED jobs
        cancelled_count = 0
        failed_count = 0
        
        print("🔄 Cancelling QUEUED jobs...")
        for i, task in enumerate(queued, 1):
            task_id = task.get("task_id", "")
            if task_id:
                if update_task_status_to_failed(task_id, "Cancelled: Job was in queue"):
                    cancelled_count += 1
                    if i % 10 == 0:
                        print(f"   Progress: {i}/{len(queued)}")
                else:
                    failed_count += 1
        
        print(f"✅ Cancelled {cancelled_count}/{len(queued)} QUEUED jobs")
        if failed_count > 0:
            print(f"⚠️  Failed to cancel {failed_count} QUEUED jobs")
        print("")
        
        # Cancel PROCESSING jobs
        cancelled_processing = 0
        failed_processing = 0
        
        print("🔄 Cancelling PROCESSING jobs...")
        for i, task in enumerate(processing, 1):
            task_id = task.get("task_id", "")
            if task_id:
                if update_task_status_to_failed(task_id, "Cancelled: Job was processing"):
                    cancelled_processing += 1
                    if i % 10 == 0:
                        print(f"   Progress: {i}/{len(processing)}")
                else:
                    failed_processing += 1
        
        print(f"✅ Cancelled {cancelled_processing}/{len(processing)} PROCESSING jobs")
        if failed_processing > 0:
            print(f"⚠️  Failed to cancel {failed_processing} PROCESSING jobs")
        print("")
        
        print("=" * 85)
        print("=== Summary ===")
        print("=" * 85)
        print(f"Total cancelled: {cancelled_count + cancelled_processing}")
        print(f"   QUEUED: {cancelled_count}")
        print(f"   PROCESSING: {cancelled_processing}")
        if failed_count + failed_processing > 0:
            print(f"Failed to cancel: {failed_count + failed_processing}")
        print("")
        
        return True
        
    except Exception as e:
        print(f"❌ Error cancelling jobs: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🚀 Starting Job Cleanup")
    print("📅 {}".format(__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    print("")
    
    # Step 1: Clear Redis queues
    if not clear_redis_queues():
        print("❌ Failed to clear Redis queues")
        return 1
    
    # Step 2: Cancel all QUEUED and PROCESSING jobs
    if not cancel_all_jobs():
        print("❌ Failed to cancel jobs")
        return 1
    
    print("=" * 85)
    print("=== ✅ Cleanup Complete ===")
    print("=" * 85)
    print("")
    print("💡 You can now start new transcription jobs")
    print("")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
