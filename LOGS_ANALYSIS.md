# 📊 การวิเคราะห์ Logs และปัญหา

## 🔍 สรุปปัญหา

**วันที่**: 2026-01-12  
**Model**: `models--Vinxscribe--biodatlab-whisper-th-medium-faster` ✅

---

## ⚠️ ปัญหาที่พบ

### 1. **Worker เต็ม - มี Transcription Jobs อื่นๆ กำลังทำงาน**

**Queue Status**:
- **GPU 0**: 
  - 10 jobs ใน queue (รอ)
  - 4 jobs กำลังทำงาน (started)
  - 901 finished
  - 550 failed
- **GPU 1**: 
  - 0 jobs ใน queue
  - 2 jobs กำลังทำงาน (started)
  - 56 finished
  - 14 failed

**GPU Utilization**:
- **GPU 0**: 100% utilization, 6885 MiB / 20475 MiB (33% memory)
- **GPU 1**: 58% utilization, 1060 MiB / 20475 MiB (5% memory)

### 2. **live-chunk ไม่ใช้ RQ - ใช้ Background Tasks**

**ปัญหา**:
- `live-chunk` endpoint ใช้ `background_tasks.add_task()` แทน Redis Queue
- รันใน main API process (uvicorn) โดยตรง
- เรียก `whisper_service.transcribe_file()` โดยตรง ซึ่งต้องรอ GPU

**ผลกระทบ**:
- ถ้า GPU เต็ม (100% utilization) → transcription ช้ามากหรือค้าง
- ไม่สามารถ queue ได้ → ต้องรอให้ transcription เสร็จก่อน
- ไม่มี retry mechanism → ถ้า fail จะไม่ retry

### 3. **ไม่พบ Logs ของ live-chunk**

**การตรวจสอบ**:
- ไม่พบ logs ของ `live-chunk` ใน `/tmp/main-api.log`
- ไม่พบ logs ของ `process_live_chunk_background`
- ไม่พบ error logs

**ความเป็นไปได้**:
1. Background task ไม่ได้รัน (silent failure)
2. Transcription ใช้เวลานานมาก (> 60 วินาที) และยังไม่เสร็จ
3. Logs ไม่ได้เขียนลงไฟล์ (อาจจะ stdout/stderr เท่านั้น)

---

## 💡 สาเหตุที่เป็นไปได้

### 1. **GPU 0 เต็ม (100% utilization)**

**ผลกระทบ**:
- `live-chunk` ต้องรอ GPU 0 ว่างก่อน
- มี 10 jobs ใน queue → ต้องรอให้ jobs เหล่านี้เสร็จก่อน
- มี 4 jobs กำลังทำงาน → อาจใช้เวลานาน

### 2. **Model `medium-faster` ใช้เวลานาน**

**ผลกระทบ**:
- Model `medium-faster` อาจใช้เวลา 10-30 วินาทีต่อ chunk
- ถ้า GPU เต็ม → อาจใช้เวลานานกว่า 60 วินาที

### 3. **Background Task ไม่ได้รัน**

**ความเป็นไปได้**:
- Background task อาจไม่ได้รัน (silent failure)
- Transcription อาจ fail แต่ไม่ได้ log error

---

## 🔧 วิธีแก้ไข

### 1. **เปลี่ยน live-chunk ให้ใช้ RQ**

**ข้อดี**:
- ✅ สามารถ queue ได้ (ไม่ต้องรอ)
- ✅ มี retry mechanism
- ✅ ใช้ GPU workers ที่มีอยู่แล้ว
- ✅ รองรับ priority queue

**การแก้ไข**:
```python
# แทนที่ background_tasks.add_task() ด้วย RQ
from app.services.redis_queue_service import get_redis_queue_service

queue_service = get_redis_queue_service()
job_id = queue_service.enqueue_live_chunk(
    meeting_id=meeting_id,
    chunk_index=chunk_index,
    audio_path=temp_path,
    ...
)
```

### 2. **ใช้ Priority Queue สำหรับ live-chunk**

**ข้อดี**:
- ✅ live-chunk จะได้ priority สูงกว่า transcription ปกติ
- ✅ จะได้ GPU ก่อน jobs อื่นๆ

### 3. **ตรวจสอบ Logs เพิ่มเติม**

**คำสั่ง**:
```bash
# ดู logs ของ uvicorn (stdout/stderr)
ps aux | grep uvicorn
# ดู logs ของ background tasks
tail -f /tmp/main-api.log | grep -i "live-chunk\|transcription"
```

### 4. **ลด Queue Size**

**คำสั่ง**:
```bash
# ตรวจสอบ queue stats
python3 -c "from app.services.redis_queue_service import get_redis_queue_service; service = get_redis_queue_service(); print(service.get_queue_stats())"

# Clear queue (ถ้าจำเป็น)
python3 scripts/clear_all_jobs.py
```

---

## 📝 สรุป

### ปัญหาหลัก:
1. ✅ **Worker เต็ม** - มี transcription jobs อื่นๆ กำลังทำงาน (4 jobs บน GPU0, 2 jobs บน GPU1)
2. ✅ **GPU 0 เต็ม** - 100% utilization, มี 10 jobs ใน queue
3. ✅ **live-chunk ไม่ใช้ RQ** - ใช้ background tasks ซึ่งต้องรอ GPU
4. ❌ **ไม่พบ Logs** - ไม่ทราบว่า transcription ทำงานหรือไม่

### Model Configuration:
- ✅ `CC_MODEL_SIZE=models--Vinxscribe--biodatlab-whisper-th-medium-faster` (ถูกต้อง)
- ✅ `CC_ENABLED=true` (เปิดใช้งาน)

### ขั้นตอนถัดไป:
1. ตรวจสอบ logs ของ uvicorn (stdout/stderr)
2. เปลี่ยน live-chunk ให้ใช้ RQ + Priority Queue
3. ลด queue size (clear jobs ที่ค้างอยู่)
4. ทดสอบอีกครั้งหลังจาก clear queue

---

**Last Updated**: 2026-01-12
