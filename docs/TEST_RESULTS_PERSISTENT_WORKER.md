# 📊 Test Results: Persistent Worker Optimization

## 🧪 Test Date
2024-12-14

## 📋 Test Configuration
- **Workers**: 2 GPUs (GPU 0, GPU 1)
- **Model**: base
- **Chunk Duration**: 90s
- **File**: uploads/v30-1.mp4 (30 minutes, 308MB)

---

## 📊 Results

### Test 1: Single Request
- **Time**: 121s (2 minutes 1 second)
- **Status**: ✅ Success
- **Text Length**: 2,558 chars
- **Queue**: Redis Queue

### Test 2: 5 Concurrent Requests
- **Total Time**: 595s (9 minutes 55 seconds)
- **Completed**: 5/5 (100%)
- **Failed**: 0/5
- **Average per Request**: 119s

---

## 🔍 Analysis

### Comparison

| Metric | Before (Init per job) | After (Persistent) | Change |
|--------|----------------------|-------------------|--------|
| Single request | 121s | 121s | 0% |
| 5 concurrent | 598s | 595s | -0.5% |
| Success rate | 100% | 100% | Same |

### Observations

1. **No significant improvement yet**
   - เวลายังเหมือนเดิม (~121s)
   - อาจเป็นเพราะ:
     - Model ยังถูก init ใหม่ทุกครั้ง
     - หรือ persistent worker ยังไม่ทำงาน

2. **Success Rate 100%**
   - ไม่มี timeout
   - Queue system ทำงานได้ดี

3. **Concurrent Processing**
   - 5 requests สำเร็จทั้งหมด
   - Average 119s ต่อ request (ใกล้เคียง single request)

---

## 🔧 Next Steps

1. **ตรวจสอบว่า persistent worker ทำงานจริง**
   - ดู logs ว่า "Initializing persistent TranscriptionService" ปรากฏหรือไม่
   - ตรวจสอบว่า model ถูก reuse หรือ init ใหม่ทุกครั้ง

2. **ตรวจสอบ Worker Function Path**
   - ตรวจสอบว่า RQ ใช้ `app.workers.rq_worker.process_transcription_job` หรือไม่

3. **Monitor Model Loading**
   - ดูว่า job แรกใช้เวลานานกว่า job ถัดไปหรือไม่
   - ถ้า job แรกช้ากว่า = model ถูก init ใหม่ทุกครั้ง

---

## 📝 Notes

- Persistent worker module ถูกสร้างแล้ว (`app/workers/rq_worker.py`)
- RedisQueueService ใช้ path ถูกต้องแล้ว
- Workers ถูก restart แล้ว
- ต้องตรวจสอบ logs เพิ่มเติมเพื่อยืนยันว่า persistent service ทำงาน

