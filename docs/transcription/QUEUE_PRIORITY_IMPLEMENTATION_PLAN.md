# แผน Implement Queue Priority (Live / Record / Upload)

**วันที่:** 2026-02-24  
**อ้างอิง:** คำแนะนำจากผู้เชี่ยวชาญเรื่อง cooperative preemption และ 3-level queue

---

## 1. สถานะปัจจุบันของระบบ

### 1.1 โครงสร้างคิวที่มีอยู่

| ประเภท | คิว | Worker ที่ฟัง | สถานะ |
|--------|-----|--------------|--------|
| **Live (FE Live / NeMo CC)** | `transcription_priority` | GPU workers 0..(CC-1) ฟัง priority ก่อน gpu$i | ✅ แยกแล้ว |
| **Record (Video Record)** | Preprocess: `transcription_preprocess_video_record` | Preprocess workers ฟัง video_record ก่อน preprocess | ✅ แยกที่ preprocess |
| **Upload (File Transcription)** | Preprocess: `transcription_preprocess` | Preprocess workers | ✅ แยกที่ preprocess |

**จุดสำคัญ:** Record และ Upload แยกกันเฉพาะที่ **preprocess** เท่านั้น  
หลัง preprocess เสร็จ → chunks ทั้งสองประเภทไป **คิว GPU เดียวกัน** (`transcription_gpu0`, `transcription_gpu1`)

### 1.2 Flow ปัจจุบัน

```
API Request (source=video_record หรือ null)
    ↓
Rate Limiter (MAX_CONCURRENT_REQUESTS=50)
    ↓
Preprocess Queue: video_record → preprocess_video_record, อื่นๆ → preprocess
    ↓
Preprocess Worker (ฟัง video_record ก่อน)
    ↓
Enqueue chunks → transcription_gpu0, transcription_gpu1 (ไม่มี source)
    ↓
Chunk เสร็จ → enqueue chunk ถัดไป (ไม่มี cooperative preemption)
```

### 1.3 สิ่งที่ยังไม่มี

- [ ] **source** ไม่ถูกส่งต่อใน `chunks_metadata` → chunk completion ไม่รู้ว่าเป็น Record หรือ Upload
- [ ] **Cooperative preemption** — เมื่อ Record backlog > 0 ไม่มีการ hold การ enqueue chunk ถัดไปของ Upload
- [ ] **Live reserved slots** — Live ใช้ priority queue แต่ไม่มี hard-reserve (อาจถูก file jobs แย่งได้)
- [ ] **Record vs Upload แยกที่ GPU level** — chunks ทั้งสองไปคิวเดียวกัน
- [ ] **Chunk duration แยก Record/Upload** — Record ควรใช้ 60–120s, Upload ใช้ 240s ได้
- [ ] **Aging** — Upload ที่รอนานไม่มี priority boost

---

## 2. ความเป็นไปได้ของคำแนะนำ

### 2.1 สรุป: **ทำได้** แต่ต้องแก้หลายจุด

| คำแนะนำ | ทำได้ | ความซับซ้อน | หมายเหตุ |
|---------|-------|-------------|----------|
| 1. แยกคิว 3 ระดับ (Live / Record / Upload) | ✅ | กลาง | Live มีแล้ว, Record/Upload แยกที่ preprocess แล้ว แต่ GPU ยังรวมกัน |
| 2. Hard-reserve ให้ Live (4 slots) | ✅ | ต่ำ | ปรับ `GPU_WORKERS_FOR_CC_PER_GPU` และ worker listen order |
| 3. Cooperative preemption (hold Upload เมื่อ Record backlog > 0) | ✅ | สูง | ต้องส่ง `source` ผ่าน chunks_metadata และเพิ่ม logic ใน chunk completion |
| 4. Record chunk 60–120s, Upload 240s | ✅ | ต่ำ | เพิ่ม env `RECORD_CHUNK_DURATION` |
| 5. Aging สำหรับ Upload | ✅ | กลาง | ต้องเก็บ `created_at` ใน metadata และตรวจก่อน enqueue |

---

## 3. แผน Implement แบบ Phase

### Phase 1: พื้นฐาน (ทำได้เร็ว)

#### 1.1 ส่ง `source` ผ่าน chunks_metadata

**ไฟล์:** `app/workers/rq_worker.py`

- `process_preprocess_job`: เพิ่ม `source` ใน `chunks_metadata` (ต้องรับจาก task_data หรือ API)
- `process_preprocess_job_chunk_group`: เพิ่ม `source` ใน `chunks_metadata`

**ไฟล์:** `app/api/transcribe.py`, `app/api/transcription_enhanced.py`

- ส่ง `source` ไปยัง preprocess (มีอยู่แล้วบางส่วน — ตรวจสอบว่าเก็บใน task_data หรือไม่)

#### 1.2 Chunk duration แยก Record/Upload

**Env:**
```bash
# Record: ไฟล์ 10 นาที/ทุก 10 นาที — ใช้ chunk สั้นเพื่อแซงได้เร็ว
RECORD_CHUNK_DURATION=120
# Upload: ไฟล์ ~30 นาที — ใช้ 240s ได้
TRANSCRIPTION_CHUNK_DURATION=240
```

**Logic:** ใน preprocess ถ้า `source == 'video_record'` ใช้ `RECORD_CHUNK_DURATION` แทน

#### 1.3 Live Reserved Slots

**Env (ใน .env.runpod):**
```bash
# Live concurrent สูงสุด 2 stream → กัน 4 tasks
LIVE_RESERVED_SLOTS=4
# หรือใช้ GPU_WORKERS_FOR_CC_PER_GPU=2 ต่อ GPU (2 GPU = 4 workers ฟัง priority)
```

**สถานะปัจจุบัน:** มี `GPU_WORKERS_FOR_CC_PER_GPU=2` อยู่แล้ว → workers ที่ฟัง priority มี 4 ตัว (2 GPU × 2)  
→ **Live มี reserved อยู่แล้วในทางปฏิบัติ** แต่ควรเพิ่ม env `LIVE_RESERVED_SLOTS` เพื่อความชัดเจน

---

### Phase 2: Cooperative Preemption (สำคัญที่สุด)

#### 2.1 เก็บ `source` ใน chunks_metadata

ใน `process_preprocess_job` และ `process_preprocess_job_chunk_group`:

```python
chunks_metadata = {
    "chunk_paths": chunks,
    "next_chunk_index": enqueued_count,
    "total_chunks": total_chunks,
    "chunk_duration": chunk_duration,
    "language": language,
    "model_size": model_size,
    "source": task_data.get("source") or "upload",  # "video_record" หรือ "upload"
    "created_at": datetime.now(timezone.utc).isoformat(),  # สำหรับ aging
}
```

#### 2.2 ฟังก์ชันตรวจสอบ Record Backlog

**ไฟล์:** `app/services/redis_queue_service.py` หรือ helper ใหม่

```python
def get_record_backlog_count(self) -> int:
    """จำนวน Record jobs ที่รอหรือกำลังรัน (preprocess + GPU chunks)"""
    from rq.registry import StartedJobRegistry
    # Preprocess video_record queue
    preprocess_record = len(self.preprocess_video_record_queue) + \
        len(StartedJobRegistry(queue=self.preprocess_video_record_queue))
    # Record chunks ใน GPU queues — ต้อง track ว่า task ไหนเป็น record
    # วิธีง่าย: ใช้ Redis set เก็บ task_id ของ record ที่กำลังมี chunks รัน
    # หรือประมาณจาก preprocess_record * avg_chunks_per_task
    return preprocess_record  # เริ่มจากแค่ preprocess ก่อน
```

#### 2.3 Logic Cooperative Preemption ใน Chunk Completion

**ไฟล์:** `app/workers/rq_worker.py` — ใน `process_transcription_job` ตอนที่ chunk เสร็จและจะ enqueue chunk ถัดไป:

```python
# ก่อน enqueue next chunk — ตรวจสอบ cooperative preemption
source = chunks_metadata.get("source", "upload")
if source == "upload":
    from app.services.redis_queue_service import get_redis_queue_service
    queue_service = get_redis_queue_service()
    record_backlog = queue_service.get_record_backlog_count()
    if record_backlog > 0:
        # Hold: ไม่ enqueue chunk ถัดไป — เก็บไว้ใน deferred
        # ต้องมี mechanism "retry" เมื่อ record_backlog == 0
        logger.info(f"⏸️ Hold upload chunk {claimed_index+1}/{total_chunks} (record_backlog={record_backlog})")
        # ไม่ enqueue — chunk จะถูก enqueue เมื่อมี scheduler ตรวจหรือ record โล่ง
        # Option: ใช้ Redis list เก็บ "deferred_upload_chunks" แล้วมี worker ตรวจสอบ
        return  # ไม่ enqueue
```

**ปัญหาที่ต้องแก้:** เมื่อ hold แล้ว ต้องมี mechanism "ปล่อย" เมื่อ record โล่ง  
→ ต้องมี **Scheduler/Controller** หรือ **periodic retry** ที่ตรวจ `record_backlog` แล้ว enqueue deferred chunks

#### 2.4 ทางเลือก: ใช้แยก GPU Queue สำหรับ Record vs Upload

แทนการใช้ cooperative preemption ที่ซับซ้อน อาจใช้:

- **transcription_gpu_record_0**, **transcription_gpu_record_1** — สำหรับ Record chunks
- **transcription_gpu_upload_0**, **transcription_gpu_upload_1** — สำหรับ Upload chunks

Worker ฟังตามลำดับ: `priority` → `gpu_record_$i` → `gpu_upload_$i`

→ Record แซง Upload ได้โดยธรรมชาติ (queue order)  
→ ไม่ต้อง hold/defer — แค่เลือก queue ตาม source

---

### Phase 3: ค่าที่แนะนำ (จากคำแนะนำ)

| ค่า | ค่าแนะนำ | หมายเหตุ |
|-----|----------|----------|
| MAX_TASKS | 25 | ใช้ MAX_CONCURRENT_REQUESTS=50 อยู่ (rate limit 50) |
| LIVE_RESERVED | 4 | 2 stream × 2 = 4 slots |
| RECORD_MAX | 10 | ใช้ shared pool 21 (25-4) |
| UPLOAD_MAX | 11 | ใช้ shared pool |
| Preempt rule | record_backlog > 0 ⇒ UPLOAD_MAX = 0–2 | ไม่เริ่ม chunk upload ใหม่ |

---

## 4. คำตอบคำถาม: 1 task = 1 GPU job ใช่ไหม?

**จาก code:**
- `process_transcription_job` = 1 chunk = 1 GPU inference
- 1 task (ไฟล์ 10–30 นาที) = หลาย chunks (เช่น 4–10 chunks ตาม chunk_duration)
- ดังนั้น **1 task ≠ 1 GPU job** — 1 task = 1 preprocess + N chunk jobs + 1 aggregator

**Bottleneck:**
- **GPU:** inference (ใช้ VRAM, CUDA)
- **CPU:** preprocess (ffmpeg extract, chunking), aggregator (รวมผล)
- **vCPU 10:** ต้องระวัง NUM_PREPROCESS_WORKERS (ปัจจุบัน 4) และ CPU workers (2)

---

## 5. สรุปและแผนดำเนินการ

### ทำได้แน่นอน (Phase 1)
1. ส่ง `source` ผ่าน chunks_metadata
2. Chunk duration แยก Record (120s) vs Upload (240s)
3. Live reserved 4 slots (มีอยู่แล้วบางส่วน — ตรวจสอบและยืนยัน)

### ต้องออกแบบเพิ่ม (Phase 2)
4. **Cooperative preemption** — ทางเลือก:
   - **A)** แยก GPU queue Record/Upload (ง่ายกว่า, ไม่ต้อง defer)
   - **B)** Hold + Scheduler/Retry (ซับซ้อนกว่า, แต่ control ละเอียดกว่า)

### แนะนำ
เริ่มจาก **Option A (แยก GPU queue)** เพราะ:
- Implement ง่ายกว่า
- ไม่ต้องมี Scheduler แยก
- RQ worker ฟังหลาย queue ตามลำดับได้อยู่แล้ว

---

## 6. อ้างอิงไฟล์ที่เกี่ยวข้อง

| ไฟล์ | บทบาท |
|------|--------|
| `app/services/redis_queue_service.py` | Queue, enqueue logic |
| `app/workers/rq_worker.py` | process_preprocess_job, process_preprocess_job_chunk_group, process_transcription_job (chunk completion) |
| `app/api/transcribe.py` | API, รับ source |
| `scripts/pod/start-rq-workers.sh` | Worker startup, queue order |
| `app/services/rate_limiter.py` | MAX_CONCURRENT_REQUESTS=50 |
