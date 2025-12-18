# 🧪 คู่มือการทดสอบ: ส่ง Media ผ่าน localhost → รอรับ Webhook

## 📋 คำตอบคำถาม

### 1️⃣ "ใช้ GPU 0 เท่านั้น" หมายความว่าอย่างไร?

**✅ ใช้ GPU อยู่!**

- `CUDA_VISIBLE_DEVICES=0` → ใช้ **GPU ตัวที่ 0** (ตัวแรก)
- ถ้ามี GPU หลายตัว (0, 1, 2, ...) จะเห็นแค่ตัวที่ 0
- ถ้ามี GPU เดียว → ใช้ตัวนั้น

**ตัวอย่าง:**
```
มี GPU 2 ตัว:
- GPU 0: RTX 4000 Ada (20GB)
- GPU 1: RTX 4090 (24GB)

CUDA_VISIBLE_DEVICES=0 → ใช้แค่ RTX 4000
CUDA_VISIBLE_DEVICES=1 → ใช้แค่ RTX 4090
CUDA_VISIBLE_DEVICES=0,1 → ใช้ทั้ง 2 ตัว (แต่ต้องใช้ DataParallel)
```

**ปัจจุบัน:**
- มี GPU 1 ตัว: RTX 4000 Ada (20GB)
- `CUDA_VISIBLE_DEVICES=0` → ใช้ GPU ตัวนี้

---

### 2️⃣ RabbitMQ vs Redis Streams

**ปัจจุบัน:**
- ✅ **ใช้ RabbitMQ** อยู่
  - `transcription_queue`
  - `close_caption_queue`
  - `audio_extraction_queue`
- ⚠️ **Redis** ใช้แค่ WebSocket Pub/Sub (ไม่ใช่ queue)

**เปรียบเทียบ:**

| Feature | RabbitMQ | Redis Streams | Direct Mode |
|---------|----------|---------------|-------------|
| **Speed** | ปานกลาง | เร็ว (in-memory) | เร็วที่สุด |
| **Setup** | ต้องมี server แยก | Simple (ถ้ามี Redis) | ไม่ต้อง |
| **Features** | ครบ (DLQ, Priority) | จำกัด | ไม่มี |
| **Resource** | ใช้มาก | ใช้น้อย | ใช้น้อย |

**คำแนะนำ:**
- **ทดสอบ**: Direct Mode (เร็วที่สุด, ไม่ต้อง queue)
- **Production**: Redis Streams (เร็วกว่า RabbitMQ)
- **Scale**: RabbitMQ (features ครบ)

---

### 3️⃣ ทดสอบ: ส่ง Media ผ่าน localhost → รอรับ Webhook

## 🚀 วิธีทดสอบ

### Step 1: Upload File

```bash
# cURL
curl -X POST http://localhost:8001/api/upload/ \
  -F 'file=@video.mp4'
```

**Response:**
```json
{
  "file_id": "uuid",
  "filename": "video.mp4",
  "file_path": "/workspace/transcription-service/uploads/video.mp4",
  "file_size": 12345678,
  "status": "uploaded"
}
```

### Step 2: Start Transcription with Webhook

```bash
# cURL
curl -X POST http://localhost:8001/api/transcribe/ \
  -H 'Content-Type: application/json' \
  -d '{
    "file_path": "/workspace/transcription-service/uploads/video.mp4",
    "language": "th",
    "model_size": "base",
    "callback_url": "https://your-pod-server.com/webhook"
  }'
```

**Response:**
```json
{
  "task_id": "uuid",
  "status": "queued",
  "message": "Transcription started"
}
```

### Step 3: Webhook Callback (Pod Server)

Worker จะส่ง POST ไปยัง `callback_url` เมื่อเสร็จ:

```json
POST https://your-pod-server.com/webhook
{
  "task_id": "uuid",
  "status": "completed",
  "full_text": "ข้อความที่แปลงแล้ว...",
  "segments": [
    {
      "start": 0.0,
      "end": 5.0,
      "text": "ข้อความส่วนแรก"
    }
  ],
  "processing_time": 150.5,
  "language": "th",
  "model_size": "base"
}
```

### Python Example

```python
import requests

# 1. Upload file
with open('video.mp4', 'rb') as f:
    files = {'file': f}
    response = requests.post('http://localhost:8001/api/upload/', files=files)
    upload_data = response.json()
    file_path = upload_data['file_path']

# 2. Start transcription with webhook
data = {
    'file_path': file_path,
    'language': 'th',
    'model_size': 'base',
    'callback_url': 'https://your-pod-server.com/webhook'
}
response = requests.post('http://localhost:8001/api/transcribe/', json=data)
task_data = response.json()
task_id = task_data['task_id']

print(f"Task ID: {task_id}")
print(f"Status: {task_data['status']}")
print(f"Webhook will be sent to: {data['callback_url']}")
```

### Webhook Server (Pod Server)

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post('/webhook')
async def receive_webhook(request: Request):
    """รับ webhook จาก Transcription Service"""
    data = await request.json()
    
    task_id = data.get('task_id')
    status = data.get('status')
    full_text = data.get('full_text')
    segments = data.get('segments', [])
    
    if status == 'completed':
        print(f"✅ Transcription completed: {task_id}")
        print(f"Full text: {full_text[:100]}...")
        print(f"Segments: {len(segments)}")
        # Process result...
    elif status == 'failed':
        print(f"❌ Transcription failed: {task_id}")
        print(f"Error: {data.get('error')}")
    
    return JSONResponse({"status": "received"})
```

---

## 📊 API Endpoints

### Upload
- `POST /api/upload/` - Upload file

### Transcription
- `POST /api/transcribe/` - Start transcription
- `GET /api/tasks/{task_id}` - Get task status
- `GET /api/tasks/` - List all tasks

### Close Caption
- `POST /api/caption/` - Start caption generation
- `GET /api/caption/{task_id}` - Get caption status

### Webhook
- `POST /api/webhook/subscribe` - Subscribe to webhooks
- `GET /api/webhook/subscriptions` - List subscriptions

---

## 🔍 ตรวจสอบสถานะ

### Check Task Status
```bash
curl http://localhost:8001/api/tasks/{task_id}
```

### Check Queue Status
```bash
curl http://localhost:8001/api/queue/info
```

### Check Worker Status
```bash
curl http://localhost:8001/api/queue/stats
```

---

## ⚠️ หมายเหตุ

1. **Direct Mode**: ถ้าต้องการทดสอบเร็วที่สุด (ไม่ใช้ queue) ต้องใช้ Direct API
2. **Webhook**: ต้องมี public URL สำหรับ callback (ใช้ ngrok สำหรับ local testing)
3. **File Path**: ใช้ path ที่ return จาก upload endpoint
4. **Timeout**: Transcription อาจใช้เวลานาน (10 นาที = ~150 วินาที)

---

## 🐛 Troubleshooting

### Webhook ไม่ได้รับ
- ตรวจสอบว่า `callback_url` เป็น public URL
- ตรวจสอบ firewall/network
- ใช้ ngrok สำหรับ local testing

### Task ไม่เริ่ม
- ตรวจสอบว่า Worker ทำงานอยู่
- ตรวจสอบ RabbitMQ connection
- ดู logs: `tail -f /path/to/worker.log`

### GPU ไม่ทำงาน
- ตรวจสอบ: `nvidia-smi`
- ตรวจสอบ: `CUDA_VISIBLE_DEVICES`
- ตรวจสอบ logs สำหรับ CUDA errors

