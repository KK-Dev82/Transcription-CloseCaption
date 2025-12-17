#!/usr/bin/env python3
"""
Test Script: ส่งไฟล์ v10-1.mp4 5 ครั้ง ครั้งละ 5 tasks
ใช้ API เดียวกันที่ใช้กับ dashboard
"""
import asyncio
import aiohttp
import json
import time
import os
from datetime import datetime
from pathlib import Path

# Configuration
DASHBOARD_BASE_URL = os.getenv("DASHBOARD_BASE_URL", "http://localhost:8020")
SERVER_NAME = os.getenv("TEST_SERVER_NAME", "4000-ada-sc")
VIDEO_FILE = "v10-1.mp4"
TASKS_PER_BATCH = 5
NUM_BATCHES = 5
DELAY_BETWEEN_BATCHES = 10  # seconds

async def send_batch_transcription(session, batch_num):
    """Send a batch of transcription tasks"""
    url = f"{DASHBOARD_BASE_URL}/api/batch/transcription"
    
    # Create video_files array (5 tasks with same video)
    video_files = [VIDEO_FILE] * TASKS_PER_BATCH
    
    payload = {
        "server_name": SERVER_NAME,
        "video_files": video_files,
        "concurrency": TASKS_PER_BATCH,
        "model_size": "medium",
        "language": "th"
    }
    
    print(f"\n{'='*80}")
    print(f"📤 Batch {batch_num}/{NUM_BATCHES}: Sending {TASKS_PER_BATCH} tasks...")
    print(f"   Video: {VIDEO_FILE}")
    print(f"   Server: {SERVER_NAME}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}")
    
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
            if response.status == 200:
                result = await response.json()
                batch_id = result.get("batch_id")
                print(f"✅ Batch {batch_num} sent successfully!")
                print(f"   Batch ID: {batch_id}")
                return batch_id
            else:
                error_text = await response.text()
                print(f"❌ Batch {batch_num} failed: HTTP {response.status}")
                print(f"   Error: {error_text}")
                return None
    except Exception as e:
        print(f"❌ Batch {batch_num} error: {e}")
        return None

async def check_worker_status():
    """Check worker process status"""
    import subprocess
    try:
        result = subprocess.run(
            ["pgrep", "-f", "python.*video_worker"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            return len([p for p in pids if p]), pids
        return 0, []
    except Exception as e:
        print(f"⚠️  Error checking worker status: {e}")
        return 0, []

async def check_rabbitmq_consumers():
    """Check RabbitMQ consumers"""
    try:
        import pika
        from dotenv import load_dotenv
        
        load_dotenv('env.runpod')
        
        rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        rabbitmq_port = int(os.getenv('RABBITMQ_PORT', '5672'))
        rabbitmq_user = os.getenv('RABBITMQ_USER', 'guest')
        rabbitmq_password = os.getenv('RABBITMQ_PASSWORD', 'guest')
        
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=rabbitmq_host, port=rabbitmq_port, credentials=credentials)
        )
        channel = connection.channel()
        
        queues = ['transcription_request_queue', 'audio_extraction_queue', 'transcription_queue']
        consumers = {}
        messages = {}
        
        for queue_name in queues:
            try:
                method = channel.queue_declare(queue=queue_name, passive=True)
                consumers[queue_name] = method.method.consumer_count
                messages[queue_name] = method.method.message_count
            except:
                consumers[queue_name] = 0
                messages[queue_name] = 0
        
        connection.close()
        return consumers, messages
    except Exception as e:
        print(f"⚠️  Error checking RabbitMQ: {e}")
        return {}, {}

async def monitor_worker_during_test():
    """Monitor worker status during test"""
    print("\n🔍 Starting worker monitoring...")
    
    worker_stopped = False
    last_worker_count = 0
    
    while True:
        await asyncio.sleep(5)  # Check every 5 seconds
        
        worker_count, pids = await check_worker_status()
        consumers, messages = await check_rabbitmq_consumers()
        
        if worker_count == 0 and last_worker_count > 0:
            worker_stopped = True
            print(f"\n⚠️  WORKER STOPPED! (was running with PIDs: {last_worker_count})")
            print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Check recent logs for signal
            try:
                with open("logs/video-worker.log", "r") as f:
                    lines = f.readlines()
                    recent_lines = lines[-10:] if len(lines) > 10 else lines
                    for line in recent_lines:
                        if "signal" in line.lower() or "sigterm" in line.lower():
                            print(f"   Log: {line.strip()}")
            except:
                pass
        
        if worker_stopped:
            break
        
        last_worker_count = worker_count
        
        # Print status every 30 seconds
        if int(time.time()) % 30 == 0:
            total_consumers = sum(consumers.values())
            total_messages = sum(messages.values())
            status = "✅" if worker_count > 0 and total_consumers == 3 else "⚠️"
            print(f"{status} Worker: {worker_count} process(es), Consumers: {total_consumers}/3, Messages: {total_messages}")

async def main():
    """Main test function"""
    print("="*80)
    print("🧪 Batch Transcription Test: 5 batches x 5 tasks")
    print("="*80)
    print(f"Configuration:")
    print(f"  Dashboard URL: {DASHBOARD_BASE_URL}")
    print(f"  Server: {SERVER_NAME}")
    print(f"  Video File: {VIDEO_FILE}")
    print(f"  Tasks per batch: {TASKS_PER_BATCH}")
    print(f"  Number of batches: {NUM_BATCHES}")
    print(f"  Delay between batches: {DELAY_BETWEEN_BATCHES}s")
    print("="*80)
    
    # Check if video file exists
    video_path = Path("uploads") / VIDEO_FILE
    if not video_path.exists():
        print(f"❌ Video file not found: {video_path}")
        return
    
    print(f"✅ Video file found: {video_path}")
    
    # Initial worker status check
    worker_count, pids = await check_worker_status()
    consumers, messages = await check_rabbitmq_consumers()
    
    print(f"\n📊 Initial Status:")
    print(f"  Worker processes: {worker_count}")
    if worker_count > 0:
        print(f"  Worker PIDs: {', '.join(pids)}")
    print(f"  RabbitMQ Consumers: {sum(consumers.values())}/3")
    print(f"  Queue Messages: {sum(messages.values())}")
    
    # Start monitoring task
    monitor_task = asyncio.create_task(monitor_worker_during_test())
    
    # Send batches
    batch_ids = []
    async with aiohttp.ClientSession() as session:
        for i in range(1, NUM_BATCHES + 1):
            batch_id = await send_batch_transcription(session, i)
            if batch_id:
                batch_ids.append(batch_id)
            
            # Wait before next batch (except last batch)
            if i < NUM_BATCHES:
                print(f"\n⏳ Waiting {DELAY_BETWEEN_BATCHES} seconds before next batch...")
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)
    
    # Stop monitoring
    monitor_task.cancel()
    
    # Final status check
    print(f"\n{'='*80}")
    print("📊 Final Status:")
    print(f"{'='*80}")
    
    worker_count, pids = await check_worker_status()
    consumers, messages = await check_rabbitmq_consumers()
    
    print(f"  Worker processes: {worker_count}")
    if worker_count > 0:
        print(f"  Worker PIDs: {', '.join(pids)}")
    else:
        print("  ⚠️  Worker is NOT running!")
    
    print(f"  RabbitMQ Consumers: {sum(consumers.values())}/3")
    for queue_name, count in consumers.items():
        msg_count = messages.get(queue_name, 0)
        status = "✅" if count > 0 else "❌"
        print(f"    {status} {queue_name}: {count} consumer(s), {msg_count} message(s)")
    
    print(f"\n  Total batches sent: {len(batch_ids)}/{NUM_BATCHES}")
    print(f"  Batch IDs: {', '.join(batch_ids) if batch_ids else 'None'}")
    
    print(f"\n{'='*80}")
    print("✅ Test Complete!")
    print(f"{'='*80}")
    
    if worker_count == 0:
        print("\n⚠️  WARNING: Worker stopped during test!")
        print("   Check logs/video-worker.log for details")
        print("   Check logs/worker-health-check.log for health check issues")

if __name__ == "__main__":
    asyncio.run(main())

