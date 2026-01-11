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
    """Clear stale worker registrations from Redis"""
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        
        workers = r.smembers('rq:workers')
        if not workers:
            print("✅ No workers registered in Redis")
            return 0
        
        cleared = 0
        kept = 0
        
        for worker in workers:
            worker_key = f'rq:worker:{worker}'
            worker_info = r.hgetall(worker_key)
            
            # Check if process exists using PID file
            pid_file = Path(f'/tmp/rq-{worker}.pid')
            is_alive = False
            
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    if psutil.pid_exists(pid):
                        is_alive = True
                except (ValueError, psutil.NoSuchProcess):
                    pass
            
            if not is_alive:
                # Worker is stale, remove it
                r.srem('rq:workers', worker)
                r.delete(worker_key)
                cleared += 1
            else:
                kept += 1
        
        print(f"✅ Cleared {cleared} stale workers, kept {kept} active workers")
        return cleared
        
    except Exception as e:
        print(f"❌ Error clearing stale workers: {e}")
        import traceback
        traceback.print_exc()
        return -1

if __name__ == "__main__":
    cleared = clear_stale_workers()
    sys.exit(0 if cleared >= 0 else 1)
