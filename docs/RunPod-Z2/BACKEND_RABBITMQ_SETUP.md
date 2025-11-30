# 🔌 Backend RabbitMQ Setup Guide

คู่มือการตั้งค่า RabbitMQ Connection ไปยัง Backend Server Dev

---

## 📋 Overview

**Backend Server Dev:**
- IP: `178.128.105.100`
- RabbitMQ Port: `5672`
- RabbitMQ User: `senate`
- RabbitMQ Password: `qP2VtHz6fAX4xDksEpMrLT`

**Flow:**
1. Backend Local → ส่งงานผ่าน HTTP API → Transcription Service (RunPod)
2. Transcription Service (Video Worker) → เชื่อมต่อ RabbitMQ → Backend Server Dev
3. Video Worker → รับงานจาก RabbitMQ queue → ประมวลผล → ส่งผลลัพธ์กลับ

---

## 🛠️ การตั้งค่า

### Step 1: ตั้งค่า Transcription Service (RunPod Pod)

**SSH เข้า Pod:**

```bash
ssh root@205.196.17.108 -p 13027
cd /workspace/transcription-service
```

**รัน Setup Script:**

```bash
bash scripts/pod/setup-rabbitmq-backend.sh 178.128.105.100 5672
```

**หรือตั้งค่าด้วยตนเอง:**

```bash
# สร้าง/แก้ไข .env.runpod
cat > .env.runpod << EOF
# RabbitMQ Configuration (Backend Server Dev)
RABBITMQ_HOST=178.128.105.100
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Whisper Configuration
WHISPER_PROVIDER=builtin
WHISPER_API_URL=http://localhost:8002
WHISPER_MODEL_PATH=/workspace/transcription-service/models

# Environment
ENVIRONMENT=runpod

# Storage
STORAGE_TYPE=json
JSON_STORAGE_DIR=/workspace/transcription-service/storage

# GPU Configuration
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1
EOF
```

---

### Step 2: ทดสอบ Connection

**จาก RunPod Pod:**

```bash
# ทดสอบ RabbitMQ connection
python3 -c "
import pika
try:
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host='178.128.105.100',
            port=5672,
            credentials=pika.PlainCredentials('senate', 'qP2VtHz6fAX4xDksEpMrLT'),
            connection_attempts=3,
            retry_delay=2
        )
    )
    print('✅ RabbitMQ connection successful!')
    connection.close()
except Exception as e:
    print(f'❌ RabbitMQ connection failed: {e}')
"
```

---

### Step 3: Restart Services

**จาก RunPod Pod:**

```bash
# Stop services
bash scripts/pod/stop-services.sh

# Start services (จะโหลด .env.runpod อัตโนมัติ)
bash scripts/pod/start-services-direct.sh
```

---

### Step 4: ตรวจสอบ Logs

**จาก RunPod Pod:**

```bash
# ตรวจสอบ Video Worker logs
tail -f /tmp/video-worker.log

# ควรเห็น:
# Attempting to connect to RabbitMQ at 178.128.105.100:5672 (attempt 1/10)...
# ✅ เชื่อมต่อ RabbitMQ สำเร็จ
```

---

## 🔍 Backend Local Configuration

**Backend Local ไม่ต้องปรับ** เพราะ:
- Backend ส่งงานผ่าน HTTP API ไป Transcription Service
- Transcription Service (Video Worker) จะเชื่อมต่อ RabbitMQ เอง

**แต่ถ้าต้องการให้ Backend Local ใช้ RabbitMQ ที่ Backend Dev:**

**แก้ไข `appsettings.Development.json`:**

```json
{
  "VideoRecorder": {
    "Host": "amqp://senate:qP2VtHz6fAX4xDksEpMrLT@178.128.105.100:5672/",
    "Username": "senate",
    "Password": "qP2VtHz6fAX4xDksEpMrLT"
  }
}
```

**หมายเหตุ:** การปรับนี้จะทำให้ Backend Local ใช้ RabbitMQ ที่ Backend Dev แทน localhost

---

## 🔒 Firewall Configuration

**บน Backend Server Dev (178.128.105.100):**

```bash
# เปิด port 5672 สำหรับ RabbitMQ
sudo ufw allow 5672/tcp

# ตรวจสอบ
sudo ufw status
```

**หรือถ้าใช้ Docker:**

```bash
# ตรวจสอบว่า RabbitMQ container expose port 5672
docker ps | grep rabbitmq
# ควรเห็น: 0.0.0.0:5672->5672/tcp
```

---

## 📋 Checklist

- [ ] RabbitMQ ทำงานบน Backend Server Dev
- [ ] Firewall เปิด port 5672
- [ ] .env.runpod ถูกตั้งค่า (RABBITMQ_HOST=178.128.105.100)
- [ ] Connection test ผ่าน
- [ ] Services restart แล้ว
- [ ] Video Worker logs ไม่แสดง connection errors

---

## 🧪 ทดสอบ End-to-End

### 1. ส่ง Transcription Job จาก Backend Local

```bash
# จาก Backend Local
curl -X POST http://localhost:5000/api/transcription/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "file_id": "...",
    "file_name": "test.mp4",
    "language": "th",
    "model_size": "medium"
  }'
```

### 2. ตรวจสอบ RabbitMQ Queue

**เข้าถึง RabbitMQ Management UI:**

```
http://178.128.105.100:15672
Username: senate
Password: qP2VtHz6fAX4xDksEpMrLT
```

**ตรวจสอบ Queue:**
- `media.audio.chunk.extracted` - Audio chunks จาก Backend
- `transcription_queue` - Transcription tasks

### 3. ตรวจสอบ Video Worker Logs

**จาก RunPod Pod:**

```bash
tail -f /tmp/video-worker.log
```

**ควรเห็น:**
```
Received message from queue: media.audio.chunk.extracted
Processing transcription task...
✅ Transcription completed
```

---

## 🔗 Related Documents

- **Setup Script:** `scripts/pod/setup-rabbitmq-backend.sh`
- **Start Services:** `scripts/pod/start-services-direct.sh`
- **Check Services:** `scripts/pod/check-services.sh`
- **RabbitMQ Connection:** `docs/RunPod-Z2/RABBITMQ_CONNECTION.md`

---

**Last Updated:** 2024-12-19

