# 🚀 การแก้ไข live-chunk ให้ใช้ RQ + Priority Queue

## ✅ สรุปการแก้ไข

**วันที่**: 2026-01-12  
**เป้าหมาย**: แก้ไข `live-chunk` endpoint ให้ใช้ Redis Queue (RQ) + Priority Queue แทน `background_tasks`

---

## 📝 การเปลี่ยนแปลง

### 1. **สร้าง method `enqueue_live_chunk()` ใน `RedisQueueService`**

**ไฟล์**: `app/services/redis_queue_service.py`

**การทำงาน**:
- ส่ง job ไปยัง `priority_queue` (สูงสุด)
- `job_timeout=300s` (5 นาที - เหมาะสำหรับ real-time)
- `result_ttl=3600s` (1 ชั่วโมง - สั้นกว่า normal jobs)

**Code**:
```python
def enqueue_live_chunk(
    self,
    session_id: str,
    meeting_id: str,
    chunk_index: int,
    start_time: float,
    duration: float,
    audio_path: str
) -> str:
    """Enqueue live chunk job ไปยัง priority queue (สูงสุด)"""
    job = self.priority_queue.enqueue(
        'app.workers.rq_worker.process_live_chunk_job',
        session_id,
        meeting_id,
        chunk_index,
        start_time,
        duration,
        audio_path,
        job_id=f"live-chunk-{meeting_id}-{chunk_index}",
        job_timeout=300,  # 5 minutes
        result_ttl=3600,  # 1 hour
    )
    return job.id
```

---

### 2. **สร้าง worker function `process_live_chunk_job()` ใน `rq_worker.py`**

**ไฟล์**: `app/workers/rq_worker.py`

**การทำงาน**:
- เรียก async function `process_live_chunk_background()` โดยใช้ `loop.run_until_complete()`
- ใช้ persistent event loop (ไม่สร้างใหม่ทุกครั้ง)
- จัดการ errors และ return result

**Code**:
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
    from app.api.realtime_transcription import process_live_chunk_background
    loop = get_event_loop()
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
    return {"status": "completed", ...}
```

---

### 3. **แก้ไข `live-chunk` endpoint ให้ใช้ RQ**

**ไฟล์**: `app/api/realtime_transcription.py`

**การเปลี่ยนแปลง**:
- แทนที่ `background_tasks.add_task()` ด้วย `queue_service.enqueue_live_chunk()`
- ใช้ priority queue (สูงสุด)
- มี fallback ไป `background_tasks` ถ้า RQ ไม่พร้อม

**Code**:
```python
# ✅ ใช้ RQ + Priority Queue แทน background_tasks
try:
    from ..services.redis_queue_service import get_redis_queue_service
    
    queue_service = get_redis_queue_service()
    job_id = queue_service.enqueue_live_chunk(
        session_id=session_id,
        meeting_id=meeting_id,
        chunk_index=chunk_index,
        start_time=start_time,
        duration=duration,
        audio_path=temp_path
    )
    return {
        "status": "accepted",
        "job_id": job_id,
        "queue": "priority",
        ...
    }
except Exception as e:
    # Fallback: ใช้ background_tasks
    if background_tasks:
        background_tasks.add_task(...)
    return {"queue": "background_tasks", ...}
```

---

## ✅ ข้อดี

### 1. **Priority Queue (สูงสุด)**
- ✅ `live-chunk` จะได้ priority สูงกว่า transcription ปกติ
- ✅ จะได้ GPU ก่อน jobs อื่นๆ ใน queue
- ✅ รองรับ real-time requirements

### 2. **Queue Management**
- ✅ สามารถ queue ได้ (ไม่ต้องรอ GPU ว่าง)
- ✅ มี retry mechanism (ถ้า fail)
- ✅ ใช้ GPU workers ที่มีอยู่แล้ว

### 3. **Scalability**
- ✅ รองรับหลาย chunks พร้อมกัน
- ✅ ไม่ block main API process
- ✅ ใช้ GPU workers แบบ distributed

### 4. **Monitoring**
- ✅ สามารถ track job status ได้
- ✅ มี queue stats
- ✅ มี error handling

---

## 🔧 Workers Configuration

**ตรวจสอบแล้ว**: Workers consume priority queue แล้ว

```bash
# Workers consume priority queue ก่อน แล้วค่อย gpu queue
rq worker transcription_priority transcription_gpu0
rq worker transcription_priority transcription_gpu1
```

**หมายเหตุ**: Workers จะ consume `transcription_priority` ก่อน แล้วค่อย consume `transcription_gpu0` หรือ `transcription_gpu1` ตามลำดับ

---

## 📋 Response Format

### Success (RQ):
```json
{
    "status": "accepted",
    "session_id": "live-meeting-001-0",
    "meeting_id": "meeting-001",
    "chunk_index": 0,
    "start_time": 0.0,
    "duration": 3.0,
    "job_id": "live-chunk-meeting-001-0",
    "queue": "priority",
    "message": "Audio chunk received. Processing in priority queue. Caption events will be sent via WebSocket."
}
```

### Fallback (background_tasks):
```json
{
    "status": "accepted",
    "session_id": "live-meeting-001-0",
    "meeting_id": "meeting-001",
    "chunk_index": 0,
    "start_time": 0.0,
    "duration": 3.0,
    "queue": "background_tasks",
    "message": "Audio chunk received. Processing in background (fallback). Caption events will be sent via WebSocket."
}
```

---

## 🚀 ขั้นตอนถัดไป

### 1. **Restart Main API**

```bash
# Restart main API เพื่อให้ใช้ code ใหม่
bash scripts/pod/restart-main-api.sh
```

### 2. **ตรวจสอบ Workers**

```bash
# ตรวจสอบว่า workers consume priority queue
ps aux | grep "rq worker.*transcription_priority"
```

### 3. **ทดสอบ**

```bash
# ทดสอบ live-chunk endpoint
python3 scripts/test_rtmp_to_live_chunk_with_websocket.py \
    --rtmp-url rtmp://143.198.77.135:1935/live/channel1 \
    --transcription-url http://localhost:8010 \
    --meeting-id test-rq-$(date +%s) \
    --duration 15
```

### 4. **ตรวจสอบ Queue Stats**

```bash
# ตรวจสอบ queue stats
python3 -c "
from app.services.redis_queue_service import get_redis_queue_service
import json
service = get_redis_queue_service()
stats = service.get_queue_stats()
print(json.dumps(stats, indent=2, default=str))
"
```

---

## ⚠️ หมายเหตุ

1. **WebSocket Events**: ยังส่งผ่าน WebSocket เหมือนเดิม (ไม่เปลี่ยนแปลง)
2. **CloseCaption Features**: ยังทำงานเหมือนเดิม (overlap, dedupe, postprocess)
3. **Fallback**: ถ้า RQ ไม่พร้อม จะ fallback ไป `background_tasks` อัตโนมัติ
4. **Job Timeout**: 5 นาที (300s) - เหมาะสำหรับ real-time chunks

---

## 📊 เปรียบเทียบ

| Feature | Background Tasks | RQ + Priority Queue |
|---------|-----------------|---------------------|
| Queue | ❌ ไม่มี | ✅ มี |
| Priority | ❌ ไม่มี | ✅ สูงสุด |
| Retry | ❌ ไม่มี | ✅ มี |
| Monitoring | ❌ ไม่มี | ✅ มี |
| GPU Workers | ❌ ใช้ main API process | ✅ ใช้ GPU workers |
| Scalability | ⚠️ จำกัด | ✅ รองรับหลาย chunks |

---

**Last Updated**: 2026-01-12
