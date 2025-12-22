# 🚀 Persistent Worker Optimization

## 📋 ปัญหา

Redis Queue ทำงานได้แต่ช้ากว่า HTTP sync เพราะ:
- **Init TranscriptionService ทุก job** → โหลด model ใหม่ทุกครั้ง
- **Cold start overhead** → 15-40s ต่อ job

## ✅ วิธีแก้

ใช้ **Persistent TranscriptionService** ใน worker process:
- Init ครั้งเดียวตอน worker start
- Reuse สำหรับทุก job
- ลดเวลา init จาก 15-40s → 0s

---

## 🔧 Implementation

### 1. สร้าง Persistent Worker Module

**ไฟล์:** `app/workers/rq_worker.py`

```python
# Persistent service (init ครั้งเดียว)
_transcription_service = None

def get_transcription_service():
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = TranscriptionService()
    return _transcription_service

def process_transcription_job(...):
    # ใช้ persistent service (ไม่ init ใหม่)
    service = get_transcription_service()
    return loop.run_until_complete(service._process_transcription(...))
```

### 2. อัพเดต RedisQueueService

เปลี่ยน worker function path:
```python
# จาก
'app.services.redis_queue_service.process_transcription_job'

# เป็น
'app.workers.rq_worker.process_transcription_job'
```

### 3. Pre-load Model (Optional)

ตั้งค่า `RQ_PRELOAD_MODEL=true` ใน worker script:
```bash
RQ_PRELOAD_MODEL=true rq worker ...
```

---

## 📊 ผลลัพธ์ที่คาดหวัง

| Metric | Before (Init per job) | After (Persistent) |
|--------|----------------------|-------------------|
| Single request | 121s | ~70-80s |
| 5 concurrent | 598s | ~350-400s |
| Model init time | 15-40s/job | 0s (after first) |

---

## ✅ Checklist

- [x] สร้าง `app/workers/rq_worker.py`
- [x] อัพเดต `RedisQueueService` ให้ใช้ persistent worker
- [x] เพิ่ม `RQ_PRELOAD_MODEL` ใน worker script
- [ ] ทดสอบ performance improvement

---

## 🚀 Next Steps

1. Restart workers ด้วย persistent module
2. ทดสอบ 1 request → ควรเร็วขึ้น ~40-50s
3. ทดสอบ 5 concurrent → ควรเร็วขึ้น ~200s
4. Monitor GPU utilization

