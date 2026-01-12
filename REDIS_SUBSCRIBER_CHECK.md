# 🔍 การตรวจสอบ Redis Subscriber สำหรับ live-chunk

## 📋 สรุป

**คำตอบ**: ✅ **Main API มีการใช้ Redis subscriber แล้ว** สำหรับ live-chunk

---

## ✅ ไฟล์ที่เกี่ยวข้อง

### 1. **Main API** (`app/main.py`)

**หน้าที่**: Start Redis subscriber เมื่อ application startup

**Code**:
```python
# บรรทัด 63-67
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

### 2. **WebSocket Service** (`app/services/websocket_service.py`)

**หน้าที่**: Subscribe Redis patterns และส่ง WebSocket messages

**Code**:
```python
# บรรทัด 89-93
# Subscribe pattern สำหรับ transcription updates
await pubsub.psubscribe("transcription:*")
# ✅ Subscribe pattern สำหรับ live-chunk updates
await pubsub.psubscribe("live-chunk:*")
logger.info("✅ Redis subscriber started (patterns: transcription:*, live-chunk:*)")
```

**Code (Message Handler)**:
```python
# บรรทัด 131-138
elif channel.startswith("live-chunk:"):
    # Live-chunk updates: ใช้ meeting_id
    meeting_id = message_data.get('meeting_id')
    if meeting_id:
        # ส่ง WebSocket message ไปยัง clients ที่ subscribe meeting นี้
        # ใช้ meeting_id เป็น user_id
        await self.send_to_user(meeting_id, message_data)
        logger.info(f"📡 WebSocket: Sent live-chunk event for {meeting_id} from Redis")
```

**สถานะ**: ✅ Subscribe pattern `live-chunk:*` แล้ว

---

### 3. **Realtime Transcription** (`app/api/realtime_transcription.py`)

**หน้าที่**: Publish events ไปยัง Redis channel

**Code**:
```python
# บรรทัด 743-757
# ✅ Initialize Redis client ถ้ายังไม่มี (สำหรับ worker process)
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

### 4. **RQ Worker** (`app/workers/rq_worker.py`)

**หน้าที่**: Worker process ที่เรียก `process_live_chunk_background()`

**Code**:
```python
# บรรทัด 1627-1645
# Import async function from API module
from app.api.realtime_transcription import process_live_chunk_background

# ใช้ persistent event loop
loop = get_event_loop()
logger.info(f"✅ Using persistent event loop (instance: {id(loop)})")

# เรียก async function
result = loop.run_until_complete(
    process_live_chunk_background(
        session_id=session_id,
        meeting_id=meeting_id,
        chunk_index=chunk_index,
        start_time=start_time,
        duration=duration,
        audio_path=audio_path
    )
)
```

**สถานะ**: ✅ เรียก `process_live_chunk_background()` ซึ่งจะ publish ไปยัง Redis

---

## 🔍 Flow การทำงาน

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
   Redis Subscriber (listen_messages)
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

## ✅ สรุป

### Main API มีการใช้ Redis subscriber:
- ✅ **app/main.py**: เรียก `start_redis_subscriber()` เมื่อ startup
- ✅ **app/services/websocket_service.py**: Subscribe pattern `live-chunk:*`
- ✅ **app/api/realtime_transcription.py**: Publish ไปยัง Redis channel `live-chunk:{meeting_id}`

### ไฟล์ที่ต้องตรวจสอบ:
1. ✅ **app/main.py** - Start Redis subscriber
2. ✅ **app/services/websocket_service.py** - Subscribe patterns และ handle messages
3. ✅ **app/api/realtime_transcription.py** - Publish events ไปยัง Redis
4. ✅ **app/workers/rq_worker.py** - Worker process (ไม่เกี่ยวกับ Redis subscriber โดยตรง แต่เรียก function ที่ publish)

---

## 🔍 การตรวจสอบ

### 1. ตรวจสอบ Logs

```bash
# ตรวจสอบว่า Redis subscriber ถูก start หรือไม่
tail -f /tmp/main-api.log | grep -E "Redis subscriber|live-chunk|patterns:"

# ตรวจสอบว่า events ถูก publish หรือไม่
tail -f /tmp/main-api.log | grep -E "Published live-chunk|Redis: Published"

# ตรวจสอบว่า events ถูก receive หรือไม่
tail -f /tmp/main-api.log | grep -E "Sent live-chunk event|WebSocket: Sent live-chunk"
```

### 2. ตรวจสอบ Redis Connection

```bash
# ตรวจสอบว่า Redis client ถูก initialize หรือไม่
python3 -c "
from app.services.websocket_service import websocket_manager
import asyncio
async def check():
    await websocket_manager.connect_redis()
    print(f'Redis client: {websocket_manager.redis_client}')
asyncio.run(check())
"
```

### 3. ทดสอบ Redis Pub/Sub โดยตรง

```bash
# Publish test message
redis-cli PUBLISH "live-chunk:test-meeting" '{"type":"final","meeting_id":"test-meeting","text":"test"}'
```

---

## ⚠️ ปัญหาที่อาจพบ

### 1. **Redis Client ไม่ได้ถูก initialize**
- **สาเหตุ**: `REDIS_URL` ไม่ถูกต้อง หรือ Redis connection timeout
- **การแก้ไข**: ตรวจสอบ `REDIS_URL` ใน `.env.runpod`

### 2. **Redis Subscriber ไม่ได้ start**
- **สาเหตุ**: Exception ระหว่าง startup
- **การแก้ไข**: ตรวจสอบ logs ใน `/tmp/main-api.log`

### 3. **Events ไม่ได้ถูก publish**
- **สาเหตุ**: Worker process ไม่สามารถ connect Redis
- **การแก้ไข**: ตรวจสอบว่า `websocket_manager.connect_redis()` ทำงานหรือไม่

---

**Last Updated**: 2026-01-12
