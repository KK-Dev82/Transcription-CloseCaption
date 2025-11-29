# 🖥️ HP Z2 Workstation Setup

คู่มือการ Setup Transcription Service บน HP Z2 Workstation (On-Premise GPU)

---

## 📋 Overview

HP Z2 Workstation สามารถใช้ **Direct Mode** เหมือน RunPod ได้ โดยใช้ script เดียวกัน

**ความแตกต่าง:**
- **RunPod:** Pod Container → Custom Base Image → Direct Mode
- **Z2:** Ubuntu 22.04 → Direct Mode (ไม่จำเป็นต้องใช้ Custom Base Image)

---

## ✅ Prerequisites

### 1. System Requirements

- **OS:** Ubuntu 22.04 (แนะนำ)
- **GPU:** NVIDIA GPU (RTX 4080/4090 หรือเทียบเท่า)
- **RAM:** 16GB+ (แนะนำ 32GB)
- **Storage:** 50GB+ free space

### 2. Software Requirements

**NVIDIA Drivers:**
```bash
# ตรวจสอบ
nvidia-smi

# ถ้ายังไม่มี ติดตั้ง:
sudo apt-get update
sudo apt-get install -y nvidia-driver-535  # หรือ version ล่าสุด
sudo reboot
```

**Python 3.10+:**
```bash
# ตรวจสอบ
python3 --version

# ติดตั้ง (ถ้ายังไม่มี)
sudo apt-get install -y python3 python3-pip
```

**System Dependencies:**
```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    redis-server \
    ffmpeg \
    tzdata
```

---

## 🚀 Setup Steps

### Step 1: Clone Repository

```bash
cd /workspace  # หรือ directory อื่น
git clone <repo-url> transcription-service
cd transcription-service
git checkout staging  # หรือ branch ที่ต้องการ
```

### Step 2: Install Python Dependencies

```bash
cd /workspace/transcription-service
pip3 install --no-cache-dir -r requirements.txt
```

### Step 3: Download Whisper Models

```bash
cd /workspace/transcription-service/whisper-service
bash models/download-ggml-model.sh base
cp models/ggml-base.bin ../models/
```

### Step 4: Create Environment File

```bash
cd /workspace/transcription-service
cat > .env.runpod << EOF
# Environment Configuration
ENVIRONMENT=production
STORAGE_TYPE=json
JSON_STORAGE_DIR=/workspace/transcription-service/storage

# RabbitMQ Configuration
RABBITMQ_HOST=10.200.22.61  # Backend server IP
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Whisper Configuration
WHISPER_PROVIDER=builtin
WHISPER_FALLBACK_ENABLED=false
WHISPER_API_URL=http://localhost:8002

# GPU Configuration
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1
EOF
```

### Step 5: Start Services

```bash
cd /workspace/transcription-service
bash scripts/pod/start-services-direct.sh
```

---

## 🔧 Optional: ใช้ Custom Base Image (ไม่จำเป็น)

ถ้าต้องการใช้ Custom Base Image (เหมือน RunPod):

### Step 1: Pull Custom Base Image

```bash
# Login ACR
az acr login --name kksenateacr

# Pull image
docker pull kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
```

### Step 2: Run Container

```bash
docker run -d \
  --name transcription-z2 \
  --gpus all \
  -v /workspace/transcription-service:/workspace/transcription-service \
  -p 8001:8001 \
  -p 8002:8002 \
  -p 6379:6379 \
  kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
```

### Step 3: Clone Repository ใน Container

```bash
docker exec -it transcription-z2 bash
cd /workspace
git clone <repo-url> transcription-service
cd transcription-service
bash scripts/pod/start-services-direct.sh
```

**หมายเหตุ:** วิธีนี้ไม่จำเป็น เพราะ Z2 สามารถรัน Direct Mode ได้โดยตรง

---

## 🔄 Auto-start Services (Systemd Service)

สร้าง systemd service เพื่อ auto-start services เมื่อ boot:

### Step 1: Create Service File

```bash
sudo nano /etc/systemd/system/transcription-service.service
```

**Content:**
```ini
[Unit]
Description=Transcription Service
After=network.target redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/workspace/transcription-service
Environment="PYTHONPATH=/workspace/transcription-service"
ExecStart=/usr/bin/bash /workspace/transcription-service/scripts/pod/start-services-direct.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Step 2: Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable transcription-service
sudo systemctl start transcription-service
```

### Step 3: Check Status

```bash
sudo systemctl status transcription-service
sudo journalctl -u transcription-service -f
```

---

## 📊 Monitoring

### Check Services

```bash
# Check processes
ps aux | grep -E "(python|redis)"

# Check health
curl http://localhost:8001/health
curl http://localhost:8002/health
redis-cli ping

# Check GPU
nvidia-smi
watch -n 1 nvidia-smi
```

### Check Logs

```bash
# Service logs (ถ้าใช้ systemd)
sudo journalctl -u transcription-service -f

# Direct logs
tail -f /tmp/whisper.log
tail -f /tmp/video-worker.log
```

---

## 🔄 Update Code

```bash
cd /workspace/transcription-service
bash scripts/pod/update-code.sh staging
```

---

## ⚠️ Troubleshooting

### Issue: GPU not detected

**แก้ไข:**
```bash
# ตรวจสอบ NVIDIA drivers
nvidia-smi

# ตรวจสอบ CUDA
python3 -c "import torch; print(torch.cuda.is_available())"
```

### Issue: Services not starting

**แก้ไข:**
```bash
# ตรวจสอบ logs
tail -f /tmp/whisper.log
tail -f /tmp/video-worker.log

# ตรวจสอบ dependencies
pip3 list | grep -E "(aiofiles|pika|redis|pythainlp)"
```

---

## 🔗 Related Documents

- **Direct Mode Setup:** [DIRECT_MODE_SETUP.md](./DIRECT_MODE_SETUP.md)
- **FAQ:** [FAQ.md](./FAQ.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

---

**Last Updated:** 2024-12-19

