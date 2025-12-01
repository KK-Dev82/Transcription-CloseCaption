# 🐳 คู่มือการใช้ Docker Container สำหรับ Faster-Whisper ที่ Local

## 📋 ภาพรวม

คู่มือนี้จะช่วยให้คุณรัน faster-whisper ใน Docker container ที่ local machine เหมือนกับ GPU Pod

## ✅ ข้อดี

1. **Environment เหมือน Production** - ใช้ container เดียวกับ RunPod
2. **ไม่ต้องติดตั้ง dependencies ที่ local** - ทุกอย่างอยู่ใน container
3. **รองรับทั้ง CPU และ GPU** - ใช้ได้ทั้งสองแบบ
4. **ง่ายต่อการทดสอบ** - ไม่ต้องกังวลเรื่อง environment

## 🚀 การใช้งาน

### ขั้นตอนที่ 1: Build Docker Image

#### CPU Mode (แนะนำสำหรับ local ที่ไม่มี GPU)

```bash
cd transcription-close-caption-service

# Build image
docker build -f Dockerfile.local-faster-whisper \
  --build-arg GPU_MODE=false \
  -t kk-transcription:local-faster-whisper .
```

#### GPU Mode (ถ้ามี NVIDIA GPU)

```bash
# ตรวจสอบว่า GPU พร้อมใช้งาน
nvidia-smi

# Build image with GPU support
docker build -f Dockerfile.local-faster-whisper \
  --build-arg GPU_MODE=true \
  --build-arg CUDA_VERSION=12.1.0 \
  -t kk-transcription:local-faster-whisper .
```

### ขั้นตอนที่ 2: สร้าง .env file

```bash
# สร้าง .env.local-faster-whisper
cat > .env.local-faster-whisper << EOF
# Faster-Whisper Configuration
WHISPER_PROVIDER=faster-whisper
WHISPER_MODEL=base
WHISPER_DEVICE=auto
WHISPER_COMPUTE_TYPE=float32

# สำหรับ GPU mode
# WHISPER_MODEL=medium
# WHISPER_DEVICE=cuda
# WHISPER_COMPUTE_TYPE=float16

# RabbitMQ (ถ้าใช้)
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT

# GPU Mode (true/false)
GPU_MODE=false
EOF
```

### ขั้นตอนที่ 3: รัน Docker Compose

#### CPU Mode

```bash
docker compose -f docker-compose.local-faster-whisper.yml \
  --env-file .env.local-faster-whisper \
  up -d
```

#### GPU Mode

```bash
# ตรวจสอบว่า nvidia-container-toolkit ติดตั้งแล้ว
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# รันด้วย GPU profile
docker compose -f docker-compose.local-faster-whisper.yml \
  --env-file .env.local-faster-whisper \
  --profile gpu \
  up -d
```

### ขั้นตอนที่ 4: ทดสอบ

```bash
# เข้าไปใน container
docker exec -it transcription-api-local-faster-whisper bash

# ทดสอบ faster-whisper
python3 -c "
from faster_whisper import WhisperModel
import torch

print('CUDA available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('CUDA device:', torch.cuda.get_device_name(0))

# Load model
model = WhisperModel('base', device='cpu', compute_type='float32')
print('Model loaded successfully!')
"

# ทดสอบ transcription
python3 scripts/pod/test-direct-transcription.py uploads/test_audio.wav th base
```

## 🔧 Configuration

### Environment Variables

| Variable | CPU Mode | GPU Mode | Description |
|----------|----------|----------|-------------|
| `WHISPER_PROVIDER` | `faster-whisper` | `faster-whisper` | Provider ที่ใช้ |
| `WHISPER_MODEL` | `base` | `medium` | ขนาด model |
| `WHISPER_DEVICE` | `cpu` | `cuda` | Device ที่ใช้ |
| `WHISPER_COMPUTE_TYPE` | `float32` | `float16` | Compute type |
| `WHISPER_BEAM_SIZE` | `1` | `1` | Beam size |
| `WHISPER_TEMPERATURE` | `0` | `0` | Temperature |
| `WHISPER_VAD_FILTER` | `true` | `true` | Voice Activity Detection |

### Model Sizes

| Model | CPU Memory | GPU Memory | Speed (CPU) | Speed (GPU) |
|-------|------------|------------|-------------|-------------|
| `tiny` | ~100MB | ~100MB | Fast | Very Fast |
| `base` | ~500MB | ~500MB | Medium | Fast |
| `small` | ~1GB | ~1GB | Slow | Medium |
| `medium` | ~2GB | ~2GB | Very Slow | Medium |
| `large` | ~4GB | ~4GB | Too Slow | Slow |

**แนะนำ:**
- **CPU Mode**: ใช้ `base` หรือ `tiny`
- **GPU Mode**: ใช้ `medium` หรือ `large`

## 📊 Performance Comparison

### CPU Mode (MacBook M1/M2)

```
Model: base
Audio: 1 minute
Time: ~2-5 minutes
Memory: ~500MB
```

### GPU Mode (NVIDIA GPU)

```
Model: medium
Audio: 1 minute
Time: ~30-60 seconds
Memory: ~2GB
```

## 🐛 Troubleshooting

### ปัญหา: Cannot connect to Docker daemon

**แก้ไข:**
```bash
# ตรวจสอบว่า Docker ทำงานอยู่
docker ps

# ถ้าไม่ได้ → เปิด Docker Desktop
```

### ปัญหา: GPU not found (GPU mode)

**แก้ไข:**
```bash
# ตรวจสอบว่า nvidia-container-toolkit ติดตั้งแล้ว
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# ถ้าไม่ได้ → ติดตั้ง nvidia-container-toolkit
# macOS: ไม่รองรับ GPU ใน Docker Desktop (ใช้ CPU mode แทน)
# Linux: ติดตั้ง nvidia-container-toolkit
```

### ปัญหา: Out of memory

**แก้ไข:**
- ใช้ model ที่เล็กกว่า (`base` แทน `medium`)
- ลด memory limit ใน docker-compose.yml
- ใช้ CPU mode แทน GPU mode

### ปัญหา: Transcription ช้ามาก (CPU mode)

**แก้ไข:**
- ใช้ model `base` หรือ `tiny`
- ลดขนาดไฟล์ audio
- ใช้ GPU mode ถ้ามี GPU

## 📝 สรุป

1. **Build image** - ใช้ `Dockerfile.local-faster-whisper`
2. **สร้าง .env file** - ตั้งค่า environment variables
3. **Run docker compose** - ใช้ `docker-compose.local-faster-whisper.yml`
4. **ทดสอบ** - เข้าไปใน container และทดสอบ transcription

## 🔄 เปรียบเทียบกับ RunPod

| Feature | Local Container | RunPod |
|---------|----------------|--------|
| GPU Support | ✅ (ถ้ามี GPU) | ✅ |
| CPU Support | ✅ | ✅ |
| Faster-Whisper | ✅ | ✅ |
| Environment | เหมือนกัน | เหมือนกัน |
| Cost | ฟรี | ต้องจ่าย |

## ✅ Checklist

- [ ] Docker ติดตั้งแล้ว
- [ ] Build image สำเร็จ
- [ ] สร้าง .env file
- [ ] รัน docker compose
- [ ] ทดสอบ transcription
- [ ] ตรวจสอบ logs

