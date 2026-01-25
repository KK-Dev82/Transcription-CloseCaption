#!/usr/bin/env python3
"""
สคริปต์ตรวจสอบสถานะ Transcription Service
- ตรวจสอบ Redis queue status
- ตรวจสอบ failed jobs
- ตรวจสอบ transcription errors ใน logs
"""

import os
import sys
from pathlib import Path
from redis import Redis
from rq import Queue
from rq.registry import StartedJobRegistry, FailedJobRegistry

# โหลด .env.runpod
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass
except Exception:
    pass


def check_redis_queues():
    """ตรวจสอบ Redis queue status"""
    redis_url = os.getenv('REDIS_URL')
    if not redis_url:
        print("❌ REDIS_URL is not set in environment")
        return False
    
    # ซ่อน password ใน log
    redis_url_log = redis_url
    if '@' in redis_url:
        parts = redis_url.split('@')
        if len(parts) == 2:
            user_pass = parts[0].replace('redis://', '').replace('rediss://', '')
            if ':' in user_pass:
                redis_url_log = redis_url.replace(f':{user_pass.split(":")[1]}', ':****')
    
    print(f"🔗 Connecting to Redis: {redis_url_log}")
    
    try:
        conn = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=10)
        conn.ping()
        print("✅ Redis connection successful!\n")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False
    
    # ตรวจสอบ queue lengths
    queues = ['gpu0', 'gpu1', 'cpu0', 'cpu1', 'preprocess0', 'preprocess1', 'PRIORITY']
    
    print("📊 Redis Queue Status:\n")
    total_queued = 0
    for queue_name in queues:
        try:
            queue = Queue(queue_name, connection=conn)
            length = len(queue)
            total_queued += length
            if length > 0:
                print(f"  ⚠️  {queue_name}: {length} jobs (มี jobs รอคิว)")
            else:
                print(f"  ✅ {queue_name}: {length} jobs")
        except Exception as e:
            print(f"  ❌ {queue_name}: Error - {e}")
    
    # ตรวจสอบ failed jobs
    failed_queue = Queue('failed', connection=conn)
    failed_count = len(failed_queue)
    if failed_count > 0:
        print(f"\n⚠️  Failed jobs: {failed_count}")
        print("\n📋 Failed jobs (ล่าสุด 5):")
        for i, job_id in enumerate(list(failed_queue.job_ids)[:5]):
            try:
                job = failed_queue.job_class.fetch(job_id, connection=conn)
                if job:
                    error_msg = job.exc_info[:200] if job.exc_info else 'No error info'
                    print(f"  {i+1}. {job_id}")
                    print(f"     Error: {error_msg}")
            except Exception as e:
                print(f"  {i+1}. {job_id}: (ไม่สามารถดึงข้อมูลได้: {e})")
    else:
        print(f"\n✅ Failed jobs: {failed_count}")
    
    # ตรวจสอบ jobs ที่กำลังทำงาน
    started_count = 0
    for queue_name in ['gpu0', 'gpu1']:
        try:
            started_registry = StartedJobRegistry(queue_name, connection=conn)
            started_count += len(started_registry)
        except:
            pass
    
    if started_count > 0:
        print(f"\n🔄 Jobs กำลังทำงาน: {started_count}")
    
    print(f"\n📊 Summary:")
    print(f"  - Jobs ใน queue: {total_queued}")
    print(f"  - Failed jobs: {failed_count}")
    print(f"  - Jobs กำลังทำงาน: {started_count}")
    
    return True


def check_logs_errors():
    """ตรวจสอบ errors ใน logs"""
    log_file = Path(__file__).parent.parent / "logs" / "transcription.log"
    if not log_file.exists():
        print(f"\n⚠️  Log file not found: {log_file}")
        return
    
    print(f"\n📋 Checking errors in {log_file.name}...")
    
    # นับ errors
    error_count = 0
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            if 'ERROR' in line or 'CRITICAL' in line:
                error_count += 1
    
    print(f"  - Total errors: {error_count}")
    
    # ดู errors ล่าสุด (ที่ไม่ใช่ Invalid model size)
    print(f"\n  Recent errors (excluding 'Invalid model size'):")
    recent_errors = []
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in reversed(lines[-500:]):  # ดู 500 บรรทัดล่าสุด
            if ('ERROR' in line or 'CRITICAL' in line) and 'Invalid model size' not in line:
                recent_errors.append(line.strip())
                if len(recent_errors) >= 5:
                    break
    
    if recent_errors:
        for i, error in enumerate(recent_errors, 1):
            print(f"    {i}. {error[:150]}")
    else:
        print("    ✅ No recent errors (excluding 'Invalid model size')")


if __name__ == "__main__":
    print("=" * 60)
    print("📊 Transcription Service Status Check")
    print("=" * 60)
    
    # ตรวจสอบ Redis queues
    redis_ok = check_redis_queues()
    
    # ตรวจสอบ logs
    check_logs_errors()
    
    print("\n" + "=" * 60)
    if redis_ok:
        print("✅ Status check completed")
    else:
        print("⚠️  Status check completed with errors")
        sys.exit(1)
