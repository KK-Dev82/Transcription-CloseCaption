#!/usr/bin/env python3
"""
Test Script สำหรับทดสอบความเสถียรของระบบ
ทดสอบ 1, 2, 3 requests ตามลำดับ และตรวจสอบ tmp files และ Redis
"""
import requests
import json
import time
import os
from pathlib import Path
from datetime import datetime
from redis import Redis
from rq import Queue
from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry

# Load .env.runpod
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
except:
    pass

API_URL = "http://localhost:8010"
TEST_URL = "http://korrakang.com/video/v30-1.mp4"
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

def get_redis_conn():
    """Get Redis connection"""
    return Redis.from_url(REDIS_URL, decode_responses=False)

def check_redis_status():
    """ตรวจสอบสถานะ Redis"""
    conn = get_redis_conn()
    
    # Memory info
    info = conn.info('memory')
    used_memory = info.get('used_memory', 0)
    used_memory_mb = used_memory / (1024**2)
    
    # Count keys
    db_size = conn.dbsize()
    
    # Count job keys
    job_keys = list(conn.scan_iter(match="rq:job:*", count=1000))
    task_keys = list(conn.scan_iter(match="task:*", count=1000))
    chunk_keys = list(conn.scan_iter(match="chunk:*", count=1000))
    
    # Queue stats
    num_gpus = int(os.getenv('NUM_GPUS', '2'))
    queues_to_check = ['transcription_priority', 'transcription_preprocess', 'transcription_cpu']
    for i in range(num_gpus):
        queues_to_check.append(f'transcription_gpu{i}')
    
    total_queued = 0
    total_started = 0
    
    for queue_name in queues_to_check:
        try:
            queue = Queue(queue_name, connection=conn)
            queued_count = len(queue)
            started_registry = StartedJobRegistry(queue_name, connection=conn)
            started_count = len(started_registry)
            total_queued += queued_count
            total_started += started_count
        except:
            pass
    
    return {
        'memory_mb': used_memory_mb,
        'total_keys': db_size,
        'job_keys': len(job_keys),
        'task_keys': len(task_keys),
        'chunk_keys': len(chunk_keys),
        'queued_jobs': total_queued,
        'started_jobs': total_started
    }

def check_tmp_files():
    """ตรวจสอบ tmp files"""
    tmp_dirs = [
        '/tmp',
        '/workspace/transcription-service/uploads',
        '/workspace/transcription-service/storage',
    ]
    
    tmp_files = []
    for tmp_dir in tmp_dirs:
        if os.path.exists(tmp_dir):
            for root, dirs, files in os.walk(tmp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        stat = os.stat(file_path)
                        size_mb = stat.st_size / (1024**2)
                        tmp_files.append({
                            'path': file_path,
                            'size_mb': size_mb,
                            'modified': datetime.fromtimestamp(stat.st_mtime)
                        })
                    except:
                        pass
    
    # เรียงตามขนาด
    tmp_files.sort(key=lambda x: x['size_mb'], reverse=True)
    
    total_size = sum(f['size_mb'] for f in tmp_files)
    
    return {
        'count': len(tmp_files),
        'total_size_mb': total_size,
        'files': tmp_files[:20]  # Top 20
    }

def send_transcription_request():
    """ส่ง transcription request"""
    payload = {
        "file_url": TEST_URL,
        "language": "th",
        "model_size": "base"
    }
    
    try:
        response = requests.post(f"{API_URL}/api/transcribe/", json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  ❌ Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"  ❌ Error sending request: {e}")
        return None

def wait_for_task(task_id, max_wait=600):
    """รอให้ task เสร็จ"""
    start_time = time.time()
    check_interval = 5
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{API_URL}/api/tasks/{task_id}", timeout=10)
            if response.status_code == 200:
                result = response.json()
                status = result.get('status', 'unknown')
                
                if status == 'completed':
                    return True, result
                elif status in ['failed', 'error']:
                    return False, result
                # else: still processing
        except Exception as e:
            pass
        
        time.sleep(check_interval)
    
    return None, {"error": "timeout"}

def main():
    print("=" * 70)
    print("🧪 ทดสอบความเสถียรของระบบ")
    print("=" * 70)
    print()
    print(f"📋 Test URL: {TEST_URL}")
    print(f"📋 API URL: {API_URL}")
    print()
    
    # ตรวจสอบสถานะเริ่มต้น
    print("📊 ตรวจสอบสถานะเริ่มต้น:")
    print("-" * 70)
    initial_redis = check_redis_status()
    initial_tmp = check_tmp_files()
    
    print(f"Redis Memory: {initial_redis['memory_mb']:.2f} MB")
    print(f"Redis Keys: {initial_redis['total_keys']}")
    print(f"  - Job Keys: {initial_redis['job_keys']}")
    print(f"  - Task Keys: {initial_redis['task_keys']}")
    print(f"  - Chunk Keys: {initial_redis['chunk_keys']}")
    print(f"Queued Jobs: {initial_redis['queued_jobs']}")
    print(f"Started Jobs: {initial_redis['started_jobs']}")
    print()
    print(f"Tmp Files: {initial_tmp['count']} files ({initial_tmp['total_size_mb']:.2f} MB)")
    print()
    
    # ทดสอบ 1, 2, 3 requests
    test_counts = [1, 2, 3]
    all_task_ids = []
    
    for test_count in test_counts:
        print("=" * 70)
        print(f"🧪 ทดสอบ {test_count} Request(s)")
        print("=" * 70)
        print()
        
        # ส่ง requests
        task_ids = []
        for i in range(test_count):
            print(f"📤 Sending request {i+1}/{test_count}...")
            result = send_transcription_request()
            if result:
                task_id = result.get('task_id')
                task_ids.append(task_id)
                all_task_ids.append(task_id)
                print(f"  ✅ Task ID: {task_id[:8]}...")
            else:
                print(f"  ❌ Failed to send request {i+1}")
            time.sleep(1)  # รอ 1 วินาทีระหว่าง requests
        
        print()
        print(f"⏳ Waiting for {len(task_ids)} task(s) to complete...")
        
        # รอให้ tasks เสร็จ
        completed = 0
        failed = 0
        for task_id in task_ids:
            success, result = wait_for_task(task_id, max_wait=600)
            if success:
                completed += 1
                print(f"  ✅ {task_id[:8]}...: completed")
            elif success is False:
                failed += 1
                print(f"  ❌ {task_id[:8]}...: failed")
            else:
                print(f"  ⏰ {task_id[:8]}...: timeout")
        
        print()
        print(f"📊 Results: {completed} completed, {failed} failed, {len(task_ids) - completed - failed} timeout")
        print()
        
        # ตรวจสอบสถานะหลังทดสอบ
        print("📊 ตรวจสอบสถานะหลังทดสอบ:")
        print("-" * 70)
        after_redis = check_redis_status()
        after_tmp = check_tmp_files()
        
        print(f"Redis Memory: {after_redis['memory_mb']:.2f} MB (เพิ่มขึ้น: {after_redis['memory_mb'] - initial_redis['memory_mb']:.2f} MB)")
        print(f"Redis Keys: {after_redis['total_keys']} (เพิ่มขึ้น: {after_redis['total_keys'] - initial_redis['total_keys']})")
        print(f"  - Job Keys: {after_redis['job_keys']} (เพิ่มขึ้น: {after_redis['job_keys'] - initial_redis['job_keys']})")
        print(f"  - Task Keys: {after_redis['task_keys']} (เพิ่มขึ้น: {after_redis['task_keys'] - initial_redis['task_keys']})")
        print(f"  - Chunk Keys: {after_redis['chunk_keys']} (เพิ่มขึ้น: {after_redis['chunk_keys'] - initial_redis['chunk_keys']})")
        print(f"Queued Jobs: {after_redis['queued_jobs']}")
        print(f"Started Jobs: {after_redis['started_jobs']}")
        print()
        print(f"Tmp Files: {after_tmp['count']} files ({after_tmp['total_size_mb']:.2f} MB)")
        print(f"  - เพิ่มขึ้น: {after_tmp['count'] - initial_tmp['count']} files ({after_tmp['total_size_mb'] - initial_tmp['total_size_mb']:.2f} MB)")
        
        if after_tmp['files']:
            print()
            print("  Top 10 Largest Tmp Files:")
            for i, file_info in enumerate(after_tmp['files'][:10], 1):
                print(f"    {i:2d}. {file_info['size_mb']:7.2f} MB - {file_info['path']}")
        
        print()
        
        # รอ 5 วินาทีก่อนทดสอบถัดไป
        if test_count < test_counts[-1]:
            print("⏳ รอ 5 วินาทีก่อนทดสอบถัดไป...")
            time.sleep(5)
            print()
    
    # สรุปผล
    print("=" * 70)
    print("📊 สรุปผลการทดสอบ")
    print("=" * 70)
    print()
    
    final_redis = check_redis_status()
    final_tmp = check_tmp_files()
    
    print(f"Redis Memory:")
    print(f"  - เริ่มต้น: {initial_redis['memory_mb']:.2f} MB")
    print(f"  - สุดท้าย: {final_redis['memory_mb']:.2f} MB")
    print(f"  - เพิ่มขึ้น: {final_redis['memory_mb'] - initial_redis['memory_mb']:.2f} MB")
    print()
    
    print(f"Redis Keys:")
    print(f"  - เริ่มต้น: {initial_redis['total_keys']}")
    print(f"  - สุดท้าย: {final_redis['total_keys']}")
    print(f"  - เพิ่มขึ้น: {final_redis['total_keys'] - initial_redis['total_keys']}")
    print()
    
    print(f"Tmp Files:")
    print(f"  - เริ่มต้น: {initial_tmp['count']} files ({initial_tmp['total_size_mb']:.2f} MB)")
    print(f"  - สุดท้าย: {final_tmp['count']} files ({final_tmp['total_size_mb']:.2f} MB)")
    print(f"  - เพิ่มขึ้น: {final_tmp['count'] - initial_tmp['count']} files ({final_tmp['total_size_mb'] - initial_tmp['total_size_mb']:.2f} MB)")
    print()
    
    # วิเคราะห์
    print("=" * 70)
    print("🔍 วิเคราะห์ผล")
    print("=" * 70)
    print()
    
    memory_increase = final_redis['memory_mb'] - initial_redis['memory_mb']
    keys_increase = final_redis['total_keys'] - initial_redis['total_keys']
    tmp_increase = final_tmp['total_size_mb'] - initial_tmp['total_size_mb']
    
    if memory_increase > 100:
        print(f"⚠️  Redis Memory เพิ่มขึ้นมาก: {memory_increase:.2f} MB")
        print("   - แนะนำ: ตรวจสอบ memory leak หรือ cleanup old jobs")
    else:
        print(f"✅ Redis Memory เพิ่มขึ้นปกติ: {memory_increase:.2f} MB")
    
    if keys_increase > 500:
        print(f"⚠️  Redis Keys เพิ่มขึ้นมาก: {keys_increase}")
        print("   - แนะนำ: ตรวจสอบ TTL และ cleanup old keys")
    else:
        print(f"✅ Redis Keys เพิ่มขึ้นปกติ: {keys_increase}")
    
    if tmp_increase > 1000:
        print(f"⚠️  Tmp Files เพิ่มขึ้นมาก: {tmp_increase:.2f} MB")
        print("   - แนะนำ: ตรวจสอบ cleanup tmp files")
    else:
        print(f"✅ Tmp Files เพิ่มขึ้นปกติ: {tmp_increase:.2f} MB")
    
    print()
    print(f"📋 Task IDs ที่ทดสอบ: {len(all_task_ids)} tasks")
    for i, task_id in enumerate(all_task_ids, 1):
        print(f"  {i}. {task_id}")
    print()

if __name__ == "__main__":
    main()


