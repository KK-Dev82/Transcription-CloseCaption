# 📋 Checklist สำหรับ Deploy ไปยัง GPU Pod

## ✅ สิ่งที่ต้องตรวจสอบและปรับเปลี่ยนก่อน Pull ลง Pod

### 1. RabbitMQ Configuration ⚠️ **สำคัญที่สุด**

**Local (MacOS):**
```bash
RABBITMQ_HOST=host.docker.internal
```

**Pod GPU Server:**
```bash
RABBITMQ_HOST=178.128.105.100
```

**วิธีแก้ไข:**
- ใช้ `scripts/pod/setup-pod.sh` (จะตรวจสอบและแก้ไขอัตโนมัติ)
- หรือแก้ไข `.env.runpod` โดยตรง:
  ```bash
  sed -i 's/RABBITMQ_HOST=.*/RABBITMQ_HOST=178.128.105.100/' .env.runpod
  ```

### 2. Environment Variables ที่ต้องตั้งค่า

**`.env.runpod` บน Pod ควรมี:**

```bash
# RabbitMQ Configuration (Backend Server)
RABBITMQ_HOST=178.128.105.100
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT

# Whisper Provider
WHISPER_PROVIDER=openai-whisper  # หรือ builtin สำหรับ whisper.cpp
WHISPER_MODEL=large-v3            # สำหรับ GPU ใช้ large-v3
WHISPER_DEVICE=auto              # จะ auto-detect CUDA

# Parallel Processing (ใหม่)
WHISPER_USE_THREAD_LOCAL=true    # สำหรับ parallel processing
TRANSCRIPTION_MAX_WORKERS=5       # จำนวน workers (ปรับตาม GPU memory)
TRANSCRIPTION_PREFETCH_COUNT=20  # จำนวน messages ที่ pre-fetch

# GPU Configuration
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1

# Storage
STORAGE_TYPE=json
JSON_STORAGE_DIR=/workspace/transcription-service/storage

# Redis
REDIS_URL=redis://localhost:6379

# Environment
ENVIRONMENT=runpod
```

### 3. Endpoints ที่ต้องตรวจสอบ

**ไม่มี Endpoints ที่ต้องเปลี่ยน** - ทั้งหมดใช้ relative paths หรือ localhost:
- Main API: `http://localhost:8001` (ภายใน Pod)
- Whisper API: `http://localhost:8002` (ภายใน Pod)
- Redis: `redis://localhost:6379` (ภายใน Pod)

**RabbitMQ:** ใช้ IP `178.128.105.100` (ไม่ใช่ localhost)

### 4. Code Changes ที่ต้อง Pull

**ไฟล์ที่ถูกแก้ไข:**
- ✅ `app/services/whisper_providers/openai_whisper_provider.py`
  - เพิ่ม thread-local model support
  - รองรับ parallel และ sequential processing
  
- ✅ `app/workers/video_worker.py`
  - ThreadPoolExecutor สำหรับ parallel chunk processing
  - รองรับ `TRANSCRIPTION_MAX_WORKERS` และ `TRANSCRIPTION_PREFETCH_COUNT`

- ✅ `scripts/pod/start-pod.sh`
  - Auto-detect และ export environment variables
  - Default RabbitMQ host: `178.128.105.100`

### 5. Scripts ที่ต้องรันบน Pod

**Step 1: Clone และ Setup**
```bash
cd /workspace
git clone <repo-url> transcription-service
cd transcription-service
git pull  # Pull latest changes
bash scripts/pod/setup-pod.sh
```

**Step 2: ตรวจสอบ Configuration**
```bash
# ตรวจสอบ .env.runpod
cat .env.runpod | grep -E 'RABBITMQ|WHISPER|TRANSCRIPTION'

# ตรวจสอบ RabbitMQ connection
bash scripts/pod/check-rabbitmq-queue.sh
```

**Step 3: Start Services**
```bash
bash scripts/pod/start-pod.sh
```

**Step 4: ตรวจสอบ Status**
```bash
bash scripts/pod/check-pod.sh
```

### 6. Testing Checklist

- [ ] RabbitMQ connection ทำงาน (`check-rabbitmq-queue.sh`)
- [ ] Video Worker ทำงาน (`pgrep -f video_worker`)
- [ ] Main API ทำงาน (`curl http://localhost:8001/health`)
- [ ] GPU ถูกใช้งาน (`nvidia-smi`)
- [ ] Parallel processing ทำงาน (ดู logs: `tail -f /tmp/video-worker.log`)
- [ ] Transcription ทำงาน (`test-transcription.sh`)

## 🚀 Quick Start สำหรับ Pod

```bash
# 1. SSH เข้า Pod
ssh root@<pod-ip> -p <port>

# 2. ไปที่ project directory
cd /workspace/transcription-service

# 3. Pull latest changes
git pull

# 4. Setup (จะตรวจสอบและแก้ไข .env.runpod อัตโนมัติ)
bash scripts/pod/setup-pod.sh

# 5. ตรวจสอบ configuration
cat .env.runpod | grep -E 'RABBITMQ_HOST|WHISPER_PROVIDER|WHISPER_USE_THREAD_LOCAL'

# 6. Restart services (ถ้ามีการเปลี่ยนแปลง)
bash scripts/pod/restart-pod.sh

# 7. ตรวจสอบ status
bash scripts/pod/check-pod.sh

# 8. ทดสอบ transcription
bash scripts/pod/test-transcription.sh uploads/test.mp4 base
```

## ⚠️ สิ่งที่ต้องระวัง

### 1. RabbitMQ Host
- ❌ **อย่าใช้** `localhost` หรือ `host.docker.internal` บน Pod
- ✅ **ต้องใช้** `178.128.105.100` (Backend Server IP)

### 2. GPU Memory
- ตรวจสอบ GPU memory ก่อนตั้งค่า `TRANSCRIPTION_MAX_WORKERS`
- RTX 4080 Super 16GB → ใช้ `TRANSCRIPTION_MAX_WORKERS=5-8`
- ถ้า GPU memory น้อย → ลด `TRANSCRIPTION_MAX_WORKERS` หรือใช้ `WHISPER_USE_THREAD_LOCAL=false`

### 3. Model Size
- `base` model → ใช้ memory น้อย → สามารถใช้ parallel processing ได้มาก
- `large-v3` model → ใช้ memory มาก → ต้องระวัง GPU memory

### 4. Environment Variables
- ตรวจสอบว่า `.env.runpod` มี newlines ระหว่าง variables (ไม่ใช่ต่อกัน)
- ใช้ `scripts/pod/setup-pod.sh` เพื่อสร้าง `.env.runpod` ที่ถูกต้อง

## 📝 Summary

**สิ่งที่ต้องเปลี่ยน:**
1. ✅ `RABBITMQ_HOST`: `host.docker.internal` → `178.128.105.100`
2. ✅ เพิ่ม `WHISPER_USE_THREAD_LOCAL=true` (สำหรับ parallel processing)
3. ✅ เพิ่ม `TRANSCRIPTION_MAX_WORKERS` และ `TRANSCRIPTION_PREFETCH_COUNT` (optional)

**สิ่งที่ไม่ต้องเปลี่ยน:**
- ❌ API Endpoints (ใช้ localhost ภายใน Pod)
- ❌ Redis URL (ใช้ localhost ภายใน Pod)
- ❌ Port numbers (8001, 8002, 6379)

**Scripts ที่ช่วย:**
- `scripts/pod/setup-pod.sh` - Setup และตรวจสอบ configuration
- `scripts/pod/start-pod.sh` - Start services พร้อม environment variables
- `scripts/pod/check-pod.sh` - ตรวจสอบ status ของ services
- `scripts/pod/check-rabbitmq-queue.sh` - ตรวจสอบ RabbitMQ connection

