# วิเคราะห์ Aggregator Bottleneck และความสัมพันธ์กับ Chunk Duration

**วันที่:** 2026-02-22

---

## 0. คำศัพท์

| คำ | ความหมาย |
|----|----------|
| **Aggregator** | ขั้นตอนที่รวมผลจากทุก chunk หลัง GPU transcribe เสร็จ — รอ chunks → merge → Thai processing → save |
| **Preprocess** | Extract เสียง + สร้าง chunks (.npy/.wav) — **GPU รอขั้นนี้** ก่อนจะ transcribe ได้ |

**Pipeline:** Preprocess → GPU (transcribe chunks) → Aggregator (merge)

---

## 1. Aggregator Flow (transcription_cpu)

Aggregator job รันบน queue `transcription_cpu` โดย `NUM_CPU_WORKERS=4` workers

### ขั้นตอนหลัก

| ขั้นตอน | งาน | ขึ้นกับ chunk_duration? |
|---------|-----|-------------------------|
| **1. Wait chunks** | Poll Redis `done_chunks` ทุก 0.5–2s จนครบ total_chunks | ไม่โดยตรง (ขึ้นกับ GPU speed) |
| **2. Fetch + merge** | วน loop `total_chunks` ครั้ง: GET Redis, parse JSON, ปรับ timestamp, insert segments | ✅ **ใช่** — total_chunks = duration/chunk_duration |
| **3. Thai processing** | PyThaiNLP + Attacut บน full_text | ไม่ขึ้นกับจำนวน chunks |
| **4. Fuzzy match** | แก้ชื่อคน/คำศัพท์ (optional, timeout 60s) | ไม่ขึ้นกับจำนวน chunks |
| **5. Save** | บันทึก task_data + segments ลง SQLite | ขึ้นกับจำนวน segments (ซึ่งขึ้นกับ chunks) |

### สูตร

```
total_chunks = ceil(ไฟล์ duration / chunk_duration)
```

**ตัวอย่าง ไฟล์ 33 นาที (1980 วินาที):**

| chunk_duration | total_chunks | Aggregator iterations |
|----------------|--------------|------------------------|
| 240s           | 9            | 9 ครั้ง |
| 150s           | 14           | 14 ครั้ง |
| 90s            | 22           | 22 ครั้ง |
| 60s            | 33           | 33 ครั้ง |

---

## 2. สรุป: Chunk Duration กับ Aggregator

### ยิ่ง chunk_duration เล็กลง → Aggregator งานมากขึ้น

1. **Fetch + merge loop**  
   วน `total_chunks` ครั้ง: GET Redis, parse JSON, ปรับ timestamp, insert segments  
   → chunk_duration เล็กลง → total_chunks เพิ่ม → aggregator ใช้เวลานานขึ้นต่อ job

2. **Segments per chunk**  
   Chunk ยาว (240s) → segments ต่อ chunk เยอะ  
   Chunk สั้น (60s) → segments ต่อ chunk น้อย  
   → รวม total segments อาจใกล้เคียงกัน แต่จำนวน Redis GET และ loop iterations เพิ่มขึ้นเมื่อ chunk_duration เล็กลง

3. **Queue backlog**  
   - `NUM_CPU_WORKERS=4`  
   - 25 jobs พร้อมกัน = 25 aggregator jobs  
   - chunk_duration เล็กลง → แต่ละ aggregator job ใช้เวลานานขึ้น  
   - 4 workers รองรับ 25 jobs ที่แต่ละ jobช้าลง → **aggregator queue ยาวขึ้น**

### สรุปความสัมพันธ์

```
chunk_duration ↓  →  total_chunks ↑  →  aggregator workload/job ↑  →  bottleneck ชัดขึ้น
```

---

## 3. Preprocess (NUM_PREPROCESS_WORKERS) กับ Chunk Duration

### create_chunks() ใน video_service.py

- **numpy path**: decode ครั้งเดียว → slice ใน RAM → `np.save()` ต่อ chunk  
- `total_chunks = ceil(duration / chunk_duration)`  
- chunk_duration เล็กลง → total_chunks เพิ่ม → loop + I/O เพิ่ม

### ความสัมพันธ์

```
chunk_duration ↓  →  total_chunks ↑  →  preprocess งาน create_chunks ↑
```

ดังนั้น **NUM_PREPROCESS_WORKERS มีผลโดยตรงกับ chunk_duration**  
ถ้าลด chunk_duration ควรพิจารณาเพิ่ม NUM_PREPROCESS_WORKERS ด้วย

---

## 4. คำแนะนำการปรับ

### ถ้าจะลด chunk_duration (เช่น 240 → 150 หรือ 90)

| การปรับ | เหตุผล |
|---------|--------|
| **เพิ่ม NUM_CPU_WORKERS** (4 → 6–8) | ลด aggregator bottleneck เมื่อ total_chunks เพิ่ม |
| **เพิ่ม NUM_PREPROCESS_WORKERS** (12 → 16–20) | รองรับ create_chunks ที่หนักขึ้นเมื่อ chunks เยอะขึ้น |

### ถ้ายังใช้ chunk_duration=240

- Aggregator ยังไม่น่าจะเป็น bottleneck หลัก (9 chunks/job)
- NUM_PREPROCESS_WORKERS=12 น่าจะพอ
- ถ้า CPU ยังไม่เต็ม อาจเพิ่ม NUM_PREPROCESS_WORKERS ได้อีกเล็กน้อย

---

## 5. การตรวจสอบ Bottleneck

ดูจาก `phase_timings` ใน task ที่ completed:

```bash
# ดู aggregator timing
sqlite3 storage/database.db "SELECT task_id, json_extract(phase_timings, '$.aggregator.total_aggregator_time'), json_extract(phase_timings, '$.aggregator.wait_chunks_time'), json_extract(phase_timings, '$.aggregator.fetch_chunks_time') FROM transcriptions WHERE status='completed' ORDER BY updated_at DESC LIMIT 5;"
```

หรือจาก log:

```
✅ Processed X/Y chunks (took Zs), finalizing merge...
```

- `wait_chunks_time` สูง → GPU ช้า หรือ chunk delivery ช้า  
- `fetch_chunks_time` สูง → aggregator merge ช้า (ขึ้นกับ total_chunks)  
- `thai_processing_time` สูง → Thai processing ช้า

---

## 6. สรุปสั้นๆ

| คำถาม | คำตอบ |
|-------|-------|
| Aggregator bottleneck เกี่ยวกับ chunk_duration ไหม? | **ใช่** — chunk_duration เล็กลง → total_chunks เพิ่ม → aggregator งานต่อ job เพิ่ม |
| ควรเพิ่ม NUM_PREPROCESS_WORKERS ไหม? | **ใช่** ถ้าจะลด chunk_duration — มีผลโดยตรง เพราะ create_chunks หนักขึ้น |
| ตอนนี้ chunk_duration=240? | Aggregator ยังไม่น่าจะ bottleneck หลัก (9 chunks/job) — ควรเพิ่ม NUM_PREPROCESS_WORKERS ได้ตาม CPU headroom |

---

## 7. ผลทดสอบ 25 M4A (2026-02-22)

| Config | เวลา 24 jobs | หมายเหตุ |
|--------|--------------|----------|
| Preprocess 16, GPU 14, CPU 4 | ~35 นาที | Job 25 ค้าง — Aggregator bottleneck (4 workers) |
| **แนะนำ** | เพิ่ม NUM_CPU_WORKERS 4→6 | รองรับ 25 aggregator jobs ให้ครบ |
