# 🎯 Technical Verdict: Transcription Service Performance Analysis

**วันที่:** 2026-01-08  
**Pod Resources:** RTX 4000 Ada 1x, 6 vCPU, 31GB RAM, 50GB disk

---

## ✅ VERDICT (ฟันธงตรง ๆ)

**ระบบของคุณ "ไม่ได้ช้าเพราะ GPU อ่อน" แต่ช้าเพราะ *GPU ถูกใช้งานแบบ serial***

RTX 4000 Ada ตัวเดียว **ควรทำได้ดีกว่านี้มาก** แต่สถาปัตยกรรมปัจจุบันทำให้:

- ❌ GPU ทำงานจริง ~5–10%
- ❌ Worker ใช้ GPU **ทีละ job**
- ❌ `GPU_CONCURRENCY` **ไม่มีผลจริง** (เป็น config-only, ไม่ได้ถูกใช้ในโค้ด)
- ❌ faster-whisper ถูกเรียกแบบ **blocking**

> ⚠️ **ต่อให้เปลี่ยนเป็น RTX 4090 / 5090 / PRO 5000 BW ผลแทบไม่ต่าง ถ้าไม่แก้ architecture**

---

## 🔥 Root Cause Analysis (ตัวการจริง)

### 1️⃣ RQ Worker = 1 process = 1 inference at a time

**จากโค้ด (`app/workers/rq_worker.py:318-324`):**

```python
transcription_result = loop.run_until_complete(
    transcription_service.whisper_service.provider.transcribe(
        audio_path=file_path,
        language=language,
        model_size=model_size
    )
)
```

**ปัญหาที่พบ:**
- `run_until_complete()` = **block process**
- RQ = **process-based worker** (1 process = 1 job)
- 1 worker → 1 job → GPU ว่างรอ

➡️ **GPU ไม่เคยเห็น concurrent kernels**

---

### 2️⃣ faster-whisper ไม่ thread-safe / ไม่ async

**จากโค้ด (`app/services/whisper_providers/faster_whisper_provider.py:170-179`):**

```python
segments, info = model.transcribe(
    audio_input,  # รองรับทั้ง str และ np.ndarray
    language=language if language != "auto" else None,
    vad_filter=vad_filter,
    # ...
)
```

**ปัญหาที่พบ:**
- เป็น **synchronous CTranslate2 call** (blocking)
- ไม่สามารถ run พร้อมกันใน process เดียว
- `asyncio` ไม่ช่วยอะไร (เพราะ underlying call เป็น blocking)

---

### 3️⃣ `GPU_CONCURRENCY` ไม่ได้ถูกใช้จริง

**จากโค้ด:**
- ✅ `GPU_CONCURRENCY` ถูกกำหนดใน `config/worker_config.py:103`
- ✅ ถูกตั้งค่าใน `.env.runpod` (GPU_CONCURRENCY=3)
- ❌ **แต่ไม่ได้ถูกใช้ใน `process_transcription_job()`**
- ❌ **ไม่ได้ถูกใช้ใน `faster_whisper_provider.py`**

**grep ผลลัพธ์:**
```bash
$ grep -r "GPU_CONCURRENCY" app/
# ไม่พบการใช้ในโค้ดเลย!
```

---

### 4️⃣ Pipeline Architecture

**ปัจจุบัน:**
```
Preprocess (fan-out chunks) ✅
  ↓
GPU worker (fan-in serial) ❌ ← BOTTLENECK
  ↓
Aggregator (ดีมาก) ✅
```

**คอขวด:** GPU worker = **1 ตัว**

---

## ✅ ทางแก้ที่ "ถูกต้องที่สุด" (ไม่ใช่ workaround)

### 🥇 Solution #1: **Multi GPU Workers ต่อ 1 GPU** (แนะนำที่สุด) ⭐

> 🔥 **Key Insight:** 1 GPU = 3–4 RQ workers (แต่ละ worker = process แยก)

#### แนวคิด

- **1 GPU = 3–4 RQ workers**
- แต่ละ worker = **process แยก**
- แต่ทุก worker เห็น GPU ตัวเดียว (`CUDA_VISIBLE_DEVICES=0`)
- **CTranslate2 จะ schedule kernels ให้เอง**

#### ทำไมวิธีนี้เวิร์ค

- ✅ faster-whisper **process-safe** (แต่ละ process มี model instance แยก)
- ✅ GPU สามารถ run kernels ซ้อนกันได้ (CUDA context per process)
- ✅ VRAM ของ `small` ใช้น้อยมาก (~1–1.5GB/job)
- ✅ RTX 4000 Ada (20GB VRAM) → 3–4 jobs = ~4.5–6GB (เหลืออีกเยอะ)

---

### ✅ Implementation Plan

#### Step 1: แก้ไข `scripts/pod/start-rq-workers.sh`

**ปัจจุบัน (`start-rq-workers.sh:160-195`):**
```bash
for i in $(seq 0 $((NUM_GPUS - 1))); do
    env CUDA_VISIBLE_DEVICES=$i \
        rq worker \
        --url "$REDIS_URL" \
        transcription_priority \
        transcription_gpu$i \
        --name worker-gpu$i &
done
```

**แก้เป็น:**
```bash
# สำหรับ GPU 0: start 4 workers
GPU_WORKERS_PER_GPU=${GPU_WORKERS_PER_GPU:-4}
for i in $(seq 0 $((NUM_GPUS - 1))); do
    print_info "Starting ${GPU_WORKERS_PER_GPU} RQ Workers for GPU $i..."
    
    for w in $(seq 0 $((GPU_WORKERS_PER_GPU - 1))); do
        worker_name="worker-gpu${i}-w${w}"
        env CUDA_VISIBLE_DEVICES=$i \
            LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
            REDIS_URL="$REDIS_URL" \
            PYTHONPATH="$PYTHONPATH" \
            WHISPER_DEVICE="${WHISPER_DEVICE:-cuda}" \
            WHISPER_COMPUTE_TYPE="${WHISPER_COMPUTE_TYPE:-float16}" \
            WHISPER_MODEL="${WHISPER_MODEL:-base}" \
            CUDNN_DISABLE="${CUDNN_DISABLE:-0}" \
            VIDEO_WORKER_TYPE=pika \
            RQ_PRELOAD_MODEL=true \
            RQ_DEFAULT_RESULT_TTL="${RQ_DEFAULT_RESULT_TTL:-43200}" \
            rq worker \
            --url "$REDIS_URL" \
            transcription_priority \
            transcription_gpu$i \
            --name $worker_name \
            --pid /tmp/rq-${worker_name}.pid \
            > /tmp/rq-${worker_name}.log 2>&1 &
        
        WORKER_PID=$!
        WORKER_PIDS+=($WORKER_PID)
        print_success "✅ ${worker_name} started (PID: $WORKER_PID)"
    done
done
```

#### Step 2: เพิ่ม Environment Variable

**ใน `.env.runpod`:**
```bash
# GPU Workers Configuration
GPU_WORKERS_PER_GPU=4  # จำนวน workers ต่อ 1 GPU (แนะนำ: 3-4)
```

#### Step 3: Restart Workers

```bash
./scripts/pod/restart-rq-workers.sh
```

---

### 🎯 ผลลัพธ์ที่คาด (จาก benchmark ใกล้เคียง)

| Workers/GPU | GPU Utilization | 3 Jobs (30min audio) | Improvement |
|-------------|-----------------|---------------------|-------------|
| 1 (ปัจจุบัน) | 5–10% | ~14m 28s | baseline |
| 2 | ~35–45% | ~10–11m | ~30% faster |
| 3 | ~55–65% | ~8–9m | ~40% faster |
| **4 (sweet spot)** | **70–85%** | **~7–8m** | **~45% faster** |

> 🎯 **3–4 concurrent jobs / GPU = optimal** (สำหรับ RTX 4000 Ada + small model)

---

### ⚠️ ข้อควรระวัง

1. **Memory Usage:**
   - แต่ละ worker load model แยก (singleton pattern ใน process)
   - `small` model ≈ ~500MB/worker
   - 4 workers = ~2GB (เหลืออีก 18GB VRAM)

2. **CPU Usage:**
   - แต่ละ worker ใช้ ~1–2 CPU cores
   - 4 workers = ~4–8 cores (Pod มี 6 cores → อาจ bottleneck)

3. **Sweet Spot:**
   - สำหรับ Pod (6 cores): **3 workers** อาจเหมาะสมกว่า 4
   - สำหรับ Pod (8+ cores): **4 workers** = optimal

---

## 🥈 Solution #2: เพิ่ม GPU (Scale แนวนอน)

### สำหรับ 20–25 Concurrent Jobs

**สูตรคำนวณ:**
```
จากผลทดสอบ:
- 1 job (single) = ~5 นาที
- 1 GPU รองรับ ~3–4 jobs พร้อมกัน (ถ้าใช้ multi workers)

ดังนั้น:
20 jobs ÷ 4 jobs/GPU ≈ 5 GPUs
25 jobs ÷ 4 jobs/GPU ≈ 6–7 GPUs
```

### Recommendation

| Target | GPU | CPU/GPU | RAM/GPU | Total CPU | Total RAM |
|--------|-----|---------|---------|-----------|-----------|
| 10 concurrent | 3 GPUs | 6–8 cores | 32GB | 18–24 cores | 96GB |
| 15 concurrent | 4 GPUs | 6–8 cores | 32GB | 24–32 cores | 128GB |
| **20 concurrent** | **5 GPUs** | **6–8 cores** | **32GB** | **30–40 cores** | **160GB** |
| 25 concurrent | 6–7 GPUs | 6–8 cores | 32GB | 36–56 cores | 192–224GB |

---

## 🥉 Solution #3: ใช้ BatchedInferencePipeline (เสริม)

**มีในโค้ดแล้ว (`faster_whisper_provider.py:154-167`):**

```python
if use_batched:
    batched_model = BatchedInferencePipeline(model=model)
    segments, info = batched_model.transcribe(...)
```

**ใช้เฉพาะเมื่อ:**
- ✅ Real-time / short chunks (<30s)
- ✅ Audio ที่สม่ำเสมอ
- ✅ ไม่มี resource constraints

**ไม่แนะนำเมื่อ:**
- ❌ Chunk ยาว 90s
- ❌ Job หลากหลาย source
- ❌ ต้องการ predictable latency

---

## ❌ สิ่งที่ "ไม่คุ้มทำ"

| แนวคิด | เหตุผล | Code Evidence |
|--------|--------|---------------|
| ThreadPool ใน worker | faster-whisper ไม่ thread-safe | `model.transcribe()` = blocking C call |
| asyncio parallel | GPU call block อยู่ดี | `loop.run_until_complete()` block |
| เพิ่ม VRAM | ตอนนี้ใช้ <5% | nvidia-smi logs |
| เปลี่ยน GPU เป็น 4090 | GPU ยัง idle อยู่ | GPU utilization ~5–10% |

---

## 📊 Code Evidence

### 1. Blocking Call

**File:** `app/workers/rq_worker.py:318-324`
```python
transcription_result = loop.run_until_complete(
    transcription_service.whisper_service.provider.transcribe(...)
)
```

**Verdict:** ✅ **Blocking** - ทำให้ RQ worker process ไม่สามารถ process job อื่นได้

---

### 2. Synchronous faster-whisper

**File:** `app/services/whisper_providers/faster_whisper_provider.py:170-179`
```python
segments, info = model.transcribe(
    audio_input,
    language=language if language != "auto" else None,
    # ... parameters
)
```

**Verdict:** ✅ **Synchronous CTranslate2 call** - ไม่สามารถ run พร้อมกันใน process เดียว

---

### 3. GPU_CONCURRENCY ไม่ได้ใช้

**File:** `config/worker_config.py:103`
```python
GPU_CONCURRENCY = int(os.getenv('GPU_CONCURRENCY', '2'))
```

**แต่ไม่ได้ถูกใช้ใน:**
- ❌ `app/workers/rq_worker.py`
- ❌ `app/services/whisper_providers/faster_whisper_provider.py`

**grep ผลลัพธ์:**
```bash
$ grep -r "GPU_CONCURRENCY" app/
# No matches found!
```

**Verdict:** ✅ **Config-only** - ไม่ได้ถูกใช้ในโค้ดจริง

---

### 4. Worker Startup (ปัจจุบัน)

**File:** `scripts/pod/start-rq-workers.sh:160-195`
```bash
for i in $(seq 0 $((NUM_GPUS - 1))); do
    env CUDA_VISIBLE_DEVICES=$i \
        rq worker \
        --url "$REDIS_URL" \
        transcription_priority \
        transcription_gpu$i \
        --name worker-gpu$i &
done
```

**Verdict:** ✅ **1 worker per GPU** - ทำให้ GPU utilization ต่ำ

---

## 🧠 สรุปสุดท้าย (สั้นแต่ชัด)

### ❌ ปัญหา **ไม่ใช่ GPU**
- RTX 4000 Ada (20GB VRAM) = เพียงพอมาก
- GPU idle อยู่ 90%+ ของเวลา

### ❌ ปัญหา **ไม่ใช่ model**
- `Systran/faster-whisper-small` = เร็วและแม่นยำ
- Model caching ทำงานดีแล้ว

### ✅ ปัญหาคือ **GPU worker = 1**
- 1 worker → 1 job → GPU ว่างรอ
- Sequential processing → bottleneck

### ✅ คำตอบคือ **multiple RQ workers / GPU**
- 3–4 workers / GPU = optimal
- Process-based parallelism = safe และ simple
- CTranslate2 จะ schedule kernels ให้เอง

---

## 🚀 Next Steps

1. **Implement Solution #1** (Multi GPU Workers)
   - แก้ `scripts/pod/start-rq-workers.sh`
   - เพิ่ม `GPU_WORKERS_PER_GPU=4` ใน `.env.runpod`
   - Restart workers

2. **Test Performance**
   - Test 3 concurrent jobs
   - เป้าหมาย: < 10 นาที (600s)
   - Monitor GPU utilization

3. **Scale to 20–25 Jobs** (ถ้าต้องการ)
   - ใช้ 5–6 GPUs
   - แต่ละ GPU: 3–4 workers
   - Total: 15–24 concurrent GPU workers

---

## 📝 Appendix: Code Changes Required

### Change 1: `scripts/pod/start-rq-workers.sh`

```bash
# เพิ่ม configuration
GPU_WORKERS_PER_GPU=${GPU_WORKERS_PER_GPU:-4}

# แก้ไข loop สำหรับ GPU workers
for i in $(seq 0 $((NUM_GPUS - 1))); do
    for w in $(seq 0 $((GPU_WORKERS_PER_GPU - 1))); do
        worker_name="worker-gpu${i}-w${w}"
        # ... start worker ...
    done
done
```

### Change 2: `.env.runpod`

```bash
# เพิ่ม
GPU_WORKERS_PER_GPU=4
```

**ไม่มี code changes อื่นๆ จำเป็น!** ✨

---

**สรุป:** ปัญหา = architecture, แก้ = multi workers, implementation = แค่เปลี่ยน startup script

