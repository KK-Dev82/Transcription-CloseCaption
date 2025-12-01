# 🚀 Quick Start: Local Docker Testing (Mac)

คู่มือสำหรับทดสอบ Parallel Processing บน Local Docker (MacOS)

## 📋 Prerequisites

1. **Docker Desktop** ต้องเปิดอยู่
2. **RabbitMQ** ต้องรันอยู่บน Mac (หรือใช้ Backend Dev Server)
3. **Video file** สำหรับทดสอบ (ใน `uploads/` directory)

## 🎯 Quick Start (3 ขั้นตอน)

### Step 1: Setup (ครั้งแรกเท่านั้น)

```bash
# Build image และ setup container
bash scripts/local/setup-local-direct.sh
```

**หมายเหตุ:** Script นี้จะ:
- Build `kk-transcription-local-base` image
- Start container `transcription-local-base`
- Setup dependencies และ environment

### Step 2: Start Services

```bash
# Start services (Main API, Whisper API, Video Worker, Redis)
bash scripts/local/start-local.sh
```

**หมายเหตุ:** Script นี้จะ:
- ตรวจสอบ Docker และ container
- Start services ภายใน container
- แสดงคำสั่งที่มีประโยชน์

### Step 3: Test Transcription

```bash
# ทดสอบ transcription
bash scripts/local/test-local.sh uploads/test.mp4 base 30
```

**หมายเหตุ:** 
- `base` = model size (tiny, base, small, medium, large, large-v3)
- `30` = chunk duration (วินาที)

## 📊 Monitor Progress

### View Logs

```bash
# View all logs
bash scripts/local/logs-local.sh

# View specific service
bash scripts/local/logs-local.sh worker

# Real-time logs (inside container)
docker exec -it transcription-local-base bash -c 'tail -f /tmp/video-worker.log'
```

### Check Status

```bash
# Check services status
docker exec -it transcription-local-base bash -c 'cd /workspace/transcription-service && bash scripts/pod/check-pod.sh'
```

### Check RabbitMQ Queue

```bash
# Check queue status
docker exec -it transcription-local-base bash -c 'cd /workspace/transcription-service && bash scripts/pod/check-rabbitmq-queue.sh transcription_chunk_queue'
```

## 🔧 Useful Commands

### Restart Services

```bash
# Restart services (เมื่อมีการแก้ไข code)
bash scripts/local/restart-local.sh
```

### Stop Services

```bash
# Stop services
bash scripts/local/stop-local.sh
```

### Enter Container

```bash
# Enter container เพื่อ debug
docker exec -it transcription-local-base bash

# Inside container
cd /workspace/transcription-service
bash scripts/pod/check-pod.sh
bash scripts/pod/test-transcription.sh uploads/test.mp4 base
```

### View Results

```bash
# View transcription results
docker exec -it transcription-local-base bash -c 'cd /workspace/transcription-service && bash scripts/pod/result-view.sh -detail 5'
```

## 🐛 Troubleshooting

### Container ไม่ start

```bash
# ตรวจสอบ Docker
docker info

# ตรวจสอบ container
docker ps -a | grep transcription-local-base

# ดู logs
docker logs transcription-local-base
```

### Services ไม่ start

```bash
# ตรวจสอบ logs
bash scripts/local/logs-local.sh

# Check status
docker exec -it transcription-local-base bash -c 'cd /workspace/transcription-service && bash scripts/pod/check-pod.sh'
```

### RabbitMQ Connection Error

```bash
# ตรวจสอบ RabbitMQ connection
docker exec -it transcription-local-base bash -c 'nc -zv host.docker.internal 5672'

# ตรวจสอบ environment variables
docker exec -it transcription-local-base bash -c 'cat .env.runpod | grep RABBITMQ'
```

### Progress ไม่อัปเดต

```bash
# ตรวจสอบ worker logs
bash scripts/local/logs-local.sh worker

# ตรวจสอบ queue status
docker exec -it transcription-local-base bash -c 'cd /workspace/transcription-service && bash scripts/pod/check-rabbitmq-queue.sh transcription_chunk_queue'
```

## 📝 Parallel Processing Configuration

### Environment Variables

สามารถปรับแต่งได้ใน `docker-compose.local-direct.yml`:

```yaml
environment:
  - TRANSCRIPTION_MAX_WORKERS=5      # จำนวน workers (default: 5)
  - TRANSCRIPTION_PREFETCH_COUNT=20  # prefetch count (default: 20)
```

### Current Settings

- **Max Workers**: 5 (ประมวลผล 5 chunks พร้อมกัน)
- **Prefetch Count**: 20 (รับ chunks ได้ 20 ตัวพร้อมกัน)
- **Model Lock**: เปิดใช้งาน (ป้องกัน CUDA OOM)

## 🎯 Expected Behavior

### Parallel Processing

1. **Chunks ถูกส่งไปยัง queue** → 23 chunks (สำหรับ 10-min video)
2. **Workers รับ chunks** → 5 workers ประมวลผล parallel
3. **Model Lock** → Transcription เป็น sequential (1 chunk ต่อครั้ง)
4. **Progress Update** → อัปเดตทุก 1 วินาที

### Logs Pattern

```
📨 RECEIVED MESSAGE FROM transcription_chunk_queue!
🚀 Chunk X/23 submitted to thread pool (total active: Y)
✅ Chunk X/23 acknowledged - processing in background
🔄 [Thread chunk_worker_N] Starting chunk X/23
📝 Transcribing chunk X/23...
✅ Chunk X/23 transcribed: text length=XXX
💾 Saved chunk X/23 - Progress: XX%
```

## 📚 Related Documentation

- `LOCAL_DIRECT_MODE.md` - รายละเอียด Local Direct Mode
- `../pod/README.md` - รายละเอียด Pod scripts
- `QUEUE_FLOW_EXPLANATION.md` - อธิบาย Queue Flow

