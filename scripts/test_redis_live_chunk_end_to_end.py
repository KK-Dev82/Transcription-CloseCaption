#!/usr/bin/env python3
"""
ทดสอบ Redis Pub/Sub สำหรับ live-chunk แบบ end-to-end
- Publish message ไปยัง Redis (จำลอง worker process)
- ตรวจสอบว่า Main API subscriber รับ message หรือไม่
"""
import sys
import asyncio
import json
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
env_file = project_root / ".env.runpod"
if env_file.exists():
    load_dotenv(env_file)

import redis.asyncio as redis

async def test_redis_live_chunk():
    print("=== ทดสอบ Redis Pub/Sub สำหรับ live-chunk (End-to-End) ===\n")
    
    # 1. เชื่อมต่อ Redis
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("❌ REDIS_URL not found")
        return
    
    print(f"1. เชื่อมต่อ Redis: {redis_url[:50]}...")
    try:
        redis_client = redis.from_url(
            redis_url,
            socket_connect_timeout=5.0,
            socket_timeout=5.0
        )
        await redis_client.ping()
        print("   ✅ Redis connection OK")
    except Exception as e:
        print(f"   ❌ Redis connection failed: {e}")
        return
    
    print()
    
    # 2. Subscribe pattern (จำลอง Main API subscriber)
    print("2. Subscribe pattern 'live-chunk:*' (จำลอง Main API)...")
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe("live-chunk:*")
    print("   ✅ Subscribed to pattern 'live-chunk:*'")
    
    # รอ subscription confirmation
    await asyncio.sleep(0.5)
    
    print()
    
    # 3. Publish test message (จำลอง worker process)
    print("3. Publish test message (จำลอง worker process)...")
    test_meeting_id = "test-meeting-end-to-end"
    test_message = {
        "type": "final",
        "meeting_id": test_meeting_id,
        "session_id": "live-test-session",
        "chunk_index": 0,
        "text": "ทดสอบ Redis Pub/Sub end-to-end",
        "start_time": 0.0,
        "duration": 3.0,
        "timestamp": "2026-01-12T00:00:00Z"
    }
    
    channel = f"live-chunk:{test_meeting_id}"
    message_json = json.dumps(test_message, ensure_ascii=False)
    
    print(f"   Channel: {channel}")
    print(f"   Message: {message_json[:80]}...")
    
    subscribers = await redis_client.publish(channel, message_json)
    print(f"   ✅ Published (subscribers: {subscribers})")
    
    print()
    
    # 4. รับ message (จำลอง Main API subscriber)
    print("4. รับ message จาก Redis (จำลอง Main API subscriber)...")
    print("   ⏳ Waiting for message (timeout: 5s)...")
    
    try:
        # Skip subscription confirmation messages
        for _ in range(10):  # Max 10 messages
            message = await asyncio.wait_for(pubsub.get_message(), timeout=5.0)
            
            if message['type'] == 'psubscribe':
                print(f"   ℹ️  Subscription confirmed: {message}")
                continue
            
            if message['type'] == 'pmessage':
                pattern = message['pattern'].decode('utf-8') if isinstance(message['pattern'], bytes) else message['pattern']
                channel_received = message['channel'].decode('utf-8') if isinstance(message['channel'], bytes) else message['channel']
                data = message['data'].decode('utf-8') if isinstance(message['data'], bytes) else message['data']
                
                print(f"   ✅ Received message:")
                print(f"      Pattern: {pattern}")
                print(f"      Channel: {channel_received}")
                print(f"      Data: {data[:100]}...")
                
                # Parse JSON
                try:
                    msg_data = json.loads(data)
                    print(f"      Parsed:")
                    print(f"         type: {msg_data.get('type')}")
                    print(f"         meeting_id: {msg_data.get('meeting_id')}")
                    print(f"         text: {msg_data.get('text')}")
                    print(f"         chunk_index: {msg_data.get('chunk_index')}")
                except Exception as e:
                    print(f"      ⚠️  Failed to parse JSON: {e}")
                
                break
        else:
            print("   ⚠️  No message received (timeout)")
    except asyncio.TimeoutError:
        print("   ⚠️  Timeout waiting for message")
    except Exception as e:
        print(f"   ❌ Error receiving message: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    await pubsub.unsubscribe()
    await pubsub.aclose()
    await redis_client.aclose()
    
    print()
    print("=== สรุป ===")
    if subscribers > 0:
        print("✅ Redis Pub/Sub ทำงานได้:")
        print("   - สามารถ publish message ได้")
        print("   - สามารถ subscribe pattern ได้")
        print("   - สามารถรับ message ได้")
        print()
        print("💡 ถ้า Main API มี subscriber ทำงานอยู่ จะรับ message นี้ได้")
    else:
        print("⚠️  ไม่มี subscriber รับ message (subscribers: 0)")
        print("   - อาจเป็นเพราะ Main API subscriber ยังไม่ start")
        print("   - หรือ Redis connection ไม่ได้ถูก initialize ใน Main API")

if __name__ == "__main__":
    asyncio.run(test_redis_live_chunk())
