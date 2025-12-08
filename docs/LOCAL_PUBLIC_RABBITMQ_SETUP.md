# 🔧 Local Development: ใช้ Public RabbitMQ

**วันที่สร้าง**: 2024-12-05  
**Purpose**: ตั้งค่า Local Development ให้ใช้ Public RabbitMQ สำหรับการทดสอบ

---

## 📋 สรุป

### Public RabbitMQ Server
- **Host**: `178.128.105.100`
- **Port**: `5672`
- **Username**: `senate`
- **Password**: `qP2VtHz6fAX4xDksEpMrLT`
- **VirtualHost**: `/`

---

## 🔍 ไฟล์ที่ต้องแก้ไข

### 1. Backend - appsettings.Development.json

**ไฟล์**: `senate-backend/src/Shorthand.Api/appsettings.Development.json`

**แก้ไข:**
```json
{
  "RabbitMq": {
    "Host": "amqp://senate:qP2VtHz6fAX4xDksEpMrLT@178.128.105.100:5672/",
    "Username": "senate",
    "Password": "qP2VtHz6fAX4xDksEpMrLT"
  },
  "VideoRecorder": {
    "Host": "amqp://senate:qP2VtHz6fAX4xDksEpMrLT@178.128.105.100:5672/",
    "Username": "senate",
    "Password": "qP2VtHz6fAX4xDksEpMrLT"
  }
}
```

---

### 2. Backend - docker-compose.local.yml

**ไฟล์**: `senate-backend/docker-compose.local.yml`

**แก้ไข:**
```yaml
services:
  kk-senate-backend:
    environment:
      # RabbitMQ Configuration (Public)
      RabbitMq__Host: "amqp://senate:qP2VtHz6fAX4xDksEpMrLT@178.128.105.100:5672/"
      RabbitMq__Username: "senate"
      RabbitMq__Password: "qP2VtHz6fAX4xDksEpMrLT"
      VideoRecorder__Host: "amqp://senate:qP2VtHz6fAX4xDksEpMrLT@178.128.105.100:5672/"
      VideoRecorder__Username: "senate"
      VideoRecorder__Password: "qP2VtHz6fAX4xDksEpMrLT"
```

**หมายเหตุ:**
- ถ้าใช้ `docker-compose.local.yml` และมี `rabbitmq` service อยู่ → Comment หรือลบออก
- หรือเก็บไว้สำหรับ local development แบบปกติ (ไม่ใช้ Public RabbitMQ)

---

### 3. Transcription Service - env.development

**ไฟล์**: `transcription-close-caption-service/env.development`

**แก้ไข:**
```bash
# RabbitMQ Configuration (Public)
RABBITMQ_HOST=178.128.105.100
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT
RABBITMQ_VHOST=/

# Backend API (Local)
BACKEND_API_BASE_URL=http://localhost:5173
BACKEND_URL=http://localhost:5173

# FileService (Local)
FILE_SERVICE_URL=http://localhost:5182
```

---

## 🔄 เปรียบเทียบ: Local vs Staging

| Configuration | Local (Public RabbitMQ) | Staging |
|---------------|------------------------|---------|
| **RabbitMQ Host** | `178.128.105.100:5672` | `178.128.105.100:5672` |
| **Backend URL** | `http://localhost:5173` | `http://10.200.22.61:5173` |
| **FileService URL** | `http://localhost:5182` | `http://10.200.22.60:5182` |
| **Transcription URL** | `http://localhost:8001` | `http://80.15.7.37:41314` |

---

## ✅ Checklist สำหรับ Local

### Backend
- [ ] `appsettings.Development.json`: เปลี่ยน RabbitMQ Host เป็น Public
- [ ] `docker-compose.local.yml`: เปลี่ยน RabbitMQ environment variables
- [ ] Comment หรือลบ `rabbitmq` service (ถ้าไม่ใช้)

### Transcription Service
- [ ] `env.development`: เปลี่ยน RabbitMQ Host เป็น Public
- [ ] `BACKEND_API_BASE_URL`: ใช้ `http://localhost:5173`
- [ ] `FILE_SERVICE_URL`: ใช้ `http://localhost:5182`

---

## 🧪 Testing

### 1. ตรวจสอบ RabbitMQ Connection

**Backend:**
```bash
# ตรวจสอบ logs
docker logs kk-senate-backend | grep -i rabbitmq
```

**Transcription Service:**
```bash
# ตรวจสอบ logs
tail -f logs/video_worker.log | grep -i rabbitmq
```

### 2. ทดสอบ Queue Communication

**Backend → Transcription Service:**
- Backend ส่ง task ไป RabbitMQ
- ตรวจสอบว่า Transcription Service รับ task ได้

**Transcription Service → Backend:**
- Transcription Service ส่ง completed message ไป RabbitMQ
- ตรวจสอบว่า Backend Consumer รับ message ได้

---

## ⚠️ หมายเหตุ

### ข้อดีของการใช้ Public RabbitMQ ใน Local
- ✅ ทดสอบได้เหมือน Staging
- ✅ ไม่ต้องรัน RabbitMQ local
- ✅ แชร์ queues กับ Staging (ถ้าต้องการ)

### ข้อเสีย
- ⚠️ แชร์ queues กับ Staging (อาจมี message ปะปนกัน)
- ⚠️ ต้องมี Internet connection
- ⚠️ อาจมี latency สูงกว่า local RabbitMQ

### แนะนำ
- **สำหรับการทดสอบปกติ**: ใช้ Local RabbitMQ
- **สำหรับการทดสอบ Staging integration**: ใช้ Public RabbitMQ

---

**Last Updated**: 2024-12-05  
**Status**: Ready ✅

