# Transcription Service

บริการ Transcription สำหรับวิดีโอ/เสียง โดยใช้ faster-whisper และ TyPhoon ASR พร้อม Multi-GPU Support

---

## Infrastructure

### Deployment Environments

| Environment | Server | GPU | วิธีใช้งาน |
|-------------|--------|-----|-----------|
| **Staging** | Self-hosted (10.200.22.64) | 2x NVIDIA RTX PRO 4000 (24GB each) | Docker image |
| **Development** | RunPod Cloud | RTX 4000 Ada (20GB) | git pull + pip install |

### Architecture (Staging - Self-hosted)

```
VM 64 (10.200.22.64) - GPU Transcription Server
├── transcription-service (Docker container)
│   ├── Main API         :8010  (FastAPI)
│   ├── Whisper API      :8002  (faster-whisper + CUDA)
│   ├── RQ GPU Workers   (per GPU: transcription_priority, transcription_gpu_*)
│   ├── RQ Preprocess    (audio extraction + chunking)
│   └── RQ CPU Workers   (aggregator jobs)
├── redis (Docker container)
│   └── Redis            :6379  (RQ job queue + caching)
│
│  connects to:
├── VM 61 RabbitMQ       :5672  (รับ task จาก senate-backend)
└── VM 61 Redis          :6379  (ถ้าใช้ shared Redis แทน local)
```

### Network Communication

```
senate-backend (VM 61)
  ── RabbitMQ ──> transcription-service (VM 64)  : ส่ง transcription task
  <── Callback ── transcription-service (VM 64)  : ส่งผลลัพธ์กลับ

Frontend (VM 57)
  ── WebSocket ──> transcription-service (VM 64) : Live caption streaming
  ── HTTP ──────> transcription-service (VM 64)  : Upload + status polling
```

---

## Staging: Self-hosted Server (VM 64)

### Prerequisites

- Docker + Docker Compose + NVIDIA Container Toolkit
- Network access to VM 61 (RabbitMQ :5672)

### Setup

```bash
# 1. Load Docker image (จาก tar.gz หรือ pull จาก ACR)
docker load -i kk-transcription-release-v1.0.0.tar.gz
# หรือ
az acr login --name kksenateacr
docker pull kksenateacr.azurecr.io/kk-transcription:release-v1.0.0

# 2. เตรียม directory structure
mkdir -p uploads storage models temp

# 3. แก้ .env.runpod (RabbitMQ, Redis, GPU settings)
# ดูตัวอย่างใน section Environment Config ด้านล่าง

# 4. Start
docker compose -f docker-compose.prod.yml up -d

# 5. ตรวจสอบ
docker compose -f docker-compose.prod.yml logs -f transcription
curl http://localhost:8010/health
```

### Management Commands

```bash
# Logs
docker compose -f docker-compose.prod.yml logs -f transcription

# Restart
docker compose -f docker-compose.prod.yml restart transcription

# Stop
docker compose -f docker-compose.prod.yml down

# เข้า container (debug)
docker exec -it transcription-service bash
```

### Docker Image Build (บน Mac)

```bash
# Build
docker buildx build --platform linux/amd64 \
  -f Dockerfile.prod \
  -t kksenateacr.azurecr.io/kk-transcription:release-v1.0.0 \
  --cache-from type=local,src=/Volumes/TS960GJDM850-Media/Library/Docker-Cache \
  --cache-to type=local,dest=/Volumes/TS960GJDM850-Media/Library/Docker-Cache \
  --load .

# Push to ACR
az acr login --name kksenateacr
docker push kksenateacr.azurecr.io/kk-transcription:release-v1.0.0

# Save เป็นไฟล์ (สำหรับ transfer ด้วยมือ)
docker save kksenateacr.azurecr.io/kk-transcription:release-v1.0.0 \
  | gzip > kk-transcription-release-v1.0.0.tar.gz

# Cleanup Mac
docker rmi kksenateacr.azurecr.io/kk-transcription:release-v1.0.0
docker system prune -f
```

---

## Development: RunPod Cloud

### First Setup

```bash
apt-get update && apt-get install -y ffmpeg && \
pip install -r requirements.runpod-unified.txt && \
./scripts/utility/setup-cudnn-env.sh && \
./scripts/pod/start-pod.sh && \
./scripts/pod/start-rq-workers.sh
```

### Restart (หลัง pod restart)

```bash
./scripts/pod/start-pod.sh && ./scripts/pod/start-rq-workers.sh
```

### Verify GPU

```bash
./scripts/utility/verify-ctranslate2-gpu.sh
```

---

## Environment Config (.env.runpod)

ค่าสำคัญที่ต้องตั้ง:

```bash
# Environment
ENVIRONMENT=runpod
STORAGE_TYPE=sqlite
SQLITE_DB_PATH=/workspace/transcription-service/storage/database.db

# RabbitMQ (VM 61 - senate-backend)
RABBITMQ_HOST=10.200.22.61
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT

# Redis (local container ใน docker-compose.prod.yml)
REDIS_URL=redis://redis:6379

# Whisper
WHISPER_PROVIDER=faster-whisper
WHISPER_MODEL=deepdml/faster-whisper-large-v3-turbo-ct2
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16

# GPU
NUM_GPUS=2
CUDA_VISIBLE_DEVICES=0,1

# FE Live Caption (TyPhoon ASR)
FE_CC_PROVIDER=typhoon
FE_CC_TYPHOON_MODEL=typhoon-ai/typhoon-asr-realtime
```

GPU profiles โหลดอัตโนมัติตามจำนวน GPU:
- 1 GPU -> `.env.runpod-1GPU`
- 2 GPU -> `.env.runpod-2GPU`

---

## API Endpoints

### Main API (Port 8010)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI |
| `/api/transcribe/` | POST | เริ่ม transcription job |
| `/api/v2/tasks/{task_id}` | GET | สถานะ task (format: full/progress/minimal) |
| `/api/v2/tasks/` | GET | รายการ tasks (filter: status, date, limit, offset) |
| `/api/v2/tasks/stats/summary` | GET | สถิติสรุป |

### Transcription Request

```bash
curl -X POST "http://10.200.22.64:8010/api/transcribe/" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "https://example.com/video.mp4",
    "language": "th",
    "callback_url": "http://10.200.22.61:5173/api/transcription/callback"
  }'
```

### WebSocket (Live Caption)

- `WS /api/ws/ingest-audio` - FE Live Caption streaming

### Monitoring

| Endpoint | Description |
|----------|-------------|
| `/api/monitoring/` | Stats รวม |
| `/api/monitoring/redis` | Redis stats |
| `/api/monitoring/queues` | Queue stats |
| `/api/queue/info` | Queue information |

---

## Maintenance

### ตรวจสอบ (ใน container)

```bash
docker exec -it transcription-service bash

# Worker Health
bash scripts/pod/check-worker-health.sh

# GPU Usage
bash scripts/pod/check-gpu-usage.sh

# Logs
tail -f /tmp/main-api.log      # Main API
tail -f /tmp/whisper.log        # Whisper API
tail -f /tmp/rq-worker-*.log    # Workers
```

### Restart Services (ใน container)

```bash
# Restart API
bash scripts/pod/restart-main-api.sh

# Restart Workers
bash scripts/pod/restart-rq-workers.sh
```

---

## Troubleshooting

### Workers ไม่ทำงาน

```bash
# 1. ตรวจสอบ worker health
bash scripts/pod/check-worker-health.sh

# 2. ตรวจสอบ GPU
nvidia-smi -L

# 3. ตรวจสอบ Redis connection
python3 -c "import redis; r=redis.from_url('$REDIS_URL'); r.ping(); print('OK')"

# 4. Restart workers
bash scripts/pod/restart-rq-workers.sh
```

### Transcription ช้า (GPU ไม่ทำงาน)

```bash
# ตรวจสอบว่า workers ใช้ GPU จริง
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv

# ถ้าไม่เห็น processes → cuDNN/LD_LIBRARY_PATH มีปัญหา
bash scripts/utility/setup-cudnn-env.sh
bash scripts/pod/restart-rq-workers.sh
```

---

## File Structure

```
transcription-close-caption-service/
├── app/                          # Application code (FastAPI)
├── whisper-service/              # Whisper API service
├── scripts/
│   ├── pod/                      # Start/stop/restart scripts
│   └── utility/                  # Setup + diagnostic scripts
├── config/                       # Worker configuration
├── data/                         # Fuzzy match data
├── static/                       # Web UI dashboards
├── Dockerfile.prod               # Production image (all-in-one)
├── Dockerfile.base               # Base image (CUDA + PyTorch)
├── docker-compose.prod.yml       # Production compose (self-hosted)
├── docker-compose.yml            # Legacy staging compose
├── requirements.runpod-unified.txt  # Python dependencies
├── .env.runpod                   # Environment config
├── .env.runpod-1GPU              # 1 GPU profile
└── .env.runpod-2GPU              # 2 GPU profile
```

---

Last Updated: 2026-03-27
