# 🏗️ Worker Architecture สำหรับ 25 Concurrency

## ❌ คำตอบสั้นๆ: **ไม่ต้องมี Worker 25 ตัว!**

### สถานะปัจจุบัน

**Video Worker = 1 ตัว** ที่จัดการทุกอย่าง:
- ✅ Audio Extraction (CPU)
- ✅ Transcription (GPU)
- ✅ Parallel Processing (Thread Pool)

## 📊 Architecture ปัจจุบัน

```
┌─────────────────────────────────────────────────┐
│         Video Worker (1 Process)                │
│                                                 │
│  ┌──────────────────────────────────────────┐ │
│  │  Audio Extraction (CPU)                  │ │
│  │  ├── ThreadPoolExecutor: 3 workers       │ │
│  │  ├── Queue: audio_extraction_queue       │ │
│  │  └── FFmpeg Semaphore: 3                │ │
│  └──────────────────────────────────────────┘ │
│                                                 │
│  ┌──────────────────────────────────────────┐ │
│  │  Transcription (GPU)                    │ │
│  │  ├── ThreadPoolExecutor: 5 workers      │ │
│  │  ├── Queue: transcription_queue         │ │
│  │  └── GPU Concurrency Semaphore: 2       │ │
│  └──────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### การทำงาน

1. **Video Worker 1 ตัว** รับ messages จาก RabbitMQ queues
2. **Thread Pool** จัดการ parallel processing:
   - Audio Extraction: 3 threads พร้อมกัน
   - Transcription: 5 threads พร้อมกัน
3. **GPU Semaphore** ควบคุม concurrent GPU tasks (2 tasks พร้อมกัน)

## ✅ สำหรับ 25 Concurrency: ใช้ Worker เดียว + เพิ่ม Thread Pool

### Configuration ที่แนะนำ

```bash
# Video Worker: ยังคงใช้ 1 ตัว (ไม่ต้องเพิ่ม)

# Audio Extraction (CPU)
AUDIO_EXTRACTION_MAX_WORKERS=10  # เพิ่มจาก 3 เป็น 10
FFMPEG_PROC_SEM=10              # เพิ่มจาก 3 เป็น 10

# Transcription (GPU)
TRANSCRIPTION_MAX_WORKERS=10     # เพิ่มจาก 5 เป็น 10
GPU_CONCURRENCY=10              # เพิ่มจาก 2 เป็น 10

# Queue Limits
MAX_QUEUE_TRANSCRIBE=30         # เพิ่มจาก 20 เป็น 30
```

### Architecture สำหรับ 25 Concurrency

```
┌─────────────────────────────────────────────────┐
│         Video Worker (1 Process)                 │
│                                                 │
│  ┌──────────────────────────────────────────┐ │
│  │  Audio Extraction (CPU)                  │ │
│  │  ├── ThreadPoolExecutor: 10 workers      │ │
│  │  ├── Queue: audio_extraction_queue       │ │
│  │  └── FFmpeg Semaphore: 10                │ │
│  │  ✅ รองรับ 10 audio extractions พร้อมกัน  │ │
│  └──────────────────────────────────────────┘ │
│                                                 │
│  ┌──────────────────────────────────────────┐ │
│  │  Transcription (GPU)                    │ │
│  │  ├── ThreadPoolExecutor: 10 workers      │ │
│  │  ├── Queue: transcription_queue         │ │
│  │  └── GPU Concurrency Semaphore: 10       │ │
│  │  ✅ รองรับ 10 GPU tasks พร้อมกัน          │ │
│  └──────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## 🔄 การทำงานสำหรับ 25 Tasks

### Scenario: 25 Tasks พร้อมกัน (ใช้ Chunking)

```
1. 25 Tasks เข้า Queue
   ↓
2. Video Worker (1 ตัว) รับ tasks จาก queue
   ↓
3. Audio Extraction (10 workers parallel)
   - Task 1-10: Extract audio พร้อมกัน (10 threads)
   - Task 11-20: Extract audio พร้อมกัน (10 threads)
   - Task 21-25: Extract audio พร้อมกัน (5 threads)
   ↓
4. แต่ละ Task แบ่งเป็น Chunks (30s/chunk)
   - Task 1 (10 min) = 20 chunks
   - Task 2 (10 min) = 20 chunks
   - ...
   - Task 25 (10 min) = 20 chunks
   - Total: 500 chunks
   ↓
5. Transcription (10 GPU workers parallel)
   - GPU Concurrency = 10 → process 10 chunks พร้อมกัน
   - 500 chunks / 10 = 50 batches
   - Process parallel ทั้งหมด
   ↓
6. Merge Results
   - รวม chunks กลับเป็น full transcription
   - ส่งผลลัพธ์กลับ
```

### Timeline

```
Time 0:00 - 25 tasks เข้า queue
Time 0:00-0:03 - Audio extraction (10 parallel)
  ├── Tasks 1-10: Extract (10 threads)
  ├── Tasks 11-20: Extract (10 threads)
  └── Tasks 21-25: Extract (5 threads)
Time 0:03-0:25 - Transcription (10 GPU parallel)
  ├── Batch 1: Chunks 1-10 (10 GPU tasks)
  ├── Batch 2: Chunks 11-20 (10 GPU tasks)
  ├── ...
  └── Batch 50: Chunks 491-500 (10 GPU tasks)
Time 0:25 - Merge results
Time 0:26 - ✅ 25 tasks เสร็จทั้งหมด
```

## ❌ ทำไมไม่ต้องมี Worker 25 ตัว?

### 1. **Thread Pool จัดการ Parallel Processing**

- **Worker 1 ตัว** + **Thread Pool 10 workers** = รองรับ 10 tasks พร้อมกัน
- **ไม่ต้องมี worker หลายตัว** - Thread pool จัดการให้

### 2. **GPU Semaphore ควบคุม Concurrency**

- **GPU_CONCURRENCY=10** → รองรับ 10 GPU tasks พร้อมกัน
- **ไม่ต้องมี worker หลายตัว** - Semaphore จัดการให้

### 3. **Queue-based Architecture**

- **RabbitMQ Queue** จัดการ task distribution
- **Worker 1 ตัว** รับ tasks จาก queue
- **Thread Pool** process parallel

### 4. **Resource Efficiency**

- **Worker 1 ตัว** ใช้ memory น้อยกว่า worker 25 ตัว
- **Shared resources** (model, connection) ใช้ร่วมกัน
- **ไม่ต้อง duplicate** services, connections

## 📊 เปรียบเทียบ

| Approach | Workers | Threads | GPU Concurrency | Memory | Complexity |
|----------|---------|---------|-----------------|--------|------------|
| **Worker 25 ตัว** | 25 | 1 each | 1 each | สูงมาก | สูง |
| **Worker 1 ตัว + Thread Pool** | 1 | 10 | 10 | ต่ำ | ต่ำ |

### ข้อดีของ Worker 1 ตัว + Thread Pool

- ✅ **Memory Efficient** - ใช้ memory น้อยกว่า
- ✅ **Shared Resources** - Model, connection ใช้ร่วมกัน
- ✅ **Easy Management** - จัดการ worker เดียว
- ✅ **Scalable** - เพิ่ม threads ได้ง่าย

### ข้อเสียของ Worker 25 ตัว

- ❌ **Memory Intensive** - ใช้ memory สูงมาก
- ❌ **Duplicate Resources** - Model, connection ซ้ำซ้อน
- ❌ **Complex Management** - จัดการ workers หลายตัว
- ❌ **Not Scalable** - ต้องเพิ่ม workers ใหม่ทุกครั้ง

## 🎯 สรุป

### ❌ ไม่ต้องมี:
- ❌ Video Worker 25 ตัว
- ❌ Audio Extraction Worker 25 ตัว

### ✅ ต้องมี:
- ✅ **Video Worker 1 ตัว**
- ✅ **Thread Pool 10 workers** (สำหรับ audio extraction)
- ✅ **Thread Pool 10 workers** (สำหรับ transcription)
- ✅ **GPU Concurrency 10** (semaphore)

### Configuration:

```bash
# Worker: ยังคงใช้ 1 ตัว
VIDEO_WORKER_TYPE=async

# Audio Extraction
AUDIO_EXTRACTION_MAX_WORKERS=10
FFMPEG_PROC_SEM=10

# Transcription
TRANSCRIPTION_MAX_WORKERS=10
GPU_CONCURRENCY=10

# Queue
MAX_QUEUE_TRANSCRIBE=30
```

### ผลลัพธ์:

- ✅ **รองรับ 25 tasks พร้อมกัน** (ผ่าน chunking)
- ✅ **Process parallel** - 10 audio extractions + 10 GPU tasks พร้อมกัน
- ✅ **ใช้ Worker 1 ตัว** - ไม่ต้องเพิ่ม workers
- ✅ **Resource Efficient** - ใช้ memory และ resources อย่างมีประสิทธิภาพ

---

**Last Updated**: 2025-01-XX  
**Key Point**: Worker 1 ตัว + Thread Pool = รองรับ 25 concurrency

