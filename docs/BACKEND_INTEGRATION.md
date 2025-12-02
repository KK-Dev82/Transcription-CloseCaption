# 🔗 Backend Integration Guide

คู่มือสำหรับการเชื่อมต่อ Transcription Service กับ Backend Local เพื่อทดสอบ Flow การ Transcription

---

## 📋 Flow การทำงาน

```
1. Frontend → Backend: Upload file + Start transcription
2. Backend → Transcription Service: POST /transcribe/
   - ระบุ file_url, callback_url, job_id, user_id
3. Transcription Service: Process transcription
4. Transcription Service → Backend: POST callback_url (webhook)
5. Backend: บันทึกผลลัพธ์ลง Database
6. Backend → Frontend: WebSocket/SignalR notification
```

---

## 🔄 API Flow รายละเอียด

### Step 1: Backend เรียก Transcription Service

**Endpoint**: `POST {TranscriptionService}/transcribe/`

**Request Body**:
```json
{
  "job_id": 123,
  "user_id": "1",
  "file_url": "http://file-service/api/files/{fileId}",
  "file_path": "",
  "file_name": "video.mp4",
  "language": "th",
  "model_size": "medium",
  "chunk_duration": 30,
  "callback_url": "http://backend/api/transcription/webhook/completed"
}
```

**Response**:
```json
{
  "task_id": "uuid-here",
  "status": "pending",
  "file_name": "video.mp4",
  "job_id": 123,
  "user_id": "1",
  "created_at": "2025-12-02T00:00:00"
}
```

### Step 2: Transcription Service ประมวลผล

- ดาวน์โหลดไฟล์จาก `file_url`
- แปลงเป็นข้อความด้วย Whisper Model
- บันทึกผลลัพธ์

### Step 3: Callback กลับไป Backend

**Endpoint**: `POST {callback_url}` (จาก request)

**Request Body**:
```json
{
  "jobId": 123,
  "taskId": "uuid-here",
  "status": "completed",
  "text": "ข้อความที่แปลงแล้ว...",
  "segments": [
    {
      "start_time": 0.0,
      "end_time": 5.0,
      "text": "ข้อความส่วนแรก",
      "confidence": 0.95
    }
  ],
  "audioDuration": 600.0,
  "wordCount": 500,
  "averageConfidence": 0.92,
  "completedAt": "2025-12-02T00:10:00"
}
```

**Response**: `200 OK`

---

## ⚙️ Configuration

### Backend Configuration (appsettings.json)

```json
{
  "ExternalServices": {
    "TranscriptionUrl": "http://localhost:8001",
    "TranscriptionCallbackBaseUrl": "http://localhost:5173"
  },
  "FileService": {
    "ServerUri": "http://localhost:5000",
    "InternalServerUri": "http://file-service:5000"
  }
}
```

### Transcription Service Configuration (.env)

```bash
# Server
HOST=0.0.0.0
PORT=8001

# GPU Configuration (ถ้าใช้)
CUDA_VISIBLE_DEVICES=0
CT2_USE_CUDA_GRAPH=0
OMP_NUM_THREADS=4
MKL_NUM_THREADS=4

# Model Defaults
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
WHISPER_VAD_FILTER=false
```

---

## 🧪 Testing Scripts

### 1. Test Direct Transcription API

```bash
# Test endpoint
curl -X POST http://localhost:8001/transcribe/ \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "http://localhost:5000/api/files/{fileId}",
    "file_name": "test.mp4",
    "language": "th",
    "model_size": "medium",
    "callback_url": "http://localhost:5173/api/transcription/webhook/completed",
    "job_id": 1,
    "user_id": "1"
  }'
```

### 2. Test Webhook Endpoint

```bash
# Test webhook endpoint
curl -X POST http://localhost:5173/api/transcription/webhook/completed \
  -H "Content-Type: application/json" \
  -d '{
    "jobId": 1,
    "taskId": "test-task-id",
    "status": "completed",
    "text": "ทดสอบข้อความ",
    "segments": [
      {
        "start_time": 0.0,
        "end_time": 5.0,
        "text": "ทดสอบข้อความ",
        "confidence": 0.95
      }
    ],
    "audioDuration": 5.0,
    "wordCount": 2,
    "completedAt": "2025-12-02T00:00:00"
  }'
```

---

## ✅ Checklist สำหรับ Local Testing

### Pre-requisites

- [ ] Backend running (port 5173)
- [ ] File Service running (port 5000)
- [ ] Transcription Service running (port 8001)
- [ ] Database connected
- [ ] File ที่จะทดสอบอัปโหลดแล้ว

### Configuration

- [ ] Backend: `ExternalServices:TranscriptionUrl` ชี้ไป Transcription Service
- [ ] Backend: `ExternalServices:TranscriptionCallbackBaseUrl` ชี้ไป Backend
- [ ] Backend: `FileService:ServerUri` ชี้ไป File Service
- [ ] Transcription Service: GPU environment setup (ถ้าใช้ GPU)

### Testing Steps

1. [ ] อัปโหลดไฟล์ผ่าน Backend API
2. [ ] เรียก Start Transcription
3. [ ] ตรวจสอบว่า Transcription Service รับ request
4. [ ] ตรวจสอบ progress ของ transcription
5. [ ] ตรวจสอบว่า callback กลับไป Backend สำเร็จ
6. [ ] ตรวจสอบว่า Backend บันทึกผลลัพธ์ลง Database
7. [ ] ตรวจสอบ WebSocket notification ถึง Frontend

---

## 🔍 Troubleshooting

### ปัญหา: Transcription Service ไม่รับ request

**ตรวจสอบ**:
- Transcription Service ทำงานอยู่: `curl http://localhost:8001/health`
- Backend configuration ชี้ URL ถูกต้อง
- Network connectivity ระหว่าง services

### ปัญหา: Callback ไม่ทำงาน

**ตรวจสอบ**:
- Callback URL ถูกต้องใน request
- Backend webhook endpoint `/api/transcription/webhook/completed` ทำงาน
- Network connectivity จาก Transcription Service ไป Backend

### ปัญหา: ไฟล์ดาวน์โหลดไม่ได้

**ตรวจสอบ**:
- File Service URL ถูกต้อง
- File ID ถูกต้อง
- File Service authentication (ถ้ามี)

---

## 📝 Notes

1. **Callback URL**: ต้องเป็น URL ที่ Backend สามารถรับได้ (localhost หรือ internal network)
2. **File URL**: ต้องเป็น URL ที่ Transcription Service สามารถดาวน์โหลดได้
3. **Model Size**: แนะนำใช้ `medium` สำหรับการทดสอบ (สมดุลระหว่างความเร็วและความแม่นยำ)
4. **Chunk Duration**: ใช้ 30 วินาที เป็นค่า default

---

**Last Updated**: 2025-12-02

