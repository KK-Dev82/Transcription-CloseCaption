# 🎯 GPU Pod Transcription Service - Overview

**วันที่**: 04-12-2025  
**สถานะ**: Production-Ready Architecture Implemented  
**Progress**: 100% Complete (Phase 1-5)

---

## 📋 สารบัญ

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Queue Architecture & Flow](#queue-architecture--flow)
4. [Component Overview](#component-overview)
5. [Implementation Phases](#implementation-phases)
6. [Configuration Summary](#configuration-summary)
7. [Performance Characteristics](#performance-characteristics)

---

## 🎯 Executive Summary

Transcription Service บน GPU Pod (RunPod) ได้รับการปรับปรุงให้เป็น **Production-Ready Architecture** ที่รองรับ:
- **50+ concurrent requests** พร้อมกัน
- **3-Queue Pipeline Architecture** (request → extraction → transcription)
- **Resource Control** ด้วย Semaphores และ Queue Limits
- **Error Handling & Recovery** ที่แข็งแกร่ง
- **Auto Cleanup & Monitoring** สำหรับ maintenance

### ✨ Key Features

- ✅ **3-Queue Architecture**: แยก request, extraction, และ transcription stages
- ✅ **Quorum Queues**: Production-grade durability
- ✅ **Admission Control**: ตรวจสอบ queue sizes ก่อนรับ request
- ✅ **Semaphore Control**: ควบคุม concurrent processing (FFmpeg, GPU)
- ✅ **GPU Retry Logic**: Retry ก่อน fallback
- ✅ **Idempotency**: ป้องกัน duplicate requests
- ✅ **Auto Cleanup**: Periodic cleanup และ disk space monitoring

---

## 🏗️ System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client (Frontend/Backend)                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP POST /transcribe/
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Service (Port 8010)                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  API Layer                                                │   │
│  │  - Admission Control (Queue Size Check)                  │   │
│  │  - Idempotency Check                                     │   │
│  │  - Return 503 + Retry-After if overloaded               │   │
│  └──────────────────────┬───────────────────────────────────┘   │
└─────────────────────────┼───────────────────────────────────────┘
                          │
                          │ RabbitMQ Message
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RabbitMQ Message Broker                       │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐    │
│  │ Request Queue  │→ │ Extraction     │→ │ Transcription  │    │
│  │ (max 50)       │  │ Queue (max 80) │  │ Queue (max 20) │    │
│  └────────────────┘  └────────────────┘  └────────────────┘    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ Messages consumed by Workers
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Video Workers                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Request Router Worker                                    │   │
│  │  - Download file from URL                                 │   │
│  │  - Route to extraction/transcription queue                │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Audio Extraction Worker                                  │   │
│  │  - Thread Pool (max 3 workers)                           │   │
│  │  - FFmpeg Process Semaphore (max 3)                      │   │
│  │  - Extract audio from video                              │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Transcription Worker                                     │   │
│  │  - GPU Concurrency Semaphore (max 1)                     │   │
│  │  - Faster-Whisper (CUDA)                                 │   │
│  │  - Retry Logic (3 attempts)                              │   │
│  └──────────────────────┬───────────────────────────────────┘   │
└─────────────────────────┼───────────────────────────────────────┘
                          │
                          │ Save Results
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    JSON Storage                                  │
│  - Task metadata                                                │
│  - Transcription results                                        │
│  - Metrics                                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Service Components

#### 1. **FastAPI Service** (`app/main.py`)
- Main API server (Port 8010)
- REST API endpoints
- WebSocket support (optional)
- Static file serving

#### 2. **Transcription Service** (`app/services/transcription_service.py`)
- Request handling และ admission control
- Task management และ status tracking
- Idempotency checking
- Callback/webhook management

#### 3. **RabbitMQ Service** (`app/services/rabbitmq_service.py`)
- Queue declarations (Quorum Queues)
- Message publishing
- Queue information retrieval
- DLX setup

#### 4. **Video Worker** (`app/workers/video_worker.py`)
- RabbitMQ consumer
- Task processing
- Connection maintenance
- Background monitoring

#### 5. **Video Service** (`app/services/video_service.py`)
- Audio extraction (FFmpeg)
- Thread pool management
- Process semaphore control
- Metrics recording

#### 6. **Whisper Service** (`app/services/whisper_service.py`)
- Provider pattern
- Faster-Whisper integration
- GPU/CPU fallback

#### 7. **Cleanup Service** (`app/services/cleanup_service.py`)
- Periodic cleanup scheduler
- Disk space monitoring
- Temp file cleanup

---

## 🔄 Queue Architecture & Flow

### 3-Queue Pipeline Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Phase 1: API Admission Control                                  │
│  - Check transcription_request_queue size                        │
│  - Check audio_extraction_queue size                             │
│  - Check transcription_queue size                                │
│  - Return 503 if any queue is full                              │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Queue 1: transcription_request_queue                            │
│  ────────────────────────────────────────────────────────────    │
│  Type: Quorum Queue                                              │
│  Max Length: 50 messages                                         │
│  Overflow: reject-publish (return 503)                          │
│  DLX: transcription_request_queue.dlx                           │
│  Prefetch: 1                                                     │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Worker: Download & Route                                        │
│  ────────────────────────────────────────────────────────────    │
│  - Consume from transcription_request_queue                      │
│  - Download file from file_url                                   │
│  - Check file type (video/audio)                                 │
│  - Route to appropriate queue:                                   │
│    • Video → audio_extraction_queue                              │
│    • Audio → transcription_queue                                 │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
          ┌─────────▼─────────┐  ┌───▼────────────────────────┐
          │  Video File       │  │  Audio File                │
          │  (skip extraction)│  │  (direct to transcription) │
          └─────────┬─────────┘  └───────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│  Queue 2: audio_extraction_queue                                 │
│  ────────────────────────────────────────────────────────────    │
│  Type: Quorum Queue                                              │
│  Max Length: 80 messages                                         │
│  Overflow: reject-publish                                        │
│  DLX: audio_extraction_queue.dlx                                │
│  Prefetch: 1                                                     │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Worker: Audio Extraction                                        │
│  ────────────────────────────────────────────────────────────    │
│  - Thread Pool: max 3 workers                                    │
│  - FFmpeg Process Semaphore: max 3                               │
│  - Extract audio from video (16kHz mono WAV)                     │
│  - Timeout: 900s (15 minutes)                                    │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Queue 3: transcription_queue                                    │
│  ────────────────────────────────────────────────────────────    │
│  Type: Quorum Queue                                              │
│  Max Length: 20 messages                                         │
│  Overflow: reject-publish                                        │
│  DLX: transcription_queue.dlx                                    │
│  Prefetch: 1                                                     │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Worker: Transcription (GPU)                                     │
│  ────────────────────────────────────────────────────────────    │
│  - GPU Concurrency Semaphore: 1                                  │
│  - Faster-Whisper (CUDA)                                         │
│  - Retry Logic: 3 attempts (backoff: 5/15/45s)                  │
│  - CPU Fallback: disabled (default)                              │
│  - Timeout: 3600s (1 hour)                                       │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Save Results & Cleanup                                          │
│  ────────────────────────────────────────────────────────────    │
│  - Save to JSON Storage                                          │
│  - Cleanup temp files                                            │
│  - Send callback/webhook                                         │
│  - Acknowledge message                                           │
└──────────────────────────────────────────────────────────────────┘
```

### Queue Types & Configuration

#### Transcription Request Queue
- **Purpose**: รับ requests จาก API
- **Max Length**: 50 messages
- **Overflow Behavior**: reject-publish (return 503)
- **DLX**: Enabled
- **Prefetch**: 1

#### Audio Extraction Queue
- **Purpose**: เก็บ tasks ที่ต้อง extract audio จาก video
- **Max Length**: 80 messages
- **Overflow Behavior**: reject-publish
- **DLX**: Enabled
- **Prefetch**: 1
- **Concurrency**: 3-4 workers (Thread Pool)
- **FFmpeg Processes**: max 3 (Process Semaphore)

#### Transcription Queue
- **Purpose**: เก็บ tasks ที่พร้อมสำหรับ transcription
- **Max Length**: 20 messages
- **Overflow Behavior**: reject-publish
- **DLX**: Enabled
- **Prefetch**: 1
- **GPU Concurrency**: 1 task (เริ่มต้น)

---

## 📦 Component Overview

### API Layer

#### Admission Control
- ตรวจสอบ queue sizes ทั้ง 3 queues ก่อนรับ request
- Return 503 Service Unavailable ถ้า queue เต็ม
- Include Retry-After header (30 seconds default)
- Detailed error messages ระบุ queue ที่เต็ม

#### Idempotency
- ตรวจสอบ duplicate requests ด้วย `idempotency_key`
- หรือตรวจสอบจาก file_path/file_url + parameters
- Return existing task_id ถ้าพบ completed task
- Prevent duplicate processing

### Queue Management

#### Quorum Queues
- ใช้ Quorum Queue type สำหรับความทนทาน
- Better consistency และ durability
- Configurable via `USE_QUORUM_QUEUES` env var

#### Queue Limits
- `transcription_request_queue`: max 50
- `audio_extraction_queue`: max 80
- `transcription_queue`: max 20
- All queues use `x-overflow=reject-publish`

#### Dead Letter Exchange (DLX)
- Automatic DLX setup สำหรับทุก queue
- Failed tasks ส่งไป DLX queue
- Configurable via `ENABLE_DLX` env var

### Worker Layer

#### Audio Extraction Worker
- **Thread Pool**: max 3 workers (configurable)
- **FFmpeg Process Semaphore**: max 3 processes
- **2-Level Control**: Thread Pool + Process Semaphore
- **Timeout**: 900s (15 minutes)
- **Metrics**: Separate tracking จาก transcription

#### Transcription Worker
- **GPU Concurrency**: 1 task (เริ่มต้น)
- **Retry Logic**: 3 attempts with exponential backoff
- **CPU Fallback**: Disabled by default
- **Timeout**: 3600s (1 hour)
- **Metrics**: Separate tracking จาก audio extraction

### Error Handling

#### GPU Retry
- Retry GPU transcription 3 ครั้งก่อน fail
- Exponential backoff: 5s, 15s, 45s
- Clear CUDA cache ก่อน retry
- Configurable retry count และ delay

#### CPU Fallback Control
- Default: disabled (`ALLOW_CPU_FALLBACK=false`)
- Fail fast แทนการ fallback ไป CPU
- Prevent long-running CPU tasks
- Better error reporting

#### Task Timeout
- Global timeout: 3600s (1 hour)
- ตรวจสอบ timeout ก่อนเริ่ม processing
- Mark task as failed ถ้า timeout
- Release resources immediately

### Cleanup & Monitoring

#### Periodic Cleanup
- Background task รันทุก 1 ชั่วโมง (configurable)
- ลบ temp folders ที่เก่ากว่า 24 ชั่วโมง (configurable)
- Aggressive cleanup เมื่อ disk space ต่ำ

#### Disk Space Monitoring
- Warning threshold: 10 GB (configurable)
- Critical threshold: 5 GB (configurable)
- Automatic aggressive cleanup เมื่อ critical
- API endpoint สำหรับ monitoring

---

## 🛠️ Implementation Phases

### Phase 1: Queue Setup ✅

#### 1.1: 3-Queue Architecture
- เพิ่ม `transcription_request_queue`
- เพิ่ม `audio_extraction_queue`
- Keep existing `transcription_queue`
- Update routing logic

#### 1.2: Quorum Queues Support
- Helper method สำหรับ queue arguments
- Support `x-queue-type: quorum`
- Configurable via `USE_QUORUM_QUEUES`

#### 1.3: Queue Max-Length & Overflow
- `x-max-length` สำหรับทุก queue
- `x-overflow: reject-publish`
- Configurable limits per queue

#### 1.4: DLX (Dead Letter Exchange) Setup
- DLX exchange และ queue สำหรับทุก queue
- Automatic routing สำหรับ failed tasks
- Configurable via `ENABLE_DLX`

#### 1.5: Queue Declarations Update
- Update `rabbitmq_service.py`
- Update `video_worker.py`
- Support new queue arguments

#### 1.6: Routing Logic Update
- Full admission control (check all 3 queues)
- Route to `transcription_request_queue`
- Backward compatible (legacy mode)

### Phase 2: Worker Updates ✅

#### 2.1: Semaphore Control
- Thread Pool สำหรับ Audio Extraction (มีอยู่แล้ว)
- Configurable worker count

#### 2.2: Process Semaphore for FFmpeg
- `threading.Semaphore` สำหรับ FFmpeg processes
- Max 3 concurrent FFmpeg processes
- Configurable via `FFMPEG_PROC_SEM`

#### 2.3: GPU Concurrency Semaphore
- `asyncio.Semaphore` สำหรับ GPU tasks
- Max 1 concurrent GPU task (เริ่มต้น)
- Global singleton pattern
- Configurable via `GPU_CONCURRENCY`

### Phase 3: API Updates ✅

#### 3.1: Return 503 with Retry-After Header
- Include `Retry-After` header ใน 503 responses
- Configurable retry delay
- Different delays per queue type

#### 3.2: Idempotency Check
- เพิ่ม `idempotency_key` field ใน request
- Check existing tasks ก่อนสร้างใหม่
- Return cached results

### Phase 4: Error Handling ✅

#### 4.1: Disable CPU Fallback (Default)
- `ALLOW_CPU_FALLBACK=false` (default)
- Fail fast แทน fallback
- Better error messages

#### 4.2: DLX Routing for Failed Tasks
- Automatic DLX routing (via basic_nack)
- Failed tasks ส่งไป DLX queue
- Manual retry mechanism

#### Other Error Handling Features (ทำแล้วก่อนหน้านี้)
- GPU Retry with Backoff
- Task Timeout
- RabbitMQ Heartbeat Timeout (1800s)
- Background Thread for Connection Maintenance

### Phase 5: Cleanup ✅

#### 5.1: Periodic Cleanup Scheduler
- Background task รันทุก 1 ชั่วโมง
- Auto-cleanup old temp folders
- Startup และ shutdown handlers

#### 5.2: Disk Space Monitoring
- Real-time disk space checking
- Warning และ critical thresholds
- Aggressive cleanup เมื่อ critical

#### 5.3: Auto-cleanup Enhancements
- Startup cleanup
- Periodic scheduler
- Cleanup statistics
- API endpoints

---

## ⚙️ Configuration Summary

### Environment Variables

#### Queue Configuration
```
MAX_QUEUE_REQUEST=50
MAX_QUEUE_EXTRACTION=80
MAX_QUEUE_TRANSCRIBE=20
RETRY_AFTER_SECONDS=30
USE_3QUEUE_ARCHITECTURE=true
USE_QUORUM_QUEUES=true
ENABLE_DLX=true
```

#### Worker Configuration
```
TRANSCRIPTION_QUEUE_PREFETCH_COUNT=1
AUDIO_EXTRACTION_MAX_WORKERS=3
FFMPEG_PROC_SEM=3
GPU_CONCURRENCY=1
```

#### Error Handling
```
ALLOW_CPU_FALLBACK=false
GPU_TRANSCRIPTION_MAX_RETRIES=3
GPU_TRANSCRIPTION_RETRY_DELAY=5.0
TRANSCRIPTION_TASK_TIMEOUT_SECONDS=3600
```

#### RabbitMQ Connection
```
RABBITMQ_HEARTBEAT_TIMEOUT=1800
RABBITMQ_BLOCKED_TIMEOUT=600
RABBITMQ_CONNECTION_CHECK_INTERVAL=30
```

#### Cleanup Service
```
CLEANUP_INTERVAL_SECONDS=3600
TEMP_FOLDER_MAX_AGE_HOURS=24
DISK_SPACE_WARNING_THRESHOLD_GB=10.0
DISK_SPACE_CRITICAL_THRESHOLD_GB=5.0
```

#### GPU Configuration
```
WHISPER_PROVIDER=faster-whisper
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
WHISPER_BATCH_SIZE=32
CUDA_VISIBLE_DEVICES=0
```

---

## 📊 Performance Characteristics

### Expected Performance with 50 Concurrent Requests

#### Queue Distribution
- **Request Queue**: 50 messages (all accepted)
- **Extraction Queue**: 3-4 processing, 46-47 waiting
- **Transcription Queue**: 1 processing, 2-3 waiting

#### Processing Timeline
- **Audio Extraction**: ~15 minutes/file × 4 concurrent = ~3.75 files/min
- **Transcription**: ~3-5 minutes/file × 1 concurrent = ~0.2 files/min
- **Total Processing Time**: ~4-6 hours สำหรับ 50 files

#### Resource Usage
- **CPU**: Controlled (max 3 FFmpeg processes)
- **RAM**: Controlled (semaphore limits)
- **GPU**: Controlled (single task, no OOM)
- **Disk**: Auto-cleanup prevents overflow

### Concurrency Limits

| Component | Concurrency Limit | Control Mechanism |
|-----------|-------------------|-------------------|
| Request Queue | 50 messages | Queue max-length |
| Audio Extraction | 3-4 workers | Thread Pool |
| FFmpeg Processes | 3 processes | Process Semaphore |
| GPU Transcription | 1 task | GPU Semaphore |

### Error Recovery

- **GPU Retry**: 3 attempts with backoff
- **DLX Routing**: Failed tasks ส่งไป DLX queue
- **Connection Maintenance**: Automatic reconnection
- **Task Timeout**: 1 hour timeout per task

---

## 🔄 Complete Request Flow

### Step-by-Step Flow

```
1. Client Request
   └─ POST /transcribe/ with file_url, language, model_size, etc.
   
2. API Admission Control
   └─ Check all 3 queue sizes
   └─ Return 503 if any queue is full
   └─ Include Retry-After header
   
3. Idempotency Check (optional)
   └─ Check if request already processed
   └─ Return existing task_id if found
   
4. Send to Request Queue
   └─ transcription_request_queue (max 50)
   └─ Create task_id และ save to storage
   
5. Download & Route Worker
   └─ Download file from file_url
   └─ Check file type (video/audio)
   └─ Route to:
      • Video → audio_extraction_queue
      • Audio → transcription_queue
   
6. Audio Extraction (if video)
   └─ audio_extraction_queue (max 80)
   └─ Thread Pool (3 workers)
   └─ FFmpeg Process Semaphore (3 processes)
   └─ Extract audio (16kHz mono WAV)
   └─ Send to transcription_queue
   
7. Transcription
   └─ transcription_queue (max 20)
   └─ GPU Concurrency Semaphore (1 task)
   └─ Faster-Whisper (CUDA)
   └─ Retry logic (3 attempts)
   └─ No CPU fallback (fail fast)
   
8. Save Results
   └─ Save to JSON Storage
   └─ Update task status
   └─ Cleanup temp files
   
9. Callback/Webhook
   └─ POST to callback_url (if provided)
   └─ Include task_id, status, results
   
10. Acknowledge Message
    └─ ACK message in RabbitMQ
    └─ Task complete
```

---

## 📁 File Structure

### Key Files Modified/Created

#### Services
- `app/services/rabbitmq_service.py` - Queue declarations, DLX setup
- `app/services/transcription_service.py` - Admission control, routing, idempotency
- `app/services/video_service.py` - Audio extraction, process semaphore
- `app/services/whisper_providers/faster_whisper_provider.py` - GPU semaphore, retry logic
- `app/services/cleanup_service.py` - Cleanup scheduler, disk monitoring

#### Workers
- `app/workers/video_worker.py` - Queue declarations, consumers, connection maintenance

#### API
- `app/api/transcription.py` - API endpoints, idempotency support
- `app/api/cleanup.py` - Cleanup monitoring endpoints

#### Models
- `app/models/transcription.py` - Request/Response models, idempotency_key field

#### Main Application
- `app/main.py` - Startup/shutdown events, cleanup service integration

#### Configuration
- `env.runpod` - Environment variables สำหรับ RunPod deployment

---

## 🎯 Key Improvements Summary

### Reliability
- ✅ Quorum Queues สำหรับความทนทาน
- ✅ DLX สำหรับ error recovery
- ✅ Connection maintenance thread
- ✅ Retry logic สำหรับ GPU tasks

### Performance
- ✅ Semaphore control สำหรับ resource management
- ✅ 3-Queue pipeline สำหรับ parallel processing
- ✅ Prefetch=1 เพื่อควบคุม concurrency
- ✅ GPU concurrency = 1 เพื่อป้องกัน OOM

### Scalability
- ✅ Queue limits เพื่อรับ burst traffic
- ✅ Admission control เพื่อป้องกัน overload
- ✅ Configurable concurrency limits
- ✅ Backward compatible (legacy mode)

### Maintainability
- ✅ Periodic cleanup scheduler
- ✅ Disk space monitoring
- ✅ Comprehensive logging
- ✅ Metrics tracking (extraction vs transcription)

### User Experience
- ✅ 503 responses with Retry-After
- ✅ Idempotency support
- ✅ Clear error messages
- ✅ Fast failure (no CPU fallback)

---

## 📊 Implementation Status

| Phase | Tasks | Status | Progress |
|-------|-------|--------|----------|
| Phase 1: Queue Setup | 6 | ✅ Complete | 100% |
| Phase 2: Worker Updates | 3 | ✅ Complete | 100% |
| Phase 3: API Updates | 2 | ✅ Complete | 100% |
| Phase 4: Error Handling | 6 | ✅ Complete | 100% |
| Phase 5: Cleanup | 3 | ✅ Complete | 100% |
| **Total** | **20** | **✅ Complete** | **100%** |

---

## 🔗 Related Documentation

- `QUEUE_ARCHITECTURE_FINAL.md` - Detailed architecture design
- `IMPLEMENTATION_STATUS_SUMMARY.md` - Implementation tracking
- `PHASE1_IMPLEMENTATION_PLAN.md` - Phase 1 implementation details
- `env.runpod` - Environment configuration

---

**Last Updated**: 04-12-2025  
**Status**: Production-Ready ✅  
**Version**: 1.0 (Final Architecture)

