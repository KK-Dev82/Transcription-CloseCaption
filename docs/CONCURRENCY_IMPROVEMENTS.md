# 🚀 การปรับปรุง Concurrency และ Fairness

**วันที่:** 2026-01-11  
**เป้าหมาย:** รองรับหลาย jobs พร้อมกันแบบยุติธรรม (fairness) โดยไม่ให้ job ใหม่รอนาน

---

## 📊 สถานะปัจจุบัน

### Configuration:
- `GPU_WORKERS_PER_GPU=5`
- `NUM_PREPROCESS_WORKERS=2`
- `NUM_CPU_WORKERS=2`

### ปัญหาที่พบ:
1. ❌ Job แรกสามารถ enqueue chunks ทั้งหมด (12-15 chunks) ลง GPU queue
2. ❌ Job ใหม่ที่เข้ามาทีหลังต้องรอจน job แรกเสร็จ
3. ❌ ไม่มี fairness - job ใหม่อาจรอนาน

---

## ✅ การแก้ไขที่ทำ

### 1. Windowed/JIT Enqueue
**ปัญหา:** Enqueue chunks ทั้งหมดทันทีทำให้ job แรกกิน GPU หมด

**การแก้ไข:**
- Enqueue แค่ **4 chunks แรก** (configurable via `CHUNK_ENQUEUE_WINDOW_SIZE`)
- เมื่อ chunk เสร็จ → enqueue chunk ถัดไปอัตโนมัติ
- ลด queue backlog และเพิ่ม fairness

**Environment Variable:**
```bash
CHUNK_ENQUEUE_WINDOW_SIZE=4  # จำนวน chunks ที่ enqueue ครั้งแรก
```

### 2. Inflight Limit ต่อ Job
**ปัญหา:** Job เดียวสามารถมี chunks กำลังประมวลผลได้ไม่จำกัด

**การแก้ไข:**
- จำกัดจำนวน chunks ที่กำลังประมวลผลต่อ job = **2 chunks** (configurable)
- ถ้ามี job เดียว → ได้ workers เต็ม (5 workers)
- ถ้ามีหลาย jobs → แต่ละ job ได้อย่างน้อย 2 chunks (fair)

**Environment Variable:**
```bash
CHUNK_INFLIGHT_LIMIT_PER_JOB=2  # จำนวน chunks ที่กำลังประมวลผลต่อ job สูงสุด
```

### 3. ข้อเสนอแนะ GPU_WORKERS_PER_GPU
**แนะนำ:** ลดจาก 5 → **3** เพื่อ fairness

**เหตุผล:**
- Medium model บน RTX 4000 Ada (20GB) → 3 workers = optimal
- 5 workers อาจทำให้ context switching มากเกินไป
- 3 workers ยังคงเร็วสำหรับ job เดียว แต่ fair มากขึ้นเมื่อมีหลาย jobs

---

## 🔧 Implementation Details

### Windowed Enqueue Flow:

1. **Preprocess Job:**
   - สร้าง chunks ทั้งหมด (12-15 chunks)
   - Enqueue แค่ 4 chunks แรก
   - เก็บ chunk paths ทั้งหมดใน Redis (`task:{task_id}:chunks_metadata`)

2. **Chunk Worker (เมื่อ chunk เสร็จ):**
   - ตรวจสอบว่ามี chunks ที่ยังไม่ได้ enqueue หรือไม่
   - ตรวจสอบ inflight limit (ไม่เกิน 2 chunks ต่อ job)
   - Enqueue chunk ถัดไปถ้ายังไม่เกิน limit

3. **Inflight Tracking:**
   - `task:{task_id}:inflight_chunks` = จำนวน chunks ที่กำลังประมวลผล
   - `task:{task_id}:done_chunks` = จำนวน chunks ที่เสร็จแล้ว
   - `inflight = enqueued - done`

---

## 📊 ผลลัพธ์ที่คาดหวัง

### Before (Greedy Enqueue):
- Job 1: Enqueue 12 chunks → ใช้ GPU 5 workers → เสร็จใน 2-3 min
- Job 2: ต้องรอจน Job 1 เสร็จ → เริ่มช้า

### After (Windowed + Inflight Limit):
- Job 1: Enqueue 4 chunks → ใช้ GPU 2-3 workers → enqueue ถัดไปเมื่อเสร็จ
- Job 2: Enqueue 4 chunks → ใช้ GPU 2-3 workers → enqueue ถัดไปเมื่อเสร็จ
- **Fairness:** ทั้ง 2 jobs ได้ GPU พร้อมกัน

---

## 🎯 Configuration Recommendations

### สำหรับ RTX 4000 Ada + Medium Model:

```bash
# GPU Workers
GPU_WORKERS_PER_GPU=3  # ลดจาก 5 → 3 (fairness)

# Preprocess Workers
NUM_PREPROCESS_WORKERS=2  # OK (ไม่เกิน 3)

# CPU Workers (Aggregator)
NUM_CPU_WORKERS=2  # OK

# Windowed Enqueue
CHUNK_ENQUEUE_WINDOW_SIZE=4  # เริ่มต้น 4 chunks

# Inflight Limit
CHUNK_INFLIGHT_LIMIT_PER_JOB=2  # สูงสุด 2 chunks ต่อ job
```

### สำหรับ High Concurrency (25+ jobs):

```bash
GPU_WORKERS_PER_GPU=2  # ลดลงเพื่อ fairness
CHUNK_ENQUEUE_WINDOW_SIZE=2  # ลด window size
CHUNK_INFLIGHT_LIMIT_PER_JOB=1  # จำกัด 1 chunk ต่อ job
```

---

## 📝 Testing

### Test Scenario:
1. Submit 5 jobs พร้อมกัน
2. ตรวจสอบว่า:
   - Jobs เริ่มประมวลผลพร้อมกัน (ไม่รอ)
   - แต่ละ job ได้ GPU workers อย่างยุติธรรม
   - ไม่มี job ใดรอนานเกินไป

### Expected Results:
- Jobs เริ่มประมวลผลเร็วขึ้น (ไม่ต้องรอ job แรกเสร็จ)
- Fairness ดีขึ้น (แต่ละ job ได้ GPU workers)
- Throughput รวมดีขึ้น (หลาย jobs พร้อมกัน)

---

## 🔍 Monitoring

### Redis Keys to Monitor:
- `task:{task_id}:chunks_metadata` - ข้อมูล chunks ทั้งหมด
- `task:{task_id}:inflight_chunks` - จำนวน chunks กำลังประมวลผล
- `task:{task_id}:done_chunks` - จำนวน chunks เสร็จแล้ว
- `task:{task_id}:total_chunks` - จำนวน chunks ทั้งหมด

### Metrics:
- Average wait time (submit → start processing)
- Fairness index (แต่ละ job ได้ GPU workers เท่าไร)
- Throughput (jobs/min)

---

## ⚠️ หมายเหตุ

1. **Backward Compatibility:**
   - ระบบยังรองรับการ enqueue chunks ทั้งหมด (ถ้าไม่ตั้ง env vars)
   - Default values: window_size=4, inflight_limit=2

2. **Performance Trade-off:**
   - Job เดียวอาจช้าลงเล็กน้อย (เพราะ windowed enqueue)
   - แต่ fairness และ throughput รวมดีขึ้น

3. **Tuning:**
   - ปรับ `CHUNK_ENQUEUE_WINDOW_SIZE` และ `CHUNK_INFLIGHT_LIMIT_PER_JOB` ตาม workload
   - ถ้า jobs น้อย → เพิ่มค่า (เร็วขึ้น)
   - ถ้า jobs เยอะ → ลดค่า (fair มากขึ้น)
