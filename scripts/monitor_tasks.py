#!/usr/bin/env python3
"""
Monitor transcription tasks progress and calculate completion time
"""
import os
import sys
import time
import json
import redis
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('.env.runpod')
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

def get_task_status(task_id):
    """Get task status from JSON storage or Redis"""
    # Try JSON storage first (multiple possible paths)
    json_paths = [
        f"/workspace/transcription-service/storage/{task_id}.json",
        f"/workspace/transcription-service/storage/transcriptions/{task_id}/metadata.json",
        f"/workspace/transcription-service/storage/transcriptions/{task_id}.json"
    ]
    
    for json_file in json_paths:
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    task = json.load(f)
                return task
            except:
                pass
    
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/monitor_tasks.py <task_id1> [task_id2] ...")
        sys.exit(1)
    
    task_ids = sys.argv[1:]
    
    try:
        conn = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
        conn.ping()
    except Exception as e:
        print(f"❌ Cannot connect to Redis: {e}")
        sys.exit(1)
    
    print("=" * 85)
    print("=== ติดตาม Progress ของ Tasks ===")
    print("=" * 85)
    print("")
    
    # เก็บ start time และสถานะ
    start_times = {}
    prev_done = {}
    completed_times = {}
    
    for task_id in task_ids:
        task_data = get_task_status(task_id)
        if task_data and task_data.get('created_at'):
            try:
                created_at = task_data['created_at']
                # Handle different datetime formats
                if 'T' in created_at:
                    created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    created = datetime.fromtimestamp(float(created_at))
                start_times[task_id] = created.timestamp()
            except Exception as e:
                print(f"⚠️  Cannot parse created_at for {task_id[:8]}...: {e}")
                start_times[task_id] = time.time()
        else:
            start_times[task_id] = time.time()
        
        prev_done[task_id] = -1
        completed_times[task_id] = None
    
    check_count = 0
    
    try:
        while True:
            check_count += 1
            current_time = time.time()
            all_completed = True
            
            # Clear previous line
            if check_count > 1:
                print("\033[F" * (len(task_ids) + 2), end='')
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Check #{check_count}")
            
            for i, task_id in enumerate(task_ids, 1):
                total = int(conn.get(f"task:{task_id}:total_chunks") or 0)
                done = int(conn.get(f"task:{task_id}:done_chunks") or 0)
                started = int(conn.get(f"task:{task_id}:started_chunks") or 0)
                
                elapsed_seconds = current_time - start_times[task_id]
                elapsed_str = f"{int(elapsed_seconds//60)}m {int(elapsed_seconds%60)}s"
                
                if total > 0:
                    progress_pct = (done / total) * 100 if total > 0 else 0
                    
                    if done == total:
                        if completed_times[task_id] is None:
                            completed_times[task_id] = elapsed_seconds
                        status_icon = "✅"
                        print(f"   {status_icon} Job {i}: {done}/{total} chunks (100%) | COMPLETED in {int(completed_times[task_id]//60)}m {int(completed_times[task_id]%60)}s")
                    else:
                        status_icon = "🔄"
                        print(f"   {status_icon} Job {i}: {done}/{total} chunks ({progress_pct:.1f}%) | {elapsed_str}", end='')
                        
                        # ประมาณเวลาที่เหลือ
                        if done > 0 and done != prev_done[task_id]:
                            avg_time_per_chunk = elapsed_seconds / done
                            remaining_chunks = total - done
                            estimated_remaining = avg_time_per_chunk * remaining_chunks
                            estimated_total = elapsed_seconds + estimated_remaining
                            print(f" | Est: {int(estimated_total//60)}m {int(estimated_total%60)}s", end='')
                        
                        print()
                        
                        if done < total:
                            all_completed = False
                    
                    prev_done[task_id] = done
                else:
                    print(f"   ⏳ Job {i}: Waiting for preprocess | {elapsed_str}")
                    all_completed = False
            
            if all_completed:
                print("\n✅ All tasks completed!")
                break
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped by user")
    
    # สรุปผล
    print("\n" + "=" * 85)
    print("=== สรุปผลการทดสอบ ===")
    print("=" * 85)
    print("")
    
    for i, task_id in enumerate(task_ids, 1):
        total = int(conn.get(f"task:{task_id}:total_chunks") or 0)
        done = int(conn.get(f"task:{task_id}:done_chunks") or 0)
        
        if completed_times[task_id]:
            total_time = completed_times[task_id]
            print(f"Job {i}: {task_id[:36]}...")
            print(f"   ✅ COMPLETED")
            print(f"   Total time: {int(total_time//60)}m {int(total_time%60)}s ({int(total_time)}s)")
        else:
            elapsed_seconds = time.time() - start_times[task_id]
            print(f"Job {i}: {task_id[:36]}...")
            print(f"   Status: {done}/{total} chunks ({'COMPLETED' if done == total else 'PROCESSING'})")
            print(f"   Elapsed: {int(elapsed_seconds//60)}m {int(elapsed_seconds%60)}s")
        print()
    
    print("=" * 85)

if __name__ == "__main__":
    main()

