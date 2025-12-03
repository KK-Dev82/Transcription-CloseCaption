# 🔍 Root Cause Analysis: Worker Stuck & Connection Loss

## 📊 สรุปปัญหา

### ปัญหาที่พบ:
1. **Worker stuck ใน CPU mode** - CPU 666%, GPU 0%
2. **Connection หลุด** - RabbitMQ connection ไม่สามารถรับ messages ใหม่ได้
3. **Messages รอ 26 ตัว** - ไม่ถูก process
4. **5 tasks กำลัง process ใน CPU mode** - ช้ามาก (อาจใช้เวลาหลายชั่วโมง)

---

## 🔴 สาเหตุหลัก

### 1. GPU Timeout → CPU Fallback

**สาเหตุ:**
```
- มี 50 concurrent requests ส่งพร้อมกัน
- GPU ถูกใช้งานเต็มที่ → segments collection timeout (60s)
- เมื่อ timeout → fallback to CPU mode → ช้ามาก (10-20 เท่า)
```

**Code ที่เกี่ยวข้อง:**
```python
# app/services/whisper_providers/faster_whisper_provider.py
dynamic_timeout = max(60.0, min(300.0, audio_duration / 10.0))
timeout = max(base_timeout, dynamic_timeout)
# 60s timeout → ไม่พอเมื่อ GPU ถูกใช้งานมาก
```

**ปัญหาที่แท้จริง:**
- ⚠️ ไม่มีการจำกัด concurrent GPU tasks
- ⚠️ เมื่อมี 50 requests → GPU overload → timeout
- ⚠️ CPU fallback ไม่ควรเป็น default behavior

---

### 2. RabbitMQ Connection Loss

**สาเหตุ:**
```
- Worker กำลัง process 5 tasks ใน CPU mode (ช้ามาก)
- CPU mode ใช้เวลานานมาก (หลายชั่วโมง)
- RabbitMQ heartbeat timeout (600s) → connection หลุด
- Worker ไม่สามารถรับ messages ใหม่ได้
```

**Code ที่เกี่ยวข้อง:**
```python
# app/workers/video_worker.py
heartbeat=600,  # 10 นาที heartbeat
blocked_connection_timeout=300,  # 5 นาที blocked timeout
```

**ปัญหาที่แท้จริง:**
- ⚠️ Heartbeat timeout ไม่พอเมื่อ worker busy
- ⚠️ ไม่มีการ maintain connection เมื่อ worker กำลัง process ยาวนาน
- ⚠️ Connection หลุดแล้ว retry logic ไม่ทำงาน

---

### 3. ไม่มีการจำกัด Concurrent Tasks

**สาเหตุ:**
```
- มี 50 requests ส่งพร้อมกัน
- Worker รับทั้งหมด (prefetch_count=1 แต่ process parallel)
- GPU overload → timeout → CPU fallback
- Messages รอใน queue มากเกินไป
```

**ปัญหาที่แท้จริง:**
- ⚠️ ไม่มีการ rate limiting
- ⚠️ ไม่มีการ queue management
- ⚠️ ไม่มีการ reject requests เมื่อ queue เต็ม

---

## 💡 แนวทางแก้ไข

### 1. เพิ่ม Retry Logic สำหรับ Transcription

**ปัญหา:**
- เมื่อ GPU timeout → fallback to CPU → ช้ามาก
- ไม่มีการ retry เพื่อใช้ GPU ใหม่

**แนวทางแก้ไข:**

```python
# app/services/whisper_providers/faster_whisper_provider.py

MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds

async def transcribe(self, audio_path: str, language: str = "th", model_size: str = None):
    """Transcribe with retry logic"""
    last_error = None
    
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            # ลอง GPU mode ก่อน
            result = await self._transcribe_gpu(...)
            return result
            
        except TimeoutError as e:
            last_error = e
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                logger.warning(f"⚠️ GPU timeout (attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS}), retrying in {RETRY_DELAY}s...")
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

**ผลลัพธ์:**
- ✅ Retry GPU mode ก่อน fallback to CPU
- ✅ Release GPU resources ก่อน retry
- ✅ CPU fallback เป็น last resort เท่านั้น

---

### 2. ปรับปรุง RabbitMQ Connection Management

**ปัญหา:**
- Connection หลุดเมื่อ worker busy
- Heartbeat timeout ไม่พอ

**แนวทางแก้ไข:**

```python
# app/workers/video_worker.py

# เพิ่ม heartbeat และ timeout
parameters = pika.ConnectionParameters(
    host=self.rabbitmq_host,
    port=self.rabbitmq_port,
    virtual_host=self.rabbitmq_vhost,
    credentials=credentials,
    heartbeat=1800,  # เพิ่มเป็น 30 นาที
    blocked_connection_timeout=600,  # เพิ่มเป็น 10 นาที
    connection_attempts=3,
    retry_delay=2
)

# เพิ่ม background thread เพื่อ maintain connection
def _maintain_connection(self):
    """Background thread to maintain RabbitMQ connection"""
    while True:
        try:
            if not self.connection or self.connection.is_closed:
                logger.warning("⚠️ Connection lost, attempting to reconnect...")
                if self.connect_rabbitmq(max_retries=5, retry_delay=5):
                    logger.info("✅ Reconnected successfully")
                    self.setup_consumers()
                else:
                    logger.error("❌ Reconnection failed")
            
            # Send heartbeat manually if needed
            if self.connection and not self.connection.is_closed:
                self.connection.process_data_events(time_limit=0.1)
            
            time.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Error in connection maintenance: {e}")
            time.sleep(60)
```

**ผลลัพธ์:**
- ✅ Heartbeat timeout เพิ่มขึ้น (30 นาที)
- ✅ Background thread maintain connection
- ✅ Auto-reconnect เมื่อ connection หลุด

---

### 3. เพิ่ม Queue Rate Limiting

**ปัญหา:**
- มี 50 requests ส่งพร้อมกัน → GPU overload

**แนวทางแก้ไข:**

```python
# app/api/routes/transcription.py

MAX_QUEUE_SIZE = 20  # จำกัด queue size
MAX_CONCURRENT_TASKS = 5  # จำกัด concurrent tasks

@router.post("/start")
async def start_transcription(...):
    # ตรวจสอบ queue size
    queue_size = await check_queue_size()
    
    if queue_size >= MAX_QUEUE_SIZE:
        raise HTTPException(
            status_code=503,
            detail=f"Queue is full ({queue_size}/{MAX_QUEUE_SIZE}). Please try again later."
        )
    
    # ตรวจสอบ concurrent tasks
    active_tasks = await count_active_tasks()
    
    if active_tasks >= MAX_CONCURRENT_TASKS:
        raise HTTPException(
            status_code=503,
            detail=f"Too many concurrent tasks ({active_tasks}/{MAX_CONCURRENT_TASKS}). Please try again later."
        )
    
    # ส่ง task ไปยัง queue
    ...
```

**ผลลัพธ์:**
- ✅ ป้องกัน queue overflow
- ✅ ป้องกัน GPU overload
- ✅ Return 503 Service Unavailable เมื่อ queue เต็ม

---

### 4. เพิ่ม Task Timeout และ Cancellation

**ปัญหา:**
- Tasks stuck ใน CPU mode นานมาก
- ไม่สามารถ cancel tasks ได้

**แนวทางแก้ไข:**

```python
# app/services/transcription_service.py

TASK_TIMEOUT = 3600  # 1 ชั่วโมง timeout

async def _process_transcription(self, task_id: str, ...):
    """Process transcription with timeout"""
    start_time = time.time()
    
    try:
        # ใช้ asyncio.wait_for เพื่อ timeout
        result = await asyncio.wait_for(
            self._transcribe_audio(...),
            timeout=TASK_TIMEOUT
        )
        return result
        
    except asyncio.TimeoutError:
        logger.error(f"❌ Task {task_id} timeout after {TASK_TIMEOUT}s")
        
        # Update task status
        await self._update_task_status(task_id, status="failed", error="Task timeout")
        
        # Release resources
        await self._release_resources(task_id)
        
        raise
```

**ผลลัพธ์:**
- ✅ Tasks จะ timeout หลังจาก 1 ชั่วโมง
- ✅ Resources จะถูก release
- ✅ ไม่ให้ tasks ค้างนานเกินไป

---

### 5. เพิ่ม Monitoring และ Alerting

**ปัญหา:**
- ไม่รู้ว่า queue เต็มหรือ worker stuck

**แนวทางแก้ไข:**

```python
# app/services/monitoring_service.py

async def check_system_health():
    """Check system health and send alerts"""
    
    # Check queue size
    queue_size = await check_queue_size()
    if queue_size > MAX_QUEUE_SIZE * 0.8:
        logger.warning(f"⚠️ Queue is 80% full: {queue_size}/{MAX_QUEUE_SIZE}")
        # Send alert
    
    # Check worker status
    worker_status = await check_worker_status()
    if worker_status.get("cpu_usage", 0) > 500 and worker_status.get("gpu_usage", 0) == 0:
        logger.warning("⚠️ Worker stuck in CPU mode")
        # Send alert
    
    # Check connection status
    if not worker_status.get("rabbitmq_connected", False):
        logger.error("❌ RabbitMQ connection lost")
        # Send alert
```

**ผลลัพธ์:**
- ✅ Monitoring queue size
- ✅ Monitoring worker status
- ✅ Alerting เมื่อมีปัญหา

---

## 📋 สรุปการแก้ไข

### Immediate Actions (Quick Fix):

1. ✅ **เพิ่ม Retry Logic** - Retry GPU mode ก่อน fallback to CPU
2. ✅ **ปรับ Heartbeat Timeout** - เพิ่มเป็น 30 นาที
3. ✅ **เพิ่ม Queue Rate Limiting** - จำกัด queue size และ concurrent tasks

### Long-term Improvements:

1. ⭐ **Task Timeout** - Timeout tasks หลังจาก 1 ชั่วโมง
2. ⭐ **Connection Maintenance** - Background thread maintain connection
3. ⭐ **Monitoring & Alerting** - Monitor system health

---

## 🎯 Expected Results

### Before:
- ❌ GPU timeout → CPU fallback (ช้ามาก)
- ❌ Connection หลุดเมื่อ worker busy
- ❌ Queue overflow (50 requests)

### After:
- ✅ Retry GPU mode ก่อน fallback
- ✅ Connection stable แม้ worker busy
- ✅ Queue rate limiting (ป้องกัน overflow)

---

## 📝 Next Steps

1. ✅ Implement retry logic สำหรับ transcription
2. ✅ ปรับ heartbeat timeout
3. ✅ เพิ่ม queue rate limiting
4. ✅ เพิ่ม task timeout
5. ✅ เพิ่ม monitoring & alerting

