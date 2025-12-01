# Queue Flow และ Parallel Processing Architecture

## คำถามที่พบบ่อย

### 1. Consumer คืออะไร?
**Consumer** = **Worker** (Video Worker) ที่รับ messages จาก RabbitMQ queue

- **Consumer** = โปรแกรมที่รับ messages จาก queue
- **Worker** = Video Worker process ที่ทำงาน transcription
- **ในระบบนี้**: Consumer = Video Worker (ตัวเดียวกัน)

### 2. Flow การทำงาน

#### Direct Video Flow (Standalone)

```
Client → Transcription API → Transcription Service
                              ↓
                              [1] Audio Extraction (FFmpeg)
                              ↓
                              [2] Chunking (30s chunks)
                              ↓
                              [3] ส่ง chunks ไปยัง transcription_chunk_queue
                              ↓
                              RabbitMQ Queue (transcription_chunk_queue)
                              ↓
                              [4] Video Worker (3 workers parallel)
                              ↓
                              [5] Transcription (Whisper)
                              ↓
                              [6] Merge Results
                              ↓
                              [7] Save & Callback
```

#### คำถาม: Chunks ไหนแบ่งก่อน เริ่ม transcription ก่อน (ดีไหม) หรือรอแบ่งเสร็จก่อนทีเดียวดี?

**คำตอบ: รอแบ่งเสร็จก่อนทีเดียวดีกว่า (Current Implementation)**

**เหตุผล:**
1. **Sequential Chunking**: FFmpeg extract audio chunks เป็น sequential (ต้องรอ chunk ก่อนหน้าเสร็จ)
2. **Parallel Transcription**: ส่ง chunks ทั้งหมดไปยัง queue พร้อมกัน → Workers ประมวลผล parallel
3. **Better Resource Management**: รู้จำนวน chunks ทั้งหมดก่อน → ตั้งค่า progress tracking ได้ถูกต้อง

**Flow ปัจจุบัน:**
```
[1] Extract Audio → [2] Create All Chunks (Sequential) → [3] Send All Chunks to Queue → [4] Workers Process Parallel
```

**ถ้าเปลี่ยนเป็น "Chunk ไหนแบ่งก่อน เริ่ม transcription ก่อน":**
```
[1] Extract Audio → [2] Create Chunk 1 → [3] Send Chunk 1 → [4] Worker Transcribe Chunk 1
                    ↓
                    [2] Create Chunk 2 → [3] Send Chunk 2 → [4] Worker Transcribe Chunk 2
                    ↓
                    ...
```

**ข้อเสีย:**
- Workers อาจ idle รอ chunks ใหม่
- Progress tracking ซับซ้อนขึ้น
- ไม่ได้ประโยชน์จาก parallel processing มากเท่า

### 3. Queue Management

#### Queues ที่ใช้

1. **`transcription_queue`**
   - **Purpose**: รับ full video transcription tasks
   - **Consumer**: Video Worker (1 consumer)
   - **Flow**: Client → API → Queue → Worker → Extract Audio → Chunking → Send to `transcription_chunk_queue`

2. **`transcription_chunk_queue`**
   - **Purpose**: รับ individual chunk transcription tasks (สำหรับ parallel processing)
   - **Consumer**: Video Worker (1 consumer, แต่มี 3 workers ใน ThreadPoolExecutor)
   - **Prefetch Count**: 3 (รับ messages ได้ 3 ตัวพร้อมกัน)
   - **Flow**: Transcription Service → Queue → Workers (Parallel)

#### Consumer vs Workers

- **Consumer (RabbitMQ)**: 1 consumer สำหรับ `transcription_chunk_queue`
- **Workers (ThreadPoolExecutor)**: 3 workers ที่ประมวลผล chunks พร้อมกัน

**ทำไมถึงเป็นแบบนี้?**
- RabbitMQ Consumer รับ messages จาก queue (1 consumer)
- แต่ละ message ถูกส่งไปยัง ThreadPoolExecutor (3 workers)
- Workers ประมวลผล parallel แต่ใช้ model ร่วมกัน (ต้อง lock)

### 4. Parallel Processing Strategy

#### Current Implementation

```
transcription_chunk_queue
├── Message 1 (Chunk 0) → Worker 1 (Thread 1) → [Lock] → Model → Transcribe
├── Message 2 (Chunk 1) → Worker 2 (Thread 2) → [Wait Lock] → Model → Transcribe
├── Message 3 (Chunk 2) → Worker 3 (Thread 3) → [Wait Lock] → Model → Transcribe
└── Message 4 (Chunk 3) → Worker 1 (Thread 1) → [Wait Lock] → Model → Transcribe
```

**ข้อดี:**
- GPU memory ไม่เต็ม (ใช้ model เดียวกัน)
- ไม่เกิด CUDA OOM
- Thread-safe

**ข้อเสีย:**
- Transcription เป็น sequential (เพราะ lock)
- แต่ยังได้ประโยชน์จาก parallel processing ในส่วนอื่น (audio extraction, chunking)

#### Alternative: Multiple Model Instances (ไม่แนะนำ)

```
transcription_chunk_queue
├── Message 1 (Chunk 0) → Worker 1 → Model Instance 1 → Transcribe (Parallel)
├── Message 2 (Chunk 1) → Worker 2 → Model Instance 2 → Transcribe (Parallel)
└── Message 3 (Chunk 2) → Worker 3 → Model Instance 3 → Transcribe (Parallel)
```

**ข้อเสีย:**
- GPU memory เต็ม (3x model memory)
- เกิด CUDA OOM
- ไม่เหมาะกับ RTX 4080 Super 16GB

### 5. File Path Resolution

**ปัญหา**: `../../uploads/v10-1.mp4` (relative path) ไม่ถูกต้อง

**แก้ไข**: ใช้ `Path.resolve()` เพื่อแปลงเป็น absolute path

```python
if local_file_path:
    local_file_path = str(Path(local_file_path).resolve())
```

### 6. Queue Status Monitoring

**ตรวจสอบ Queue Status:**
```bash
bash scripts/pod/check-rabbitmq-queue.sh transcription_chunk_queue
```

**ผลลัพธ์ที่คาดหวัง:**
- Messages: 0-23 (ขึ้นอยู่กับจำนวน chunks)
- Consumers: 1 (Video Worker)
- Status: ✅ Parallel (ถ้ามี messages หลายตัว)

### 7. Best Practices

1. **Audio Extraction**: Sequential (FFmpeg limitation)
2. **Chunking**: Sequential (ต้องรอ audio extraction เสร็จ)
3. **Sending to Queue**: Parallel (ส่ง chunks ทั้งหมดพร้อมกัน)
4. **Transcription**: Sequential (เพราะ model lock) แต่ workers ยังทำงาน parallel ในส่วนอื่น

## สรุป

- **Consumer** = **Worker** (Video Worker)
- **รอแบ่ง chunks เสร็จก่อน** → ส่งทั้งหมดไปยัง queue → Workers ประมวลผล parallel (แต่ transcription เป็น sequential เพราะ lock)
- **File path**: ใช้ absolute path เสมอ
- **Queue management**: ใช้ prefetch_count=3 เพื่อให้ workers รับ messages ได้ 3 ตัวพร้อมกัน

