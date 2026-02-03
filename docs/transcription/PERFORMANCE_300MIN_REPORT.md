# รายงาน Performance งานแปลงข้อมูลยาว (200+ นาที)

**วันที่วิเคราะห์:** 2026-01-29  
**แหล่งข้อมูล:** SQLite storage (`phase_timings`), สคริปต์ `scripts/analyze_performance.py`

---

## 1. งานที่ใช้เวลานานที่สุดใน Storage

| รายการ | ค่า |
|--------|-----|
| **Task ID** | `dc534414-5fef-49b9-a5aa-4f597396d16d` |
| **ไฟล์** | `uploads/5e8413e7-c89d-4c9c-88bf-e3d7b8849687_S25690120008167C03.wav` |
| **สร้างเมื่อ** | 2026-01-20 10:03:36 UTC |
| **เสร็จเมื่อ** | 2026-01-20 13:56:29 UTC |
| **Total End-to-End** | **232.83 นาที** (~3 ชม. 53 นาที) |
| **Wall clock (created → completed)** | ~232.88 นาที |

### Phase breakdown (งาน 232 นาที)

- **Preprocess:** รวม ~9.4 วินาที (extract ~0.4s, chunk ~0.4s, enqueue ~0.9s) → **~0.01%** ของ total
- **Aggregator (ที่บันทึก):** รวม ~6.3 วินาที (wait_chunks, fetch, merge, thai)  
  - หมายเหตุ: งานนี้เวลาส่วนใหญ่ (~232 นาที) อยู่ที่ **การรอ GPU แปลงทุก chunk** (ช่วงระหว่าง preprocess จบ กับ aggregator เริ่ม) ซึ่งอาจไม่ถูกแยกเก็บใน `wait_chunks_time` ในรุ่นที่รันงานนี้

---

## 2. Performance จากงานที่ completed ล่าสุด (มี phase_timings ชัด)

จาก 30 task ที่วิเคราะห์ (เรียงตาม Total End-to-End):

| ตัวชี้วัด | ค่า |
|-----------|-----|
| **งานที่ใช้เวลานานสุด (E2E)** | **4.05 นาที** (task `f027feb0-...`) |
| **งานที่สั้นสุด (E2E)** | **0.39 นาที** (~23 วินาที) |
| **เวลาเฉลี่ยต่อ task** | **~2.1 นาที** |
| **เวลารวม (30 task)** | **61.7 นาที** |

### สัดส่วนเวลาโดย phase (งาน 2–4 นาที)

- **Preprocess (extract + chunk + enqueue):** ~5–11% ของ total
- **Wait chunks (รอ GPU ทำครบทุก chunk):** **~75–88%** ของ total ← **bottleneck หลัก**
- **Fetch + Merge + Thai:** ~2–6% ของ total

---

## 3. สรุป Performance

1. **งาน ~233 นาที (ใกล้ 300 นาที)**  
   - มีใน storage งานเดียวที่ **Total End-to-End ~232.83 นาที**  
   - เวลาส่วนใหญ่เป็น **การประมวลผล GPU แปลงทีละ chunk** (หลายร้อย/พัน chunk)  
   - Preprocess ใช้เวลาไม่ถึง 10 วินาที (~0.01%)

2. **Bottleneck หลัก (จากงาน 2–4 นาที)**  
   - **Wait chunks** ใช้ **75–88%** ของเวลารวม  
   - แนะนำตาม `PERFORMANCE_RECORDS.md`: เพิ่ม `GPU_WORKERS_PER_GPU`, `CHUNK_INFLIGHT_LIMIT_PER_JOB`, `CHUNK_ENQUEUE_WINDOW_SIZE` เพื่อให้ GPU ได้งานต่อเนื่องและลดเวลารอ

3. **Logs**  
   - ในโฟลเดอร์ `logs/` ของ repo ไม่พบบรรทัด "Total End-to-End" / "minutes)" (อาจ log อยู่ที่ RunPod หรือ rotation ไปแล้ว)  
   - ใช้ **Storage (phase_timings)** เป็นแหล่งหลักสำหรับวิเคราะห์ performance

---

## 4. Chunk duration (File transcription) และ Live CC

### File transcription (use_chunking)

- **Default chunk:** **150 วินาที (2.5 นาที)** ไม่ใช่ 30 วินาที  
  - มาจาก `request.chunk_duration or 150` ใน `app/api/transcribe.py` และ `process_preprocess_job(..., chunk_duration=150)` ใน RQ worker
- **ถ้าลดเหลือ 10 วินาที:** จำนวน chunk จะเพิ่มประมาณ 15 เท่า (150/10)  
  - **แนวโน้ม:** ไม่ทำให้เร็วขึ้น โดยรวมอาจช้าลง เพราะ (1) overhead ต่อ chunk สูง (2) wait_chunks รอ chunk มากขึ้น (3) คิว GPU แย่งกันมากขึ้น  
  - Chunk เล็กเกินไป (เช่น 10s) มักทำให้ throughput แย่ลง

**Segment ละ 30 วินาที:** ตอนนี้ default คือ **150 วินาที** ไม่ใช่ 30 — ถ้าต้องการ 30s ส่ง `chunk_duration: 30` จาก client ได้  
**Overlapping สำหรับ file transcription:** ตอนนี้ **ยังไม่มี** — `create_chunks` ตัดแบบไม่ overlap (chunk 0: 0–150s, chunk 1: 150–300s, …). ถ้าต้องการ overlap ต้องเพิ่ม logic (hop + window, merge/dedupe ผล) ใน video_service + aggregator  
**Segment ละ 10 วินาที:** **ได้** — ส่ง `chunk_duration: 10` ใน request ได้ (API รองรับอยู่แล้ว) แต่จำนวน chunk จะเพิ่มมาก เวลารวมอาจช้าลง

### Live-chunk FE CC (Close Caption)

- **การแปลง (backend):**
  - **Hop (ความยาว chunk ที่ส่งเข้า inference):** **3 วินาที** (env: `CC_CHUNK_HOP`, default `3.0`)
  - **Overlap:** **0.6 วินาที** (env: `CC_CHUNK_OVERLAP`, default `0.6`)
  - Window = 3 + 0.6 = **3.6 วินาที** (ใช้กับ OverlapBuffer)
- **WebSocket (FE ส่งเสียงมา server ทำ rolling window):**
  - **Window:** **3 วินาที** (`FE_CC_WINDOW_SECONDS`, default `3.0`)
  - **Step:** **1 วินาที** (`FE_CC_STEP_SECONDS`, default `1.0`)
  - Min window 2s, Silence threshold 0.8s

**ปรับเป็น overlap 1 วินาที (แปลงทีละ 3s, overlap 1s):** ตั้ง backend เท่านั้น  
- ตั้ง env `CC_CHUNK_OVERLAP=1.0` (หรือ `1`) แล้ว restart API/worker  
- **ไม่ต้องแก้ FE** — Overlap ทำที่ backend (OverlapBuffer อ่านจาก `CC_CHUNK_OVERLAP`); FE ยังส่ง chunk ละ 3 วินาทีเหมือนเดิม

---

## 5. ตรวจสอบ Task 797c52ec และการใช้งาน GPU/RAM/CPU

### สถานะ Task `797c52ec-583d-481a-9a27-a7a37f6b15a2`

| รายการ | ค่า |
|--------|-----|
| **Status** | completed |
| **ไฟล์** | uploads/abab9e3a-baa0-434a-a2bd-68b0cd212c4c_v30-1.mp4 |
| **Created** | 2026-01-29 22:25:18 UTC |
| **Completed** | 2026-01-29 22:29:22 UTC |
| **chunk_duration** | 30 วินาที |
| **Total End-to-End** | **240.39 วินาที** (~4 นาที) |

**Phase breakdown (จาก storage):**

- Preprocess: extract ~5.0s, chunk ~0.85s, enqueue ~1.74s → รวม ~7.5s
- **Wait chunks:** **200.44s** (~83% ของ total) ← bottleneck
- Fetch chunks: 14.62s, Merge: 3.45s, Thai: มีใน aggregator

### Logs สำหรับ GPU / RAM / CPU

- **File transcription (chunk + aggregator):** ก่อนหน้านี้ **ไม่ได้ log RAM/CPU** ใน worker — งาน 797c52ec จึงไม่มีบรรทัด RAM/CPU ใน log
- **ตอนนี้:** เพิ่มการ log แล้วใน `app/workers/rq_worker.py`:
  - **Chunk job (GPU):** ก่อน/หลัง transcribe จะมีบรรทัด `📊 Chunk resources: RAM X MB (delta: ±Y MB) | CPU before/after: A% / B%`
  - **Aggregator job:** ก่อน/หลัง aggregator จะมีบรรทัด `📊 Aggregator resources: RAM ... | CPU before/after: ...`
- **Live chunk:** มี log RAM/CPU อยู่แล้ว (`   RAM: ... | CPU before/after: ...`)

**ที่อยู่ log:**

- งานรันบน **RunPod / server** → ดูที่ **transcription.log** (หรือ `transcription.log.YYYY-MM-DD`) บน pod นั้น
- ใน repo มีแค่ `logs/transcription.log.2026-01-27` ลงไป — **ไม่มี log วันที่ 29** จึงไม่พบ 797c52ec ใน workspace

**วิธีตรวจว่าใช้ GPU/RAM/CPU เต็มประสิทธิภาพแค่ไหน:**

1. **จาก log (หลัง deploy รุ่นที่เพิ่ม RAM/CPU แล้ว):** หาบรรทัด `Chunk resources` / `Aggregator resources` ของ task นั้น (ค้นหา task_id หรือเวลาประมาณ 22:25–22:29)
2. **GPU บน server:** รัน `nvidia-smi` (หรือ `watch -n 1 nvidia-smi`) ขณะรัน job — ดู **GPU-Util** และ **Memory-Usage**
3. **RAM/CPU บน server:** `htop` หรือ `top` หรือ `ps aux` ดู process ของ RQ worker

**สรุปสำหรับ 797c52ec:** จาก storage ใช้เวลารวม ~4 นาที; ส่วนใหญ่เป็น **wait_chunks** (~83%) แปลว่า GPU ยังมี capacity แต่ chunk ถูกแจกจ่าย/รอคิว — ไม่ได้หมายความว่า GPU/RAM/CPU ถูกใช้เต็ม 100% ตลอด; ต้องการตัวเลขจริงต้องดู log บน pod (ถ้ามี) หรือรันงานใหม่หลัง deploy รุ่นที่ log RAM/CPU แล้ว

---

## 6. วิธีรันวิเคราะห์ซ้ำ

```bash
# งานที่ใช้เวลา >= 200 นาที
python scripts/analyze_performance.py --min-minutes 200 --limit 20

# งานล่าสุด 30 task (ไม่กรองความยาว)
python scripts/analyze_performance.py --limit 30

# รวมสแกนไฟล์ log (ถ้ามี)
python scripts/analyze_performance.py --limit 20 --logs
```
