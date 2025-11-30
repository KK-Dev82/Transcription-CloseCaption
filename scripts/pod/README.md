# Pod Scripts - Simplified

Scripts สำหรับจัดการ Transcription Services บน RunPod/Z2

## 📋 Scripts หลัก

### 1. `start-pod.sh`
Start services ทั้งหมด (Redis, Whisper API, Video Worker, Main API)
- สร้าง folders ที่จำเป็นอัตโนมัติ
- Setup environment variables
- Install dependencies ถ้ายังไม่ได้ติดตั้ง

```bash
bash scripts/pod/start-pod.sh
```

### 2. `stop-pod.sh`
Stop services ทั้งหมด

```bash
bash scripts/pod/stop-pod.sh
```

### 3. `restart-pod.sh`
Restart services ทั้งหมด (stop แล้ว start ใหม่)

```bash
bash scripts/pod/restart-pod.sh
```

### 4. `logs-pod.sh`
ดู logs ของ services

```bash
# ดู logs ทั้งหมด
bash scripts/pod/logs-pod.sh

# ดู logs แยกตาม service
bash scripts/pod/logs-pod.sh api          # Main API
bash scripts/pod/logs-pod.sh whisper      # Whisper API
bash scripts/pod/logs-pod.sh worker      # Video Worker

# ดู logs จำนวนบรรทัดที่กำหนด
bash scripts/pod/logs-pod.sh all 100     # 100 บรรทัดล่าสุด
```

### 5. `setup-pod.sh`
Setup Pod ครั้งแรก หรือตรวจสอบและจัดการส่วนที่ขาด
- สร้าง directories
- Setup .env.runpod
- ตรวจสอบ Python dependencies
- ตรวจสอบ Whisper models
- Download models ถ้ายังไม่มี

```bash
bash scripts/pod/setup-pod.sh
```

### 6. `check-pod.sh`
ตรวจสอบการทำงานของ services ต่างๆ พร้อมแจ้ง error
- ตรวจสอบ Redis, Whisper API, Video Worker, Main API
- ตรวจสอบ RabbitMQ connection
- ตรวจสอบ duplicate workers
- แสดง summary และ recommendations

```bash
bash scripts/pod/check-pod.sh
```

### 7. `download-tool.sh` (Optional)
Tool สำหรับ download models และ videos

```bash
# Download model
bash scripts/pod/download-tool.sh model medium
bash scripts/pod/download-tool.sh model large-v3

# Download video
bash scripts/pod/download-tool.sh video https://example.com/video.mp4
bash scripts/pod/download-tool.sh video /tmp/video.mp4 uploads/
```

### 8. `test-transcription.sh` (Optional)
ทดสอบ transcription (เลือก model และ video ได้)

```bash
# ทดสอบด้วย model default (medium)
bash scripts/pod/test-transcription.sh uploads/video.mp4

# เลือก model
bash scripts/pod/test-transcription.sh uploads/video.mp4 large-v3

# ระบุ API URL
bash scripts/pod/test-transcription.sh uploads/video.mp4 medium http://localhost:8001
```

### 9. `result-view.sh` (Optional)
ดูผลลัพธ์ transcription

```bash
# ดูผลลัพธ์ของ task-id
bash scripts/pod/result-view.sh <task-id>

# แสดง list ให้เลือก
bash scripts/pod/result-view.sh
```

### 10. `task-service.sh` (Optional)
จัดการ Transcription Tasks (stop, clear, cleanup)

```bash
# แสดง list tasks
bash scripts/pod/task-service.sh list

# หยุด task ที่กำลังทำงาน
bash scripts/pod/task-service.sh stop <task-id>

# ลบ task (permanent)
bash scripts/pod/task-service.sh clear <task-id>

# ลบ tasks ทั้งหมด (completed/failed/cancelled)
bash scripts/pod/task-service.sh clear-all

# ลบ tasks เก่า (default: 24 hours)
bash scripts/pod/task-service.sh cleanup [hours]

# ดูสถานะ task
bash scripts/pod/task-service.sh status <task-id>
```

## 🚀 Quick Start

### 1. Setup ครั้งแรก
```bash
bash scripts/pod/setup-pod.sh
```

### 2. Start Services
```bash
bash scripts/pod/start-pod.sh
```

### 3. Check Status
```bash
bash scripts/pod/check-pod.sh
```

### 4. Test Transcription
```bash
# Download video (ถ้ายังไม่มี)
bash scripts/pod/download-tool.sh video https://example.com/video.mp4

# Test transcription
bash scripts/pod/test-transcription.sh uploads/video.mp4 medium
```

## 📝 Workflow

### หลังจาก Pod Start ใหม่:
```bash
# 1. Setup (ครั้งแรกเท่านั้น)
bash scripts/pod/setup-pod.sh

# 2. Start services
bash scripts/pod/start-pod.sh

# 3. Check status
bash scripts/pod/check-pod.sh
```

### Restart Services:
```bash
bash scripts/pod/restart-pod.sh
```

### ดู Logs:
```bash
# ดู logs ทั้งหมด
bash scripts/pod/logs-pod.sh

# Follow logs real-time
tail -f /tmp/main-api.log
tail -f /tmp/whisper.log
tail -f /tmp/video-worker.log
```

## 🔧 Troubleshooting

### Services ไม่ start
```bash
# ตรวจสอบ status
bash scripts/pod/check-pod.sh

# Restart services
bash scripts/pod/restart-pod.sh

# ดู logs
bash scripts/pod/logs-pod.sh
```

### Multiple Workers
```bash
# ตรวจสอบ workers
bash scripts/pod/check-pod.sh

# Stop และ start ใหม่
bash scripts/pod/restart-pod.sh
```

### RabbitMQ Connection Issues
```bash
# ตรวจสอบ .env.runpod
cat .env.runpod | grep RABBITMQ

# Update RabbitMQ config
# แก้ไข .env.runpod หรือรัน setup-pod.sh อีกครั้ง
bash scripts/pod/setup-pod.sh
```

## 📂 File Locations

- Logs: `/tmp/main-api.log`, `/tmp/whisper.log`, `/tmp/video-worker.log`
- Config: `.env.runpod`
- Models: `models/`
- Videos: `uploads/`
- Storage: `storage/`

## 🔗 Related Scripts

- `build-and-push-runpod-base.sh` - Build และ push base image ไป ACR
- `healthcheck.sh` - Health check script สำหรับ Docker
