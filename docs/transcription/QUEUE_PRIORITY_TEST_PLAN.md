# แผนทดสอบ Shared Pool + Priority Queue

**วันที่:** 2026-02-24  
**วัตถุประสงค์:** ตรวจสอบว่าระบบคิวทำงานถูกต้องตาม Shared Pool + Priority (Live > Record > Upload)

---

## สิ่งที่ต้องทดสอบ

| # | รายการ | วิธีตรวจสอบ |
|---|--------|-------------|
| 1 | Upload → ไปคิว upload | ดู record_* = 0, upload_* > 0 |
| 2 | Record → ไปคิว record | ดู upload_* ไม่เพิ่ม, record_* > 0 |
| 3 | Record แซง Upload | ส่ง Upload ก่อน แล้วส่ง Record → Record ได้ slot ก่อน |
| 4 | Live/Record ว่าง → Upload เต็ม 25 | Upload ใช้ได้เต็มเมื่อไม่มี Live/Record |

---

## เครื่องมือที่ใช้

### 1. Debug Endpoint (ตรวจสอบ queue status)

```bash
curl -s http://localhost:8010/api/transcribe/debug/queue | jq '.queues'
```

หรือ

```bash
curl -s http://localhost:8010/api/monitoring/queues
```

**ดูที่:** `record_gpu0`, `record_gpu1`, `upload_gpu0`, `upload_gpu1`, `priority`

### 2. RQ Info (ถ้ามี rq ติดตั้ง)

```bash
rq info --url $REDIS_URL
```

### 3. Worker Logs

```bash
tail -f /tmp/rq-worker-gpu0-w0.log
# ดู log ว่า job ไป queue ไหน เช่น "Enqueueing Record job" หรือ "Enqueueing Upload job"
```

---

## แผนทดสอบแบบง่าย (Manual)

### Test 1: Upload ไปคิว Upload

**ขั้นตอน:**
1. Clear queue ก่อน: `python scripts/clear_all_jobs.py` (หรือรอให้ queue ว่าง)
2. ส่ง 1 Upload task (ไม่ใส่ source หรือ source=null):
   ```bash
   curl -X POST http://localhost:8010/api/transcribe/ \
     -H "Content-Type: application/json" \
     -d '{"file_path": "uploads/your_file.wav", "language": "th"}'
   ```
3. รอ ~10–30 วินาที (ให้ preprocess เสร็จ แล้ว chunks ไป GPU queue)
4. ตรวจสอบ:
   ```bash
   curl -s http://localhost:8010/api/transcribe/debug/queue | jq '.queues | {upload_gpu0, upload_gpu1, record_gpu0, record_gpu1}'
   ```
   **คาดหวัง:** `upload_gpu0` หรือ `upload_gpu1` มี `length` หรือ `started` > 0, `record_*` = 0

---

### Test 2: Record ไปคิว Record

**ขั้นตอน:**
1. Clear queue ก่อน
2. ส่ง 1 Record task (source=video_record):
   ```bash
   curl -X POST http://localhost:8010/api/transcribe/ \
     -H "Content-Type: application/json" \
     -d '{"file_path": "uploads/your_file.wav", "language": "th", "source": "video_record"}'
   ```
3. รอ ~10–30 วินาที
4. ตรวจสอบ:
   ```bash
   curl -s http://localhost:8010/api/transcribe/debug/queue | jq '.queues | {upload_gpu0, upload_gpu1, record_gpu0, record_gpu1}'
   ```
   **คาดหวัง:** `record_gpu0` หรือ `record_gpu1` มี `length` หรือ `started` > 0

---

### Test 3: Record แซง Upload (Priority)

**ขั้นตอน:**
1. Clear queue
2. ส่ง Upload 5–10 tasks ก่อน (ให้ preprocess เริ่มและ chunks ไป upload queue)
3. รอ ~20 วินาที
4. ส่ง Record 1 task (source=video_record)
5. ดู worker log:
   ```bash
   tail -f /tmp/rq-worker-gpu0-w0.log
   ```
   **คาดหวัง:** เห็น "Enqueueing Record job" และ Record ถูก process ก่อน Upload ที่รออยู่ (เมื่อ worker ว่าง จะดึง Record ก่อน)
6. ตรวจสอบ queue: Record ควรมี `started` หรือ `length` ลดลงก่อน Upload

**หมายเหตุ:** การ "แซง" เกิดขึ้นเมื่อ worker ว่าง → เช็ค priority ก่อน → record → upload ดังนั้น Record จะได้ slot แรกที่ว่าง

---

### Test 4: Chunk Duration แยก Record/Upload

**ขั้นตอน:**
1. ส่ง Record task (source=video_record) กับไฟล์ ~10 นาที
2. ดู worker log ว่าใช้ `RECORD_CHUNK_DURATION=120`:
   ```bash
   grep "Record mode: ใช้ RECORD_CHUNK_DURATION" /tmp/rq-worker-preprocess-0.log
   ```
3. ส่ง Upload task (ไม่ใส่ source) กับไฟล์เดียวกัน
4. เปรียบเทียบจำนวน chunks: Record ควรมี chunks มากกว่า (120s vs 240s)

---

## แผนทดสอบแบบ Script (Optional)

สร้าง script `scripts/test_queue_priority.py`:

```python
#!/usr/bin/env python3
"""ทดสอบ Queue Priority: Upload vs Record ไปคิวถูกต้อง"""
import requests
import time
import os

BASE = os.getenv("API_BASE", "http://localhost:8010")
FILE = "uploads/your_test_file.wav"  # ต้องมีไฟล์จริง

def debug_queues():
    r = requests.get(f"{BASE}/api/transcribe/debug/queue", timeout=5)
    return r.json().get("queues", {})

def send_upload():
    r = requests.post(f"{BASE}/api/transcribe/", json={
        "file_path": FILE, "language": "th"
    }, timeout=10)
    return r.json().get("task_id")

def send_record():
    r = requests.post(f"{BASE}/api/transcribe/", json={
        "file_path": FILE, "language": "th", "source": "video_record"
    }, timeout=10)
    return r.json().get("task_id")

# Test 1: Upload
print("Test 1: Send Upload...")
t1 = send_upload()
time.sleep(25)
q = debug_queues()
u = q.get("upload_gpu0", {}) or q.get("upload_gpu1", {})
ok = (u.get("length", 0) + u.get("started", 0)) > 0
print(f"  Upload queue has jobs: {ok} (task_id={t1[:8]}...)")

# Test 2: Record
print("Test 2: Send Record...")
t2 = send_record()
time.sleep(25)
q = debug_queues()
r = q.get("record_gpu0", {}) or q.get("record_gpu1", {})
ok = (r.get("length", 0) + r.get("started", 0)) > 0
print(f"  Record queue has jobs: {ok} (task_id={t2[:8]}...)")
```

---

## Checklist สรุป

- [ ] Test 1: Upload → upload_gpu* มี jobs
- [ ] Test 2: Record → record_gpu* มี jobs
- [ ] Test 3: Record แซง Upload (ดูจาก log หรือ queue order)
- [ ] Test 4: Record ใช้ RECORD_CHUNK_DURATION (ดูจาก log)
- [ ] Worker ฟัง priority → record → upload (ดูจาก start-rq-workers.sh output)

---

## หมายเหตุ

- ต้องมีไฟล์ทดสอบใน `uploads/` (เช่น .wav, .m4a)
- ต้องมี API + Workers + Redis ทำงานอยู่
- Preprocess ใช้เวลา ~10–30 วินาที ก่อน chunks ไป GPU queue
