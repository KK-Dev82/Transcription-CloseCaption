# 🔍 คู่มือการทดสอบ Redis สำหรับ live-chunk

## ✅ สรุป

**Redis ถูก initialize ถูกต้องแล้ว** (จากการทดสอบ)

---

## 🧪 วิธีทดสอบ

### 1. **ทดสอบ Redis Connection และ Pub/Sub**

```bash
cd /workspace/transcription-service
python3 scripts/test_redis_subscriber.py
```

**ผลลัพธ์ที่คาดหวัง**:
```
✅ Redis client: OK
✅ Redis connection: OK
✅ Redis Pub/Sub: OK (สามารถ publish/subscribe ได้)
```

---

### 2. **ทดสอบ Redis Pub/Sub แบบ End-to-End**

```bash
cd /workspace/transcription-service
python3 scripts/test_redis_live_chunk_end_to_end.py
```

**ผลลัพธ์ที่คาดหวัง**:
```
✅ Redis Pub/Sub ทำงานได้:
   - สามารถ publish message ได้
   - สามารถ subscribe pattern ได้
   - สามารถรับ message ได้
```

**หมายเหตุ**: ถ้า `subscribers: 0` แสดงว่า Main API subscriber ยังไม่ start หรือไม่ได้ subscribe pattern `live-chunk:*`

---

### 3. **ตรวจสอบ Logs ของ Main API**

```bash
# ตรวจสอบว่า Redis subscriber ถูก start หรือไม่
tail -f /tmp/main-api.log | grep -E "Redis subscriber|patterns:|live-chunk"

# ตรวจสอบว่า events ถูก publish หรือไม่
tail -f /tmp/main-api.log | grep -E "Published live-chunk|Redis: Published"

# ตรวจสอบว่า events ถูก receive หรือไม่
tail -f /tmp/main-api.log | grep -E "Sent live-chunk event|WebSocket: Sent live-chunk"
```

---

### 4. **ทดสอบด้วย Redis CLI**

```bash
# Publish test message
redis-cli PUBLISH "live-chunk:test-meeting" '{"type":"final","meeting_id":"test-meeting","text":"test"}'

# ตรวจสอบว่า Main API รับ message หรือไม่ (ดู logs)
tail -f /tmp/main-api.log | grep -E "Sent live-chunk event"
```

---

## 📊 เปรียบเทียบ Transcription vs Live-chunk

### **Transcription** (ใช้ได้แล้ว)
- **Channel**: `transcription:{task_id}`
- **Publish**: `broadcast_task_update()` → `publish('transcription:{task_id}')`
- **Subscribe**: `psubscribe('transcription:*')`
- **Status**: ✅ ทำงานได้

### **Live-chunk** (ต้องทดสอบ)
- **Channel**: `live-chunk:{meeting_id}`
- **Publish**: `process_live_chunk_background()` → `publish('live-chunk:{meeting_id}')`
- **Subscribe**: `psubscribe('live-chunk:*')`
- **Status**: ⚠️ ต้องทดสอบ

---

## 🔍 การตรวจสอบ

### 1. **ตรวจสอบว่า Redis client ถูก initialize หรือไม่**

```python
from app.services.websocket_service import websocket_manager
import asyncio

async def check():
    if websocket_manager.redis_client:
        await websocket_manager.redis_client.ping()
        print("✅ Redis client OK")
    else:
        print("❌ Redis client not initialized")

asyncio.run(check())
```

### 2. **ตรวจสอบว่า Redis subscriber ถูก start หรือไม่**

ดู logs:
```bash
tail -f /tmp/main-api.log | grep "Redis subscriber started"
```

ควรเห็น:
```
✅ Redis subscriber started (patterns: transcription:*, live-chunk:*)
```

### 3. **ทดสอบ publish/subscribe โดยตรง**

ใช้สคริปต์ทดสอบ:
```bash
python3 scripts/test_redis_live_chunk_end_to_end.py
```

---

## ⚠️ ปัญหาที่อาจพบ

### 1. **Redis client ไม่ได้ถูก initialize**
- **สาเหตุ**: `REDIS_URL` ไม่ถูกต้อง หรือ Redis connection timeout
- **การแก้ไข**: ตรวจสอบ `REDIS_URL` ใน `.env.runpod`

### 2. **Redis subscriber ไม่ได้ start**
- **สาเหตุ**: Exception ระหว่าง startup
- **การแก้ไข**: ตรวจสอบ logs ใน `/tmp/main-api.log`

### 3. **Events ไม่ได้ถูก publish**
- **สาเหตุ**: Worker process ไม่สามารถ connect Redis
- **การแก้ไข**: ตรวจสอบว่า `websocket_manager.connect_redis()` ทำงานหรือไม่

### 4. **Events ไม่ได้ถูก receive**
- **สาเหตุ**: Main API subscriber ไม่ได้ subscribe pattern `live-chunk:*`
- **การแก้ไข**: ตรวจสอบ logs ว่า subscriber ถูก start หรือไม่

---

## 📝 สรุป

### ✅ Redis ถูก initialize ถูกต้อง:
- ✅ Redis connection ทำงานได้
- ✅ Redis Pub/Sub ทำงานได้
- ✅ สามารถ publish/subscribe ได้

### ⚠️ ต้องตรวจสอบ:
- Main API subscriber ถูก start หรือไม่
- Main API subscriber subscribe pattern `live-chunk:*` หรือไม่
- Events ถูก publish ไปยัง Redis หรือไม่
- Events ถูก receive และส่ง WebSocket หรือไม่

---

**Last Updated**: 2026-01-12
