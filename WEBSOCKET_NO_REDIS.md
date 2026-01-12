# 🔌 WebSocket Service - NO REDIS Version

## 📋 สรุปการเปลี่ยนแปลง

**ตัด Redis pub/sub ออกจาก WebSocket service เพื่อให้ระบบ start ได้แน่นอน**

### ✅ สิ่งที่เปลี่ยน

1. **websocket_service.py** - ตัด Redis ทั้งหมด
   - ไม่มี `connect_redis()`, `start_redis_subscriber()`, `stop_redis_subscriber()`
   - ทำงานแบบ in-process only
   - ไม่ block startup

2. **main.py** - ตัด subscriber loop
   - ไม่มี retry loop
   - ไม่มี timeout
   - Start ได้ทันที

3. **HTTP Callback Endpoint** - เพิ่ม `/api/internal/ws-event`
   - Worker ส่ง HTTP callback แทน Redis publish
   - Main API broadcast ไปยัง WebSocket clients

---

## 🚀 ผลลัพธ์

### ✅ ข้อดี
- **Main API start ได้ทันที** - ไม่ต้องรอ Redis
- **ไม่ block startup** - ไม่มี timeout หรือ retry
- **เสถียร** - ไม่พึ่งพา Redis Cloud
- **ง่าย** - HTTP callback ตรงไปตรงมา

### ⚠️ ข้อจำกัด
- **Single-instance only** - WebSocket ทำงานใน process เดียว
- **Worker ต้องส่ง HTTP callback** - แทน Redis publish
- **ไม่รองรับ multi-instance** - ถ้ามีหลาย API instances หลัง load balancer

---

## 📡 วิธีใช้ HTTP Callback

### สำหรับ Transcription Updates

**Worker → Main API:**
```python
import aiohttp
import json

async def send_transcription_update(task_id: str, message: dict):
    """ส่ง transcription update ไปยัง Main API"""
    api_url = os.getenv("MAIN_API_URL", "http://localhost:8010")
    
    payload = {
        "task_id": task_id,
        "message": message
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{api_url}/api/internal/ws-event",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5.0)
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"✅ WS event sent: {result}")
                else:
                    logger.warning(f"⚠️ WS event failed: {resp.status}")
        except Exception as e:
            logger.warning(f"⚠️ WS event error: {e}")
```

### สำหรับ Live-Chunk Updates

**Worker → Main API:**
```python
async def send_live_chunk_update(meeting_id: str, message: dict):
    """ส่ง live-chunk update ไปยัง Main API"""
    api_url = os.getenv("MAIN_API_URL", "http://localhost:8010")
    
    payload = {
        "meeting_id": meeting_id,
        "message": message
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{api_url}/api/internal/ws-event",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5.0)
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"✅ WS event sent: {result}")
        except Exception as e:
            logger.warning(f"⚠️ WS event error: {e}")
```

---

## 🔧 API Endpoint

### `POST /api/internal/ws-event`

**Request Body:**
```json
{
  "task_id": "task_123",  // สำหรับ transcription updates
  "meeting_id": "meeting_456",  // สำหรับ live-chunk updates
  "message": {
    "type": "progress",
    "progress": 50,
    "status": "processing",
    "stage": "transcribing"
  }
}
```

**Response:**
```json
{
  "ok": true,
  "type": "task_update",
  "task_id": "task_123"
}
```

---

## 📝 Migration Guide

### 1. แก้ไข Worker Code

**เดิม (Redis publish):**
```python
# ใน app/workers/rq_worker.py หรือ app/api/realtime_transcription.py
if websocket_manager.redis_client:
    await websocket_manager.redis_client.publish(
        f"transcription:{task_id}",
        json.dumps(payload)
    )
```

**ใหม่ (HTTP callback):**
```python
# ใช้ HTTP callback แทน
import aiohttp
import os

api_url = os.getenv("MAIN_API_URL", "http://localhost:8010")
async with aiohttp.ClientSession() as session:
    await session.post(
        f"{api_url}/api/internal/ws-event",
        json={"task_id": task_id, "message": payload},
        timeout=aiohttp.ClientTimeout(total=5.0)
    )
```

### 2. ตั้งค่า Environment Variable

```bash
# ใน worker environment
export MAIN_API_URL=http://localhost:8010
# หรือ
export MAIN_API_URL=https://your-api-domain.com
```

---

## 🔍 ตรวจสอบ

### 1. ตรวจสอบว่า WebSocket ทำงาน
```bash
curl http://localhost:8010/health
```

### 2. ทดสอบ HTTP Callback
```bash
curl -X POST http://localhost:8010/api/internal/ws-event \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test_123",
    "message": {
      "type": "progress",
      "progress": 50,
      "status": "processing"
    }
  }'
```

### 3. ดู WebSocket Stats
```python
from app.services.websocket_service import websocket_manager
stats = websocket_manager.get_stats()
print(stats)
```

---

## ⚠️ หมายเหตุ

### Single-Instance Limitation

ถ้าคุณ run Main API หลาย instances หลัง load balancer:
- Client ต่อ WebSocket ไป instance A
- Worker ส่ง callback ไป instance B
- → Client จะไม่เห็น event

**วิธีแก้:**
1. ใช้ **single API instance** (แนะนำสำหรับตอนนี้)
2. ใช้ **WebSocket Gateway** (แนะนำสำหรับ production)
3. ใช้ **Message Broker** ที่เหมาะกว่า (RabbitMQ/NATS) ในอนาคต

### Environment Variable

Worker ต้องรู้ Main API URL:
```bash
export MAIN_API_URL=http://localhost:8010
```

---

## 🎯 สรุป

- ✅ **ตัด Redis ออกแล้ว** - ไม่ block startup
- ✅ **HTTP callback** - Worker ส่ง event ผ่าน HTTP
- ✅ **WebSocket ยังทำงาน** - แต่เป็น single-instance
- ✅ **Startup เร็ว** - ไม่มี timeout หรือ retry

**ตอนนี้ Main API ควร start ได้ทันทีแล้ว!** 🚀
