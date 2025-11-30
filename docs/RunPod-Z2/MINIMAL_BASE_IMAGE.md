# Minimal Base Image สำหรับ RunPod/Z2

## ภาพรวม

`Dockerfile.runpod-base` สร้าง **Minimal Base Image** ที่มีแค่:
- CUDA 12.1.0 base
- System dependencies (build tools, Python, FFmpeg, etc.)
- Python packages พื้นฐาน
- Azure CLI (สำหรับ pull images จาก ACR)

## ⚠️ สิ่งที่ Image นี้ **ไม่** มี

- ❌ ไม่มี services start อัตโนมัติ
- ❌ ไม่มี setup scripts ที่ copy ไปใน image
- ❌ ไม่มี CMD ที่ start services

## ทำไมต้องเป็น Minimal?

### ปัญหาเดิม:
1. Image มี `CMD ["/workspace/start-services.sh"]` → start services อัตโนมัติ
2. User ยัง run `start-services-direct.sh` อีกครั้ง → **Duplicate Workers**
3. Docker Compose + Direct mode → **Multiple Workers** consume messages

### วิธีแก้:
- Image เป็น minimal base เท่านั้น
- User ต้อง clone repo และ start services เอง
- **ป้องกัน duplicate workers**

## การใช้งาน

### 1. Build และ Push Image

```bash
# Login ACR
az acr login --name kksenateacr

# Build และ Push
bash scripts/pod/build-and-push-runpod-base.sh
```

### 2. ใช้ใน RunPod Pod Template

**Container Image Override:**
```
kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
```

### 3. หลังจาก Pod Start

```bash
# 1. Clone repository
cd /workspace
git clone <repo-url> transcription-service

# 2. Start services (Direct mode)
cd /workspace/transcription-service
bash scripts/pod/restart-pod-services.sh
```

## ตรวจสอบ Services

```bash
# Check status
bash scripts/pod/check-services-status.sh

# Check workers (ต้องมีแค่ 1 worker)
bash scripts/pod/check-all-workers.sh

# View logs
tail -f /tmp/main-api.log /tmp/whisper.log /tmp/video-worker.log
```

## สิ่งที่ควรเห็น

### ✅ ถูกต้อง:
- **1 Video Worker process** เท่านั้น
- **1 Consumer** ใน RabbitMQ queue
- Services start จาก Direct mode script

### ❌ ผิดพลาด:
- **Multiple Video Worker processes** (2+)
- **Multiple Consumers** (2+) ใน RabbitMQ queue
- Services start จากทั้ง Docker Compose และ Direct mode

## Troubleshooting

### ปัญหา: Multiple Workers

**สาเหตุ:**
- Docker Compose ยัง run อยู่
- Direct mode workers หลายตัว
- Old processes ยังไม่ถูก kill

**วิธีแก้:**
```bash
# 1. หยุด Docker Compose (ถ้ามี)
docker compose -f docker-compose.runpod.yml down

# 2. Kill workers ทั้งหมด
pkill -f "python.*video_worker"

# 3. ตรวจสอบ
bash scripts/pod/check-all-workers.sh

# 4. Start worker ใหม่ (แค่ตัวเดียว)
bash scripts/pod/restart-video-worker.sh
```

### ปัญหา: Services ไม่ start

**สาเหตุ:**
- Repository ยังไม่ได้ clone
- Scripts ไม่มี execute permission

**วิธีแก้:**
```bash
# 1. Clone repository
cd /workspace
git clone <repo-url> transcription-service

# 2. Start services
cd /workspace/transcription-service
bash scripts/pod/restart-pod-services.sh
```

## สรุป

- ✅ Image เป็น minimal base (CUDA + dependencies)
- ✅ ไม่มี services start อัตโนมัติ
- ✅ User ต้อง clone repo และ start services เอง
- ✅ **ป้องกัน duplicate workers**

