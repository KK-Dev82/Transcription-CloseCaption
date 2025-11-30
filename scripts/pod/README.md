# 📁 Pod Scripts (RunPod & HP Z2)

Scripts สำหรับการ Setup และ Deploy บน RunPod (Cloud GPU) และ HP Z2 Workstation (On-Premise GPU)

## 📋 Scripts

### `setup-runpod.sh`
**Setup Transcription Service บน RunPod Pod**
- ตรวจสอบ GPU และ Docker
- สร้าง directories
- สร้าง .env.runpod file
- Pull images จาก ACR
- Build Whisper GPU image
- Start services ด้วย docker-compose.runpod.yml

**Usage:**
```bash
# บน RunPod Pod
cd /workspace/transcription-service
bash scripts/pod/setup-runpod.sh
```

**Prerequisites:**
- RunPod Pod created
- SSH access to Pod
- Repository cloned to /workspace/transcription-service

---

### `start-services-direct.sh` ⭐ (แนะนำ - Direct Mode)
**Start Services โดยตรงใน Container (ไม่ใช้ Docker Compose)**
- รัน Redis, Whisper API, Video Worker, Main API ใน container เดียวกัน
- เหมาะสำหรับ Pod Container (ไม่สามารถรัน Docker-in-Docker ได้)
- ไม่ต้องใช้ Docker daemon

**Usage:**
- ใช้ใน Custom Base Image (`Dockerfile.runpod-base`) - เป็น default CMD
- Container จะ start services อัตโนมัติเมื่อมี repository แล้ว

**Environment Variables:**
- `RABBITMQ_HOST` - RabbitMQ host (default: localhost)
- `RABBITMQ_PORT` - RabbitMQ port (default: 5672)
- `REDIS_URL` - Redis URL (default: redis://localhost:6379)
- `WHISPER_PROVIDER` - Whisper provider (default: builtin)
- `GROQ_API_KEY` - Groq API key (optional)

**Architecture:**
- Redis: Port 6379 (local)
- Whisper API: Port 8002 (background)
- Video Worker: Background process
- Main API: Port 8001 (foreground)

---

### `start-runpod-services.sh` (Deprecated - ใช้ Docker Compose)
**⚠️ Deprecated:** ใช้ `start-services-direct.sh` แทน (ไม่ใช้ Docker Compose)

**Start Services ใน Custom Base Image (ใช้ Docker Compose)**
- Start Docker daemon (ถ้ายังไม่ทำงาน)
- Clone repository (ถ้ายังไม่มี)
- Login ACR และ pull images
- Build Whisper GPU image
- Start services ด้วย docker-compose.runpod.yml

**หมายเหตุ:** Script นี้ใช้ Docker Compose ซึ่งไม่เหมาะสำหรับ Pod Container

---

### `build-and-push-runpod-base.sh`
**Build และ Push Custom Base Image ไป ACR**
- Build Custom Base Image (`Dockerfile.runpod-base`)
- Tag images ด้วย version
- Push ไป ACR

**Usage:**
```bash
bash scripts/pod/build-and-push-runpod-base.sh
```

**Prerequisites:**
- Azure CLI installed
- Login ACR: `az acr login --name kksenateacr`

**Output:**
- `kksenateacr.azurecr.io/kk-transcription-runpod-base:latest`
- `kksenateacr.azurecr.io/kk-transcription-runpod-base:<version>`

---

### `stop-services.sh` ⭐ (ใหม่)
**Stop Services ทั้งหมด**
- Stop Main API, Whisper API, Video Worker, Redis
- ตรวจสอบว่า processes หยุดทำงานแล้ว

**Usage:**
```bash
bash scripts/pod/stop-services.sh
```

---

### `update-code.sh` ⭐ (ใหม่)
**อัปเดต Code บน RunPod Pod Server**
- Stop services
- Backup .env.runpod
- Pull latest code จาก Git
- Reinstall dependencies (ถ้า requirements.txt เปลี่ยน)
- Restore .env.runpod
- Start services ใหม่

**Usage:**
```bash
# อัปเดตจาก staging branch (default)
bash scripts/pod/update-code.sh

# อัปเดตจาก main branch
bash scripts/pod/update-code.sh main
```

**หมายเหตุ:** Script นี้จะ stop services ก่อน pull code และ start ใหม่หลัง pull เสร็จ

---

### `restart-pod-services.sh` ⭐ (ใหม่)
**Restart Services หลัง Start Pod ใหม่**
- ตรวจสอบ GPU
- ตรวจสอบ services ที่รันอยู่
- ตรวจสอบ project structure
- ตรวจสอบ .env.runpod (restore จาก backup ถ้ามี)
- ตรวจสอบ models
- Start services ใหม่

**Usage:**
```bash
# หลัง Start Pod ใหม่
bash scripts/pod/restart-pod-services.sh
```

**ใช้เมื่อ:**
- Pod ถูก Stop แล้ว Start ใหม่
- Services หยุดทำงาน
- ต้องการ Restart Services

---

### `setup-rabbitmq-backend.sh` ⭐ (ใหม่)
**ตั้งค่า RabbitMQ Connection ไปยัง Backend Server**
- ทดสอบ RabbitMQ connection
- สร้าง/อัปเดต .env.runpod
- แนะนำให้ restart services

**Usage:**
```bash
# ตั้งค่า RabbitMQ ไปยัง Backend Server Dev
bash scripts/pod/setup-rabbitmq-backend.sh 178.128.105.100 5672

# ตั้งค่าด้วย custom credentials
bash scripts/pod/setup-rabbitmq-backend.sh 178.128.105.100 5672 senate password
```

---

### `get-acr-credentials.sh`
**ดึง ACR Credentials สำหรับ RunPod Registry Auth**
- Enable Admin User (ถ้ายังไม่เปิด)
- ดึง Admin Username และ Password
- สร้าง Service Principal (optional)

**Usage:**
```bash
bash scripts/pod/get-acr-credentials.sh
```

**Output:**
- Admin Username และ Password (สำหรับ RunPod Registry Auth)
- Service Principal credentials (ถ้าสร้าง)

**หมายเหตุ:** ใช้ credentials เหล่านี้ใน RunPod Template → Registry Auth

---

### `healthcheck.sh`
**Health Check Script สำหรับ Custom Base Image**
- ตรวจสอบ API health (port 8001)
- ตรวจสอบ Whisper health (port 8002)

**Usage:**
- ใช้ใน Custom Base Image (`Dockerfile.runpod-base`)
- Container health check

---

### `test-runpod-gpu.sh`
**ทดสอบ GPU Performance บน RunPod**
- ตรวจสอบ GPU information
- ตรวจสอบ CUDA
- ตรวจสอบ Redis, API, Whisper health
- ตรวจสอบ running processes
- Monitor GPU usage

**Usage:**
```bash
# บน RunPod Pod
bash scripts/pod/test-runpod-gpu.sh
```

**หมายเหตุ:** Script นี้รองรับทั้ง Docker Compose และ Direct Mode

---

### `check-services.sh` ⭐
**ตรวจสอบสถานะ Services บน RunPod/Z2**
- ตรวจสอบ running processes (Redis, Whisper API, Video Worker, Main API)
- ตรวจสอบ listening ports (8001, 8002, 6379)
- ตรวจสอบ health endpoints (local)
- แสดง summary และ recommendations

**Usage:**
```bash
# บน RunPod Pod หรือ HP Z2 Workstation
bash scripts/pod/check-services.sh
```

---

### `test-health-external.sh` ⭐
**ทดสอบ Health Check จาก External (MacOS) ไปยัง RunPod**
- ทดสอบ Main API และ Whisper API
- ใช้ direct IP (205.196.17.108)
- แสดง possible reasons และ solutions

**Usage:**
```bash
# จาก MacOS (Local Machine)
bash scripts/pod/test-health-external.sh [pod-ip] [api-port] [whisper-port]

# ตัวอย่าง
bash scripts/pod/test-health-external.sh 205.196.17.108 8001 8002
```

---

### `test-health-runpod-url.sh` ⭐
**ทดสอบ Health Check ด้วย RunPod HTTP Services URL**
- ทดสอบ Main API และ Whisper API
- ใช้ RunPod HTTP Services URL (proxy.runpod.net)
- แสดง possible reasons และ solutions

**Usage:**
```bash
# จาก MacOS (Local Machine)
bash scripts/pod/test-health-runpod-url.sh [api-url] [whisper-url]

# ตัวอย่าง (ใช้ URLs จาก RunPod Connect tab)
bash scripts/pod/test-health-runpod-url.sh \
  https://xxxxx-8001.proxy.runpod.net \
  https://xxxxx-8002.proxy.runpod.net
```

---

## 🔗 Related Files

- `Dockerfile.runpod-base` - Custom Base Image สำหรับ RunPod/Z2
- `docker-compose.runpod.yml` - Docker Compose สำหรับ RunPod
- `.env.runpod` - Environment variables สำหรับ RunPod

---

## 📝 Workflow

### Option 1: ใช้ Custom Base Image (แนะนำ)

1. **Build และ Push Custom Base Image:**
   ```bash
   bash scripts/pod/build-and-push-runpod-base.sh
   ```

2. **ใช้ใน RunPod Pod Template Overrides:**
   ```
   Container Image: kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
   ```

3. **Pod จะ start services อัตโนมัติ**

---

### Option 2: ใช้ PyTorch Template (แบบเดิม)

1. **สร้าง RunPod Pod** (PyTorch 2.2.0 หรือ 2.4.0)

2. **SSH เข้า Pod และ Setup:**
   ```bash
   ssh root@<runpod-ip> -p <port>
   cd /workspace
   git clone <repo-url> transcription-service
   cd transcription-service
   bash scripts/pod/setup-runpod.sh
   ```

---

## 🖥️ สำหรับ HP Z2 Workstation

**ใช้ Custom Base Image:**
```bash
# Pull image
az acr login --name kksenateacr
docker pull kksenateacr.azurecr.io/kk-transcription-runpod-base:latest

# Run container
docker run -d \
  --name transcription-base \
  --gpus all \
  -p 8001:8001 -p 8002:8002 \
  -v $(pwd):/workspace/transcription-service \
  kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
```

**หมายเหตุ:** Z2 ต้องมี NVIDIA drivers และ nvidia-container-toolkit (ไม่ต้องติดตั้ง CUDA Toolkit แยก)

