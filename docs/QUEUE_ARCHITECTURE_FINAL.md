# 🏗️ Queue Architecture Final Design (Production-Ready)

## 📋 สรุป Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  API Layer (Admission Control)                              │
│  - Check queue sizes                                         │
│  - Return 503 if overloaded                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  transcription_request_queue                                 │
│  - Type: Quorum Queue                                        │
│  - Max Length: 50                                           │
│  - Overflow: reject-publish                                 │
│  - DLX: transcription_request_queue.dlx                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
[Download & Route Worker]
- Prefetch: 1
- Thread Pool: 1 (single-threaded routing)
                       │
                       ├─ Video ──►
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  audio_extraction_queue                                      │
│  - Type: Quorum Queue                                        │
│  - Max Length: 80                                           │
│  - Prefetch: 1                                              │
│  - Process Semaphore: 3-4                                   │
│  - FFmpeg Process Semaphore: 2-3                            │
│  - DLX: audio_extraction_queue.dlx                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
[Audio Extraction Worker]
- Prefetch: 1
- Extract Pool Size: 4
- FFmpeg Process Sem: 3
- Timeout: 900s (15 min)
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  transcription_queue                                         │
│  - Type: Quorum Queue                                        │
│  - Max Length: 20                                           │
│  - Prefetch: 1                                              │
│  - GPU Concurrency: 1 (start with 1)                        │
│  - DLX: transcription_queue.dlx                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
[Transcription Worker]
- Prefetch: 1
- GPU Concurrency Semaphore: 1
- GPU Retry: 3 attempts (backoff: 5/15/45s)
- CPU Fallback: false (default)
- Timeout: 3600s (1 hour)
```

---

## 🔧 Key Improvements

### 1. ✅ Queue Limits (Max Length)

**ไม่ปล่อย "no limit"** - ตั้งเพดานจริงที่คิว:

```python
# Queue declarations with max-length
channel.queue_declare(
    queue='transcription_request_queue',
    durable=True,
    arguments={
        'x-queue-type': 'quorum',
        'x-max-length': 50,
        'x-overflow': 'reject-publish',  # Reject when full
        'x-dead-letter-exchange': 'transcription_request_queue.dlx'
    }
)
```

**Benefits:**
- ป้องกัน queue overflow
- Back-pressure mechanism
- API ตอบ 503 เมื่อ queue เต็ม

### 2. ✅ Prefetch = 1 + Semaphore Control

**ไม่ใช้ prefetch=3-5** - ใช้ prefetch=1 แล้วคุมด้วย semaphore:

```python
# Worker setup
channel.basic_qos(prefetch_count=1)  # Always 1

# Concurrency control with semaphore
extraction_semaphore = asyncio.Semaphore(4)  # Max 4 concurrent
transcription_semaphore = asyncio.Semaphore(1)  # Max 1 GPU task
```

**Benefits:**
- ควบคุม concurrency ได้ดีกว่า
- ACK เมื่องานเสร็จจริง
- ไม่ดูดงานเกิน

### 3. ✅ Process Semaphore for Audio Extraction

**FFmpeg เป็น process แยก** - ต้องใช้ process semaphore:

```python
# Two-level semaphore control
extraction_pool_semaphore = asyncio.Semaphore(4)  # Max 4 extraction tasks
ffmpeg_process_semaphore = asyncio.Semaphore(3)   # Max 3 FFmpeg processes

async def extract_audio(file_path):
    async with extraction_pool_semaphore:
        async with ffmpeg_process_semaphore:
            # Run FFmpeg
            await run_ffmpeg(...)
```

**Benefits:**
- ป้องกัน I/O/CPU spike
- Control FFmpeg process count
- Better resource management

### 4. ✅ GPU Concurrency = 1 (Start)

**เริ่มที่ 1 ก่อน** - GPU memory จำกัด:

```python
# GPU concurrency semaphore
gpu_concurrency_semaphore = asyncio.Semaphore(1)  # Start with 1

# Later can test with 2 if model allows
# GPU_CONCURRENCY = int(os.getenv('GPU_CONCURRENCY', '1'))
```

**Benefits:**
- ป้องกัน CUDA OOM
- Stable processing
- Can scale later

### 5. ✅ Disable CPU Fallback (Default)

**ปิด CPU fallback** - กันงานลาก:

```python
ALLOW_CPU_FALLBACK = os.getenv('ALLOW_CPU_FALLBACK', 'false').lower() == 'true'

if not ALLOW_CPU_FALLBACK:
    # Fail fast instead of falling back to CPU
    raise GPUError("GPU transcription failed, CPU fallback disabled")
```

**Benefits:**
- Fail fast instead of slow CPU processing
- Better error handling
- User knows immediately

### 6. ✅ DLX/TTL for Retry Pipeline

**Dead Letter Exchange** สำหรับ retry:

```python
# Queue with DLX
channel.queue_declare(
    queue='transcription_queue',
    durable=True,
    arguments={
        'x-queue-type': 'quorum',
        'x-dead-letter-exchange': 'transcription_queue.dlx',
        'x-message-ttl': 3600000  # 1 hour TTL
    }
)

# DLX queue
channel.queue_declare(
    queue='transcription_queue.dlx',
    durable=True
)
```

**Benefits:**
- Automatic retry mechanism
- Failed tasks don't block queue
- Better error recovery

### 7. ✅ Admission Control at API

**ตรวจสอบ queue ก่อนรับ request**:

```python
async def start_transcription(...):
    # Check queue sizes
    queue_info = rabbitmq_service.get_queue_info()
    
    request_queue_size = queue_info['transcription_request_queue']['message_count']
    extraction_queue_size = queue_info['audio_extraction_queue']['message_count']
    transcription_queue_size = queue_info['transcription_queue']['message_count']
    
    # Admission control
    if request_queue_size >= 50:
        raise HTTPException(
            status_code=503,
            detail="Request queue is full. Please try again later.",
            headers={"Retry-After": "30"}
        )
    
    if extraction_queue_size >= 80:
        raise HTTPException(
            status_code=503,
            detail="Audio extraction queue is full.",
            headers={"Retry-After": "60"}
        )
    
    if transcription_queue_size >= 20:
        raise HTTPException(
            status_code=503,
            detail="Transcription queue is full.",
            headers={"Retry-After": "120"}
        )
```

**Benefits:**
- Prevent overload before queuing
- Better user experience (503 with Retry-After)
- System stability

### 8. ✅ Quorum Queues

**ใช้ Quorum Queues** แทน Classic:

```python
arguments = {
    'x-queue-type': 'quorum',
    'x-max-length': 50,
    'x-overflow': 'reject-publish'
}
```

**Benefits:**
- Better durability
- Better performance
- Better replication support

### 9. ✅ Storage & Temp Cleanup

**ลบ temp files ทันที** หลังจบ:

```python
async def process_transcription(task_data):
    try:
        # Process transcription
        result = await transcribe(audio_path)
        
        # Save results
        await save_results(result)
        
    finally:
        # Always cleanup temp files
        cleanup_temp_files(audio_path)
        cleanup_temp_files(video_path)
```

**Benefits:**
- Save disk space
- Prevent disk full errors
- Better resource management

### 10. ✅ Timeout & Idempotency

**Timeout ครอบแต่ละ stage**:

```python
# Task timeout per stage
EXTRACT_TASK_TIMEOUT = 900  # 15 minutes
TRANSCRIPTION_TASK_TIMEOUT = 3600  # 1 hour

# Idempotency check
def check_idempotency(task_id):
    existing_task = storage.load_transcription(task_id)
    if existing_task and existing_task['status'] == 'completed':
        return existing_task  # Return cached result
    return None
```

**Benefits:**
- Prevent stuck tasks
- Handle retries safely
- Better resource cleanup

---

## 📝 Configuration Values

### Recommended Settings (RTX 4080 Super 16GB)

```bash
# API (Admission Control)
MAX_QUEUE_REQUEST=50
MAX_QUEUE_EXTRACTION=80
MAX_QUEUE_TRANSCRIBE=20
RETRY_AFTER_SECONDS=30

# RabbitMQ Consumers
PREFETCH=1
HEARTBEAT=1800
BLOCKED_CONNECTION_TIMEOUT=600

# Extraction
EXTRACT_POOL_SIZE=4
FFMPEG_PROC_SEM=3
EXTRACT_TASK_TIMEOUT=900  # 15 minutes

# Transcription (GPU)
GPU_CONCURRENCY=1        # Start with 1, test 2 later
TASK_TIMEOUT=3600        # 1 hour
GPU_RETRY_MAX=3
GPU_RETRY_BACKOFFS=5,15,45
ALLOW_CPU_FALLBACK=false

# Queue Types
USE_QUORUM_QUEUES=true
ENABLE_DLX=true
```

---

## 🔄 Message Flow

### Complete Flow

```
1. Client Request
   │
   ▼
2. API Admission Control
   - Check queue sizes
   - Return 503 if full
   │
   ▼
3. transcription_request_queue (max 50)
   │
   ▼
4. Download & Route Worker (prefetch=1)
   - Download file
   - Check file type
   - Route to appropriate queue
   │
   ├─ Video ──►
   │
   ▼
5. audio_extraction_queue (max 80, prefetch=1)
   │
   ▼
6. Audio Extraction Worker
   - Process semaphore: 4
   - FFmpeg semaphore: 3
   - Extract audio
   │
   ▼
7. transcription_queue (max 20, prefetch=1)
   │
   ▼
8. Transcription Worker
   - GPU semaphore: 1
   - Transcribe with retry (3 attempts)
   - No CPU fallback
   │
   ▼
9. Save Results & Cleanup
   - Save to storage
   - Cleanup temp files
   - Acknowledge message
```

---

## 🛠️ Implementation Checklist

### Phase 1: Queue Setup
- [ ] Create quorum queues with max-length
- [ ] Setup DLX queues
- [ ] Configure queue limits (50/80/20)
- [ ] Test queue overflow behavior
- [x] Basic queue size limiting (50 tasks)

### Phase 2: Worker Updates
- [x] Set prefetch=1 for all consumers
- [ ] Implement semaphore control
- [ ] Add process semaphore for FFmpeg
- [ ] Set GPU concurrency to 1
- [x] Thread Pool for Audio Extraction

### Phase 3: API Updates
- [x] Add admission control (basic)
- [x] Check queue sizes before queuing
- [ ] Return 503 with Retry-After header
- [ ] Check multiple queues (request/extraction/transcription)
- [ ] Add idempotency check

### Phase 4: Error Handling
- [ ] Disable CPU fallback (default)
- [x] Implement GPU retry with backoff
- [ ] Setup DLX for failed tasks
- [x] Add timeout per stage (task timeout)
- [x] RabbitMQ Heartbeat Timeout (1800s)
- [x] Background Thread for Connection Maintenance

### Phase 5: Cleanup
- [ ] Auto-cleanup temp files
- [ ] Monitor disk space
- [ ] Setup cleanup scheduler

---

## 📊 Expected Performance

### With 50 Concurrent Requests

**Queue Distribution:**
- Request Queue: 50 (accepted)
- Extraction Queue: 3-4 (processing), 46-47 (waiting)
- Transcription Queue: 1 (processing), 2-3 (waiting)

**Processing Timeline:**
- Extraction: ~15 minutes per file × 4 concurrent = ~3.75 files/min
- Transcription: ~3-5 minutes per file × 1 concurrent = ~0.2 files/min
- Total: ~50 files processed in ~4-6 hours

**Resource Usage:**
- CPU: Controlled (max 3 FFmpeg processes)
- RAM: Controlled (semaphore limits)
- GPU: Controlled (single task, no OOM)

---

## 🔗 Related Documents

- [Implementation Status Summary](./IMPLEMENTATION_STATUS_SUMMARY.md) - สรุปสถานะการ implement
- [Quick Test Guide](./QUICK_TEST_GUIDE.md) - คู่มือทดสอบ
- [Testing Checklist](./TESTING_CHECKLIST.md) - Checklist สำหรับการทดสอบ

---

**Last Updated**: 2024-12-04  
**Status**: Final Design (Production-Ready)

