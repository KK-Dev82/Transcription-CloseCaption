#!/usr/bin/env python3
"""
สคริปต์ตรวจสอบ Task ที่ค้างอยู่ใน Redis Queue
แสดงรายละเอียดของ jobs ที่รอ, กำลังทำงาน, และล้มเหลว
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import json

# Load .env.runpod if exists
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent.parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass
except Exception:
    pass

from redis import Redis
from rq import Queue
from rq.job import Job
from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry

def get_redis_connection():
    """Get Redis connection"""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    return Redis.from_url(redis_url, decode_responses=False)

def format_time(ts):
    """Format timestamp"""
    if ts is None:
        return "N/A"
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    return str(ts)

def format_duration(seconds):
    """Format duration in seconds to human readable"""
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"

def get_job_info(job):
    """Get job information"""
    try:
        info = {
            'job_id': job.id,
            'status': job.get_status(),
            'created_at': format_time(job.created_at),
            'started_at': format_time(job.started_at),
            'ended_at': format_time(job.ended_at),
        }
        
        # Calculate duration
        if job.started_at and job.ended_at:
            duration = (job.ended_at - job.started_at).total_seconds()
            info['duration'] = format_duration(duration)
        elif job.started_at:
            duration = (datetime.now(timezone.utc) - job.started_at.replace(tzinfo=timezone.utc)).total_seconds()
            info['duration'] = f"{format_duration(duration)} (running)"
        else:
            info['duration'] = "N/A"
        
        # Get function name and args
        try:
            func_name = job.func_name if hasattr(job, 'func_name') else str(job.func)
            info['function'] = func_name.split('.')[-1] if '.' in func_name else func_name
            
            # Try to get task_id from args
            if job.args:
                args = job.args
                if len(args) > 0:
                    info['task_id'] = args[0] if isinstance(args[0], str) else "N/A"
                else:
                    info['task_id'] = "N/A"
            else:
                info['task_id'] = "N/A"
        except:
            info['function'] = "N/A"
            info['task_id'] = "N/A"
        
        # Error info
        if job.is_failed:
            info['error'] = str(job.exc_info) if job.exc_info else "Unknown error"
        
        return info
    except Exception as e:
        return {
            'job_id': job.id if hasattr(job, 'id') else 'unknown',
            'status': 'error',
            'error': str(e)
        }

def check_pending_tasks():
    """ตรวจสอบ task ที่ค้างอยู่"""
    print("=" * 80)
    print("🔍 ตรวจสอบ Task ที่ค้างอยู่ใน Redis Queue")
    print("=" * 80)
    print()
    
    try:
        conn = get_redis_connection()
        num_gpus = int(os.getenv('NUM_GPUS', '2'))
        
        # Queues to check
        queues_to_check = ['transcription_priority', 'transcription_preprocess', 'transcription_cpu']
        for i in range(num_gpus):
            queues_to_check.append(f'transcription_gpu{i}')
        
        total_queued = 0
        total_started = 0
        total_failed = 0
        
        print("📊 สรุป Queue Status:")
        print("-" * 80)
        
        for queue_name in queues_to_check:
            try:
                queue = Queue(queue_name, connection=conn)
                queued_count = len(queue)
                
                started_registry = StartedJobRegistry(queue_name, connection=conn)
                finished_registry = FinishedJobRegistry(queue_name, connection=conn)
                failed_registry = FailedJobRegistry(queue_name, connection=conn)
                
                started_count = len(started_registry)
                finished_count = len(finished_registry)
                failed_count = len(failed_registry)
                
                total_queued += queued_count
                total_started += started_count
                total_failed += failed_count
                
                status_icon = "⚠️" if queued_count > 0 or started_count > 0 else "✅"
                print(f"{status_icon} {queue_name:30s} | Queued: {queued_count:3d} | Started: {started_count:3d} | Failed: {failed_count:3d}")
                
            except Exception as e:
                print(f"❌ {queue_name:30s} | Error: {e}")
        
        print("-" * 80)
        print(f"📈 รวม: Queued: {total_queued} | Started: {total_started} | Failed: {total_failed}")
        print()
        
        # Show detailed queued jobs
        if total_queued > 0:
            print("⏳ Jobs ที่รออยู่ใน Queue:")
            print("=" * 80)
            for queue_name in queues_to_check:
                try:
                    queue = Queue(queue_name, connection=conn)
                    queued_jobs = queue.jobs
                    
                    if queued_jobs:
                        print(f"\n📋 {queue_name}:")
                        for job in queued_jobs[:10]:  # Show first 10
                            info = get_job_info(job)
                            print(f"  • Job ID: {info['job_id']}")
                            print(f"    Task ID: {info.get('task_id', 'N/A')}")
                            print(f"    Function: {info.get('function', 'N/A')}")
                            print(f"    Created: {info['created_at']}")
                            print()
                        
                        if len(queued_jobs) > 10:
                            print(f"  ... และอีก {len(queued_jobs) - 10} jobs")
                except Exception as e:
                    print(f"  ❌ Error: {e}")
        
        # Show detailed started jobs
        if total_started > 0:
            print("🔄 Jobs ที่กำลังทำงาน:")
            print("=" * 80)
            for queue_name in queues_to_check:
                try:
                    started_registry = StartedJobRegistry(queue_name, connection=conn)
                    started_jobs = started_registry.get_job_ids()
                    
                    if started_jobs:
                        print(f"\n📋 {queue_name}:")
                        for job_id in started_jobs[:10]:  # Show first 10
                            try:
                                job = Job.fetch(job_id, connection=conn)
                                info = get_job_info(job)
                                print(f"  • Job ID: {info['job_id']}")
                                print(f"    Task ID: {info.get('task_id', 'N/A')}")
                                print(f"    Function: {info.get('function', 'N/A')}")
                                print(f"    Started: {info['started_at']}")
                                print(f"    Duration: {info['duration']}")
                                print()
                            except Exception as e:
                                print(f"  • Job ID: {job_id} (Error fetching: {e})")
                        
                        if len(started_jobs) > 10:
                            print(f"  ... และอีก {len(started_jobs) - 10} jobs")
                except Exception as e:
                    print(f"  ❌ Error: {e}")
        
        # Show failed jobs
        if total_failed > 0:
            print("❌ Jobs ที่ล้มเหลว (ล่าสุด 10 jobs):")
            print("=" * 80)
            for queue_name in queues_to_check:
                try:
                    failed_registry = FailedJobRegistry(queue_name, connection=conn)
                    failed_jobs = failed_registry.get_job_ids()
                    
                    if failed_jobs:
                        print(f"\n📋 {queue_name}:")
                        for job_id in failed_jobs[-10:]:  # Show last 10
                            try:
                                job = Job.fetch(job_id, connection=conn)
                                info = get_job_info(job)
                                print(f"  • Job ID: {info['job_id']}")
                                print(f"    Task ID: {info.get('task_id', 'N/A')}")
                                print(f"    Function: {info.get('function', 'N/A')}")
                                print(f"    Failed: {info['ended_at']}")
                                print(f"    Error: {info.get('error', 'N/A')[:200]}")
                                print()
                            except Exception as e:
                                print(f"  • Job ID: {job_id} (Error fetching: {e})")
                except Exception as e:
                    print(f"  ❌ Error: {e}")
        
        # Check Redis task keys
        print("🔑 ตรวจสอบ Task Keys ใน Redis:")
        print("=" * 80)
        task_keys = list(conn.scan_iter(match="task:*", count=100))
        chunk_keys = list(conn.scan_iter(match="task:*:chunk:*", count=100))
        done_keys = list(conn.scan_iter(match="task:*:done_chunks", count=100))
        
        print(f"  • Task keys: {len(task_keys)}")
        print(f"  • Chunk keys: {len(chunk_keys)}")
        print(f"  • Done chunk counters: {len(done_keys)}")
        
        if task_keys:
            print("\n  Task IDs ที่พบ (ตัวอย่าง 10 ตัวแรก):")
            for key in task_keys[:10]:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                print(f"    - {key_str}")
        
        print()
        print("=" * 80)
        
        # Summary
        if total_queued > 0 or total_started > 0:
            print("⚠️  พบ Task ที่ค้างอยู่!")
            print(f"   - {total_queued} jobs รออยู่ใน queue")
            print(f"   - {total_started} jobs กำลังทำงาน")
            if total_failed > 0:
                print(f"   - {total_failed} jobs ล้มเหลว")
        else:
            print("✅ ไม่พบ Task ที่ค้างอยู่ - ระบบทำงานปกติ")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    check_pending_tasks()

