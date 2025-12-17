# 🚀 การตั้งค่าเพื่อรองรับ 25 Concurrency (Parallel Processing)

## 📊 สถานะปัจจุบัน

### Configuration ปัจจุบัน
```bash
GPU_CONCURRENCY=2                    # ⚠️ รองรับแค่ 2 concurrent GPU tasks
MAX_QUEUE_TRANSCRIBE=20              # ⚠️ Queue limit = 20 (ไม่พอสำหรับ 25)
TRANSCRIPTION_MAX_WORKERS=5          # Thread pool สำหรับ chunk processing
TRANSCRIPTION_QUEUE_PREFETCH_COUNT=1 # Worker รับ 1 message ต่อครั้ง
```

### ❌ ปัญหาที่พบ

1. **GPU Concurrency ต่ำเกินไป**
   - ปัจจุบัน: `GPU_CONCURRENCY=2` → รองรับแค่ **2 tasks พร้อมกัน**
   - ต้องการ: **25 tasks พร้อมกัน**
   - **ขาด: 23 concurrent slots**

2. **Queue Limit ไม่พอ**
   - ปัจจุบัน: `MAX_QUEUE_TRANSCRIBE=20` → Queue เต็มที่ 20 tasks
   - ต้องการ: **25 tasks**
   - **ขาด: 5 slots**

3. **GPU Memory อาจไม่พอ**
   - Medium model: ~2.4GB VRAM per instance
   - 25 concurrent: 25 × 2.4GB = **60GB VRAM** (ไม่พอสำหรับ RTX 4080 SUPER 16GB)
   - **ต้องใช้ chunking หรือลด model size**

## ✅ วิธีแก้ไข: รองรับ 25 Concurrency

### Option 1: ใช้ Chunking (แนะนำ) ⭐

**แนวคิด**: แบ่ง video เป็น chunks และ process parallel

#### Configuration
```bash
# GPU Concurrency - เพิ่มตาม GPU memory
GPU_CONCURRENCY=10  # สำหรับ RTX 4080 SUPER 16GB (10 × 2.4GB = 24GB → ใกล้เต็ม)

# Queue Limits - เพิ่มเพื่อรองรับ 25 tasks
MAX_QUEUE_TRANSCRIBE=30  # เพิ่มจาก 20 เป็น 30 (buffer)

# Transcription Workers - เพิ่มเพื่อ process chunks parallel
TRANSCRIPTION_MAX_WORKERS=10  # เพิ่มจาก 5 เป็น 10

# Prefetch Count - เพิ่มเพื่อให้ worker รับ chunks มากขึ้น
TRANSCRIPTION_PREFETCH_COUNT=10  # เพิ่มจาก 5 เป็น 10
```

#### วิธีใช้งาน
```python
# ใช้ chunking เมื่อส่ง task
await transcription_service.start_transcription(
    file_url=file_url,
    use_chunking=True,  # ✅ เปิด chunking
    chunk_duration=30,  # 30 วินาทีต่อ chunk
    ...
)
```

#### ข้อดี
- ✅ **รองรับ 25 concurrency** - แต่ละ task แบ่งเป็น chunks และ process parallel
- ✅ **ใช้ GPU memory อย่างมีประสิทธิภาพ** - ไม่ต้อง load model หลายครั้ง
- ✅ **เร็วกว่า** - Process chunks พร้อมกัน

#### ข้อเสีย
- ⚠️ **ต้องใช้ chunking** - ไม่สามารถ transcribe ทั้งไฟล์พร้อมกัน 25 ไฟล์ได้
- ⚠️ **ต้อง merge results** - ต้องรวม chunks กลับเป็น full transcription

### Option 2: เพิ่ม GPU Concurrency (ไม่แนะนำ - ต้อง GPU memory สูง)

#### Configuration
```bash
# GPU Concurrency - เพิ่มเป็น 25 (ต้อง GPU memory 60GB+)
GPU_CONCURRENCY=25

# Queue Limits
MAX_QUEUE_TRANSCRIBE=30

# Transcription Workers
TRANSCRIPTION_MAX_WORKERS=25
```

#### ข้อเสีย
- ❌ **ต้อง GPU memory สูงมาก** - 25 × 2.4GB = 60GB VRAM
- ❌ **ไม่เหมาะกับ RTX 4080 SUPER 16GB** - จะเกิด CUDA OOM
- ❌ **ต้องใช้ GPU ที่มี VRAM สูง** - เช่น A100 80GB, H100 80GB

### Option 3: ใช้ Model Size เล็กกว่า (Base Model)

#### Configuration
```bash
# ใช้ Base model แทน Medium (ใช้ VRAM น้อยกว่า)
WHISPER_MODEL=base  # แทน medium

# GPU Concurrency - Base model ใช้ ~1GB per instance
GPU_CONCURRENCY=15  # 15 × 1GB = 15GB (พอสำหรับ RTX 4080 SUPER 16GB)

# Queue Limits
MAX_QUEUE_TRANSCRIBE=30

# Transcription Workers
TRANSCRIPTION_MAX_WORKERS=15
```

#### ข้อดี
- ✅ **ใช้ VRAM น้อยกว่า** - Base model ~1GB per instance
- ✅ **รองรับ concurrency สูงกว่า** - 15 concurrent tasks

#### ข้อเสีย
- ⚠️ **ความแม่นยำต่ำกว่า** - Base model มี accuracy ต่ำกว่า Medium
- ⚠️ **ยังไม่ถึง 25** - ต้องใช้ chunking ร่วมด้วย

## 🎯 แนะนำ: Option 1 (Chunking) + GPU Concurrency ปานกลาง

### Configuration ที่แนะนำ

```bash
# .env.runpod หรือ environment variables

# GPU Concurrency - ปรับตาม GPU memory
# RTX 4080 SUPER 16GB: ใช้ 10-12 (เผื่อ buffer)
GPU_CONCURRENCY=10

# Queue Limits - เพิ่มเพื่อรองรับ 25 tasks
MAX_QUEUE_TRANSCRIBE=30

# Transcription Workers - เพิ่มเพื่อ process chunks parallel
TRANSCRIPTION_MAX_WORKERS=10

# Prefetch Count - เพิ่มเพื่อให้ worker รับ chunks มากขึ้น
TRANSCRIPTION_PREFETCH_COUNT=10

# Model Configuration
WHISPER_MODEL=medium
WHISPER_COMPUTE_TYPE=float16
WHISPER_BATCH_SIZE=32
```

### การทำงาน

1. **รับ 25 tasks พร้อมกัน**
   - Tasks เข้า queue (max 30)
   - แต่ละ task แบ่งเป็น chunks (30 วินาทีต่อ chunk)

2. **Process Chunks Parallel**
   - GPU Concurrency = 10 → process 10 chunks พร้อมกัน
   - Thread Pool = 10 workers → process chunks parallel
   - 25 tasks × chunks → process parallel ทั้งหมด

3. **Merge Results**
   - รวม chunks กลับเป็น full transcription
   - ส่งผลลัพธ์กลับ

### ตัวอย่าง: 25 Tasks, 10 นาทีต่อไฟล์

```
Task 1: 10 นาที = 20 chunks (30s/chunk)
Task 2: 10 นาที = 20 chunks
...
Task 25: 10 นาที = 20 chunks

Total: 25 tasks × 20 chunks = 500 chunks

Processing:
- GPU Concurrency = 10 → process 10 chunks พร้อมกัน
- Throughput = 10 chunks / batch
- Total batches = 500 / 10 = 50 batches

Time per batch = ~30 วินาที (transcription time)
Total time = 50 batches × 30s = 25 นาที

✅ 25 tasks เสร็จใน ~25 นาที (parallel processing)
```

## 📝 ขั้นตอนการตั้งค่า

### 1. อัปเดต `.env.runpod`

```bash
# เพิ่ม/แก้ไขใน .env.runpod
GPU_CONCURRENCY=10
MAX_QUEUE_TRANSCRIBE=30
TRANSCRIPTION_MAX_WORKERS=10
TRANSCRIPTION_PREFETCH_COUNT=10
```

### 2. Restart Services

```bash
# Restart worker เพื่อใช้ configuration ใหม่
bash scripts/pod/restart-pod-services.sh
```

### 3. ตรวจสอบ Configuration

```bash
# ตรวจสอบว่า configuration ถูกต้อง
env | grep -E 'GPU_CONCURRENCY|MAX_QUEUE_TRANSCRIBE|TRANSCRIPTION_MAX_WORKERS'
```

### 4. ทดสอบ 25 Concurrency

```python
# ส่ง 25 tasks พร้อมกัน (ใช้ chunking)
tasks = []
for i in range(25):
    task = await transcription_service.start_transcription(
        file_url=f"video_{i}.mp4",
        use_chunking=True,  # ✅ เปิด chunking
        chunk_duration=30,
        ...
    )
    tasks.append(task)

# Monitor progress
for task in tasks:
    status = await transcription_service.get_task_status(task.task_id)
    print(f"Task {task.task_id}: {status.status}")
```

## ⚠️ ข้อควรระวัง

### 1. GPU Memory

- **ตรวจสอบ GPU memory ก่อนเพิ่ม GPU_CONCURRENCY**
  ```bash
  nvidia-smi
  ```
- **Medium model**: ~2.4GB per instance
- **RTX 4080 SUPER 16GB**: แนะนำ `GPU_CONCURRENCY=10` (เผื่อ buffer)

### 2. Queue Overflow

- **Monitor queue size** - อย่าให้เกิน `MAX_QUEUE_TRANSCRIBE`
- **ใช้ Admission Control** - API จะ reject ถ้า queue เต็ม

### 3. Processing Time

- **Chunking เพิ่ม overhead** - ต้อง merge chunks
- **Monitor processing time** - ตรวจสอบว่าเร็วกว่าหรือไม่

### 4. Resource Monitoring

```bash
# Monitor GPU memory
watch -n 1 nvidia-smi

# Monitor queue size
curl http://localhost:8001/api/queue/status
```

## 📊 เปรียบเทียบ

| Configuration | GPU Concurrency | Queue Limit | รองรับ 25 Tasks? | หมายเหตุ |
|--------------|----------------|-------------|------------------|----------|
| **ปัจจุบัน** | 2 | 20 | ❌ ไม่ | GPU concurrency ต่ำเกินไป |
| **Option 1 (Chunking)** | 10 | 30 | ✅ ใช่ | ใช้ chunking + parallel processing |
| **Option 2 (High GPU)** | 25 | 30 | ⚠️ ต้อง GPU 60GB+ | ต้อง GPU memory สูงมาก |
| **Option 3 (Base Model)** | 15 | 30 | ⚠️ ต้อง chunking | ใช้ Base model + chunking |

## ✅ สรุป

### สำหรับ 25 Concurrency (Parallel):

1. **ใช้ Chunking** (`use_chunking=True`) - แบ่ง video เป็น chunks
2. **เพิ่ม GPU_CONCURRENCY=10** - สำหรับ RTX 4080 SUPER 16GB
3. **เพิ่ม MAX_QUEUE_TRANSCRIBE=30** - รองรับ 25 tasks + buffer
4. **เพิ่ม TRANSCRIPTION_MAX_WORKERS=10** - process chunks parallel
5. **Monitor GPU memory** - ตรวจสอบว่าไม่เกิน VRAM

### ผลลัพธ์:

- ✅ **รองรับ 25 tasks พร้อมกัน** - แต่ละ task แบ่งเป็น chunks
- ✅ **Process parallel** - 10 chunks พร้อมกัน (GPU concurrency)
- ✅ **ใช้ GPU memory อย่างมีประสิทธิภาพ** - ไม่เกิด OOM
- ✅ **เร็วกว่า sequential** - process chunks พร้อมกัน

---

**Last Updated**: 2025-01-XX  
**Recommended**: Option 1 (Chunking) + GPU_CONCURRENCY=10

