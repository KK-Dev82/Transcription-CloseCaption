# 🚀 การตั้งค่าเพื่อรองรับ 25 Tasks พร้อมกัน (Audio Extraction → Chunking → Transcription)

## 📋 Flow ที่ต้องการ

```
25 tasks เข้า queue
  ↓
Audio Extraction (25 parallel)
  [1] Extract audio ┐
  [2] Extract audio │
  ...              │ → ทั้งหมดทำพร้อมกัน
  [25] Extract audio┘
  ↓
Chunking (25 parallel)
  [1] Chunk ┐
  [2] Chunk │
  ...       │ → ทั้งหมดทำพร้อมกัน
  [25] Chunk┘
  ↓
Transcription (25 parallel)
  [1] Transcribe ┐
  [2] Transcribe │
  ...            │ → ทั้งหมดทำพร้อมกัน
  [25] Transcribe┘
  ↓
✅ 25 tasks เสร็จทั้งหมดพร้อมกัน
```

## ✅ Configuration ที่ต้องตั้งค่า

### 1. Audio Extraction (25 parallel)

```bash
# Audio Extraction Workers - 25 workers พร้อมกัน
AUDIO_EXTRACTION_MAX_WORKERS=25
FFMPEG_PROC_SEM=25
EXTRACT_POOL_SIZE=25
```

### 2. Chunking (25 parallel)

**หมายเหตุ**: Chunking ทำงานใน main thread ของแต่ละ task (ไม่ต้องตั้งค่าเพิ่ม)

- แต่ละ task จะ chunk หลังจาก audio extraction เสร็จ
- 25 tasks = 25 chunking operations พร้อมกัน (แต่ละ task chunk เอง)

### 3. Transcription (25 parallel)

```bash
# GPU Concurrency - 25 tasks พร้อมกัน
GPU_CONCURRENCY=25

# Transcription Workers - 25 workers พร้อมกัน
TRANSCRIPTION_MAX_WORKERS=25
TRANSCRIPTION_PREFETCH_COUNT=25

# Queue Limits
MAX_QUEUE_TRANSCRIBE=30
MAX_QUEUE_EXTRACTION=30
```

### 4. Model Configuration (ประหยัด Memory)

```bash
# ใช้ Base model (ใช้ VRAM น้อยกว่า Medium)
WHISPER_MODEL=base

# ใช้ Model Sharing (ประหยัด memory)
WHISPER_USE_THREAD_LOCAL=false

# Compute Type
WHISPER_COMPUTE_TYPE=float16
WHISPER_BATCH_SIZE=32
```

## 📝 Configuration ครบถ้วน

### `.env.runpod`

```bash
# ============================================================================
# Model Configuration
# ============================================================================
WHISPER_MODEL=base
WHISPER_USE_THREAD_LOCAL=false
WHISPER_COMPUTE_TYPE=float16
WHISPER_BATCH_SIZE=32

# ============================================================================
# Audio Extraction Configuration (25 parallel)
# ============================================================================
AUDIO_EXTRACTION_MAX_WORKERS=25
FFMPEG_PROC_SEM=25
EXTRACT_POOL_SIZE=25
EXTRACT_TASK_TIMEOUT=900

# ============================================================================
# Transcription Configuration (25 parallel)
# ============================================================================
TRANSCRIPTION_MAX_WORKERS=25
TRANSCRIPTION_QUEUE_PREFETCH_COUNT=1
TRANSCRIPTION_PREFETCH_COUNT=25
TRANSCRIPTION_REQUEST_PREFETCH_COUNT=1

# ============================================================================
# GPU Concurrency (25 parallel)
# ============================================================================
GPU_CONCURRENCY=25
ALLOW_CPU_FALLBACK=false

# ============================================================================
# Queue Limits
# ============================================================================
MAX_QUEUE_REQUEST=30
MAX_QUEUE_EXTRACTION=30
MAX_QUEUE_TRANSCRIBE=30
TRANSCRIPTION_MAX_QUEUE_SIZE=30

# ============================================================================
# Worker Type
# ============================================================================
VIDEO_WORKER_TYPE=async
```

## 🔄 การทำงาน

### Step 1: 25 Tasks เข้า Queue

```
transcription_request_queue: [Task1, Task2, ..., Task25]
```

### Step 2: Audio Extraction (25 parallel)

```
Video Worker (1 ตัว)
├── ThreadPoolExecutor: 25 workers
├── FFmpeg Semaphore: 25
└── Process:
    ├── Task 1: Extract audio (thread 1)
    ├── Task 2: Extract audio (thread 2)
    ├── ...
    └── Task 25: Extract audio (thread 25)
    
✅ ทั้งหมดทำพร้อมกัน (25 threads)
```

### Step 3: Chunking (25 parallel)

```
แต่ละ Task (หลังจาก audio extraction เสร็จ):
├── Task 1: Create chunks (main thread)
├── Task 2: Create chunks (main thread)
├── ...
└── Task 25: Create chunks (main thread)

✅ ทั้งหมดทำพร้อมกัน (25 tasks chunk พร้อมกัน)
```

**หมายเหตุ**: Chunking ทำงานใน main thread ของแต่ละ task หลังจาก audio extraction เสร็จ

### Step 4: Transcription (25 parallel)

```
Video Worker (1 ตัว)
├── ThreadPoolExecutor: 25 workers
├── GPU Concurrency Semaphore: 25
└── Process:
    ├── Task 1: Transcribe chunks (GPU task 1)
    ├── Task 2: Transcribe chunks (GPU task 2)
    ├── ...
    └── Task 25: Transcribe chunks (GPU task 25)
    
✅ ทั้งหมดทำพร้อมกัน (25 GPU tasks)
```

## 📊 Memory Calculation

### Base Model + Model Sharing

```
Base Model: ~1GB (shared model)
25 concurrent tasks: 25 × 0.1GB (buffers) = 2.5GB
Audio Extraction: ~0.5GB (temporary files)
Total: 1GB + 2.5GB + 0.5GB = 4GB ✅ (พอสำหรับ 16GB)
```

### Medium Model (ไม่แนะนำ - ใช้ VRAM มาก)

```
Medium Model: ~2.4GB per instance
25 concurrent: 25 × 2.4GB = 60GB ❌ (ไม่พอสำหรับ 16GB)
```

## 🎯 Timeline ตัวอย่าง

### Scenario: 25 Tasks, 10 นาทีต่อไฟล์

```
Time 0:00 - 25 tasks เข้า queue
  ↓
Time 0:00-0:03 - Audio Extraction (25 parallel)
  [1-25] Extract audio พร้อมกัน (25 threads)
  ✅ เสร็จพร้อมกัน
  ↓
Time 0:03-0:04 - Chunking (25 parallel)
  [1-25] Create chunks พร้อมกัน (25 tasks)
  ✅ เสร็จพร้อมกัน
  ↓
Time 0:04-0:30 - Transcription (25 parallel)
  [1-25] Transcribe chunks พร้อมกัน (25 GPU tasks)
  ✅ เสร็จพร้อมกัน
  ↓
Time 0:30 - ✅ 25 tasks เสร็จทั้งหมดพร้อมกัน
```

## 📝 ขั้นตอนการตั้งค่า

### 1. อัปเดต `.env.runpod`

```bash
# Copy configuration ด้านบนไปใส่ใน .env.runpod
```

### 2. Restart Services

```bash
# Restart worker เพื่อใช้ configuration ใหม่
bash scripts/pod/restart-pod-services.sh
```

### 3. ตรวจสอบ Configuration

```bash
# ตรวจสอบว่า configuration ถูกต้อง
env | grep -E 'GPU_CONCURRENCY|AUDIO_EXTRACTION_MAX_WORKERS|TRANSCRIPTION_MAX_WORKERS|WHISPER_MODEL'
```

### 4. ทดสอบ 25 Concurrency

```python
# ส่ง 25 tasks พร้อมกัน (ใช้ chunking)
tasks = []
for i in range(25):
    task = await transcription_service.start_transcription(
        file_url=f"video_{i}.mp4",
        use_chunking=True,  # ✅ เปิด chunking
        chunk_duration=30,  # 30 วินาทีต่อ chunk
        model_size="base",  # ✅ ใช้ Base model
        ...
    )
    tasks.append(task)

# Monitor progress
for task in tasks:
    status = await transcription_service.get_task_status(task.task_id)
    print(f"Task {task.task_id}: {status.status}, Progress: {status.progress}%")
```

## ⚠️ ข้อควรระวัง

### 1. GPU Memory

- **ตรวจสอบ GPU memory ก่อน**
  ```bash
  nvidia-smi
  ```
- **Base model**: ~1GB (shared) + buffers
- **RTX 4080 SUPER 16GB**: พอสำหรับ 25 concurrent (ใช้ model sharing)

### 2. Chunking Overhead

- **Chunking ใช้เวลาเพิ่ม** - แต่ละ task ต้อง chunk หลังจาก audio extraction
- **Monitor processing time** - ตรวจสอบว่าเร็วพอหรือไม่

### 3. Queue Overflow

- **Monitor queue size** - อย่าให้เกิน `MAX_QUEUE_TRANSCRIBE`
- **ใช้ Admission Control** - API จะ reject ถ้า queue เต็ม

### 4. Resource Monitoring

```bash
# Monitor GPU memory
watch -n 1 nvidia-smi

# Monitor queue size
curl http://localhost:8001/api/queue/status

# Monitor worker logs
tail -f /tmp/video-worker.log | grep -E 'Extract|Chunk|Transcribe'
```

## 📊 เปรียบเทียบ

| Configuration | Audio Extraction | Chunking | Transcription | Memory | Status |
|--------------|------------------|----------|---------------|--------|--------|
| **ปัจจุบัน** | 3 parallel | Sequential | 2 parallel | Low | ❌ ไม่พอ |
| **25 Parallel** | 25 parallel | 25 parallel | 25 parallel | ~4GB | ✅ พอ |

## ✅ สรุป

### สำหรับ 25 Tasks พร้อมกัน (Audio Extraction → Chunking → Transcription):

1. **Audio Extraction**: `AUDIO_EXTRACTION_MAX_WORKERS=25` - 25 parallel
2. **Chunking**: ทำงานใน main thread ของแต่ละ task - 25 parallel (อัตโนมัติ)
3. **Transcription**: `GPU_CONCURRENCY=25` + `TRANSCRIPTION_MAX_WORKERS=25` - 25 parallel
4. **Model**: `WHISPER_MODEL=base` + `WHISPER_USE_THREAD_LOCAL=false` - ประหยัด memory

### ผลลัพธ์:

- ✅ **25 tasks ทำพร้อมกัน** - Audio Extraction → Chunking → Transcription
- ✅ **เสร็จในเวลาเดียวกัน** - ทั้งหมด process parallel
- ✅ **ใช้ RTX 4080 SUPER 16GB ได้** - ใช้ Base model + model sharing
- ✅ **รองรับ Chunking** - แต่ละ task แบ่งเป็น chunks และ process parallel

---

**Last Updated**: 2025-01-XX  
**Key Point**: 25 parallel ในทุกขั้นตอน (Audio Extraction → Chunking → Transcription)

