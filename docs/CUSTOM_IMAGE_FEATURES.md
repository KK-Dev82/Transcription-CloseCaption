# 📋 Custom Image Features - สรุปความสามารถ

## 🎯 คำถาม: Custom Image ที่สร้าง เมื่อ Start Pod แล้ว จะทำแบบนี้ได้เลยหรือไม่?

---

## 1️⃣ ใช้งาน Transcription ผ่าน API ได้เลย (Direct) - มี Standby API (nohup) Start Pod แล้ว Service เปิดให้เลยไหม?

### ✅ **ตอบ: ต้อง Start Services เอง (ยังไม่ Auto-Start)**

**สถานะปัจจุบัน**:
- ❌ **ยังไม่ Auto-Start** - ต้อง run script หลัง start pod
- ✅ **มี Scripts สำหรับ Start Services**:
  - `scripts/start-all-nohup.sh` - Start ทั้ง API และ Worker แบบ nohup
  - `scripts/start-api-nohup.sh` - Start API แบบ nohup
  - `scripts/start-worker-nohup.sh` - Start Worker แบบ nohup

**วิธีใช้งาน**:
```bash
# หลัง start pod
cd /workspace/transcription-service
bash scripts/start-all-nohup.sh
```

**สิ่งที่ต้องทำเพิ่ม (ถ้าต้องการ Auto-Start)**:
- เพิ่ม startup script ใน Dockerfile CMD หรือ ENTRYPOINT
- หรือใช้ systemd service
- หรือใช้ supervisor/PM2

**คำแนะนำ**:
- ✅ **ตอนนี้**: ต้อง start services เองหลัง start pod (ใช้เวลา ~10 วินาที)
- 🔄 **อนาคต**: สามารถเพิ่ม auto-start ใน Dockerfile หรือ startup script

---

## 2️⃣ รองรับทั้งแบบ Full Transcription, Chunk

### ✅ **ตอบ: รองรับทั้งสองแบบ**

**Full Transcription**:
```json
{
  "file_path": "uploads/video.mp4",
  "language": "th",
  "model_size": "base",
  "use_chunking": false
}
```

**Chunk-based Transcription**:
```json
{
  "file_path": "uploads/video.mp4",
  "language": "th",
  "model_size": "base",
  "use_chunking": true,
  "chunk_duration": 30
}
```

**สถานะ**:
- ✅ **Full Transcription**: ทำงานได้เต็มที่
- ⚠️ **Chunk Transcription**: มี code แต่ยังไม่ fully implemented (มี TODO comment)
- ✅ **Caption Service**: รองรับ chunk-based processing (ใช้ chunk_duration=3s)

**API Endpoint**:
- `POST /api/transcribe/` - รองรับ `use_chunking` parameter

---

## 3️⃣ มีรูปแบบ Webhook

### ✅ **ตอบ: รองรับ Webhook**

**Webhook Callback**:
```json
{
  "file_path": "uploads/video.mp4",
  "language": "th",
  "model_size": "base",
  "callback_url": "https://your-server.com/webhook"
}
```

**Webhook Payload**:
```json
{
  "task_id": "uuid-here",
  "status": "completed",
  "full_text": "...",
  "chunks": [...],
  "chunks_count": 10,
  "processing_time": 150.5
}
```

**Features**:
- ✅ **Callback URL**: ส่ง POST request เมื่อ transcription เสร็จ
- ✅ **Webhook Service**: มี `WebhookService` สำหรับจัดการ webhooks
- ✅ **Webhook Endpoints**: `/api/webhook/subscribe`, `/api/webhook/subscriptions`
- ✅ **Events**: `transcription.started`, `transcription.progress`, `transcription.completed`, `transcription.failed`

**API Endpoint**:
- `POST /api/transcribe/` - รองรับ `callback_url` parameter

---

## 4️⃣ รองรับทั้ง mp4, wav

### ✅ **ตอบ: รองรับทั้ง mp4 และ wav**

**Video Formats** (รองรับ):
- ✅ `.mp4`, `.avi`, `.mov`, `.mkv`, `.flv`, `.wmv`, `.webm`, `.m4v`, `.3gp`

**Audio Formats** (รองรับ):
- ✅ `.wav`, `.mp3`, `.m4a`, `.aac`, `.ogg`, `.flac`, `.wma`, `.opus`

**การทำงาน**:
- ✅ **Video Files**: แยกเสียงอัตโนมัติด้วย FFmpeg → WAV format
- ✅ **Audio Files**: ใช้โดยตรง
- ✅ **File Detection**: ตรวจสอบ file type อัตโนมัติ

**API Endpoint**:
- `POST /api/upload/` - รองรับทั้ง video และ audio files
- `POST /api/transcribe/` - รองรับทั้ง `file_path` และ `file_url`

---

## 5️⃣ ถ้ามีการติดต่อกับการใช้งาน close Caption ที่ต้องการส่ง wav file มาให้ Transcription อย่างต่อเนื่อง เช่น ทุก 5 วินาที สามารถรองรับได้หรือไม่?

### ⚠️ **ตอบ: รองรับบางส่วน แต่ต้องปรับปรุง**

**สถานะปัจจุบัน**:

#### ✅ **มี Features ที่เกี่ยวข้อง**:
1. **LiveStreamingService**:
   - รองรับ real-time audio chunks
   - Buffer duration: 10 วินาที (configurable)
   - Process audio chunks แบบ real-time

2. **RealtimeCaptionService**:
   - รองรับ chunk-based processing
   - Chunk duration: 3 วินาที (สำหรับ close caption)
   - Real-time caption generation

3. **Chunk-based Transcription**:
   - รองรับ `chunk_duration` parameter
   - สามารถตั้งค่า chunk duration ได้ (เช่น 5 วินาที)

#### ⚠️ **ข้อจำกัด**:
- ❌ **ยังไม่มี API endpoint สำหรับ continuous upload** - ต้องส่ง request ใหม่ทุกครั้ง
- ❌ **ยังไม่มี session management** สำหรับ continuous transcription
- ⚠️ **Chunking ยังไม่ fully implemented** - มี TODO comment

**วิธีใช้งานปัจจุบัน** (Workaround):
```bash
# ส่ง wav file ทุก 5 วินาที (ต้องส่ง request ใหม่ทุกครั้ง)
curl -X POST "http://localhost:8010/api/transcribe/" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "uploads/chunk_1.wav",
    "language": "th",
    "model_size": "base",
    "use_chunking": false,
    "callback_url": "https://your-server.com/webhook"
  }'
```

**สิ่งที่ต้องทำเพิ่ม** (ถ้าต้องการรองรับ continuous transcription):
- ✅ สร้าง API endpoint สำหรับ continuous/streaming transcription
- ✅ เพิ่ม session management
- ✅ รองรับ WebSocket สำหรับ real-time updates
- ✅ Implement chunking logic ให้สมบูรณ์

---

## 6️⃣ ตอนนี้รองรับการใช้งานแบบ 1:1 ใช่ไหม?

### ✅ **ตอบ: รองรับ Concurrent Requests (ไม่ใช่ 1:1 แบบ strict)**

**สถานะปัจจุบัน**:
- ✅ **Concurrent Processing**: รองรับหลาย requests พร้อมกัน
- ✅ **Single GPU**: ใช้ GPU 0 เท่านั้น (`CUDA_VISIBLE_DEVICES=0`)
- ✅ **Async Processing**: ใช้ `asyncio.create_task()` สำหรับ non-blocking
- ✅ **Task Queue**: แต่ละ request สร้าง task แยกกัน

**Configuration**:
```bash
# .env.runpod
CUDA_VISIBLE_DEVICES=0  # Single GPU only
WHISPER_DEVICE=cuda     # ใช้ GPU (device 0)
API_WORKERS=1           # API workers
```

**API Behavior**:
- ✅ **Async Processing**: ใช้ `asyncio.create_task()` สำหรับ non-blocking
- ✅ **Task Queue**: แต่ละ request สร้าง task แยกกัน
- ✅ **Sequential GPU Processing**: แต่ละ task ใช้ GPU 0 ตามลำดับ

**หมายเหตุ**:
- ⚠️ **ไม่ใช่ 1:1 แบบ strict** - รองรับ concurrent requests
- ✅ **Single GPU Only** - ไม่มี multi-GPU support
- ❌ **Multi-GPU** - ไม่มี code สำหรับ multi-GPU (ไม่มี GPU manager, Round Robin)

---

## 📊 สรุปตาราง

| Feature | รองรับ? | สถานะ | หมายเหตุ |
|---------|---------|-------|----------|
| **Standby API (Auto-Start)** | ⚠️ | ต้อง Start เอง | มี scripts แต่ต้อง run manual |
| **Full Transcription** | ✅ | ทำงานได้ | ใช้ `use_chunking=false` |
| **Chunk Transcription** | ⚠️ | ยังไม่สมบูรณ์ | มี code แต่มี TODO |
| **Webhook** | ✅ | ทำงานได้ | รองรับ `callback_url` |
| **mp4 Support** | ✅ | ทำงานได้ | แยกเสียงอัตโนมัติ |
| **wav Support** | ✅ | ทำงานได้ | ใช้โดยตรง |
| **Continuous (5s)** | ⚠️ | ต้องปรับปรุง | ต้องส่ง request ใหม่ทุกครั้ง |
| **1:1 Usage** | ⚠️ | Concurrent | ตั้ง `MAX_WORKERS=1` สำหรับ 1:1 |

---

## 🚀 สิ่งที่ต้องทำเพิ่ม (ถ้าต้องการ)

### 1. Auto-Start Services
```dockerfile
# เพิ่มใน Dockerfile.base-new
CMD ["/bin/bash", "-c", "cd /workspace/transcription-service && bash scripts/start-all-nohup.sh && tail -f /dev/null"]
```

### 2. Continuous Transcription API
- สร้าง endpoint `/api/transcribe/continuous` สำหรับ streaming
- เพิ่ม session management
- รองรับ WebSocket

### 3. Complete Chunking Implementation
- Implement `_process_with_chunking()` ให้สมบูรณ์
- เพิ่ม chunk merging logic

---

**Last Updated**: 2025-01-XX  
**Custom Image**: `pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`

