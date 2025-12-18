# 📋 Redis Setup Guide

## เปรียบเทียบ Redis Services

### 1. Redis.io (Redis Cloud) - แนะนำ ✅

**ข้อดี:**
- ✅ Official Redis service
- ✅ Free tier: 30MB storage, 30 connections
- ✅ Performance ดี
- ✅ เสถียร
- ✅ ง่ายต่อการใช้งาน

**ข้อเสีย:**
- ⚠️ ต้องสร้าง account

**Setup:**
1. ไปที่ https://redis.io/try-free/
2. สร้าง account (free tier)
3. สร้าง database
4. Copy connection details
5. รัน: `bash scripts/setup-redis-cloud.sh`

---

### 2. Upstash

**ข้อดี:**
- ✅ Serverless Redis
- ✅ Free tier: 10K commands/day
- ✅ Auto-scaling

**ข้อเสีย:**
- ⚠️ Rate limiting
- ⚠️ อาจช้ากว่า Redis.io

**Setup:**
1. ไปที่ https://upstash.com/
2. สร้าง account
3. สร้าง Redis database
4. Copy connection details
5. ตั้งค่า environment variables

---

### 3. CloudAMQP

**ข้อเสีย:**
- ❌ เป็น RabbitMQ (ไม่ใช่ Redis)
- ❌ ไม่เหมาะกับระบบที่เปลี่ยนไปใช้ Redis แล้ว

---

## การตั้งค่า Redis Cloud (redis.io)

### วิธีที่ 1: ใช้ Script (แนะนำ)

```bash
bash scripts/setup-redis-cloud.sh
```

Script จะ:
1. ถาม Redis connection details
2. บันทึกใน `.env.runpod`
3. ทดสอบ connection

### วิธีที่ 2: ตั้งค่าด้วยตนเอง

1. สร้าง/แก้ไข `.env.runpod`:

```bash
REDIS_HOST=your-redis-host.redis.cloud
REDIS_PORT=12345
REDIS_PASSWORD=your-password
```

2. ทดสอบ connection:

```bash
python3 -c "
import redis
import os
from dotenv import load_dotenv

load_dotenv('.env.runpod')

r = redis.Redis(
    host=os.getenv('REDIS_HOST'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    password=os.getenv('REDIS_PASSWORD'),
    decode_responses=True
)
print('✅ Redis connection OK:', r.ping())
"
```

---

## การใช้งาน

### Start Worker

```bash
python3 -m app.workers.sync.redis_worker
```

### ตรวจสอบ Queue Status

```python
from app.services.redis_queue_service import RedisQueueService

service = RedisQueueService()
print(f"Chunk queue length: {service.get_queue_length('transcription_chunk_queue')}")
```

---

## Troubleshooting

### Connection Refused

- ตรวจสอบว่า Redis host และ port ถูกต้อง
- ตรวจสอบว่า Redis password ถูกต้อง
- ตรวจสอบ firewall/network

### Authentication Failed

- ตรวจสอบ Redis password
- ตรวจสอบว่า Redis database ถูกต้อง

### Timeout

- ตรวจสอบ network connection
- ตรวจสอบว่า Redis service ยังทำงานอยู่

