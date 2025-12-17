# 🚀 การตั้งค่าเพื่อรองรับ 25 Tasks พร้อมกัน (True Parallel - ไม่ใช่ Chunking)

## 📋 ความต้องการ

ต้องการให้ **25 tasks ทำพร้อมกัน** และเสร็จในเวลาเดียวกัน:

```
[1] -> (Audio Extraction) -> (Transcription) ┐
[2] -> (Audio Extraction) -> (Transcription) │
[3] -> (Audio Extraction) -> (Transcription) │
...                                           │ → ทั้งหมดทำพร้อมกัน
[24] -> (Audio Extraction) -> (Transcription)│
[25] -> (Audio Extraction) -> (Transcription)┘
```

## ❌ ปัญหาหลัก: GPU Memory

### สถานะปัจจุบัน

```
GPU: RTX 4080 SUPER 16GB VRAM
Model: Medium (~2.4GB per instance)
GPU_CONCURRENCY: 2

25 tasks พร้อมกัน:
- 25 × 2.4GB = 60GB VRAM ❌ (ไม่พอ! ต้องการ 60GB แต่มีแค่ 16GB)
```

### ข้อจำกัด

1. **GPU Memory ไม่พอ**
   - RTX 4080 SUPER: 16GB VRAM
   - Medium model: ~2.4GB per instance
   - 25 concurrent: 60GB VRAM (เกิน 4 เท่า!)

2. **GPU Concurrency ต่ำ**
   - ปัจจุบัน: `GPU_CONCURRENCY=2`
   - ต้องการ: `GPU_CONCURRENCY=25`

## ✅ วิธีแก้ไข: 3 ทางเลือก

### Option 1: ใช้ Base Model (แนะนำ) ⭐

**Base Model ใช้ VRAM น้อยกว่า Medium มาก**

#### Configuration

```bash
# ใช้ Base model แทน Medium
WHISPER_MODEL=base  # แทน medium

# GPU Concurrency - Base model ใช้ ~300MB-1GB per instance
GPU_CONCURRENCY=25  # 25 × 1GB = 25GB (เกิน 16GB แต่ใช้ model sharing)

# Model Sharing - ใช้ model เดียวกันสำหรับทุก threads (ประหยัด memory)
WHISPER_USE_THREAD_LOCAL=false  # ใช้ shared model

# Audio Extraction
AUDIO_EXTRACTION_MAX_WORKERS=25
FFMPEG_PROC_SEM=25

# Transcription Workers
TRANSCRIPTION_MAX_WORKERS=25

# Queue Limits
MAX_QUEUE_TRANSCRIBE=30
```

#### Memory Calculation

```
Base Model: ~300MB-1GB per instance
Model Sharing: 1 model สำหรับทุก threads
- 1 × 1GB (model) + 25 × 0.1GB (buffers) = ~3.5GB ✅ (พอสำหรับ 16GB)
```

#### ข้อดี
- ✅ **ใช้ VRAM น้อย** - Base model ~1GB (vs Medium 2.4GB)
- ✅ **รองรับ 25 concurrent** - ใช้ model sharing
- ✅ **ไม่ต้องเปลี่ยน GPU** - ใช้ RTX 4080 SUPER ได้

#### ข้อเสีย
- ⚠️ **ความแม่นยำต่ำกว่า** - Base model มี accuracy ต่ำกว่า Medium ~5-10%
- ⚠️ **ต้องทดสอบ** - ตรวจสอบว่า accuracy พอหรือไม่

### Option 2: ใช้ GPU ที่มี Memory สูงกว่า

#### GPU Options

| GPU | VRAM | 25 × Medium (60GB) | 25 × Base (25GB) | Status |
|-----|------|-------------------|------------------|--------|
| RTX 4080 SUPER | 16GB | ❌ ไม่พอ | ⚠️ ต้อง model sharing | ปัจจุบัน |
| RTX 4090 | 24GB | ❌ ไม่พอ | ✅ พอ | Upgrade |
| A100 40GB | 40GB | ❌ ไม่พอ | ✅ พอ | Cloud |
| A100 80GB | 80GB | ✅ พอ | ✅ พอ | Cloud |
| H100 80GB | 80GB | ✅ พอ | ✅ พอ | Cloud |

#### Configuration สำหรับ A100 80GB

```bash
# ใช้ Medium model
WHISPER_MODEL=medium

# GPU Concurrency - 25 tasks พร้อมกัน
GPU_CONCURRENCY=25

# Audio Extraction
AUDIO_EXTRACTION_MAX_WORKERS=25
FFMPEG_PROC_SEM=25

# Transcription Workers
TRANSCRIPTION_MAX_WORKERS=25

# Queue Limits
MAX_QUEUE_TRANSCRIBE=30
```

#### Memory Calculation

```
Medium Model: ~2.4GB per instance
25 concurrent: 25 × 2.4GB = 60GB ✅ (พอสำหรับ A100 80GB)
```

#### ข้อดี
- ✅ **ใช้ Medium model** - ความแม่นยำสูง
- ✅ **รองรับ 25 concurrent** - ไม่ต้อง model sharing

#### ข้อเสีย
- ❌ **ต้องเปลี่ยน GPU** - ต้องใช้ GPU ที่มี VRAM สูงกว่า
- ❌ **ค่าใช้จ่ายสูง** - A100/H100 แพงกว่า RTX 4080 SUPER

### Option 3: ใช้ Model Sharing + Base Model (ประหยัด Memory)

#### Configuration

```bash
# ใช้ Base model
WHISPER_MODEL=base

# Model Sharing - ใช้ model เดียวกันสำหรับทุก threads
WHISPER_USE_THREAD_LOCAL=false  # Shared model (ประหยัด memory)

# GPU Concurrency - 25 tasks พร้อมกัน
GPU_CONCURRENCY=25

# Audio Extraction
AUDIO_EXTRACTION_MAX_WORKERS=25
FFMPEG_PROC_SEM=25

# Transcription Workers
TRANSCRIPTION_MAX_WORKERS=25

# Queue Limits
MAX_QUEUE_TRANSCRIBE=30
```

#### Memory Calculation

```
Base Model: ~1GB (shared)
25 concurrent tasks: 25 × 0.1GB (buffers) = 2.5GB
Total: 1GB + 2.5GB = 3.5GB ✅ (พอสำหรับ 16GB)
```

#### ข้อดี
- ✅ **ใช้ VRAM น้อยมาก** - ~3.5GB (vs 60GB)
- ✅ **รองรับ 25 concurrent** - ใช้ RTX 4080 SUPER ได้
- ✅ **ไม่ต้องเปลี่ยน GPU**

#### ข้อเสีย
- ⚠️ **ต้องใช้ Base model** - ความแม่นยำต่ำกว่า Medium
- ⚠️ **อาจช้ากว่า** - Model sharing อาจมี overhead เล็กน้อย

## 🎯 แนะนำ: Option 1 (Base Model + Model Sharing)

### Configuration ที่แนะนำ

```bash
# .env.runpod

# Model Configuration
WHISPER_MODEL=base  # ใช้ Base model (ใช้ VRAM น้อยกว่า Medium)
WHISPER_USE_THREAD_LOCAL=false  # ใช้ shared model (ประหยัด memory)
WHISPER_COMPUTE_TYPE=float16
WHISPER_BATCH_SIZE=32

# GPU Concurrency - 25 tasks พร้อมกัน
GPU_CONCURRENCY=25

# Audio Extraction - 25 workers พร้อมกัน
AUDIO_EXTRACTION_MAX_WORKERS=25
FFMPEG_PROC_SEM=25

# Transcription Workers - 25 workers พร้อมกัน
TRANSCRIPTION_MAX_WORKERS=25
TRANSCRIPTION_PREFETCH_COUNT=25

# Queue Limits
MAX_QUEUE_TRANSCRIBE=30

# Worker Type
VIDEO_WORKER_TYPE=async
```

### การทำงาน

```
Time 0:00 - 25 tasks เข้า queue
  ↓
Time 0:00-0:03 - Audio Extraction (25 parallel)
  ├── Task 1: Extract audio (thread 1)
  ├── Task 2: Extract audio (thread 2)
  ├── ...
  └── Task 25: Extract audio (thread 25)
  ✅ ทั้งหมดทำพร้อมกัน (25 threads)
  ↓
Time 0:03-0:30 - Transcription (25 parallel)
  ├── Task 1: Transcribe (GPU task 1)
  ├── Task 2: Transcribe (GPU task 2)
  ├── ...
  └── Task 25: Transcribe (GPU task 25)
  ✅ ทั้งหมดทำพร้อมกัน (25 GPU tasks)
  ↓
Time 0:30 - ✅ 25 tasks เสร็จทั้งหมดพร้อมกัน
```

## 📝 ขั้นตอนการตั้งค่า

### 1. อัปเดต `.env.runpod`

```bash
# แก้ไขใน .env.runpod
WHISPER_MODEL=base
WHISPER_USE_THREAD_LOCAL=false
GPU_CONCURRENCY=25
AUDIO_EXTRACTION_MAX_WORKERS=25
FFMPEG_PROC_SEM=25
TRANSCRIPTION_MAX_WORKERS=25
TRANSCRIPTION_PREFETCH_COUNT=25
MAX_QUEUE_TRANSCRIBE=30
```

### 2. Restart Services

```bash
# Restart worker เพื่อใช้ configuration ใหม่
bash scripts/pod/restart-pod-services.sh
```

### 3. ตรวจสอบ Configuration

```bash
# ตรวจสอบว่า configuration ถูกต้อง
env | grep -E 'GPU_CONCURRENCY|WHISPER_MODEL|AUDIO_EXTRACTION_MAX_WORKERS|TRANSCRIPTION_MAX_WORKERS'
```

### 4. ทดสอบ 25 Concurrency

```python
# ส่ง 25 tasks พร้อมกัน (ไม่ใช้ chunking)
tasks = []
for i in range(25):
    task = await transcription_service.start_transcription(
        file_url=f"video_{i}.mp4",
        use_chunking=False,  # ❌ ไม่ใช้ chunking
        model_size="base",   # ✅ ใช้ Base model
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

- **ตรวจสอบ GPU memory ก่อน**
  ```bash
  nvidia-smi
  ```
- **Base model**: ~1GB (shared) + buffers
- **RTX 4080 SUPER 16GB**: พอสำหรับ 25 concurrent (ใช้ model sharing)

### 2. Model Accuracy

- **Base model มี accuracy ต่ำกว่า Medium ~5-10%**
- **ทดสอบก่อนใช้งานจริง** - ตรวจสอบว่า accuracy พอหรือไม่

### 3. Processing Time

- **Base model อาจช้ากว่า Medium เล็กน้อย**
- **Monitor processing time** - ตรวจสอบว่าเร็วพอหรือไม่

### 4. Resource Monitoring

```bash
# Monitor GPU memory
watch -n 1 nvidia-smi

# Monitor queue size
curl http://localhost:8001/api/queue/status

# Monitor worker logs
tail -f /tmp/video-worker.log
```

## 📊 เปรียบเทียบ

| Option | Model | GPU | VRAM Usage | Accuracy | Cost |
|--------|-------|-----|------------|----------|------|
| **Option 1** | Base | RTX 4080 SUPER | ~3.5GB | Medium | Low |
| **Option 2** | Medium | A100 80GB | ~60GB | High | High |
| **Option 3** | Base + Sharing | RTX 4080 SUPER | ~3.5GB | Medium | Low |

## ✅ สรุป

### สำหรับ 25 Tasks พร้อมกัน (True Parallel):

1. **ใช้ Base Model** (`WHISPER_MODEL=base`) - ใช้ VRAM น้อยกว่า Medium
2. **ใช้ Model Sharing** (`WHISPER_USE_THREAD_LOCAL=false`) - ประหยัด memory
3. **เพิ่ม GPU_CONCURRENCY=25** - รองรับ 25 GPU tasks พร้อมกัน
4. **เพิ่ม AUDIO_EXTRACTION_MAX_WORKERS=25** - รองรับ 25 audio extractions พร้อมกัน
5. **เพิ่ม TRANSCRIPTION_MAX_WORKERS=25** - รองรับ 25 transcriptions พร้อมกัน
6. **ไม่ใช้ Chunking** (`use_chunking=False`) - transcribe ทั้งไฟล์พร้อมกัน

### ผลลัพธ์:

- ✅ **รองรับ 25 tasks พร้อมกัน** - ทั้ง audio extraction และ transcription
- ✅ **เสร็จในเวลาเดียวกัน** - ทั้งหมด process parallel
- ✅ **ใช้ RTX 4080 SUPER 16GB ได้** - ใช้ Base model + model sharing
- ⚠️ **ความแม่นยำต่ำกว่า Medium** - Base model มี accuracy ต่ำกว่า ~5-10%

---

**Last Updated**: 2025-01-XX  
**Recommended**: Option 1 (Base Model + Model Sharing) สำหรับ RTX 4080 SUPER 16GB

