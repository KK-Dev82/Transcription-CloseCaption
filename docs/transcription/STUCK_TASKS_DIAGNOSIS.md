# การวินิจฉัย Tasks ค้าง (CPU/GPU ใช้แต่ไม่มีการแปลงเสียง)

## สถานการณ์ที่พบ

- มี tasks status=processing
- CPU/GPU มีการใช้งาน (จาก watch_resources)
- แต่ไม่มีการแปลงเสียงเป็นข้อความ
- **Task ค้างที่ 40%** — Aggregator รอ chunks แต่ done_chunks ไม่เพิ่ม

## สาเหตุที่พบจาก Diagnostic

### 1. Tasks ติด On Hold (Priority feature)
- Tasks อยู่ใน Redis `tasks:on_hold`
- `next_chunk_index=0`, `done_chunks=0`, `inflight=0` → **ไม่มี chunk ถูก enqueue เลย**
- Preprocess เสร็จแล้ว แต่ chunk ไม่ถูกส่งไป GPU queue เพราะ record_backlog > 0 ตอนนั้น

### 2. ไม่มี Trigger ให้ Resume
- `_try_release_on_hold_tasks` ถูกเรียกเฉพาะเมื่อ **chunk เสร็จ**
- ถ้าทุก task on_hold (ไม่มี chunk รัน) → ไม่มี chunk จะเสร็จ → **deadlock**

### 3. Periodic Release (แก้แล้ว)
- เพิ่ม `try_release_on_hold_tasks()` ใน StuckTaskMonitor
- เรียกทุก 30 วินาที เมื่อ record_backlog == 0

**หมายเหตุ**: StuckTaskMonitor รันใน **Main API process** เท่านั้น  
→ ต้องมี Main API (uvicorn) รันอยู่ ถึงจะมีการ release อัตโนมัติ

### 4. Preprocess Trigger (แก้แล้ว - ไม่ต้องพึ่ง Main API)
- เรียก `try_release_on_hold_tasks()` ที่ **ต้น preprocess job** (ใน RQ worker)
- ทุกครั้งที่ preprocess worker รับ job ใหม่ (รวม Resubmit) จะ release on_hold ก่อน
- **ไม่ต้องมี Main API รัน** — ทำงานได้แม้รันแค่ workers

## วิธีตรวจสอบและแก้ไข

### 1. ตรวจสอบสถานะ
```bash
python scripts/diagnose_stuck_processing.py
```

### 2. ตรวจสอบว่า Main API รันอยู่หรือไม่
```bash
pgrep -f "uvicorn.*app.main"
curl -s http://localhost:8010/health
```
ถ้า Main API ไม่รัน → Periodic release จะไม่ทำงาน

### 3. Release แบบ Manual (เมื่อ record_backlog=0)
```bash
# วิธีที่ 1: สคริปต์สำเร็จรูป
./scripts/run_release_on_hold.sh

# วิธีที่ 2: รันเป็น loop ทุก 30 วินาที (background)
./scripts/run_release_on_hold.sh --loop 30 &

# วิธีที่ 3: Python one-liner
python -c "
from app.services.on_hold_release import try_release_on_hold_tasks
released = try_release_on_hold_tasks()
print('Released:', released)
"
```

### 4. Resume ผ่าน API (สำหรับ task ที่รู้ task_id)
```bash
curl -X POST "http://localhost:8010/api/v2/tasks/{task_id}/resume"
```

### 5. ตรวจสอบ Workers
```bash
# Workers ต้องฟัง transcription_gpu_upload_* และ transcription_gpu_record_*
ps aux | grep "rq worker"
tail -50 /tmp/rq-worker-gpu0-w0.log
```

### 6. ตรวจสอบ Queue
```bash
curl -s http://localhost:8010/api/transcribe/debug/queue | python3 -m json.tool
```

## สรุป Flow

```
Preprocess เสร็จ → record_backlog > 0? 
  YES → on_hold (ไม่ enqueue chunks)
  NO  → enqueue chunks ไป GPU

On Hold → รอ record_backlog = 0
  Trigger 1: Chunk เสร็จ → _try_release_on_hold_tasks (ใน rq_worker)
  Trigger 2: ทุก 30s → try_release_on_hold_tasks (ใน StuckTaskMonitor - Main API)
  Trigger 3: ต้น preprocess job → try_release_on_hold_tasks (ใน rq_worker) ← ไม่ต้องพึ่ง Main API
```

**สำคัญ**: Trigger 3 ทำให้ Resubmit หรือ job ใหม่ใดๆ จะ release on_hold อัตโนมัติ แม้ Main API ไม่รัน

### 5. แก้ไขตั้งแต่ Priority (2026-02)
- **ENABLE_ON_HOLD_FOR_RECORD=false** เป็น default — ป้องกัน task ค้างเมื่อใช้แค่ Upload
- **get_record_backlog_count** กรอง stale jobs (worker ตาย, orphan ใน StartedJobRegistry)
- ถ้าใช้แค่ Upload → ตั้ง `ENABLE_ON_HOLD_FOR_RECORD=false` ใน .env

---

## Resubmit แล้ว GPU ไม่ทำงาน

### Flow ของ Resubmit
1. API สร้าง task ใหม่ + enqueue preprocess job ไป Redis
2. Preprocess worker รับ job → extract audio, create chunks
3. Enqueue chunk jobs ไป GPU queue (หรือ on_hold ถ้า record_backlog > 0)
4. GPU workers รับ chunk jobs → แปลงเสียง

### สาเหตุที่ GPU ไม่ทำงาน

| สาเหตุ | ตรวจสอบ |
|--------|----------|
| **Preprocess workers ไม่รัน** | `ps aux \| grep "rq worker"` |
| **GPU workers ไม่รัน** | เหมือนด้านบน |
| **REDIS_URL ไม่ตรง** | API และ Workers ต้องใช้ Redis ตัวเดียวกัน |
| **On_hold** | Preprocess เสร็จแต่ record_backlog > 0 → chunks ไม่ไป GPU |

### ตรวจสอบ Resubmit flow
```bash
./scripts/check_resubmit_flow.sh
```
