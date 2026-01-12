# 🔍 การวิเคราะห์ Redis Subscriber สำหรับ live-chunk

## ✅ สรุป

**Main API มีการใช้ Redis subscriber แล้ว** สำหรับ live-chunk

---

## 📁 ไฟล์ที่เกี่ยวข้อง

### 1. **app/main.py** (Start Redis Subscriber)

**หน้าที่**: Start Redis subscriber เมื่อ application startup

**Code Location**: บรรทัด 63-67

```python
# เริ่ม Redis subscriber เพื่อรับ notifications จาก worker processes
try:
    logger.info("🔄 Starting Redis subscriber for WebSocket notifications...")
    await websocket_manager.start_redis_subscriber()
    logger.info("✅ Redis subscriber started for WebSocket notifications - ready to receive messages from workers")
except Exception as sub_e:
    logger.error(f"❌ Failed to start Redis subscriber: {sub_e} (continuing anyway)", exc_info=True)
```

**สถานะ**: ✅ ถูกเรียกเมื่อ application startup

---

### 2. **app/services/websocket_service.py** (Subscribe Patterns)

**หน้าที่**: Subscribe Redis patterns และ handle messages

**Code Location**: 
- บรรทัด 89-93: Subscribe patterns
- บรรทัด 131-138: Handle live-chunk messages

```python
# Subscribe patterns
await pubsub.psubscribe("transcription:*")
await pubsub.psubscribe("live-chunk:*")
logger.info("✅ Redis subscriber started (patterns: transcription:*, live-chunk:*)")

# Handle messages
elif channel.startswith("live-chunk:"):
    meeting_id = message_data.get('meeting_id')
    if meeting_id:
        await self.send_to_user(meeting_id, message_data)
        logger.info(f"📡 WebSocket: Sent live-chunk event for {meeting_id} from Redis")
```

**สถานะ**: ✅ Subscribe pattern `live-chunk:*` แล้ว

---

### 3. **app/api/realtime_transcription.py** (Publish Events)

**หน้าที่**: Publish events ไปยัง Redis channel

**Code Location**: บรรทัด 743-757

```python
# Initialize Redis client ถ้ายังไม่มี (สำหรับ worker process)
if not websocket_manager.redis_client:
    try:
        await websocket_manager.connect_redis()
        logger.info(f"✅ Redis client initialized for live-chunk worker")
    except Exception as redis_init_e:
        logger.warning(f"⚠️  Failed to initialize Redis client: {redis_init_e}")

if websocket_manager.redis_client:
    try:
        import json
        await websocket_manager.redis_client.publish(
            f"live-chunk:{meeting_id}",
            json.dumps(final_event, ensure_ascii=False)
        )
        logger.info(f"📡 Redis: Published live-chunk event for {meeting_id} to Redis channel 'live-chunk:{meeting_id}'")
    except Exception as redis_e:
        logger.warning(f"⚠️  Redis publish failed for {meeting_id}: {redis_e}")
```

**สถานะ**: ✅ Publish ไปยัง Redis channel `live-chunk:{meeting_id}` แล้ว

---

### 4. **app/workers/rq_worker.py** (Worker Process)

**หน้าที่**: Worker process ที่เรียก `process_live_chunk_background()`

**Code Location**: บรรทัด 1601-1663

```python
def process_live_chunk_job(
    session_id: str,
    meeting_id: str,
    chunk_index: int,
    start_time: float,
    duration: float,
    audio_path: str
) -> Dict:
    """RQ Worker function สำหรับ live chunk transcription (Priority Queue)"""
    # Import async function from API module
    from app.api.realtime_transcription import process_live_chunk_background
    
    # ใช้ persistent event loop
    loop = get_event_loop()
    
    # เรียก async function
    result = loop.run_until_complete(
        process_live_chunk_background(...)
    )
    return result
```

**สถานะ**: ✅ เรียก `process_live_chunk_background()` ซึ่งจะ publish ไปยัง Redis

**หมายเหตุ**: `rq_worker.py` **ไม่เกี่ยวกับ Redis subscriber โดยตรง** - มันเป็น worker process ที่ publish ไปยัง Redis

---

## 🔄 Flow การทำงาน

```
1. Worker Process (rq_worker.py)
   ↓
   process_live_chunk_job()
   ↓
   process_live_chunk_background() (realtime_transcription.py)
   ↓
   websocket_manager.redis_client.publish("live-chunk:{meeting_id}", event)
   ↓
2. Redis Channel: "live-chunk:{meeting_id}"
   ↓
3. Main API Process (websocket_service.py)
   ↓
   Redis Subscriber (listen_messages) - subscribe pattern "live-chunk:*"
   ↓
   Receive message from "live-chunk:{meeting_id}"
   ↓
   websocket_manager.send_to_user(meeting_id, message_data)
   ↓
4. WebSocket Client
   ↓
   Receive final event
```

---

## ⚠️ ปัญหาที่พบ

### **Redis Client ไม่ได้ถูก initialize**

**Logs แสดง**:
```
⚠️  No Redis client and no local subscriptions for {task_id} - message may be lost
```

**สาเหตุที่เป็นไปได้**:
1. **Redis connection timeout** - `REDIS_URL` ไม่สามารถเชื่อมต่อได้
2. **Redis connection failed** - Exception ระหว่าง connection
3. **Redis subscriber ไม่ได้ start** - Exception ระหว่าง startup

---

## 🔍 การตรวจสอบ

### 1. **ตรวจสอบ Logs**

```bash
# ตรวจสอบว่า Redis connection ทำงานหรือไม่
tail -f /tmp/main-api.log | grep -E "Redis|redis|subscriber|connect|initialized"

# ตรวจสอบว่า subscriber ถูก start หรือไม่
tail -f /tmp/main-api.log | grep -E "subscriber started|patterns:"

# ตรวจสอบว่า events ถูก publish หรือไม่
tail -f /tmp/main-api.log | grep -E "Published live-chunk|Redis: Published"
```

### 2. **ตรวจสอบ REDIS_URL**

```bash
# ตรวจสอบว่า REDIS_URL ถูกตั้งค่าหรือไม่
grep "^REDIS_URL" .env.runpod

# ทดสอบ Redis connection
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('.env.runpod')
redis_url = os.getenv('REDIS_URL')
print(f'REDIS_URL: {redis_url[:50]}...' if redis_url else 'REDIS_URL not set')
"
```

### 3. **ทดสอบ Redis Pub/Sub โดยตรง**

```bash
# Publish test message
redis-cli PUBLISH "live-chunk:test-meeting" '{"type":"final","meeting_id":"test-meeting","text":"test"}'
```

---

## 📝 สรุป

### ✅ Main API มีการใช้ Redis subscriber:
- ✅ **app/main.py**: เรียก `start_redis_subscriber()` เมื่อ startup
- ✅ **app/services/websocket_service.py**: Subscribe pattern `live-chunk:*`
- ✅ **app/api/realtime_transcription.py**: Publish ไปยัง Redis channel `live-chunk:{meeting_id}`

### 📝 ไฟล์ที่ต้องตรวจสอบสำหรับ live-chunk:
1. ✅ **app/main.py** - Start Redis subscriber (บรรทัด 66)
2. ✅ **app/services/websocket_service.py** - Subscribe patterns (บรรทัด 92)
3. ✅ **app/api/realtime_transcription.py** - Publish events (บรรทัด 754)
4. ✅ **app/workers/rq_worker.py** - Worker process (ไม่เกี่ยวกับ subscriber แต่เรียก function ที่ publish)

### ⚠️ ต้องตรวจสอบ:
- Redis client ถูก initialize หรือไม่ (ใน Main API process)
- Redis subscriber ถูก start หรือไม่
- Events ถูก publish ไปยัง Redis หรือไม่

---

**Last Updated**: 2026-01-12
