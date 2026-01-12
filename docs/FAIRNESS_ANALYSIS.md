# 📊 Fairness Analysis และการปรับปรุงเพื่อรองรับ 10-15 jobs

**วันที่:** 2026-01-11  
**เป้าหมาย:** 1 GPU รองรับ 10-15 jobs พร้อมกัน

---

## 📊 สถานะปัจจุบัน

### Configuration (จาก test script):
- `GPU_WORKERS_PER_GPU=3`
- `CHUNK_INFLIGHT_LIMIT_PER_JOB=2` (default)
- `CHUNK_ENQUEUE_WINDOW_SIZE=4` (default)

### ผลการทดสอบ 5 Jobs:
- Job 1: 4.0s
- Job 2: 6.2s
- Job 3: 30.7s
- Job 4: 34.7s
- Job 5: 46.9s
- Total: 46.9s
- Average: 24.5s

### ปัญหาที่พบ:
1. ❌ Jobs ไม่ได้รันพร้อมกัน (sequential)
2. ❌ Job ใหม่ต้องรอ job ก่อนหน้าเสร็จ
3. ❌ Capacity ต่ำ (3 workers / 2 chunks = 1.5 jobs)

---

## 🎯 การคำนวณ Capacity

### สูตร:
```
Capacity = GPU_WORKERS_PER_GPU / CHUNK_INFLIGHT_LIMIT_PER_JOB
```

### Current Configuration:
- `GPU_WORKERS=3, LIMIT=2` → Capacity = **1.5 jobs** ❌
- `GPU_WORKERS=5, LIMIT=2` → Capacity = **2.5 jobs** ❌

### สำหรับ 10-15 jobs:
- `GPU_WORKERS=10, LIMIT=1` → Capacity = **10 jobs** ✅
- `GPU_WORKERS=15, LIMIT=1` → Capacity = **15 jobs** ✅
- `GPU_WORKERS=12, LIMIT=1` → Capacity = **12 jobs** ✅ (แนะนำ)

---

## ✅ ข้อเสนอแนะ Configuration

### สำหรับ 1 GPU รองรับ 10-15 jobs:

#### 1. GPU_WORKERS_PER_GPU: **12-15**
- เพิ่มจาก 5 → 12-15
- เพื่อรองรับ 10-15 jobs
- **แนะนำ: 12** (balance ระหว่าง performance และ resource)

#### 2. CHUNK_INFLIGHT_LIMIT_PER_JOB: **1**
- ลดจาก 2 → 1
- แต่ละ job ได้ 1 chunk
- Capacity = 12-15 jobs

#### 3. CHUNK_ENQUEUE_WINDOW_SIZE: **2**
- ลดจาก 4 → 2
- Enqueue แค่ 2 chunks แรก
- เพื่อลด queue backlog

---

## 📊 ตัวอย่าง Configuration

### สำหรับ 10-15 jobs ต่อ GPU:

```bash
# Environment Variables
export GPU_WORKERS_PER_GPU=12
export CHUNK_INFLIGHT_LIMIT_PER_JOB=1
export CHUNK_ENQUEUE_WINDOW_SIZE=2
```

### ผลลัพธ์:
- **Capacity:** 12 workers / 1 chunk = **12 jobs**
- **Fairness:** แต่ละ job ได้ 1 chunk (fair)
- **Performance:** Jobs เริ่มเร็วขึ้น (window size = 2)

---

## 🔍 Trade-offs

### Option 1: GPU_WORKERS=12, LIMIT=1
**ข้อดี:**
- ✅ รองรับ 12 jobs
- ✅ Fairness ดี (แต่ละ job ได้ 1 chunk)
- ✅ Jobs เริ่มเร็ว

**ข้อเสีย:**
- ⚠️ Context switching มากขึ้น
- ⚠️ VRAM pressure (medium model ใช้ ~2-3GB)

**แนะนำ:** ✅ สำหรับ 10-15 jobs

### Option 2: GPU_WORKERS=15, LIMIT=1
**ข้อดี:**
- ✅ รองรับ 15 jobs
- ✅ Fairness ดี

**ข้อเสีย:**
- ⚠️ Context switching มาก
- ⚠️ VRAM pressure สูง

**แนะนำ:** ⚠️ ใช้เฉพาะเมื่อต้องการรองรับ 15+ jobs

### Option 3: GPU_WORKERS=10, LIMIT=1
**ข้อดี:**
- ✅ รองรับ 10 jobs
- ✅ Fairness ดี

**ข้อเสีย:**
- ⚠️ ไม่พอสำหรับ 15 jobs

**แนะนำ:** ✅ สำหรับ 10 jobs

---

## 📝 Testing Recommendations

### Test Scenario:
1. Submit 10-15 jobs พร้อมกัน
2. ตรวจสอบว่า:
   - Jobs เริ่มประมวลผลพร้อมกัน (ไม่รอ)
   - แต่ละ job ได้ GPU workers อย่างยุติธรรม
   - ไม่มี job ใดรอนานเกินไป
   - Throughput รวมดีขึ้น

### Expected Results:
- Jobs เริ่มประมวลผลเร็ว (ไม่ต้องรอ job แรกเสร็จ)
- Fairness ดี (แต่ละ job ได้ GPU workers)
- Capacity = 12 jobs (พร้อมกัน)
- Throughput รวมดีขึ้น (หลาย jobs พร้อมกัน)

---

## ⚠️ หมายเหตุ

1. **VRAM Usage:**
   - Medium model ใช้ ~2-3GB VRAM
   - 12 workers × 2GB = ~24GB (พอสำหรับ RTX 4000 Ada 20GB)
   - ควร monitor VRAM usage

2. **Context Switching:**
   - Workers มากขึ้น → context switching มากขึ้น
   - อาจส่งผลต่อ performance ของแต่ละ job
   - ควรทดสอบและ monitor

3. **Tuning:**
   - ปรับ `GPU_WORKERS_PER_GPU` ตาม workload
   - ปรับ `CHUNK_INFLIGHT_LIMIT_PER_JOB` ตาม fairness ที่ต้องการ
   - Monitor GPU utilization และ VRAM usage

---

## 📊 Summary

### สำหรับ 1 GPU รองรับ 10-15 jobs:

**Recommended Configuration:**
```bash
GPU_WORKERS_PER_GPU=12
CHUNK_INFLIGHT_LIMIT_PER_JOB=1
CHUNK_ENQUEUE_WINDOW_SIZE=2
```

**Capacity:** 12 jobs  
**Fairness:** แต่ละ job ได้ 1 chunk  
**Performance:** Jobs เริ่มเร็วขึ้น
