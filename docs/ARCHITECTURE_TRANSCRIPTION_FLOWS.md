# สถาปัตยกรรม Transcription Service - 2 Flow Patterns

## 📋 Overview

Transcription Service รองรับ 2 Flow Patterns:

1. **Direct Video Flow** - ส่งวีดิโอตรงๆให้ Transcription Service
2. **Full Flow with Backend** - Backend จัดการผ่าน Media Processor

---

## 1. Direct Video Flow (Standalone)

### Flow Diagram (Current)
```
Client → Transcription API → RabbitMQ (transcription_queue)
                              ↓
                         Video Worker
                              ↓
                    [Audio Extraction]
                              ↓
                    [Chunking (30s default)]
                              ↓
                    [Sequential Processing] ❌ (ช้า)
```

### Flow Diagram (Recommended)
```
Client → Transcription API → [Audio Extraction]
                              ↓
                         [Chunking (30-60s)]
                              ↓
                    RabbitMQ (transcription_chunk_queue)
                              ↓
                    [Parallel Workers] ✅
                              ↓
                    [Merge Results]
```

### 1.1 Audio Extraction

**Location**: `app/services/transcription_service.py` → `_process_transcription()`

**Current Implementation**:
- ตรวจสอบประเภทไฟล์ (audio/video)
- ถ้าเป็น video: ใช้ `video_service.extract_audio_chunks()` 
- ถ้าเป็น audio: ใช้ `file_service.create_chunks()`

**Code**:
```python
if self.file_service.is_audio_file(local_file_path):
    chunks = self.file_service.create_chunks(local_file_path, chunk_duration)
elif self.file_service.is_video_file(local_file_path):
    chunks = self.video_service.extract_audio_chunks(local_file_path, chunk_duration)
```

**✅ ต้องมี**: Direct Video Flow ต้อง extract audio เอง (ไม่มี Media Processor)

### 1.2 Chunking Strategy

**Current**: 30 วินาที (default)

**คำถาม**: จำเป็นไหม หรือให้ Media Processor จัดการ?

**คำตอบ**:
- ✅ **สำหรับ Direct Flow**: Transcription Service ต้องจัดการเอง
  - ไม่มี Media Processor
  - ต้อง extract audio และ chunk เอง
  - **แนะนำ**: 30-60s chunks (ไม่ใช่ 3s)
  
- ⚠️ **สำหรับ Close Caption (3s chunks)**:
  - **แนะนำ**: ให้ Media Processor จัดการ
  - Close Caption ต้องการ chunks เล็ก (3-5s) สำหรับ real-time
  - Media Processor มี FFmpeg service แยกต่างหาก
  - ลดภาระของ Transcription Service

**Recommendation**:
```python
# Direct Flow: ใช้ chunk_duration จาก request (default: 30-60s)
chunk_duration = request.chunk_duration or 30  # ไม่ใช่ 3s

# Close Caption: ใช้ Media Processor (3-5s chunks)
# ไม่ต้อง chunk ใน Transcription Service
```

### 1.3 Parallel Processing (สำคัญ!)

**Current Implementation**: Sequential (ไม่ใช่ parallel) ❌

**Location**: `app/services/transcription_service.py` → `_process_transcription()`

**Code**:
```python
for i, chunk_path in enumerate(chunks):
    result = self.whisper_service.transcribe_file(...)  # Sequential
```

**ปัญหา**:
- GPU utilization ต่ำ (24%)
- ช้ากว่า real-time (1.7x real-time)
- ไม่มี parallel processing

**Solution: RabbitMQ Queue-based Parallel** ✅

**Implementation**:
```python
# 1. Extract audio และสร้าง chunks
chunks = self.video_service.extract_audio_chunks(local_file_path, chunk_duration)

# 2. ส่งแต่ละ chunk ไปยัง queue (ไม่ process ตรงๆ)
for i, chunk_path in enumerate(chunks):
    chunk_task = {
        "task_id": f"{task_id}_chunk_{i}",
        "parent_task_id": task_id,
        "chunk_path": chunk_path,
        "chunk_index": i,
        "total_chunks": len(chunks),
        "chunk_duration": chunk_duration,
        "model_size": model_size,
        "language": language,
        "file_path": local_file_path,
        "file_name": file_name,
        "created_at": datetime.now().isoformat()
    }
    # ส่งไปยัง transcription_chunk_queue
    self.rabbitmq_service.send_chunk_transcription_task(chunk_task)
```

**Queue Structure**:
- `transcription_queue` - Full video tasks (optional, สำหรับ backward compatibility)
- `transcription_chunk_queue` - Individual chunks (ใหม่, สำหรับ parallel processing)

**Worker Configuration**:
```python
# app/workers/video_worker.py
self.channel.basic_qos(prefetch_count=5)  # รับงานได้ 5 งานพร้อมกัน
```

**Multiple Workers**:
- Worker 1: prefetch_count=5 → 5 chunks in parallel
- Worker 2: prefetch_count=5 → 5 chunks in parallel
- **Total**: 10 chunks processed in parallel

**Benefits**:
- ✅ GPU utilization สูงขึ้น (80-100%)
- ✅ เร็วกว่า real-time (0.5-1.0x)
- ✅ Auto-balancing (RabbitMQ จัดการเอง)
- ✅ Scalable (เพิ่ม workers ได้)

### 1.4 RabbitMQ Management

**Current**: Transcription Service ส่งไปยัง `transcription_queue` แล้ว Video Worker process ตรงๆ (sequential)

**Recommended**: 
- สร้าง `transcription_chunk_queue` สำหรับ chunks
- ส่ง chunks ไปยัง queue แทนที่จะ process ตรงๆ
- Workers process chunks แบบ parallel

**Implementation**:
```python
# app/services/rabbitmq_service.py
def send_chunk_transcription_task(self, chunk_task: Dict) -> str:
    """ส่ง chunk transcription task ไปยัง queue"""
    self._ensure_connection()
    self.channel.queue_declare(queue='transcription_chunk_queue', durable=True)
    self.channel.basic_publish(
        exchange='',
        routing_key='transcription_chunk_queue',
        body=json.dumps(chunk_task),
        properties=pika.BasicProperties(delivery_mode=2)
    )
```

**Worker Handler**:
```python
# app/workers/video_worker.py
def _process_chunk_transcription_task(self, ch, method, properties, body):
    """ประมวลผล chunk transcription task"""
    chunk_task = json.loads(body.decode('utf-8'))
    parent_task_id = chunk_task['parent_task_id']
    chunk_path = chunk_task['chunk_path']
    chunk_index = chunk_task['chunk_index']
    
    # Transcribe chunk
    result = self.transcription_service.whisper_service.transcribe_file(
        chunk_path, 
        chunk_task['model_size'],
        chunk_task['language']
    )
    
    # Save chunk result
    self._save_chunk_result(parent_task_id, chunk_index, result)
    
    # Check if all chunks done → merge results
    if self._all_chunks_completed(parent_task_id):
        self._merge_and_finalize(parent_task_id)
    
    ch.basic_ack(delivery_tag=method.delivery_tag)
```

---

## 2. Full Flow with Backend

### Flow Diagram
```
Client → Backend → RabbitMQ → Media Processor
                            ↓
                    [Audio Extraction]
                            ↓
                    [Chunking (3-5s)]
                            ↓
                    [Publish: media.audio.chunk.extracted]
                            ↓
                    Backend → RabbitMQ → Transcription Service
                                            ↓
                                    [Parallel Workers]
                                            ↓
                                    [Publish: transcription.chunk.completed]
                                            ↓
                                    Backend (SignalR)
```

### 2.1 Backend → Media Processor Flow

**Backend Code** (`TranscriptionController.cs`):
```csharp
// Publish audio extraction request
var extractReq = new AudioExtractRequest(...);
await _publisher.PublishJsonAsync(
    QueueNames.MediaExchange, 
    QueueNames.MediaAudioExtractRequest, 
    extractReq
);
```

**Media Processor** (`ChunkedAudioExtractor.cs`):
```csharp
// Extract audio และแบ่ง chunks (3-5s)
// Publish แต่ละ chunk
var message = new AudioChunkExtractedMessage(...);
await messagePublisher.PublishJsonAsync(
    "media.exchange",
    "media.audio.chunk.extracted",
    message
);
```

**Queue**: `media.audio.chunk.extracted`

### 2.2 Transcription Service Processing

**Current Implementation**: `app/workers/video_worker.py` → `_process_audio_chunk_extracted()`

**Flow**:
1. Receive message จาก `media.audio.chunk.extracted`
2. Download audio file จาก URL
3. Transcribe chunk
4. Publish result → `transcription.chunk.completed`

**Code**:
```python
def _process_audio_chunk_extracted(self, ch, method, properties, body):
    message_data = json.loads(body.decode('utf-8'))
    asyncio.run(self._execute_audio_chunk_transcription(message_data))
    ch.basic_ack(delivery_tag=method.delivery_tag)
```

### 2.3 Worker Parallel Management

**คำถาม**: Backend อาจไม่รู้ว่า Transcription Queue ว่างหรือ Overload

**Current Solution**: RabbitMQ Prefetch + Multiple Workers

**Configuration**:
```python
# app/workers/video_worker.py
self.channel.basic_qos(prefetch_count=3)  # รับงานได้ 3 งานพร้อมกัน
```

**How It Works**:
1. **RabbitMQ Prefetch**: Worker จะรับงานได้ 3 งานพร้อมกัน
2. **Multiple Workers**: ถ้ามี 2 workers → 6 chunks processed in parallel
3. **Auto-balancing**: RabbitMQ จะ distribute messages ไปยัง workers ที่ว่าง
4. **Backend ไม่ต้องรู้**: RabbitMQ จัดการเอง

**Example**:
```
Queue: media.audio.chunk.extracted (20 messages)

Worker 1: [chunk1, chunk2, chunk3] (processing)
Worker 2: [chunk4, chunk5, chunk6] (processing)
Queue: [chunk7, chunk8, ..., chunk20] (waiting)

เมื่อ Worker 1 เสร็จ chunk1 → รับ chunk7 ทันที
```

**Monitoring**:
```bash
# ตรวจสอบ queue status
bash scripts/pod/check-pod.sh

# ดู queue depth
curl http://localhost:15672/api/queues/%2F/media.audio.chunk.extracted
```

---

## 🎯 Recommendations

### สำหรับ Direct Video Flow:

1. **Audio Extraction**: Transcription Service จัดการเอง ✅
2. **Chunking**: 
   - Full transcription: 30-60s chunks (default)
   - Close Caption: ให้ Media Processor จัดการ (3-5s chunks)
3. **Parallel Processing**: 
   - ใช้ RabbitMQ Queue-based parallel (แนะนำ)
   - สร้าง `transcription_chunk_queue` แยก
4. **RabbitMQ Management**: Transcription Service จัดการเอง ✅

### สำหรับ Full Flow with Backend:

1. **Audio Extraction**: Media Processor จัดการ ✅
2. **Chunking**: Media Processor จัดการ (3-5s) ✅
3. **Parallel Processing**: 
   - ใช้ RabbitMQ Prefetch + Multiple Workers ✅
   - Backend ไม่ต้องรู้ queue status
   - RabbitMQ จัดการ auto-balancing
4. **Queue Management**: RabbitMQ จัดการเอง ✅

---

## 📊 Performance Optimization

### Current Issues:
- GPU utilization ต่ำ (24%)
- Sequential processing
- Chunking overhead

### Solutions:

1. **เพิ่ม prefetch_count**:
   ```python
   # ปัจจุบัน: prefetch_count=3
   # แนะนำ: prefetch_count=5-10 (ขึ้นกับ GPU memory)
   self.channel.basic_qos(prefetch_count=5)
   ```

2. **Multiple Workers**:
   ```bash
   # Run multiple workers
   python3 -m app.workers.video_worker &  # Worker 1
   python3 -m app.workers.video_worker &  # Worker 2
   python3 -m app.workers.video_worker &  # Worker 3
   ```

3. **Batch Processing** (สำหรับ Direct Flow):
   ```python
   # ส่ง chunks ไปยัง queue แทนที่จะ process ตรงๆ
   for chunk in chunks:
       rabbitmq_service.send_chunk_task(chunk)
   ```

---

## 🔧 Implementation Plan

### Phase 1: Direct Video Flow Optimization
- [ ] สร้าง `transcription_chunk_queue`
- [ ] แก้ไข `_process_transcription()` ให้ส่ง chunks ไปยัง queue
- [ ] เพิ่ม chunk processing handler ใน Video Worker
- [ ] เพิ่ม prefetch_count configuration

### Phase 2: Full Flow Monitoring
- [ ] เพิ่ม queue monitoring API
- [ ] เพิ่ม worker status API
- [ ] เพิ่ม metrics (queue depth, processing time)

### Phase 3: Auto-scaling (Optional)
- [ ] Worker auto-scaling based on queue depth
- [ ] Dynamic prefetch_count adjustment

---

## 📝 Summary

### Direct Video Flow:
- Transcription Service จัดการ audio extraction, chunking, และ queue management
- ใช้ RabbitMQ Queue-based parallel processing
- ไม่ต้องพึ่ง Media Processor

### Full Flow with Backend:
- Media Processor จัดการ audio extraction และ chunking
- Transcription Service รับ chunks จาก queue
- RabbitMQ จัดการ parallel processing อัตโนมัติ
- Backend ไม่ต้องรู้ queue status (RabbitMQ จัดการเอง)

**Key Point**: RabbitMQ Prefetch + Multiple Workers = Auto-balancing Parallel Processing

