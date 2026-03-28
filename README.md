# Transcription Service

บริการ Transcription สำหรับวิดีโอ/เสียง โดยใช้ faster-whisper และ TyPhoon ASR พร้อม Multi-GPU Support

---

## Deployment Environments

| Environment | Server | GPU | วิธีใช้งาน |
|---|---|---|---|
| Staging | Self-hosted (10.200.22.64) | 2x NVIDIA RTX PRO 4000 (24GB each) | Docker image + git pull |
| Development | RunPod Cloud | RTX 4000 Ada (20GB) | git pull + pip install |

---

## Architecture

```
VM 64 (10.200.22.64) - GPU Transcription Server
├── transcription-service (Docker)
│   ├── Main API         :8010  (FastAPI)
│   ├── Whisper API      :8002  (faster-whisper + CUDA)
│   ├── RQ GPU Workers   (per GPU: priority, record, upload queues)
│   ├── RQ Preprocess    (audio extraction + chunking)
│   └── RQ CPU Workers   (aggregator jobs)
├── redis (Docker)
│   └── Redis            :6379  (RQ job queue)
│
│  connects to:
├── VM 61 RabbitMQ       :5672  (รับ task จาก senate-backend)
└── VM 61 Redis          :6379  (shared cache ถ้าต้องการ)

Network:
  senate-backend (VM 61) ── RabbitMQ ──> transcription (VM 64)
  Frontend (VM 57) ── HTTP/WebSocket ──> transcription (VM 64)
```

---

## Folder Structure

```
transcription-close-caption-service/
│
├── app/                              # Application code
│   ├── main.py                       # FastAPI entry point
│   ├── api/                          # API endpoints
│   │   ├── transcribe.py             #   POST /api/transcribe/
│   │   ├── v2/unified_tasks.py       #   GET  /api/v2/tasks/
│   │   ├── webhook.py                #   Webhook subscriptions
│   │   ├── websocket.py              #   WebSocket connections
│   │   ├── realtime_caption.py       #   Live caption streaming
│   │   ├── monitoring.py             #   System monitoring
│   │   ├── queue.py                  #   Queue management
│   │   └── ...                       #   Other endpoints
│   ├── services/                     # Business logic
│   │   ├── transcription_service.py  #   Core transcription
│   │   ├── redis_queue_service.py    #   RQ job management
│   │   ├── whisper_providers/        #   Whisper engine providers
│   │   │   ├── faster_whisper_provider.py
│   │   │   ├── nemo_typhoon_provider.py
│   │   │   └── ...
│   │   ├── typhoon_asr_service.py    #   TyPhoon ASR (live caption)
│   │   ├── webhook_service.py        #   Webhook delivery
│   │   └── ...
│   ├── workers/                      # Background workers
│   │   ├── video_worker.py           #   Video processing worker
│   │   └── rq_worker.py              #   RQ worker entry point
│   ├── models/                       # Pydantic models
│   └── utils/                        # Utilities (storage, logging, etc.)
│
├── whisper-service/                  # Whisper API (standalone)
│   └── whisper_api.py                #   faster-whisper HTTP API
│
├── scripts/
│   ├── pod/                          # Production scripts
│   │   ├── start-pod.sh              #   Start all services
│   │   ├── start-rq-workers.sh       #   Start RQ workers
│   │   ├── restart-main-api.sh       #   Restart API only
│   │   ├── restart-rq-workers.sh     #   Restart workers only
│   │   ├── check-worker-health.sh    #   Health check
│   │   └── check-gpu-usage.sh        #   GPU monitoring
│   └── utility/                      # Setup & diagnostic
│       ├── setup-cudnn-env.sh        #   cuDNN environment setup
│       ├── load-env-by-gpu.sh        #   Auto-load env by GPU count
│       └── verify-ctranslate2-gpu.sh #   GPU verification
│
├── config/                           # Configuration
│   ├── worker_config.yaml            #   Worker settings
│   └── worker_config.py              #   Worker config loader
│
├── data/                             # Static data
│   └── fuzzy_match/                  #   Name/vocabulary data
│
├── static/                           # Web UI
│   ├── task-dashboard.html           #   Task monitoring dashboard
│   ├── transcription-upload.html     #   Upload interface
│   └── ...
│
├── tests/                            # Test suite
│
├── Dockerfile.base                   # Docker image (OS + CUDA + dependencies)
├── docker-compose.prod.yml           # Production compose (self-hosted)
├── .dockerignore                     # Docker build exclusions
├── .env.runpod                       # Environment config
├── requirements.txt   # Python dependencies
├── Docker-Image.md                   # Build/Push/Deploy guide
└── README.md                         # This file
│
│  Runtime directories (volume mounted, not in git):
├── uploads/                          # Video/audio files
├── storage/                          # Transcription results (SQLite/JSON)
├── models/                           # AI models (auto-download)
└── temp/                             # Temporary processing files
```

---

## Staging: Self-hosted (VM 64)

### Setup

```bash
# 1. Pull Docker image
az acr login --name kksenateacr
docker pull kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch280
# หรือ: docker load -i kk-base-ubuntu2404-cuda128-torch280.tar.gz

# 2. Clone code
git clone <repo-url> /workspace/transcription-service
cd /workspace/transcription-service
mkdir -p uploads storage models temp

# 3. Start
docker compose -f docker-compose.prod.yml up -d

# 4. Verify
curl http://localhost:8010/health
docker compose -f docker-compose.prod.yml logs -f transcription
```

### Update Code

```bash
cd /workspace/transcription-service
git pull
docker compose -f docker-compose.prod.yml restart transcription
```

### Docker Image Build/Push

ดู [Docker-Image.md](Docker-Image.md)

---

## Development: RunPod Cloud

### First Setup

```bash
apt-get update && apt-get install -y ffmpeg && \
pip install -r requirements.txt && \
./scripts/utility/setup-cudnn-env.sh && \
./scripts/pod/start-pod.sh && \
./scripts/pod/start-rq-workers.sh
```

### Restart

```bash
./scripts/pod/start-pod.sh && ./scripts/pod/start-rq-workers.sh
```

---

## Environment Config (.env.runpod)

```bash
ENVIRONMENT=runpod
STORAGE_TYPE=sqlite
SQLITE_DB_PATH=/workspace/transcription-service/storage/database.db

# RabbitMQ (VM 61)
RABBITMQ_HOST=10.200.22.61
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT

# Redis (local container)
REDIS_URL=redis://redis:6379

# Whisper
WHISPER_PROVIDER=faster-whisper
WHISPER_MODEL=deepdml/faster-whisper-large-v3-turbo-ct2
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16

# GPU
NUM_GPUS=2
CUDA_VISIBLE_DEVICES=0,1

# FE Live Caption
FE_CC_PROVIDER=typhoon
FE_CC_TYPHOON_MODEL=typhoon-ai/typhoon-asr-realtime
```

---

## API Endpoints

### Main API (Port 8010)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI |
| `/api/transcribe/` | POST | เริ่ม transcription job |
| `/api/v2/tasks/{task_id}` | GET | สถานะ task (format: full/progress/minimal) |
| `/api/v2/tasks/` | GET | รายการ tasks (filter: status, date, limit, offset) |
| `/api/v2/tasks/stats/summary` | GET | สถิติสรุป |
| `/api/monitoring/` | GET | System monitoring |
| `/api/queue/info` | GET | Queue information |

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

### WebSocket

- `WS /api/ws/ingest-audio` - FE Live Caption streaming

---

## Maintenance

### ตรวจสอบ (เข้า container)

```bash
docker exec -it transcription-service bash

bash scripts/pod/check-worker-health.sh   # Worker health
bash scripts/pod/check-gpu-usage.sh       # GPU usage
tail -f /tmp/main-api.log                 # API logs
tail -f /tmp/rq-worker-*.log              # Worker logs
```

### Restart

```bash
# Restart ทั้งหมด (จากนอก container)
docker compose -f docker-compose.prod.yml restart transcription

# Restart เฉพาะ API (ใน container)
bash scripts/pod/restart-main-api.sh

# Restart เฉพาะ Workers (ใน container)
bash scripts/pod/restart-rq-workers.sh
```

---

## Troubleshooting

### Workers ไม่ทำงาน

```bash
bash scripts/pod/check-worker-health.sh
python3 -c "import redis; r=redis.from_url('$REDIS_URL'); r.ping(); print('OK')"
bash scripts/pod/restart-rq-workers.sh
```

### GPU ไม่ทำงาน (Transcription ช้า)

```bash
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
bash scripts/utility/setup-cudnn-env.sh
bash scripts/pod/restart-rq-workers.sh
```

---

Last Updated: 2026-03-28
