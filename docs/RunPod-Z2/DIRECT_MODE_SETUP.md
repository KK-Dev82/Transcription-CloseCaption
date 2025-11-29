# 🚀 Direct Mode Setup (Pod Container)

คู่มือการใช้งาน Transcription Service ใน **Direct Mode** สำหรับ RunPod Pod Container

---

## 📋 Overview

เมื่อใช้ **Custom Base Image** (`Dockerfile.runpod-base`) บน RunPod Pod Container, เราไม่สามารถใช้ Docker Compose ได้ (เพราะ Pod Container เองก็เป็น Container อยู่แล้ว)

**Direct Mode** = รัน services โดยตรงใน container เดียวกัน (ไม่ใช้ Docker Compose)

---

## 🎯 Architecture

```
┌─────────────────────────────────────────┐
│  RunPod Pod Container                   │
│  (Custom Base Image)                    │
│                                         │
│  ┌─────────────┐                       │
│  │   Redis     │  Port 6379            │
│  └─────────────┘                       │
│                                         │
│  ┌─────────────┐                       │
│  │ Whisper API │  Port 8002           │
│  └─────────────┘                       │
│                                         │
│  ┌─────────────┐                       │
│  │ Video Worker│  Background Process   │
│  └─────────────┘                       │
│                                         │
│  ┌─────────────┐                       │
│  │  Main API   │  Port 8001 (Foreground)│
│  └─────────────┘                       │
│                                         │
│  GPU: RTX 4080 (CUDA 13.0)            │
└─────────────────────────────────────────┘
```

---

## 🚀 ขั้นตอนการ Setup

### Step 1: สร้าง Custom Template ใน RunPod

1. ไปที่ RunPod Console → **"Templates"** → **"Create New Template"**
2. ตั้งค่า:
   - **Type:** `Pod`
   - **Compute Type:** `Nvidia GPU`
   - **Container Image:** `kksenateacr.azurecr.io/kk-transcription-runpod-base:latest`
   - **Registry Auth:** ตั้งค่า ACR credentials (ดู [RUNPOD_REGISTRY_AUTH_SETUP.md](./RUNPOD_REGISTRY_AUTH_SETUP.md))
   - **Container Disk:** `50 GB`
   - **HTTP Ports:** `8001,8002`
   - **TCP Ports:** `22`

### Step 2: Deploy Pod

1. ไปที่ **"Pods"** → **"Deploy"**
2. เลือก Custom Template ที่สร้างไว้
3. เลือก GPU: **RTX 4080** (แนะนำ)
4. คลิก **"Deploy"**

### Step 3: SSH เข้า Pod

```bash
ssh root@<runpod-ip> -p <port>
```

### Step 4: Clone Repository

```bash
cd /workspace
git clone <repo-url> transcription-service
```

**หมายเหตุ:** Custom Base Image จะ start services อัตโนมัติเมื่อ container เริ่มทำงาน แต่ถ้ายังไม่มี repository, container จะรอให้ clone repository ก่อน

### Step 5: ตรวจสอบ Services

```bash
# ตรวจสอบ processes
ps aux | grep -E "(python|redis)"

# ตรวจสอบ API health
curl http://localhost:8001/health

# ตรวจสอบ Whisper health
curl http://localhost:8002/health

# ตรวจสอบ Redis
redis-cli ping
```

---

## 📝 Environment Variables

สร้างไฟล์ `.env.runpod` ใน `/workspace/transcription-service/`:

```bash
# Environment Configuration
ENVIRONMENT=runpod
STORAGE_TYPE=json
JSON_STORAGE_DIR=/workspace/transcription-service/storage

# RabbitMQ Configuration
# สำหรับ Local Testing: ใช้ localhost (ผ่าน SSH Tunnel)
# สำหรับ Staging: ใช้ IP ของ Backend server
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT

# Redis Configuration (local)
REDIS_URL=redis://localhost:6379

# Whisper Configuration
WHISPER_PROVIDER=builtin
WHISPER_FALLBACK_ENABLED=false
WHISPER_API_URL=http://localhost:8002

# Groq API (optional)
GROQ_API_KEY=

# GPU Configuration
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1
```

---

## 🔧 Manual Start Services

ถ้า services ไม่ start อัตโนมัติ, สามารถ start manual ได้:

```bash
cd /workspace/transcription-service
bash scripts/pod/start-services-direct.sh
```

---

## 🧪 Testing

### Test GPU

```bash
bash scripts/pod/test-runpod-gpu.sh
```

### Test Transcription

```bash
# Upload audio file
curl -X POST http://localhost:8001/api/transcription/upload \
  -F 'file=@test_audio.wav' \
  -F 'language=th' \
  -F 'model_size=small'
```

---

## 📊 Monitoring

### Check Logs

```bash
# Whisper API logs
tail -f /tmp/whisper.log

# Video Worker logs
tail -f /tmp/video-worker.log

# Main API logs (foreground process)
# Logs จะแสดงใน console ที่รัน start-services-direct.sh
```

### Check GPU Usage

```bash
# Real-time GPU monitoring
watch -n 1 nvidia-smi
```

### Check Service Status

```bash
# Check processes
ps aux | grep -E "(python|redis)"

# Check ports
netstat -tlnp | grep -E "(8001|8002|6379)"
```

---

## ⚠️ Troubleshooting

### Issue: Services ไม่ start

**อาการ:**
- `curl http://localhost:8001/health` ไม่ตอบสนอง

**แก้ไข:**
1. ตรวจสอบว่า repository ถูก clone แล้ว:
   ```bash
   ls -la /workspace/transcription-service
   ```

2. ตรวจสอบ logs:
   ```bash
   tail -f /tmp/whisper.log
   tail -f /tmp/video-worker.log
   ```

3. Start services manual:
   ```bash
   cd /workspace/transcription-service
   bash scripts/pod/start-services-direct.sh
   ```

---

### Issue: Redis ไม่ทำงาน

**อาการ:**
- `redis-cli ping` ไม่ตอบสนอง

**แก้ไข:**
```bash
# Start Redis manual
redis-server --daemonize yes --port 6379
```

---

### Issue: Whisper API ไม่ทำงาน

**อาการ:**
- `curl http://localhost:8002/health` ไม่ตอบสนอง

**แก้ไข:**
1. ตรวจสอบ logs:
   ```bash
   tail -f /tmp/whisper.log
   ```

2. ตรวจสอบว่า models ถูก download แล้ว:
   ```bash
   ls -la /workspace/transcription-service/models/
   ```

3. Start Whisper API manual:
   ```bash
   cd /workspace/transcription-service/whisper-service
   export WHISPER_MODEL_PATH=/workspace/transcription-service/models
   python3 whisper_api.py > /tmp/whisper.log 2>&1 &
   ```

---

### Issue: GPU ไม่ถูกใช้งาน

**อาการ:**
- `nvidia-smi` แสดง "No running processes found"

**แก้ไข:**
1. ตรวจสอบว่า CUDA_VISIBLE_DEVICES ถูกตั้งค่า:
   ```bash
   echo $CUDA_VISIBLE_DEVICES
   ```

2. ตรวจสอบว่า WHISPER_CUBLAS=1:
   ```bash
   echo $WHISPER_CUBLAS
   ```

3. ตรวจสอบว่า Whisper API ใช้ CUDA:
   ```bash
   grep -i cuda /tmp/whisper.log
   ```

---

## 🔗 Related Documents

- **Custom Template Configuration:** [CUSTOM_TEMPLATE_CONFIGURATION.md](./CUSTOM_TEMPLATE_CONFIGURATION.md)
- **Registry Auth Setup:** [RUNPOD_REGISTRY_AUTH_SETUP.md](./RUNPOD_REGISTRY_AUTH_SETUP.md)
- **Scripts:** `scripts/pod/start-services-direct.sh`

---

**Last Updated:** 2024-12-19

