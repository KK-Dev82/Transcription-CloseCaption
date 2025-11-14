# 🎤 Transcription & Close Caption Service

ระบบแปลงเสียงเป็นข้อความ (Transcription) และสร้าง Close Caption สำหรับวิดีโอ โดยใช้ AI Whisper Model พร้อมการปรับปรุงความแม่นยำภาษาไทย

## 📋 สารบัญ

- [เกี่ยวกับระบบ](#เกี่ยวกับระบบ)
- [Features](#features)
- [System Requirements](#system-requirements)
- [การติดตั้ง (เริ่มจาก 0)](#การติดตั้ง-เริ่มจาก-0)
- [การใช้งาน](#การใช้งาน)
- [API Documentation](#api-documentation)
- [การแก้ไขปัญหา](#การแก้ไขปัญหา)

---

## 🎯 เกี่ยวกับระบบ

ระบบนี้เป็น **Microservice** สำหรับแปลงเสียงเป็นข้อความและสร้าง Close Caption สำหรับวิดีโอ โดยใช้:

- **Whisper AI Model** - OpenAI Whisper สำหรับแปลงเสียงเป็นข้อความ
- **FastAPI** - Python Web Framework สำหรับ REST API
- **Docker & Docker Compose** - Containerization
- **RabbitMQ** - Message Queue สำหรับ background processing
- **Redis** - Caching และ session management
- **WebSocket** - Real-time updates

### สถาปัตยกรรม

```
┌─────────────┐
│   Client    │
│  (Frontend) │
└──────┬──────┘
       │ HTTP/WebSocket
       ▼
┌─────────────────┐
│  API Service    │  ← FastAPI (Port 8001)
│  (Main Service) │
└──────┬──────────┘
       │
       ├──► RabbitMQ ──► Video Workers (Background Processing)
       │
       ├──► Redis (Caching)
       │
       └──► Whisper Service ──► Whisper AI Model
            (Port 8002)
```

---

## ✨ Features

- ✅ **Real-time Transcription** - แปลงเสียงเป็นข้อความแบบ real-time
- ✅ **Thai Language Optimization** - ปรับปรุงความแม่นยำภาษาไทยด้วย NLP
- ✅ **Progress Tracking** - ติดตาม progress แบบ real-time ผ่าน WebSocket
- ✅ **Multiple Formats** - รองรับไฟล์วิดีโอและเสียงหลากหลาย (MP4, MP3, WAV, etc.)
- ✅ **Chunk Processing** - แบ่งไฟล์ใหญ่เป็นส่วนย่อยเพื่อประมวลผล
- ✅ **Caption Generation** - สร้าง SRT subtitles อัตโนมัติ
- ✅ **Live Streaming** - รองรับ live transcription
- ✅ **Scalable** - รองรับ concurrent users และ background workers

---

## 💻 System Requirements

### Server Requirements

- **OS:** Linux (Ubuntu 20.04+ หรือ Debian 11+)
- **CPU:** 2+ cores (แนะนำ 4+ cores)
- **RAM:** 4GB+ (แนะนำ 8GB+)
- **Storage:** 20GB+ free space
- **Network:** Internet connection สำหรับดาวน์โหลด images และ models

### Software Requirements

- **Docker:** 20.10+
- **Docker Compose:** 2.0+
- **Git:** สำหรับ clone repository

### External Services (Optional)

- **RabbitMQ:** สำหรับ message queue (สามารถรันใน container)
- **Redis:** สำหรับ caching (สามารถรันใน container)

---

## 🚀 การติดตั้ง (เริ่มจาก 0)

### Step 1: เตรียม Server Linux

#### 1.1 อัปเดตระบบ

```bash
# อัปเดต package list
sudo apt update && sudo apt upgrade -y

# ติดตั้ง dependencies พื้นฐาน
sudo apt install -y \
    curl \
    wget \
    git \
    ca-certificates \
    gnupg \
    lsb-release
```

#### 1.2 ติดตั้ง Docker

```bash
# เพิ่ม Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# ตั้งค่า repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# ติดตั้ง Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# ตรวจสอบการติดตั้ง
sudo docker --version
sudo docker compose version
```

#### 1.3 ตั้งค่า Docker (ไม่ต้องใช้ sudo)

```bash
# เพิ่ม user เข้า docker group
sudo usermod -aG docker $USER

# Logout และ login ใหม่ หรือใช้คำสั่งนี้
newgrp docker

# ทดสอบว่าใช้งานได้
docker ps
```

### Step 2: Clone Repository

```bash
# ไปที่ directory ที่ต้องการ
cd /opt  # หรือ directory อื่นที่ต้องการ

# Clone repository
git clone <repository-url> transcription-close-caption-service
cd transcription-close-caption-service

# ตรวจสอบว่า clone สำเร็จ
ls -la
```

### Step 3: เตรียม Directories และ Permissions

```bash
# สร้าง directories ที่จำเป็น
mkdir -p uploads storage temp models test-files

# ตั้งค่า permissions
chmod 755 uploads storage temp models test-files
chmod 755 scripts/*.sh 2>/dev/null || true

# ตรวจสอบ
ls -la
```

### Step 4: ดาวน์โหลด Whisper Model

#### วิธีที่ 1: ใช้ Script (แนะนำ)

```bash
# ให้สิทธิ์ execute
chmod +x scripts/download-models.sh

# ดาวน์โหลด model
./scripts/download-models.sh

# ตรวจสอบ
ls -lh models/ggml-base.bin
# ควรเห็น: ggml-base.bin (ประมาณ 148MB)
```

#### วิธีที่ 2: ดาวน์โหลดด้วย wget

```bash
# สร้าง directory
mkdir -p models

# ดาวน์โหลด model
wget -O models/ggml-base.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin

# ตรวจสอบขนาด (ควรเป็น ~148MB)
ls -lh models/ggml-base.bin
```

#### วิธีที่ 3: ดาวน์โหลดด้วย curl

```bash
# สร้าง directory
mkdir -p models

# ดาวน์โหลด model
curl -L -o models/ggml-base.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin

# ตรวจสอบขนาด
ls -lh models/ggml-base.bin
```

**รายละเอียด Model:**
- **URL:** `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin`
- **Directory:** `models/`
- **Filename:** `ggml-base.bin`
- **Size:** ~148MB (148,000,000 bytes)

**ตรวจสอบ Model:**

```bash
# ตรวจสอบว่าไฟล์มีอยู่
ls -lh models/ggml-base.bin
# ควรเห็น: -rw-r--r-- 1 user user 148M ... ggml-base.bin

# ตรวจสอบประเภทไฟล์ (ควรเป็น binary)
file models/ggml-base.bin
# ควรเห็น: models/ggml-base.bin: data

# ตรวจสอบขนาด (ควรมากกว่า 100MB)
stat -c%s models/ggml-base.bin
# ควรเห็น: 148000000
```

### Step 5: ตั้งค่า Environment Variables

```bash
# คัดลอกไฟล์ environment (ถ้ามี)
cp env.staging .env 2>/dev/null || true

# หรือสร้างไฟล์ .env ใหม่
cat > .env << EOF
# Environment
ENVIRONMENT=production

# Storage
STORAGE_TYPE=json
JSON_STORAGE_DIR=/app/storage

# RabbitMQ (ปรับตาม environment ของคุณ)
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

# Redis
REDIS_URL=redis://redis:6379

# Whisper Service
WHISPER_API_URL=http://whisper:8002
EOF
```

### Step 6: ตั้งค่า Docker Compose

```bash
# ตรวจสอบไฟล์ docker-compose ที่ต้องการใช้
ls -la docker-compose*.yml

# สำหรับ Production ใช้ docker-compose.digitalocean.yml หรือ docker-compose.production.yml
# สำหรับ Local Development ใช้ docker-compose.local.yml

# ตรวจสอบ configuration
docker compose -f docker-compose.digitalocean.yml config
```

**แก้ไข docker-compose.yml ตามความต้องการ:**

- **RabbitMQ:** ปรับ `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`
- **Redis:** ปรับ `REDIS_URL` ถ้าใช้ external Redis
- **Ports:** ปรับ ports ตามต้องการ (default: 8001, 8002)

### Step 7: Pull Docker Images

```bash
# Login to Azure Container Registry (ถ้าใช้ private registry)
# az acr login --name <registry-name>

# Pull images
docker compose -f docker-compose.digitalocean.yml pull

# หรือ build images เอง (ถ้าไม่ใช้ pre-built images)
# docker compose -f docker-compose.digitalocean.yml build
```

### Step 8: เริ่ม Services

```bash
# เริ่ม services
docker compose -f docker-compose.digitalocean.yml up -d

# ตรวจสอบ status
docker compose -f docker-compose.digitalocean.yml ps

# ดู logs
docker compose -f docker-compose.digitalocean.yml logs -f
```

### Step 9: ตรวจสอบการติดตั้ง

```bash
# ตรวจสอบ health check
curl http://localhost:8001/health
# ควรเห็น: {"status":"healthy",...}

curl http://localhost:8002/health
# ควรเห็น: {"status":"healthy","service":"whisper-transcription"}

# ตรวจสอบว่า Whisper เห็น model
curl http://localhost:8002/models
# ควรเห็น JSON ที่มี model ในรายการ

# ตรวจสอบ containers
docker ps
# ควรเห็น containers ทั้งหมด running
```

---

## 📖 การใช้งาน

### 1. API Endpoints

#### Health Check

```bash
# API Service
curl http://localhost:8001/health

# Whisper Service
curl http://localhost:8002/health
```

#### Upload และ Transcription

```bash
# 1. Upload ไฟล์วิดีโอ
curl -X POST http://localhost:8001/upload/ \
  -F "file=@/path/to/video.mp4"

# Response: {"file_id": "...", "filename": "...", ...}

# 2. เริ่ม Transcription
curl -X POST http://localhost:8001/transcribe-enhanced/start \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "<file_id>",
    "model_size": "base"
  }'

# Response: {"task_id": "...", "status": "processing", ...}

# 3. ตรวจสอบ Progress
curl http://localhost:8001/progress/<task_id>

# 4. ดึงผลลัพธ์
curl http://localhost:8001/history/transcriptions/<task_id>
```

### 2. WebSocket (Real-time Updates)

```javascript
// เชื่อมต่อ WebSocket
const ws = new WebSocket('ws://localhost:8001/ws/transcription');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Progress:', data.progress);
  console.log('Status:', data.status);
  console.log('Text:', data.text);
};

// ส่ง task_id เพื่อ subscribe
ws.send(JSON.stringify({
  task_id: '<task_id>'
}));
```

### 3. Frontend Integration

```javascript
// ตัวอย่างการใช้งานใน Frontend
async function transcribeVideo(file) {
  // 1. Upload file
  const formData = new FormData();
  formData.append('file', file);
  
  const uploadResponse = await fetch('http://localhost:8001/upload/', {
    method: 'POST',
    body: formData
  });
  const uploadData = await uploadResponse.json();
  
  // 2. Start transcription
  const transcribeResponse = await fetch('http://localhost:8001/transcribe-enhanced/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_id: uploadData.file_id,
      model_size: 'base'
    })
  });
  const transcribeData = await transcribeResponse.json();
  
  // 3. Connect WebSocket for real-time updates
  const ws = new WebSocket(`ws://localhost:8001/ws/transcription`);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateUI(data);
  };
  ws.send(JSON.stringify({ task_id: transcribeData.task_id }));
  
  return transcribeData.task_id;
}
```

### 4. Test Files

```bash
# เปิด test page ใน browser
http://localhost:8001/test-files/

# หรือใช้ test files ที่มีอยู่
# - test-staging.html
# - test-local.html
# - test-frontend.html
```

---

## 📚 API Documentation

### Main Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/upload/` | Upload video/audio file |
| `POST` | `/transcribe-enhanced/start` | Start transcription |
| `GET` | `/progress/{task_id}` | Get transcription progress |
| `GET` | `/history/transcriptions/{task_id}` | Get transcription result |
| `WS` | `/ws/transcription` | WebSocket for real-time updates |

### Whisper Service Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/models` | List available models |
| `POST` | `/transcribe` | Transcribe audio file |
| `POST` | `/download-model` | Download Whisper model |

### ตัวอย่าง Request/Response

**Upload File:**
```bash
POST /upload/
Content-Type: multipart/form-data

Response:
{
  "file_id": "uuid-here",
  "filename": "video.mp4",
  "size": 12345678,
  "content_type": "video/mp4"
}
```

**Start Transcription:**
```bash
POST /transcribe-enhanced/start
Content-Type: application/json

Request:
{
  "file_id": "uuid-here",
  "model_size": "base"
}

Response:
{
  "task_id": "task-uuid",
  "status": "processing",
  "progress": 0
}
```

**Get Progress:**
```bash
GET /progress/{task_id}

Response:
{
  "task_id": "task-uuid",
  "status": "processing",
  "progress": 45,
  "current_segment": 5,
  "total_segments": 10
}
```

---

## 🔧 การแก้ไขปัญหา

### 1. Permission Issues

```bash
# ตั้งค่า permissions ใหม่
chmod -R 755 uploads storage temp models
chmod 644 models/ggml-base.bin

# ตรวจสอบ permissions
ls -la uploads/ storage/ temp/ models/
```

### 2. Model Not Found

```bash
# ตรวจสอบว่า model มีอยู่
ls -lh models/ggml-base.bin

# ถ้าไม่มี ให้ดาวน์โหลดใหม่
./scripts/download-models.sh

# ตรวจสอบว่า Whisper service เห็น model
curl http://localhost:8002/models
```

### 3. Container ไม่ Healthy

```bash
# ตรวจสอบ logs
docker compose -f docker-compose.digitalocean.yml logs api
docker compose -f docker-compose.digitalocean.yml logs whisper

# ตรวจสอบ health check
docker ps
# ดู status ของ containers

# Restart containers
docker compose -f docker-compose.digitalocean.yml restart
```

### 4. Port Already in Use

```bash
# ตรวจสอบว่า port ถูกใช้อยู่
sudo netstat -tulpn | grep 8001
sudo netstat -tulpn | grep 8002

# แก้ไข ports ใน docker-compose.yml
# เปลี่ยน "8001:8001" เป็น "8003:8001" (ตัวอย่าง)
```

### 5. RabbitMQ Connection Failed

```bash
# ตรวจสอบ RabbitMQ
docker compose -f docker-compose.digitalocean.yml ps rabbitmq

# ตรวจสอบ environment variables
docker compose -f docker-compose.digitalocean.yml config | grep RABBITMQ

# Restart RabbitMQ
docker compose -f docker-compose.digitalocean.yml restart rabbitmq
```

### 6. Out of Memory

```bash
# ตรวจสอบ memory usage
docker stats

# ลดจำนวน workers ใน docker-compose.yml
# หรือเพิ่ม memory limit
```

---

## 📝 หมายเหตุ

### File Permissions

- **Directories:** `755` (drwxr-xr-x) - `uploads/`, `temp/`, `storage/`, `models/`
- **Files:** `644` (rw-r--r--) - ไฟล์ทั่วไป
- **Docker Volumes:** `777` (drwxrwxrwx) - สำหรับ Docker volume mount

### Performance

- **ไฟล์ 4 วินาที:** ใช้เวลาประมาณ 1-2 นาที (อัตราส่วน ~20x)
- **Model size:** ggml-base.bin = 148MB
- **Memory usage:** ประมาณ 1-2GB RAM สำหรับ Whisper service

### Network & Ports

- **API:** Port 8001 (HTTP/WebSocket)
- **Whisper:** Port 8002 (HTTP)
- **Redis:** Port 6379
- **RabbitMQ:** Port 5672 (AMQP), 15672 (Management UI)

### Cleanup

- ไฟล์ใน `temp/` จะถูกลบอัตโนมัติหลัง 24 ชั่วโมง
- ระบบรองรับ WebSocket และ Polling fallback

---

## 📞 Support

สำหรับปัญหาหรือคำถามเพิ่มเติม:
- ตรวจสอบ logs: `docker compose logs -f`
- ตรวจสอบ health: `curl http://localhost:8001/health`
- ดู test files: `http://localhost:8001/test-files/`

---

## 📄 License

[ระบุ License ตามที่ต้องการ]

---

**Last Updated:** 2024

