#!/usr/bin/env python3
"""
สคริปต์ตรวจสอบ tasks ที่ค้าง (stuck tasks)
ตรวจสอบ tasks ที่ progress ไม่เปลี่ยนแปลงเกินเวลาที่กำหนด
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

# เพิ่ม project root เข้า Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# โหลด .env.runpod
try:
    from dotenv import load_dotenv
    env_file = project_root / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
except:
    pass


def check_stuck_tasks(stuck_threshold_seconds: int = 60):
    """ตรวจสอบ tasks ที่ค้าง"""
    storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
    
    print(f"📋 Checking Stuck Tasks (stuck > {stuck_threshold_seconds} seconds)")
    print(f"📦 Storage Type: {storage_type}\n")
    
    if storage_type == 'sqlite':
        from app.utils.sqlite_storage import SQLiteStorage
        storage = SQLiteStorage()
        all_tasks_list = storage.list_all_transcriptions()
        all_tasks = []
        for task in all_tasks_list:
            task_id = task.get('task_id')
            if task_id:
                task_data = storage.load_transcription(task_id, skip_migration=True)
                if task_data:
                    all_tasks.append((task_id, task_data))
    else:
        from app.utils.json_storage import JSONStorage
        storage = JSONStorage()
        storage_dir = Path("storage/transcriptions")
        all_tasks = []
        if storage_dir.exists():
            for task_file in storage_dir.glob("*.json"):
                task_id = task_file.stem
                task_data = storage.load_transcription(task_id)
                if task_data:
                    all_tasks.append((task_id, task_data))
    
    print(f"Total tasks found: {len(all_tasks)}\n")
    
    # ตรวจสอบ tasks ที่ค้าง
    stuck_tasks = []
    current_time = datetime.now(timezone.utc)
    
    for task_id, task_data in all_tasks:
        status = task_data.get('status', 'unknown')
        progress = task_data.get('progress', 0)
        updated_at_str = task_data.get('updated_at')
        
        # ข้าม tasks ที่เสร็จแล้วหรือ failed
        if status in ['completed', 'failed']:
            continue
        
        if updated_at_str:
            try:
                # Parse timestamp
                if isinstance(updated_at_str, str):
                    if updated_at_str.endswith('Z'):
                        updated_at_str = updated_at_str[:-1] + '+00:00'
                    elif '+' not in updated_at_str and 'Z' not in updated_at_str:
                        updated_at_str = updated_at_str + '+00:00'
                    updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                else:
                    continue
                
                # คำนวณเวลาที่ผ่านไป
                time_diff = (current_time - updated_at).total_seconds()
                
                # ถ้าค้างเกิน threshold
                if time_diff > stuck_threshold_seconds:
                    stuck_tasks.append({
                        'task_id': task_id,
                        'status': status,
                        'progress': progress,
                        'updated_at': updated_at_str,
                        'stuck_seconds': int(time_diff),
                        'current_stage': task_data.get('current_stage', 'N/A'),
                        'stage_description': task_data.get('current_stage_description', 'N/A')
                    })
            except Exception as e:
                pass
    
    # เรียงตามเวลาที่ค้าง (มากสุดก่อน)
    stuck_tasks.sort(key=lambda x: x['stuck_seconds'], reverse=True)
    
    return stuck_tasks


def print_stuck_tasks(stuck_tasks, limit: int = 30):
    """แสดงรายการ stuck tasks"""
    print(f"⚠️  Stuck Tasks: {len(stuck_tasks)}\n")
    
    if stuck_tasks:
        print("=" * 120)
        print(f"{'Task ID':<40} {'Status':<12} {'Progress':<10} {'Stuck (s)':<12} {'Stuck (min)':<12} {'Stage':<20}")
        print("=" * 120)
        
        for task in stuck_tasks[:limit]:
            stuck_min = task['stuck_seconds'] / 60
            print(f"{task['task_id']:<40} {task['status']:<12} {task['progress']:<10}% {task['stuck_seconds']:<12} {stuck_min:<12.1f} {task['current_stage']:<20}")
        
        if len(stuck_tasks) > limit:
            print(f"\n... and {len(stuck_tasks) - limit} more tasks")
        
        print("\n" + "=" * 120)
        print(f"\n📊 Summary:")
        print(f"  Total stuck tasks: {len(stuck_tasks)}")
        
        # สถิติ
        by_status = {}
        for task in stuck_tasks:
            status = task['status']
            by_status[status] = by_status.get(status, 0) + 1
        
        print(f"\n  By Status:")
        for status, count in sorted(by_status.items(), key=lambda x: x[1], reverse=True):
            print(f"    {status}: {count}")
        
        # Average stuck time
        if stuck_tasks:
            avg_stuck = sum(t['stuck_seconds'] for t in stuck_tasks) / len(stuck_tasks)
            max_stuck = max(t['stuck_seconds'] for t in stuck_tasks)
            min_stuck = min(t['stuck_seconds'] for t in stuck_tasks)
            
            print(f"\n  Stuck Time:")
            print(f"    Average: {avg_stuck/60:.1f} minutes ({avg_stuck:.0f} seconds)")
            print(f"    Max: {max_stuck/60:.1f} minutes ({max_stuck:.0f} seconds)")
            print(f"    Min: {min_stuck:.0f} seconds")
    else:
        print("✅ No stuck tasks found!")


if __name__ == "__main__":
    threshold = 60
    if len(sys.argv) > 1:
        try:
            threshold = int(sys.argv[1])
        except:
            print(f"Invalid threshold: {sys.argv[1]}, using default: 60 seconds")
    
    stuck_tasks = check_stuck_tasks(threshold)
    print_stuck_tasks(stuck_tasks)
    
    # Return exit code based on number of stuck tasks
    sys.exit(0 if len(stuck_tasks) == 0 else 1)
