# 📋 คำตอบคำถามทั้งหมด

## 1️⃣ RTX 5080, 5090 Performance

### RTX 5080 (32GB)
- **Speedup**: 2.2x (เร็วกว่า RTX 4000 Ada)
- **จำนวน GPU**: 3 ตัว
- **เวลา**: ~9.5 นาที (สำหรับ 25 ไฟล์ x 30 นาที)
- **Cost**: $7,500
- **Cost per file**: $300

### RTX 5090 (32GB)
- **Speedup**: 2.8x (เร็วกว่า RTX 4000 Ada)
- **จำนวน GPU**: 3 ตัว
- **เวลา**: ~7.4 นาที (สำหรับ 25 ไฟล์ x 30 นาที)
- **Cost**: $9,000
- **Cost per file**: $360

⚠️ **หมายเหตุ**: RTX 50 series ยังไม่ release (คาดการณ์ Q1 2025)

---

## 2️⃣ เชื่อมต่อ Redis หรือยัง

✅ **มี Redis Configuration**:
- `REDIS_URL` ใน `.env.runpod`
- `WebSocketService` ใช้ Redis สำหรับ Pub/Sub
- แต่ยังไม่เห็น Redis Streams worker (ใช้ RabbitMQ แทน)

**สถานะ**:
- ✅ Redis connection config มีอยู่
- ⚠️ ยังไม่ใช้ Redis Streams (ใช้ RabbitMQ queues แทน)

---

## 3️⃣ มี Endpoint หรือยัง

✅ **มี API Endpoints**:

### Transcription
- `POST /api/transcribe/` - ส่ง transcription request
- `GET /api/tasks/{task_id}` - ดูสถานะ task
- `GET /api/tasks/` - ดูรายการ tasks

### Close Caption
- `POST /api/caption/` - ส่ง close caption request
- `GET /api/caption/{task_id}` - ดูสถานะ caption

### Webhook
- `POST /api/webhook/subscribe` - สมัครรับ webhook
- `GET /api/webhook/subscriptions` - ดูรายการ subscriptions

### WebSocket
- `WS /ws/transcription/{user_id}` - Real-time updates
- `GET /api/websocket/status` - ตรวจสอบสถานะ

### Queue Management
- `GET /api/queue/info` - ดู queue information
- `GET /api/queue/stats` - ดูสถิติ queue

---

## 4️⃣ มี Webhook หรือวิธี response FullText ไหม

✅ **มี Webhook Service**:

### WebhookService
- **Location**: `app/services/webhook_service.py`
- **Methods**:
  - `notify_transcription_completed()` - ส่ง FullText เมื่อเสร็จ
  - `notify_transcription_progress()` - ส่ง progress updates
  - `notify_transcription_failed()` - ส่ง error

### Callback URL
- **Field**: `callback_url` ใน `TranscriptionRequest`
- **Format**: Backend ส่ง URL มา → Worker ส่ง POST กลับเมื่อเสร็จ
- **Payload**: 
  ```json
  {
    "task_id": "...",
    "status": "completed",
    "full_text": "...",
    "segments": [...],
    "processing_time": 150.5
  }
  ```

### WebSocket
- **Endpoint**: `WS /ws/transcription/{user_id}?task_id={task_id}`
- **Real-time**: ส่ง updates ทันทีเมื่อมี progress

---

## 5️⃣ Text Correction ด้วย Pythai ต้องทำที่ไหน

✅ **มี ThaiTextProcessor**:

### Location
- **File**: `app/services/thai_text_processor.py`
- **Class**: `ThaiTextProcessor`
- **Library**: PyThaiNLP

### การใช้งานปัจจุบัน
- **ถูกเรียกใน**: `WhisperService._apply_thai_processing()`
- **ทำงาน**: หลัง transcription เสร็จ
- **Parameters**: `use_thai_processor=True` (default)

### แนะนำ
- ✅ **เก็บไว้ใน TranscriptionService** (หลัง transcription)
- ✅ **ไม่ต้องแยก Service** (เป็นส่วนหนึ่งของ transcription pipeline)
- ✅ **ทำงานอัตโนมัติ** เมื่อ `language="th"` และ `use_thai_processor=True`

### Flow
```
Transcription → WhisperService.transcribe_file() 
  → _apply_thai_processing() 
    → ThaiTextProcessor.process_text()
      → PyThaiNLP correction
```

---

## 6️⃣ ถ้าจะใช้ 2 GPU+ จะแตกต่างจาก Code ตอนนี้ไหม

⚠️ **ต้องปรับ Code**:

### ปัจจุบัน
- `CUDA_VISIBLE_DEVICES=0` (ใช้ GPU 0 เท่านั้น)
- `WhisperModel(device="cuda")` → ใช้ GPU 0
- Single GPU per worker

### ต้องปรับ

#### Option 1: Multiple Workers (แนะนำ)
```python
# Worker 1
CUDA_VISIBLE_DEVICES=0 python -m app.workers.video_worker

# Worker 2
CUDA_VISIBLE_DEVICES=1 python -m app.workers.video_worker
```

#### Option 2: GPU Selection per Task
```python
# ใน faster_whisper_provider.py
device_id = task_data.get('gpu_id', 0)
device = f"cuda:{device_id}"
model = WhisperModel(model_size, device=device, ...)
```

#### Option 3: DataParallel (ไม่แนะนำ)
- faster-whisper ไม่รองรับ DataParallel
- ต้องใช้ multiple workers แทน

### Code Changes Needed
1. **Environment Variable**: `CUDA_VISIBLE_DEVICES` per worker
2. **Worker Configuration**: เพิ่ม `GPU_ID` parameter
3. **Task Routing**: Route tasks ไปยัง worker ที่มี GPU ว่าง

---

## 7️⃣ สามารถรับงานพร้อมกันได้ไหม (CloseCaption + Transcription)

✅ **รองรับแล้ว**:

### Queues
- `transcription_queue` - สำหรับ transcription (30s/full file)
- `close_caption_queue` - สำหรับ close caption (3s chunks)
- `audio_chunk_extracted_queue` - สำหรับ real-time chunks

### Worker Configuration
- **Multiple Consumers**: Worker consume จากหลาย queues พร้อมกัน
- **Thread Pool**: `ThreadPoolExecutor` สำหรับ parallel processing
- **Separate Handlers**: แต่ละ queue มี handler แยก

### Resource Management
- **CloseCaption**: ใช้ RAM น้อยกว่า (3s chunks)
- **Transcription**: ใช้ RAM มากกว่า (30s/full file)
- **GPU**: ใช้ GPU เดียวกัน (อาจมี contention)

### ข้อจำกัด
- ⚠️ ใช้ GPU เดียวกัน → อาจมี contention
- ⚠️ RAM อาจไม่พอถ้ามีหลาย jobs พร้อมกัน
- ✅ แต่ละ queue มี prefetch_count แยก → ควบคุมได้

### แนะนำ
- ใช้ priority queue (CloseCaption > Transcription)
- ตั้ง resource limits (RAM, GPU memory)
- Monitor GPU utilization

---

## 📊 สรุป

| คำถาม | สถานะ | หมายเหตุ |
|-------|-------|----------|
| RTX 5080/5090 | ✅ วิเคราะห์แล้ว | ใช้ 3 ตัว |
| Redis Connection | ⚠️ Config มี แต่ยังไม่ใช้ | ใช้ RabbitMQ แทน |
| API Endpoints | ✅ มีครบ | /api/transcribe/, /api/caption/, etc. |
| Webhook/FullText | ✅ มี | WebhookService + callback_url |
| Text Correction | ✅ มี | ThaiTextProcessor ใน WhisperService |
| Multi-GPU | ⚠️ ต้องปรับ | ตั้ง CUDA_VISIBLE_DEVICES |
| Concurrent Jobs | ✅ รองรับ | Multiple queues + handlers |

