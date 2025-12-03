# 🏗️ Architecture Design - Transcription Service

## 📊 สรุปคำถามและการออกแบบ

### 1. API สำหรับ Monitoring (Frontend)

**คำถาม:** ต้องการ API สำหรับ Monitoring ให้ใช้กับ Frontend (`concurrency-monitor.html`)

**คำตอบ:** ✅ มีอยู่แล้ว

**API Endpoints ที่มีอยู่:**
- `GET /queue/stats` - Queue statistics (จาก `app/api/queue.py`)
- `GET /api/active-tasks` - Active tasks count (จาก `app/api/dashboard.py`)
- `GET /transcribe/{task_id}` - Task status
- `GET /transcribe/{task_id}/text` - Transcription text

**Status:** ✅ **พร้อมใช้งาน** - Frontend ใช้ API เหล่านี้อยู่แล้ว

---

### 2. การจัดการ Queue: Backend vs Transcription Service

**คำถาม:** Production Backend ติดต่อกับ RabbitMQ ควรเป็นคนจัดการ หรือให้ Transcription Service จัดการเอง?

**คำตอบ:** ✅ **ให้ Transcription Service จัดการ Queue เอง**

**เหตุผล:**
1. **Separation of Concerns**:
   - Backend รับผิดชอบ: Business logic, User management, File uploads
   - Transcription Service รับผิดชอบ: Queue management, Task processing, Worker management

2. **Scalability**:
   - Transcription Service สามารถ scale workers ได้อิสระ
   - Backend ไม่ต้องรู้รายละเอียดของ queue implementation

3. **Current Architecture** (ที่ใช้อยู่):
   ```
   Backend → HTTP API → Transcription Service → RabbitMQ → Video Worker
   ```

**แนะนำ Architecture:**
```
┌─────────────┐
│  Backend    │  (Business Logic)
│  (C#/.NET)  │
└──────┬──────┘
       │ HTTP API
       │ POST /api/v1/transcription/start
       ▼
┌─────────────────────────────┐
│  Transcription Service      │  (Queue Management)
│  (FastAPI/Python)           │
│  - Receives requests        │
│  - Manages RabbitMQ Queue   │
│  - Returns Task ID          │
└──────┬──────────────────────┘
       │ RabbitMQ
       │ (transcription_queue)
       ▼
┌─────────────────────────────┐
│  Video Worker               │  (Task Processing)
│  (Python)                   │
│  - Consumes messages        │
│  - Processes transcription  │
│  - Updates status           │
└─────────────────────────────┘
```

**Backend ควรทำ:**
- ✅ ส่งไฟล์ไปให้ Transcription Service
- ✅ เรียก API `/api/v1/transcription/start` เพื่อเริ่ม transcription
- ✅ Poll หรือใช้ webhook เพื่อติดตาม status
- ✅ **ไม่ต้อง** จัดการ RabbitMQ โดยตรง

**Transcription Service ควรทำ:**
- ✅ จัดการ RabbitMQ Queue (`transcription_queue`, `transcription_chunk_queue`)
- ✅ ตรวจสอบ Queue size และ rate limiting
- ✅ Return 503 เมื่อ queue เต็ม
- ✅ จัดการ Workers และ connection

---

### 3. RabbitMQ Service เดียวแต่รับ Queue หลายทาง

**คำถาม:** RabbitMQ service เดียวแต่รับ Queue ได้หลายทาง

**คำตอบ:** ✅ **ใช่ - ถูกต้อง**

**Current Queues:**
1. `transcription_queue` - Full video tasks
2. `transcription_chunk_queue` - Audio chunks
3. `trim_queue` - Video trimming tasks
4. `merge_queue` - Video merging tasks
5. `convert_queue` - Video format conversion
6. `resize_queue` - Video resizing tasks
7. `audio_chunk_extracted_queue` - Audio chunks from Backend

**แต่ละ Queue มีหน้าที่แยกกัน:**
- `transcription_queue`: Full video transcription tasks (จาก Backend หรือ API)
- `transcription_chunk_queue`: Audio chunks (ภายใน Transcription Service)
- `trim_queue`, `merge_queue`, etc.: Video processing tasks

**RabbitMQ Service:**
- ✅ ใช้ RabbitMQ instance เดียว
- ✅ แต่มีหลาย queues (แยกตามหน้าที่)
- ✅ แต่ละ queue มี consumers แยกกัน

---

### 4. จำกัด Queue ที่ 50 และ Return 503

**คำถาม:** จำกัด Queue ไว้ที่ 50 และ Return 503 เมื่อ queue เต็ม

**คำตอบ:** ✅ **เห็นด้วย**

**การจำกัด Queue:**
```python
MAX_QUEUE_SIZE = 50  # จำกัด queue size ที่ 50 tasks

@router.post("/api/v1/transcription/start")
async def start_transcription(...):
    # ตรวจสอบ queue size
    queue_size = await check_queue_size()
    
    if queue_size >= MAX_QUEUE_SIZE:
        raise HTTPException(
            status_code=503,
            detail=f"Queue is full ({queue_size}/{MAX_QUEUE_SIZE}). Please try again later."
        )
    
    # ส่ง task ไปยัง queue
    ...
```

**ประโยชน์:**
- ✅ ป้องกัน queue overflow
- ✅ ป้องกัน GPU overload
- ✅ Client ได้รับ feedback ชัดเจน (503 Service Unavailable)
- ✅ Client สามารถ retry ได้ทันที

**การ Return 503:**
- ✅ Standard HTTP status code สำหรับ "Service Unavailable"
- ✅ Client สามารถ retry ได้
- ✅ Load balancer สามารถ route ไปยัง instance อื่นได้ (ถ้ามี)

---

### 5. Retry Logic และ Heartbeat

**คำถาม:** Retry Logic และ Heartbeat สำคัญเพราะจะช่วยให้ระบบเสถียรขึ้น

**คำตอบ:** ✅ **เห็นด้วยอย่างยิ่ง**

**Retry Logic:**
```python
# app/services/whisper_providers/faster_whisper_provider.py

MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds

async def transcribe(self, ...):
    """Transcribe with retry logic"""
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            # ลอง GPU mode ก่อน
            result = await self._transcribe_gpu(...)
            return result
            
        except TimeoutError as e:
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                logger.warning(f"⚠️ GPU timeout (attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS}), retrying...")
                await asyncio.sleep(RETRY_DELAY)
                
                # Release GPU resources before retry
                import gc
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
            else:
                logger.error(f"❌ GPU timeout after {MAX_RETRY_ATTEMPTS} attempts, falling back to CPU")
                
    # Fallback to CPU only after all retries failed
    return await self._transcribe_cpu_fallback(...)
```

**Heartbeat:**
```python
# app/workers/video_worker.py

parameters = pika.ConnectionParameters(
    host=self.rabbitmq_host,
    port=self.rabbitmq_port,
    heartbeat=1800,  # เพิ่มเป็น 30 นาที (เดิม 10 นาที)
    blocked_connection_timeout=600,  # เพิ่มเป็น 10 นาที
    connection_attempts=3,
    retry_delay=2
)

# Background thread เพื่อ maintain connection
def _maintain_connection(self):
    """Background thread to maintain RabbitMQ connection"""
    while True:
        try:
            if not self.connection or self.connection.is_closed:
                logger.warning("⚠️ Connection lost, attempting to reconnect...")
                if self.connect_rabbitmq(max_retries=5, retry_delay=5):
                    logger.info("✅ Reconnected successfully")
                    self.setup_consumers()
            
            # Send heartbeat manually if needed
            if self.connection and not self.connection.is_closed:
                self.connection.process_data_events(time_limit=0.1)
            
            time.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Error in connection maintenance: {e}")
            time.sleep(60)
```

**ประโยชน์:**
- ✅ Retry Logic: ลดโอกาส fail เมื่อ GPU busy ชั่วคราว
- ✅ Heartbeat: Maintain connection เมื่อ worker busy processing
- ✅ Auto-reconnect: ระบบ recover ได้เองเมื่อ connection หลุด

---

### 6. Rate Limit - ใช้ Nginx หรือไม่?

**คำถาม:** Rate Limit ต้องจัดการที่ไหน ต้องใช้ Nginx ที่ Production ไหม?

**คำตอบ:** ✅ **ใช้ Nginx สำหรับ Rate Limiting (แนะนำ)**

**Rate Limiting ที่แนะนำ:**

#### Option 1: Nginx Rate Limiting (แนะนำสำหรับ Production)

**เหตุผล:**
- ✅ Performance ดี (ทำที่ Nginx layer)
- ✅ ไม่กระทบ application logic
- ✅ สามารถ configure ได้ง่าย
- ✅ ป้องกัน DDoS และ abuse

**Configuration:**
```nginx
# /etc/nginx/conf.d/rate-limit.conf

# Rate limiting zones
limit_req_zone $binary_remote_addr zone=transcription_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=general_limit:10m rate=100r/s;

# Transcription API rate limiting
location /api/v1/transcription/start {
    limit_req zone=transcription_limit burst=20 nodelay;
    
    proxy_pass http://transcription-service:8010;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

# General API rate limiting
location /api/ {
    limit_req zone=general_limit burst=50 nodelay;
    
    proxy_pass http://transcription-service:8010;
}
```

**ผลลัพธ์:**
- ✅ จำกัด 10 requests/วินาที ต่อ IP (สำหรับ transcription)
- ✅ Burst 20 requests (สำหรับ concurrent requests)
- ✅ Return 503 เมื่อเกิน limit

---

#### Option 2: Application-Level Rate Limiting (Backup)

**สำหรับกรณีที่ไม่มี Nginx:**

```python
# app/api/middleware/rate_limit.py

from fastapi import Request, HTTPException
from datetime import datetime, timedelta
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
    
    async def check_rate_limit(self, request: Request):
        client_ip = request.client.host
        
        # Clean old requests
        now = time.time()
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if now - req_time < 60
        ]
        
        # Check limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute."
            )
        
        # Add current request
        self.requests[client_ip].append(now)

# Usage
rate_limiter = RateLimiter(requests_per_minute=10)

@router.post("/api/v1/transcription/start")
async def start_transcription(request: Request, ...):
    await rate_limiter.check_rate_limit(request)
    ...
```

**ข้อดี:**
- ✅ ไม่ต้องพึ่งพา Nginx
- ✅ สามารถ customize ได้ง่าย

**ข้อเสีย:**
- ⚠️ ใช้ memory มากขึ้น (เก็บ request history)
- ⚠️ Performance น้อยกว่า Nginx

---

#### Option 3: Queue-Based Rate Limiting (ปัจจุบัน)

**ปัจจุบันใช้ Queue size checking:**

```python
MAX_QUEUE_SIZE = 50

@router.post("/api/v1/transcription/start")
async def start_transcription(...):
    queue_size = await check_queue_size()
    
    if queue_size >= MAX_QUEUE_SIZE:
        raise HTTPException(
            status_code=503,
            detail=f"Queue is full ({queue_size}/{MAX_QUEUE_SIZE})"
        )
    ...
```

**ข้อดี:**
- ✅ ป้องกัน queue overflow
- ✅ ไม่ต้องใช้ external tools

**ข้อเสีย:**
- ⚠️ ไม่จำกัด per-IP
- ⚠️ อาจถูก abuse ได้

---

## 🎯 สรุปการออกแบบ

### 1. Monitoring API
✅ **พร้อมใช้งาน** - Frontend ใช้ API อยู่แล้ว

### 2. Queue Management
✅ **ให้ Transcription Service จัดการเอง**
- Backend: ส่งไฟล์และเรียก API
- Transcription Service: จัดการ RabbitMQ Queue

### 3. RabbitMQ Architecture
✅ **RabbitMQ service เดียว แต่มีหลาย queues**
- แยก queue ตามหน้าที่
- แต่ละ queue มี consumers แยกกัน

### 4. Queue Size Limiting
✅ **จำกัดที่ 50 tasks และ Return 503**
- ป้องกัน queue overflow
- Return 503 Service Unavailable

### 5. Retry & Heartbeat
✅ **สำคัญมาก - ต้อง implement**
- Retry Logic: Retry GPU mode ก่อน fallback to CPU
- Heartbeat: เพิ่มเป็น 30 นาที
- Auto-reconnect: Background thread maintain connection

### 6. Rate Limiting
✅ **แนะนำใช้ Nginx สำหรับ Production**
- Nginx: 10 requests/วินาที ต่อ IP (สำหรับ transcription)
- Application-level: Backup (ถ้าไม่มี Nginx)
- Queue-based: ปัจจุบันใช้อยู่ (ป้องกัน queue overflow)

---

## 📋 Action Items

### Immediate (Quick Fix):
1. ✅ เพิ่ม Retry Logic สำหรับ GPU transcription
2. ✅ ปรับ Heartbeat timeout เป็น 30 นาที
3. ✅ เพิ่ม Queue size limit (50 tasks) และ Return 503

### Short-term (Production Ready):
4. ⭐ เพิ่ม Background thread สำหรับ maintain connection
5. ⭐ เพิ่ม Nginx rate limiting configuration
6. ⭐ เพิ่ม Monitoring & Alerting

### Long-term (Optimization):
7. 🔮 เพิ่ม Multiple Workers (horizontal scaling)
8. 🔮 เพิ่ม Circuit Breaker pattern
9. 🔮 เพิ่ม Distributed Tracing

