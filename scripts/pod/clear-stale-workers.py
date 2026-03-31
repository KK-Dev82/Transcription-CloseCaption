#!/usr/bin/env python3
"""
Clear Stale Worker Registrations from Redis
- ใช้เมื่อ restart workers และพบ stale registrations
- ลบ worker registrations ที่ไม่มี process ทำงานอยู่แล้ว
"""

import os
import sys
import redis
import psutil
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment
env_file = project_root / "config" / ".env.runpod"
if not env_file.exists():
    env_file = project_root / ".env.runpod"

if env_file.exists():
    load_dotenv(env_file)

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

def clear_stale_workers():
    """
    Force clear ALL worker registrations from Redis.
    เรียกตอน startup ก่อนสร้าง workers ใหม่ — ปลอดภัยเพราะ workers ทั้งหมดจะถูกสร้างใหม่
    ป้องกัน ValueError: "There exists an active worker named 'X' already" หลัง container restart
    """
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)

        # ลบ worker keys ทั้งหมด (rq:worker:worker-gpu0-w0 etc.)
        worker_keys = r.keys('rq:worker:*')
        cleared = 0
        for key in worker_keys:
            r.delete(key)
            cleared += 1

        # ลบ workers set
        workers = r.smembers('rq:workers')
        if workers:
            r.delete('rq:workers')
            cleared += len(workers)

        if cleared > 0:
            print(f"✅ Force cleared {cleared} worker registrations from Redis")
        else:
            print("✅ No workers registered in Redis")
        return cleared

    except Exception as e:
        print(f"❌ Error clearing stale workers: {e}")
        import traceback
        traceback.print_exc()
        return -1

if __name__ == "__main__":
    cleared = clear_stale_workers()
    sys.exit(0 if cleared >= 0 else 1)
