# 📦 คู่มือการติดตั้ง Transcription Service (เสถียรที่สุด)

## 🎯 Overview

คู่มือนี้ครอบคลุมการติดตั้ง Transcription Service บน **RunPod GPU Instance** ซึ่งเป็น environment ที่เสถียรและแนะนำที่สุด

## 📋 สารบัญ

- [ข้อกำหนดระบบ](#ข้อกำหนดระบบ)
- [การติดตั้งบน RunPod](#การติดตั้งบน-runpod)
- [การตั้งค่า Environment Variables](#การตั้งค่า-environment-variables)
- [การเริ่ม Services](#การเริ่ม-services)
- [การตรวจสอบการติดตั้ง](#การตรวจสอบการติดตั้ง)
- [การใช้งาน API](#การใช้งาน-api)
- [การแก้ไขปัญหา](#การแก้ไขปัญหา)
- [การอัปเดต](#การอัปเดต)

---

## 💻 ข้อกำหนดระบบ

### RunPod Pod Requirements

- **GPU**: RTX 4070/4080/4090/5080/5090 (แนะนำ RTX 4090 ขึ้นไป)
- **RAM**: 16GB+ (แนะนำ 32GB+)
- **Storage**: 50GB+ free space
- **Container Image**: 
  - `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` (สำหรับ RTX 5080/5090)
  - `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` (สำหรับ RTX 4070/4080/4090)
- **Ports**: 
  - `8010` - API Server (HTTP Expose)
  - `8020` - Webhook Server (HTTP Expose, optional)
  - `8030` - Monitoring Dashboard (HTTP Expose, optional)

### Software Requirements

- **Python**: 3.11+
- **Docker**: (ไม่จำเป็น - ใช้ scripts แทน)
- **Git**: สำหรับ clone repository

---

## 🚀 การติดตั้งบน RunPod

### Step 1: สร้าง RunPod Pod

1. ไปที่ [RunPod Dashboard](https://www.runpod.io/)
2. คลิก **"Pods"** → **"New Pod"**
3. เลือก GPU Template:
   - **RTX 5080/5090**: `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`
   - **RTX 4070/4080/4090**: `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`
4. ตั้งค่า **Container Overrides**:
   - **Expose Ports**: `8010, 8020, 8030`
   - **Volume Mounts**: `/workspace` (persistent storage)
5. คลิก **"Deploy"**

### Step 2: เชื่อมต่อ Pod

```bash
# ใช้ RunPod Terminal หรือ SSH
# ตรวจสอบว่าเชื่อมต่อสำเร็จ
pwd
# ควรเห็น: /workspace
```

### Step 3: Clone Repository

```bash
cd /workspace

# Clone repository
git clone <repository-url> transcription-service
cd transcription-service

# ตรวจสอบว่า clone สำเร็จ
ls -la
```

### Step 4: Setup Pod (ครั้งแรก)

```bash
# รัน setup script (จะสร้าง directories, .env.runpod, ตรวจสอบ dependencies)
bash scripts/pod/setup-pod.sh
```

**สิ่งที่ script จะทำ:**
- ✅ สร้าง directories ที่จำเป็น (`uploads/`, `storage/`, `temp/`, `models/`)
- ✅ สร้างไฟล์ `.env.runpod` (ถ้ายังไม่มี)
- ✅ ตรวจสอบ Python dependencies
- ✅ ตรวจสอบ Whisper models
- ✅ Download models ถ้ายังไม่มี

### Step 5: ตั้งค่า Environment Variables

ตรวจสอบและแก้ไขไฟล์ `.env.runpod`:

```bash
cat .env.runpod
```

**ไฟล์ `.env.runpod` ควรมี:**

```bash
# Environment
ENVIRONMENT=runpod
STORAGE_TYPE=json
JSON_STORAGE_DIR=/workspace/transcription-service/storage

# RabbitMQ (ปรับตาม environment ของคุณ)
RABBITMQ_HOST=178.128.105.100
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT

# Redis (ใช้ local container)
REDIS_URL=redis://localhost:6379

# Whisper API
WHISPER_API_URL=http://localhost:8002

# Provider Configuration
WHISPER_PROVIDER=faster-whisper
WHISPER_FALLBACK_ENABLED=false

# API Configuration
API_WORKERS=1
API_PORT=8010

# Worker Configuration
WORKER_CONCURRENCY=1
```

**⚠️ สำคัญ:**
- `RABBITMQ_HOST`: ใช้ IP address ของ RabbitMQ server (ไม่ใช่ localhost)
- `API_PORT`: ตั้งเป็น `8010` (ตรงกับ RunPod HTTP Expose)
- `API_WORKERS`: ตั้งเป็น `1` สำหรับ debugging, `2-4` สำหรับ production

---

## 🎬 การเริ่ม Services

### วิธีที่ 1: ใช้ Script (แนะนำ)

```bash
# Start services ทั้งหมด (Redis, Whisper API, Video Worker, Main API)
bash scripts/pod/start-pod.sh
```

**สิ่งที่ script จะทำ:**
- ✅ ตรวจสอบ GPU
- ✅ สร้าง directories ที่จำเป็น
- ✅ Load environment variables จาก `.env.runpod`
- ✅ Start Redis (ถ้ายังไม่รัน)
- ✅ Start Whisper API service
- ✅ Start Video Worker
- ✅ Start Main API service

### วิธีที่ 2: ใช้ nohup (สำหรับ background)

```bash
# Start services ด้วย nohup (รันใน background)
bash scripts/start-all-nohup.sh

# ตรวจสอบ logs
tail -f logs/api.log
tail -f logs/worker.log
```

### วิธีที่ 3: Start แยก Services

```bash
# Start Redis
redis-server --daemonize yes

# Start Whisper API (ใน terminal แยก)
cd /workspace/transcription-service
source .env.runpod
python3 -m uvicorn app.services.whisper_service:app --host 0.0.0.0 --port 8002 &

# Start Video Worker (ใน terminal แยก)
cd /workspace/transcription-service
source .env.runpod
python3 -m app.workers.sync.video_worker &

# Start Main API (ใน terminal แยก)
cd /workspace/transcription-service
source .env.runpod
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --workers 1 &
```

---

## ✅ การตรวจสอบการติดตั้ง

### 1. ตรวจสอบ Services Status

```bash
# ใช้ check script
bash scripts/pod/check-pod.sh
```

**Output ที่ควรเห็น:**
```
✅ Redis: Running
✅ Whisper API: Running (http://localhost:8002)
✅ Video Worker: Running
✅ Main API: Running (http://localhost:8010)
```

### 2. ตรวจสอบ Health Endpoints

```bash
# Main API Health
curl http://localhost:8010/health
# ควรเห็น: {"status":"healthy",...}

# Whisper API Health
curl http://localhost:8002/health
# ควรเห็น: {"status":"healthy","service":"whisper-transcription"}

# ตรวจสอบ Models
curl http://localhost:8002/models
# ควรเห็น JSON ที่มี models ในรายการ
```

### 3. ตรวจสอบ GPU

```bash
nvidia-smi
# ควรเห็น GPU information
```

### 4. ตรวจสอบ Logs

```bash
# ดู logs ทั้งหมด
bash scripts/pod/logs-pod.sh

# ดู logs แยกตาม service
bash scripts/pod/logs-pod.sh api          # Main API
bash scripts/pod/logs-pod.sh whisper      # Whisper API
bash scripts/pod/logs-pod.sh worker       # Video Worker

# ดู logs real-time
tail -f /tmp/main-api.log
tail -f /tmp/whisper.log
tail -f /tmp/video-worker.log
```

### 5. ทดสอบ Transcription

```bash
# Download test video (ถ้ายังไม่มี)
bash scripts/pod/download-tool.sh video https://example.com/video.mp4

# Test transcription
bash scripts/pod/test-transcription.sh uploads/video.mp4 medium
```

---

## 📡 การใช้งาน API

### API Base URLs

```
API Server:     https://<pod-id>-8010.proxy.runpod.net/
Webhook Server: https://<pod-id>-8020.proxy.runpod.net/ (optional)
Monitoring:     https://<pod-id>-8030.proxy.runpod.net/ (optional)
```

### 1. Upload File

```bash
curl -X POST 'https://<pod-id>-8010.proxy.runpod.net/api/upload/' \
  -F "file=@/path/to/video.mp4"
```

**Response:**
```json
{
  "file_path": "uploads/video.mp4",
  "file_name": "video.mp4",
  "size": 12345678
}
```

### 2. Upload from URL

```bash
curl -X POST 'https://<pod-id>-8010.proxy.runpod.net/api/upload/' \
  -F "url=https://example.com/video.mp4"
```

### 3. Start Transcription

```bash
curl -X POST 'https://<pod-id>-8010.proxy.runpod.net/api/transcribe/' \
  -H 'Content-Type: application/json' \
  -d '{
    "file_path": "uploads/video.mp4",
    "language": "th",
    "model_size": "base",
    "callback_url": "https://your-backend.com/webhook"
  }'
```

**หรือใช้ file_url โดยตรง:**

```bash
curl -X POST 'https://<pod-id>-8010.proxy.runpod.net/api/transcribe/' \
  -H 'Content-Type: application/json' \
  -d '{
    "file_url": "https://example.com/video.mp4",
    "language": "th",
    "model_size": "base",
    "callback_url": "https://your-backend.com/webhook"
  }'
```

**Response:**
```json
{
  "task_id": "6524ca67-0645-4a82-bdcb-766fc3949e13",
  "status": "processing",
  "progress": 0
}
```

### 4. Check Task Status

```bash
curl 'https://<pod-id>-8010.proxy.runpod.net/api/tasks/{task_id}'
```

**Response:**
```json
{
  "task_id": "6524ca67-0645-4a82-bdcb-766fc3949e13",
  "status": "completed",
  "progress": 100,
  "file_path": "uploads/video.mp4",
  "language": "th",
  "model_size": "base",
  "created_at": "2025-12-18T20:15:14.158982+00:00",
  "completed_at": "2025-12-18T20:20:09.954525+00:00",
  "full_text": "ข้อความที่แปลงแล้ว...",
  "chunks": [...],
  "chunks_count": 135
}
```

### 5. Webhook Callback

เมื่อ transcription เสร็จ Worker จะส่ง POST ไปยัง `callback_url`:

```json
{
  "task_id": "6524ca67-0645-4a82-bdcb-766fc3949e13",
  "status": "completed",
  "progress": 100,
  "file_path": "uploads/video.mp4",
  "file_name": null,
  "language": "th",
  "model_size": "base",
  "created_at": "2025-12-18T20:15:14.158982+00:00",
  "updated_at": "2025-12-18T20:20:09.974155+00:00",
  "completed_at": "2025-12-18T20:20:09.954525+00:00",
  "full_text": "ข้อความที่แปลงแล้ว...",
  "chunks": [
    {
      "start_time": 0.0,
      "end_time": 4.36,
      "text": "ข้อความ...",
      "confidence": null
    }
  ],
  "chunks_count": 135,
  "error_message": null,
  "current_stage": null,
  "current_stage_description": null,
  "total_duration": 0
}
```

---

## 🔧 การแก้ไขปัญหา

### 1. Services ไม่ Start

```bash
# ตรวจสอบ status
bash scripts/pod/check-pod.sh

# Restart services
bash scripts/pod/restart-pod.sh

# ดู logs
bash scripts/pod/logs-pod.sh
```

### 2. Port Already in Use

```bash
# ตรวจสอบว่า port ถูกใช้อยู่
sudo netstat -tulpn | grep 8010
sudo netstat -tulpn | grep 8002

# Kill process ที่ใช้ port
sudo kill -9 <PID>

# หรือแก้ไข port ใน .env.runpod
# API_PORT=8011
```

### 3. RabbitMQ Connection Failed

```bash
# ตรวจสอบ .env.runpod
cat .env.runpod | grep RABBITMQ

# ทดสอบ connection
python3 -c "
import pika
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host='178.128.105.100',
        port=5672,
        credentials=pika.PlainCredentials('senate', 'qP2VtHz6fAX4xDksEpMrLT')
    )
)
print('✅ RabbitMQ connection successful')
connection.close()
"
```

### 4. Model Not Found

```bash
# ตรวจสอบว่า model มีอยู่
ls -lh ~/.cache/whisper/

# Download model
python3 -c "import whisper; whisper.load_model('base')"
# หรือ
python3 -c "import whisper; whisper.load_model('medium')"
```

### 5. GPU Not Available

```bash
# ตรวจสอบ GPU
nvidia-smi

# ตรวจสอบ CUDA
python3 -c "import torch; print(torch.cuda.is_available())"
# ควรเห็น: True
```

### 6. Multiple Workers Issue

```bash
# ตรวจสอบ workers
bash scripts/pod/check-pod.sh

# Stop และ start ใหม่
bash scripts/pod/restart-pod.sh

# หรือ kill workers ที่ซ้ำ
pkill -f video_worker
pkill -f whisper_service
```

### 7. Out of Memory

```bash
# ตรวจสอบ memory usage
free -h
nvidia-smi

# ลด concurrency ใน .env.runpod
# WORKER_CONCURRENCY=1
# API_WORKERS=1
```

### 8. Python Cache Issues

```bash
# Clear Python cache
find . -type d -name "__pycache__" -exec rm -r {} +
find . -name "*.pyc" -delete

# Restart services
bash scripts/pod/restart-pod.sh
```

---

## 🔄 การอัปเดต

### 1. อัปเดต Code

```bash
cd /workspace/transcription-service

# Pull latest code
git pull origin main

# Clear Python cache
find . -type d -name "__pycache__" -exec rm -r {} +

# Restart services
bash scripts/pod/restart-pod.sh
```

### 2. อัปเดต Dependencies

```bash
# Install new dependencies
pip3 install -r requirements.txt

# Restart services
bash scripts/pod/restart-pod.sh
```

### 3. อัปเดต Environment Variables

```bash
# แก้ไข .env.runpod
nano .env.runpod

# Reload environment และ restart
bash scripts/pod/restart-pod.sh
```

---

## 📚 เอกสารเพิ่มเติม

- [Postman Guide](./POSTMAN_GUIDE.md) - คู่มือการทดสอบด้วย Postman
- [Quick Start Guide](./QUICK_START.md) - คู่มือเริ่มต้นใช้งาน
- [React Guide](./REACT_GUIDE.md) - คู่มือการใช้งานกับ React
- [Testing Guide](./TESTING_GUIDE.md) - คู่มือการทดสอบ
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - คู่มือแก้ไขปัญหา

---

## 🎯 Quick Reference

### Commands ที่ใช้บ่อย

```bash
# Start services
bash scripts/pod/start-pod.sh

# Stop services
bash scripts/pod/stop-pod.sh

# Restart services
bash scripts/pod/restart-pod.sh

# Check status
bash scripts/pod/check-pod.sh

# View logs
bash scripts/pod/logs-pod.sh

# Test transcription
bash scripts/pod/test-transcription.sh uploads/video.mp4 medium

# View results
bash scripts/pod/result-view.sh <task-id>
```

### File Locations

- **Logs**: `/tmp/main-api.log`, `/tmp/whisper.log`, `/tmp/video-worker.log`
- **Config**: `.env.runpod`
- **Models**: `~/.cache/whisper/` (faster-whisper)
- **Videos**: `uploads/`
- **Storage**: `storage/transcriptions/`

### Ports

- **8010**: Main API Server
- **8002**: Whisper API Service
- **6379**: Redis (local)
- **5672**: RabbitMQ (external)

---

## 📞 Support

สำหรับปัญหาหรือคำถามเพิ่มเติม:
- ตรวจสอบ logs: `bash scripts/pod/logs-pod.sh`
- ตรวจสอบ health: `curl http://localhost:8010/health`
- ดู test files: `http://localhost:8010/test-files/`

---

**Last Updated:** 2025-12-18  
**Version:** 1.0.0 (Stable)

