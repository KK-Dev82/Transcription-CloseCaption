# ✅ Checklist: RabbitMQ Configuration สำหรับ Staging

**วันที่สร้าง**: 2024-12-05  
**Purpose**: ตรวจสอบและกำหนดค่าการตั้งค่า RabbitMQ สำหรับ Staging Environment

---

## 📋 สรุป

### RabbitMQ Public Server
- **Host**: `178.128.105.100`
- **Port**: `5672`
- **Username**: `senate`
- **Password**: `qP2VtHz6fAX4xDksEpMrLT`
- **VirtualHost**: `/`

### Communication Pattern
- ✅ **Transcription Service ↔ Backend**: ใช้ **RabbitMQ** สำหรับ task queues
- ✅ **Transcription Service → Backend**: ใช้ **HTTP Callback** สำหรับ completed notifications
- ❌ **FileService**: ไม่ใช้ RabbitMQ (ไม่ต้องตั้งค่า)

---

## 🔍 ไฟล์ที่ต้องตรวจสอบ/แก้ไข

### 1. Transcription Service ✅ (พร้อมแล้ว)

**ไฟล์**: `transcription-close-caption-service/env.runpod`

```bash
# RabbitMQ (Public) ✅
RABBITMQ_HOST=178.128.105.100
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT
RABBITMQ_VHOST=/

# Backend API (VPN - ผ่าน Frontend Proxy)
BACKEND_API_BASE_URL=http://10.200.22.61:5173
# หรือผ่าน Frontend: https://staging-ph2.bms.senate.go.th

# FileService (VPN - ผ่าน Frontend Proxy)
FILE_SERVICE_URL=http://10.200.22.60:5182
# หรือผ่าน Frontend: https://staging-ph2.bms.senate.go.th/fileservice
```

**สถานะ**: ✅ **พร้อมแล้ว** (ตั้งค่า Public RabbitMQ แล้ว)

---

### 2. Backend (ต้องตรวจสอบ)

#### 2.1 appsettings.Staging.json

**ไฟล์**: `senate-backend/src/Shorthand.Api/appsettings.Staging.json`

**ต้องตรวจสอบ/แก้ไข:**
```json
{
  "RabbitMq": {
    "Host": "amqp://senate:qP2VtHz6fAX4xDksEpMrLT@178.128.105.100:5672/",
    // หรือแยกเป็น:
    "Host": "178.128.105.100",
    "Port": 5672,
    "Username": "senate",
    "Password": "qP2VtHz6fAX4xDksEpMrLT",
    "VirtualHost": "/"
  },
  
  "ExternalServices": {
    "TranscriptionUrl": "http://80.15.7.37:41314",
    // หรือผ่าน Frontend Proxy:
    "TranscriptionUrl": "https://staging-ph2.bms.senate.go.th/api/video",
    "TranscriptionCallbackBaseUrl": "http://10.200.22.61:5173"
  }
}
```

**ตรวจสอบ:**
- ✅ `RabbitMq:Host` ต้องเป็น Public RabbitMQ (`178.128.105.100`)
- ✅ `RabbitMq:Username` และ `RabbitMq:Password` ต้องถูกต้อง
- ✅ `ExternalServices:TranscriptionUrl` ต้องชี้ไปที่ Pod หรือ Frontend Proxy

---

#### 2.2 docker-compose.staging.yml

**ไฟล์**: `senate-backend/docker-compose.staging.yml`

**ต้องตรวจสอบ/แก้ไข:**
```yaml
services:
  kk-senate-backend:
    environment:
      # RabbitMQ Configuration
      RabbitMq__Host: "amqp://senate:qP2VtHz6fAX4xDksEpMrLT@178.128.105.100:5672/"
      # หรือแยกเป็น:
      RabbitMq__Host: "178.128.105.100"
      RabbitMq__Port: "5672"
      RabbitMq__Username: "senate"
      RabbitMq__Password: "qP2VtHz6fAX4xDksEpMrLT"
      RabbitMq__VirtualHost: "/"
      
      # Transcription Service
      ExternalServices__TranscriptionUrl: "http://80.15.7.37:41314"
      # หรือผ่าน Frontend Proxy:
      ExternalServices__TranscriptionUrl: "https://staging-ph2.bms.senate.go.th/api/video"
      
      ExternalServices__TranscriptionCallbackBaseUrl: "http://10.200.22.61:5173"
```

**ตรวจสอบ:**
- ✅ Environment variables ต้องชี้ไปที่ Public RabbitMQ
- ✅ ไม่ต้องมี `rabbitmq` service ใน docker-compose (เพราะใช้ Public RabbitMQ)

---

#### 2.3 RabbitMqPublisher.cs & RabbitMqBackgroundConsumer.cs

**ไฟล์**: 
- `senate-backend/src/Shorthand.Infrastructure/Messaging/RabbitMqPublisher.cs`
- `senate-backend/src/Shorthand.Api/Messaging/RabbitMqBackgroundConsumer.cs`

**ตรวจสอบ Config Keys:**
```csharp
// ✅ Code ใช้ config keys ต่อไปนี้ (ตรวจสอบแล้ว):
var host = configuration["RabbitMq:Host"] 
    ?? configuration["VideoRecorder:Host"] 
    ?? "amqp://guest:guest@localhost:5672/";
var username = configuration["RabbitMq:Username"] 
    ?? configuration["VideoRecorder:Username"];
var password = configuration["RabbitMq:Password"] 
    ?? configuration["VideoRecorder:Password"];
```

**สถานะ**: ✅ **Code ใช้ config keys ถูกต้อง** (ไม่ต้องแก้ไข code)

---

### 3. FileService ❌ (ไม่ต้องตั้งค่า)

**ตรวจสอบแล้ว**: FileService **ไม่ใช้ RabbitMQ**

**ไฟล์**: `file-service/FileService/docker-compose.staging.yml`

**สถานะ**: ✅ **ไม่ต้องแก้ไข** (FileService ไม่ใช้ RabbitMQ)

---

### 4. Frontend (nginx.staging.conf) ✅ (พร้อมแล้ว)

**ไฟล์**: `senate-vite/nginx/nginx.staging.conf`

**ตรวจสอบแล้ว:**
- ✅ Line 198-217: `/api/video/` proxy สำหรับ Transcription Service (Pod)
- ✅ Line 177-193: `/fileservice/` proxy สำหรับ FileService

**สถานะ**: ✅ **พร้อมแล้ว** (ไม่ต้องแก้ไข)

---

## 🔄 Communication Flow

### Transcription Service → Backend

**ผ่าน RabbitMQ (Task Queues):**
```
Transcription Service (Pod)
    ↓
    Publish to RabbitMQ:
    - transcription_request_queue
    - audio_extraction_queue
    - transcription_queue
    - chunk_transcription_queue
    ↓
RabbitMQ (Public: 178.128.105.100)
    ↓
    Consume from RabbitMQ:
    - transcription.completed
    - transcription.chunk.completed
    ↓
Backend (VPN: 10.200.22.61)
```

**ผ่าน HTTP Callback (Completed Notifications):**
```
Transcription Service (Pod)
    ↓
    HTTP POST: http://10.200.22.61:5173/api/transcription/webhook/completed
    หรือ: https://staging-ph2.bms.senate.go.th/api/transcription/webhook/completed
    ↓
Backend (VPN: 10.200.22.61)
```

---

### Backend → Transcription Service

**ผ่าน HTTP API:**
```
Backend (VPN: 10.200.22.61)
    ↓
    HTTP POST: http://80.15.7.37:41314/transcribe/
    หรือผ่าน Frontend Proxy: https://staging-ph2.bms.senate.go.th/api/video/transcribe/
    ↓
Transcription Service (Pod: 80.15.7.37)
```

**ผ่าน RabbitMQ (Task Queues):**
```
Backend (VPN: 10.200.22.61)
    ↓
    Publish to RabbitMQ:
    - transcription_request_queue
    ↓
RabbitMQ (Public: 178.128.105.100)
    ↓
    Consume from RabbitMQ:
    - transcription_request_queue
    ↓
Transcription Service (Pod: 80.15.7.37)
```

---

## ✅ Checklist สำหรับ Staging

### Transcription Service ✅
- [x] `env.runpod` ตั้งค่า Public RabbitMQ (`178.128.105.100`)
- [x] `BACKEND_API_BASE_URL` ชี้ไปที่ Backend (VPN หรือ Frontend Proxy)
- [x] `FILE_SERVICE_URL` ชี้ไปที่ FileService (VPN หรือ Frontend Proxy)

---

### Backend ⚠️ (ต้องตรวจสอบ)

**ตรวจสอบไฟล์:**
- [ ] `appsettings.Staging.json`
  - [ ] `RabbitMq:Host` = `178.128.105.100` (Public)
  - [ ] `RabbitMq:Username` = `senate`
  - [ ] `RabbitMq:Password` = `qP2VtHz6fAX4xDksEpMrLT`
  - [ ] `ExternalServices:TranscriptionUrl` = Pod หรือ Frontend Proxy

- [ ] `docker-compose.staging.yml`
  - [ ] Environment variables สำหรับ RabbitMQ
  - [ ] Environment variables สำหรับ Transcription Service
  - [ ] ไม่มี `rabbitmq` service (เพราะใช้ Public RabbitMQ)

**ตรวจสอบการทำงาน:**
- [ ] Backend สามารถเชื่อมต่อ RabbitMQ ได้
- [ ] Backend Consumer (`RabbitMqBackgroundConsumer`) ทำงานได้
- [ ] Backend Publisher (`RabbitMqPublisher`) ทำงานได้

---

### FileService ✅
- [x] ไม่ใช้ RabbitMQ (ไม่ต้องตั้งค่า)

---

### Frontend (nginx.staging.conf) ✅
- [x] `/api/video/` proxy สำหรับ Transcription Service
- [x] `/fileservice/` proxy สำหรับ FileService

---

## 🔧 Configuration Template

### Backend appsettings.Staging.json

```json
{
  "RabbitMq": {
    "Host": "amqp://senate:qP2VtHz6fAX4xDksEpMrLT@178.128.105.100:5672/",
    "Username": "senate",
    "Password": "qP2VtHz6fAX4xDksEpMrLT"
  },
  
  "ExternalServices": {
    "TranscriptionUrl": "http://80.15.7.37:41314",
    "TranscriptionCallbackBaseUrl": "http://10.200.22.61:5173"
  },
  
  "ConnectionStrings": {
    "SenateDb": "Host=10.200.22.59;Port=5432;Database=Senate;Username=postgres;Password=..."
  }
}
```

---

### Backend docker-compose.staging.yml

```yaml
services:
  kk-senate-backend:
    environment:
      # RabbitMQ (Public)
      RabbitMq__Host: "amqp://senate:qP2VtHz6fAX4xDksEpMrLT@178.128.105.100:5672/"
      # หรือแยกเป็น:
      # RabbitMq__Host: "178.128.105.100"
      # RabbitMq__Port: "5672"
      # RabbitMq__Username: "senate"
      # RabbitMq__Password: "qP2VtHz6fAX4xDksEpMrLT"
      
      # Transcription Service
      ExternalServices__TranscriptionUrl: "http://80.15.7.37:41314"
      ExternalServices__TranscriptionCallbackBaseUrl: "http://10.200.22.61:5173"
      
      # Database
      ConnectionStrings__SenateDb: "Host=10.200.22.59;Port=5432;Database=Senate;Username=postgres;Password=..."
```

---

## 🧪 Testing Checklist

### 1. RabbitMQ Connection Test

**Backend:**
```bash
# ตรวจสอบว่า Backend เชื่อมต่อ RabbitMQ ได้
# ดู logs: docker logs kk-senate-backend | grep -i rabbitmq
```

**Transcription Service:**
```bash
# ตรวจสอบว่า Transcription Service เชื่อมต่อ RabbitMQ ได้
# ดู logs: tail -f /workspace/transcription-service/logs/video_worker.log | grep -i rabbitmq
```

---

### 2. Queue Communication Test

**Backend → Transcription Service:**
```bash
# Backend ส่ง task ไป RabbitMQ
# ตรวจสอบว่า Transcription Service รับ task ได้
```

**Transcription Service → Backend:**
```bash
# Transcription Service ส่ง completed message ไป RabbitMQ
# ตรวจสอบว่า Backend Consumer รับ message ได้
```

---

### 3. HTTP Callback Test

**Transcription Service → Backend:**
```bash
# Transcription Service ส่ง HTTP callback ไป Backend
# ตรวจสอบว่า Backend รับ callback ได้
# Endpoint: /api/transcription/webhook/completed
```

---

## 📝 สรุป

### ✅ พร้อมแล้ว
1. **Transcription Service**: ตั้งค่า Public RabbitMQ แล้ว
2. **Frontend (nginx.staging.conf)**: Proxy config พร้อมแล้ว

### ⚠️ ต้องตรวจสอบ/แก้ไข
1. **Backend appsettings.Staging.json**: ตรวจสอบ RabbitMQ config
2. **Backend docker-compose.staging.yml**: ตรวจสอบ environment variables

### ❌ ไม่ต้องทำ
1. **FileService**: ไม่ใช้ RabbitMQ

---

**Last Updated**: 2024-12-05  
**Status**: Ready for Review ✅

