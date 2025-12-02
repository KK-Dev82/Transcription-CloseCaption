# 🚀 Backend Local Setup Guide

คู่มือการตั้งค่าและทดสอบ Transcription Service กับ Backend Local

---

## 📋 Prerequisites

### Services ที่ต้องรัน

1. **Backend** (senate-backend)
   - Port: 5173
   - URL: `http://localhost:5173`

2. **File Service**
   - Port: 5000
   - URL: `http://localhost:5000`

3. **Transcription Service** (transcription-close-caption-service)
   - Port: 8001
   - URL: `http://localhost:8001`

### Software Requirements

- Docker & Docker Compose (ถ้าใช้)
- Python 3.10+ (สำหรับ Transcription Service)
- .NET 8 (สำหรับ Backend)
- PostgreSQL (สำหรับ Backend Database)

---

## ⚙️ Configuration

### 1. Backend Configuration

**ไฟล์**: `senate-backend/src/Shorthand.Api/appsettings.Development.json`

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

**สำหรับ Docker**:
```json
{
  "ExternalServices": {
    "TranscriptionUrl": "http://transcription-service:8001",
    "TranscriptionCallbackBaseUrl": "http://backend:5173"
  },
  "FileService": {
    "ServerUri": "http://file-service:5000",
    "InternalServerUri": "http://file-service:5000"
  }
}
```

### 2. Transcription Service Configuration

**ไฟล์**: `.env` หรือ `.env.local`

```bash
# Server
HOST=0.0.0.0
PORT=8001

# GPU Configuration (ถ้าใช้)
CUDA_VISIBLE_DEVICES=0
CT2_USE_CUDA_GRAPH=0
OMP_NUM_THREADS=4
MKL_NUM_THREADS=4

# Library Paths (สำหรับ GPU)
LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/torch/lib:/usr/local/cuda-11.8/targets/x86_64-linux/lib

# Model Defaults
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
WHISPER_VAD_FILTER=false
```

---

## 🚀 Quick Start

### Step 1: เริ่ม Services

#### Backend
```bash
cd senate-backend
dotnet run --project src/Shorthand.Api
```

หรือใช้ Docker:
```bash
cd senate-backend
docker-compose -f docker-compose.local.yml up
```

#### Transcription Service
```bash
cd transcription-close-caption-service

# Setup GPU environment (ถ้าใช้ GPU)
source scripts/pod/setup-gpu-env.sh

# Run service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

หรือใช้ Docker:
```bash
docker-compose up transcription-service
```

### Step 2: ตรวจสอบ Services

```bash
# Check Transcription Service
curl http://localhost:8001/health

# Check Backend
curl http://localhost:5173/health

# Check File Service
curl http://localhost:5000/health
```

### Step 3: ทดสอบ Integration

```bash
# Test integration
bash scripts/test/test-backend-integration.sh
```

---

## 🧪 Testing Flow

### 1. ทดสอบผ่าน Backend API

```bash
# Step 1: Upload file
curl -X POST http://localhost:5173/api/transcription/upload/stream \
  -H "X-File-Name: test-video.mp4" \
  -H "X-File-Size: 12345" \
  --data-binary "@test-video.mp4"

# Step 2: Start transcription (ใช้ fileId จาก Step 1)
curl -X POST http://localhost:5173/api/transcription/start \
  -H "Content-Type: application/json" \
  -d '{
    "fileId": "file-id-from-step-1",
    "fileName": "test-video.mp4",
    "language": "th",
    "modelSize": "medium"
  }'
```

### 2. ทดสอบ Transcription Service โดยตรง

```bash
bash scripts/test/test-transcription-callback.sh \
  "http://localhost:5000/api/files/{fileId}" \
  "http://localhost:5173/api/transcription/webhook/completed" \
  999 \
  1
```

### 3. Monitor Progress

```bash
# Check transcription status
curl http://localhost:8001/transcribe/{task_id}

# Check job status in Backend
curl http://localhost:5173/api/transcription/jobs/{job_id}
```

---

## 🔍 Verification Checklist

### Services Running
- [ ] Backend running on port 5173
- [ ] File Service running on port 5000
- [ ] Transcription Service running on port 8001
- [ ] Database connected

### Configuration
- [ ] Backend: `ExternalServices:TranscriptionUrl` configured
- [ ] Backend: `ExternalServices:TranscriptionCallbackBaseUrl` configured
- [ ] Backend: `FileService:ServerUri` configured
- [ ] Transcription Service: GPU environment setup (ถ้าใช้)

### Endpoints
- [ ] `GET http://localhost:8001/health` - Working
- [ ] `GET http://localhost:5173/health` - Working
- [ ] `POST http://localhost:8001/transcribe/` - Working
- [ ] `POST http://localhost:5173/api/transcription/webhook/completed` - Working

---

## 🐛 Troubleshooting

### ปัญหา: Services ไม่เชื่อมต่อกัน

**แก้ไข**:
- ตรวจสอบ URL ใน configuration ถูกต้อง
- ตรวจสอบ network connectivity
- สำหรับ Docker: ตรวจสอบ network และ service names

### ปัญหา: Callback ไม่ทำงาน

**แก้ไข**:
- ตรวจสอบ `callback_url` ใน request
- ตรวจสอบ Backend webhook endpoint
- ตรวจสอบ logs ของ Transcription Service

### ปัญหา: ไฟล์ดาวน์โหลดไม่ได้

**แก้ไข**:
- ตรวจสอบ File Service URL
- ตรวจสอบ file ID ถูกต้อง
- ตรวจสอบ authentication (ถ้ามี)

---

## 📝 Next Steps

1. ✅ ทดสอบ Upload file ผ่าน Backend
2. ✅ ทดสอบ Start transcription
3. ✅ ทดสอบ Monitor progress
4. ✅ ทดสอบ Webhook callback
5. ✅ ทดสอบ Database storage
6. ✅ ทดสอบ Frontend integration

---

**Last Updated**: 2025-12-02

