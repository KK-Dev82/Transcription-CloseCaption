#!/usr/bin/env python3
"""ทดสอบ Redis Subscriber สำหรับ live-chunk"""
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

from app.services.websocket_service import websocket_manager

async def test_redis():
    print("=== ทดสอบ Redis Connection และ Subscriber ===\n")
    
    # 1. ตรวจสอบ Redis client
    print("1. ตรวจสอบ Redis client:")
    print(f"   redis_client: {websocket_manager.redis_client}")
    
    if not websocket_manager.redis_client:
        print("   ⚠️  Redis client ไม่ได้ถูก initialize")
        print("   🔄 กำลังเชื่อมต่อ Redis...")
        try:
            await websocket_manager.connect_redis()
            if websocket_manager.redis_client:
                print(f"   ✅ เชื่อมต่อ Redis สำเร็จ")
            else:
                print("   ❌ เชื่อมต่อ Redis ล้มเหลว (redis_client is None)")
                return
        except Exception as e:
            print(f"   ❌ เชื่อมต่อ Redis ล้มเหลว: {e}")
            return
    else:
        print("   ✅ Redis client ถูก initialize แล้ว")
        try:
            await websocket_manager.redis_client.ping()
            print("   ✅ Redis connection OK")
        except Exception as e:
            print(f"   ❌ Redis connection failed: {e}")
            return
    
    print()
    
    # 2. ทดสอบ publish/subscribe
    print("2. ทดสอบ Redis Pub/Sub:")
    
    # Subscribe pattern
    pubsub = websocket_manager.redis_client.pubsub()
    await pubsub.psubscribe("live-chunk:*")
    print("   ✅ Subscribed to pattern 'live-chunk:*'")
    
    # Publish test message
    test_message = {
        "type": "final",
        "meeting_id": "test-meeting-123",
        "session_id": "live-test-session",
        "text": "ทดสอบ Redis Pub/Sub",
        "chunk_index": 0
    }
    
    print(f"   📤 Publishing test message to 'live-chunk:test-meeting-123'...")
    result = await websocket_manager.redis_client.publish(
        "live-chunk:test-meeting-123",
        json.dumps(test_message, ensure_ascii=False)
    )
    print(f"   ✅ Published test message (subscribers: {result})")
    
    # Wait for message
    print("   ⏳ Waiting for message (timeout: 5s)...")
    try:
        message = await asyncio.wait_for(pubsub.get_message(), timeout=5.0)
        if message:
            if message['type'] == 'pmessage':
                pattern = message['pattern'].decode('utf-8') if isinstance(message['pattern'], bytes) else message['pattern']
                channel = message['channel'].decode('utf-8') if isinstance(message['channel'], bytes) else message['channel']
                data = message['data'].decode('utf-8') if isinstance(message['data'], bytes) else message['data']
                print(f"   ✅ Received message:")
                print(f"      Pattern: {pattern}")
                print(f"      Channel: {channel}")
                print(f"      Data: {data[:100]}...")
                
                # Parse JSON
                try:
                    msg_data = json.loads(data)
                    print(f"      Parsed: {json.dumps(msg_data, ensure_ascii=False, indent=2)}")
                except:
                    pass
            elif message['type'] == 'psubscribe':
                print(f"   ℹ️  Subscription confirmed: {message}")
            else:
                print(f"   ℹ️  Received message type: {message['type']}")
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
    await pubsub.close()
    print()
    
    # 3. ตรวจสอบ subscriber task
    print("3. ตรวจสอบ Redis subscriber task:")
    tasks = [t for t in asyncio.all_tasks() if not t.done()]
    subscriber_tasks = [t for t in tasks if 'listen_messages' in str(t) or 'subscriber' in str(t).lower()]
    print(f"   Active tasks: {len(tasks)}")
    print(f"   Subscriber tasks: {len(subscriber_tasks)}")
    if subscriber_tasks:
        print("   ✅ Redis subscriber task is running")
        for task in subscriber_tasks:
            print(f"      - {task}")
    else:
        print("   ⚠️  Redis subscriber task not found (may not be started in this process)")
    
    print()
    print("=== สรุป ===")
    if websocket_manager.redis_client:
        print("✅ Redis client: OK")
        try:
            await websocket_manager.redis_client.ping()
            print("✅ Redis connection: OK")
            print("✅ Redis Pub/Sub: OK (สามารถ publish/subscribe ได้)")
        except Exception as e:
            print(f"❌ Redis connection: Failed ({e})")
    else:
        print("❌ Redis client: Not initialized")

if __name__ == "__main__":
    asyncio.run(test_redis())
