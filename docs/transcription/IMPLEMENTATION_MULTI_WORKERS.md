# 🚀 Implementation: Multi GPU Workers สำหรับ 1 GPU

**วันที่:** 2026-01-08  
**เป้าหมาย:** เพิ่ม GPU utilization จาก 5-10% → 55-65% โดยใช้ multiple workers ต่อ 1 GPU

---

## ✅ การเปลี่ยนแปลงที่ทำ

### 1️⃣ `scripts/pod/start-rq-workers.sh`

**เปลี่ยนแปลง:**
- ✅ เพิ่ม nested loop สำหรับ multiple workers per GPU
- ✅ แต่ละ GPU จะมี **3 workers** (configurable via `GPU_WORKERS_PER_GPU`)
- ✅ Worker naming: `worker-gpu0-w0`, `worker-gpu0-w1`, `worker-gpu0-w2`
- ✅ ปรับปรุง kill script ให้รองรับ multi-worker pattern

**Code Changes:**
```bash
# เพิ่ม configuration
GPU_WORKERS_PER_GPU=${GPU_WORKERS_PER_GPU:-3}

# Nested loop สำหรับ multiple workers per GPU
for i in $(seq 0 $((NUM_GPUS - 1))); do
    for w in $(seq 0 $((GPU_WORKERS_PER_GPU - 1))); do
        worker_name="worker-gpu${i}-w${w}"
        # Start worker with CUDA_VISIBLE_DEVICES=$i
        env CUDA_VISIBLE_DEVICES=$i \
            rq worker \
            --url "$REDIS_URL" \
            transcription_priority \
            transcription_gpu$i \
            --name $worker_name &
    done
done
```

---

### 2️⃣ `.env.runpod`

**เพิ่ม:**
```bash
GPU_WORKERS_PER_GPU=3  # จำนวน workers ต่อ 1 GPU (3 = optimal สำหรับ 6 vCPU)
```

**เหตุผล:**
- Pod มี **6 vCPU** → ใช้ 3 workers เพื่อไม่ให้ CPU bottleneck
- แต่ละ worker ใช้ ~1-2 CPU cores → 3 workers = ~3-6 cores
- RTX 4000 Ada (20GB VRAM) + `small` model → แต่ละ worker ใช้ ~1-1.5GB
- 3 workers = ~3-4.5GB VRAM (เหลืออีก 15.5-17GB)

---

## 📊 ผลลัพธ์ที่คาดหวัง

### Before (1 worker/GPU)
- **GPU Utilization:** 5-10%
- **3 concurrent jobs:** ~14m 28s
- **ปัญหาที่พบ:** GPU idle อยู่ 90%+ ของเวลา

### After (3 workers/GPU)
- **GPU Utilization:** 55-65% (เพิ่มขึ้น ~10x)
- **3 concurrent jobs:** ~8-9m (ประมาณ **40% เร็วขึ้น**)
- **ข้อดี:** GPU ทำงาน concurrent อย่างแท้จริง

---

## 🚀 ขั้นตอนการใช้งาน

### Step 1: Restart Workers

```bash
cd /workspace/transcription-service
./scripts/pod/restart-rq-workers.sh
```

### Step 2: ตรวจสอบว่า Workers ทำงาน

```bash
# ตรวจสอบ workers ที่กำลังทำงาน
ps aux | grep 'rq worker.*gpu0'

# ควรเห็น 3 workers:
# - worker-gpu0-w0
# - worker-gpu0-w1
# - worker-gpu0-w2

# หรือตรวจสอบ logs
tail -f /tmp/rq-worker-gpu0-w0.log
tail -f /tmp/rq-worker-gpu0-w1.log
tail -f /tmp/rq-worker-gpu0-w2.log
```

### Step 3: ทดสอบ Performance

```bash
# ทดสอบ 3 concurrent jobs
# เป้าหมาย: < 10 นาที (600s) สำหรับทั้ง 3 jobs

python3 scripts/test_concurrent_jobs.py
```

---

## 🔍 Monitoring

### GPU Utilization

```bash
# Monitor GPU utilization (ควรเห็น ~55-65%)
watch -n 1 nvidia-smi
```

### Worker Status

```bash
# ตรวจสอบ queue stats
rq info --url $REDIS_URL

# ตรวจสอบ worker count
ps aux | grep 'rq worker.*gpu0' | wc -l
# ควรเห็น 3 workers
```

---

## ⚙️ Configuration

### ปรับจำนวน Workers

**ใน `.env.runpod`:**
```bash
GPU_WORKERS_PER_GPU=3  # Default สำหรับ 6 vCPU

# ถ้า Pod มี 8+ vCPU → ใช้ 4 workers
GPU_WORKERS_PER_GPU=4

# ถ้า Pod มี 4 vCPU → ใช้ 2 workers
GPU_WORKERS_PER_GPU=2
```

**สูตรคำนวณ:**
- **Workers per GPU** ≈ `vCPU / 2` (แต่ไม่เกิน 4)
- **Memory per worker:** ~1-1.5GB VRAM (`small` model)
- **CPU per worker:** ~1-2 cores

---

## 🎯 Performance Targets

| Metric | Before | After (Target) | Status |
|--------|--------|----------------|--------|
| GPU Utilization | 5-10% | 55-65% | ⏳ Testing |
| 3 Jobs Time | ~14m 28s | ~8-9m | ⏳ Testing |
| Improvement | baseline | ~40% faster | ⏳ Testing |

---

## ⚠️ ข้อควรระวัง

1. **CPU Bottleneck:**
   - Pod มี 6 vCPU → ใช้ 3 workers เพื่อไม่ให้ CPU bottleneck
   - ถ้าเพิ่มเป็น 4 workers อาจเกิด CPU contention

2. **Memory Usage:**
   - แต่ละ worker load model แยก (~500MB/worker)
   - 3 workers = ~1.5GB VRAM (เหลืออีก 18.5GB)

3. **Queue Distribution:**
   - Workers จะ consume จาก queue แบบ round-robin
   - ไม่จำเป็นต้องแก้ไข queue logic

---

## 📝 Troubleshooting

### Problem: Workers ไม่ start

**ตรวจสอบ:**
```bash
# ตรวจสอบ logs
tail -f /tmp/rq-worker-gpu0-w*.log

# ตรวจสอบ CUDA_VISIBLE_DEVICES
env | grep CUDA_VISIBLE_DEVICES

# ตรวจสอบ LD_LIBRARY_PATH
env | grep LD_LIBRARY_PATH
```

### Problem: GPU Utilization ยังต่ำ

**สาเหตุที่เป็นไปได้:**
1. Workers ไม่ทำงานจริง (ตรวจสอบ `ps aux`)
2. Queue ว่าง (ไม่มี jobs)
3. Preprocessing bottleneck (ตรวจสอบ preprocessing workers)

---

## 🔗 เอกสารที่เกี่ยวข้อง

- **[Technical Verdict](./TECHNICAL_VERDICT_2026-01-08.md)** - Root cause analysis
- **[สรุปการทำงาน](./00สรุปการทำงาน_2026-01-08.md)** - Architecture และ performance results

---

**หมายเหตุ:**  
การปรับปรุงนี้ไม่ต้องแก้ไขโค้ด Python เลย แค่เปลี่ยน startup script และ environment variable เท่านั้น ✨

