# Local Direct Mode Testing Guide

## ภาพรวม

Local Direct Mode เป็นการทดสอบ transcription service บน local machine (MacOS/Linux) โดยใช้แนวทางเดียวกับ RunPod:
- Build Container (ไม่ใช้ CUDA)
- Clone Git repository
- Start services แบบ Direct mode (ไม่ใช้ Docker Compose)

## ข้อดี

1. **ทดสอบได้ง่าย**: ไม่ต้องใช้ GPU หรือ CUDA
2. **เหมือน RunPod**: ใช้ workflow เดียวกัน ทำให้ทดสอบได้ก่อน deploy
3. **Debug ง่าย**: เข้า container และดู logs ได้โดยตรง
4. **ไม่กระทบ Production**: แยกจาก containers เดิม

## ขั้นตอนการ Setup

### 1. Stop Transcription Containers เดิม

```bash
bash scripts/local/stop-transcription-containers.sh
```

หรือ stop manually:
```bash
docker stop transcription-api-local transcription-whisper-local transcription-whisper-live-local transcription-redis-local
```

### 2. Setup Local Direct Mode

```bash
bash scripts/local/setup-local-direct.sh
```

Script นี้จะ:
- Stop containers เดิม
- Build base image (`Dockerfile.local-base`)
- Start container (`transcription-local-base`)
- Setup dependencies และ environment

### 3. เข้า Container และ Start Services

```bash
# เข้า container
docker exec -it transcription-local-base bash

# ภายใน container
cd /workspace/transcription-service

# Setup (ถ้ายังไม่ได้ setup)
bash scripts/pod/setup-pod.sh

# Start services
bash scripts/pod/start-pod.sh
```

### 4. ตรวจสอบ Status

```bash
# ภายใน container
bash scripts/pod/check-pod.sh

# ดู logs
bash scripts/pod/logs-pod.sh
```

## การใช้งาน

### Start Services

```bash
# ภายใน container
bash scripts/pod/start-pod.sh
```

### Stop Services

```bash
# ภายใน container
bash scripts/pod/stop-pod.sh
```

### Restart Services

```bash
# ภายใน container
bash scripts/pod/restart-pod.sh
```

### ดู Logs

```bash
# ภายใน container
bash scripts/pod/logs-pod.sh          # ทั้งหมด
bash scripts/pod/logs-pod.sh api     # Main API
bash scripts/pod/logs-pod.sh worker  # Video Worker
bash scripts/pod/logs-pod.sh whisper # Whisper API
```

### ทดสอบ Transcription

```bash
# ภายใน container
bash scripts/pod/test-transcription.sh uploads/test.mp4 base
```

## Configuration

### RabbitMQ

Container จะเชื่อมต่อกับ RabbitMQ บน host machine ผ่าน `host.docker.internal:5672`

ถ้า RabbitMQ อยู่ที่อื่น ให้แก้ไข `.env.runpod`:
```bash
RABBITMQ_HOST=<your-rabbitmq-host>
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT
```

### Redis

Redis จะรันภายใน container (port 6379)

### Storage

Storage จะถูก mount จาก host:
- `./storage` → `/workspace/transcription-service/storage`
- `./uploads` → `/workspace/transcription-service/uploads`
- `./temp` → `/workspace/transcription-service/temp`
- `./models` → `/workspace/transcription-service/models`

## Troubleshooting

### Container ไม่ start

```bash
# ตรวจสอบ logs
docker logs transcription-local-base

# ตรวจสอบ status
docker ps -a | grep transcription-local-base
```

### Services ไม่ start

```bash
# ตรวจสอบ dependencies
python3 -c "import aiofiles; print('OK')"

# Install dependencies ใหม่
pip3 install --no-cache-dir -r requirements.txt
```

### RabbitMQ Connection Failed

```bash
# ตรวจสอบ RabbitMQ บน host
# MacOS: docker ps | grep rabbitmq
# หรือตรวจสอบ network connectivity

# Test connection จาก container
docker exec -it transcription-local-base bash -c "nc -zv host.docker.internal 5672"
```

### Port Already in Use

```bash
# ตรวจสอบ ports ที่ใช้
lsof -i :8001
lsof -i :8002
lsof -i :6379

# Stop services ที่ใช้ ports เหล่านี้
```

## Cleanup

### Stop Container

```bash
docker stop transcription-local-base
```

### Remove Container

```bash
docker rm transcription-local-base
```

### Remove Image

```bash
docker rmi kk-transcription-local-base:latest
```

## เปรียบเทียบกับ RunPod

| Feature | Local Direct Mode | RunPod |
|---------|------------------|--------|
| GPU | ❌ ไม่มี | ✅ มี (RTX 4080) |
| CUDA | ❌ ไม่ใช้ | ✅ ใช้ |
| Base Image | Ubuntu 22.04 | CUDA 12.1.0 |
| Workflow | เหมือนกัน | เหมือนกัน |
| Scripts | ใช้ scripts/pod/* | ใช้ scripts/pod/* |

## หมายเหตุ

- Local Direct Mode **ไม่ใช้ GPU** ดังนั้น transcription จะช้ากว่า RunPod
- ใช้สำหรับทดสอบ workflow และ debugging
- สำหรับ production testing ควรใช้ RunPod หรือ HP Z2

