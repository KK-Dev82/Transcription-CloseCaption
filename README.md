# Transcription Service

บริการ Transcription สำหรับวิดีโอ/เสียง โดยใช้ faster-whisper และ TyPhoon ASR พร้อม Multi-GPU Support

---

## Deployment

| Environment | Server | Image | Update |
|---|---|---|---|
| Staging | 10.200.22.64 (2x RTX PRO 4000) | kk-transcription:latest | CI/CD auto build → manual pull |
| Development | RunPod Cloud | - | git pull + pip install |

### Docker Images

| Image | ขนาด | Build เมื่อ |
|---|---|---|
| `kk-base:ubuntu2404-cuda128-torch280` | 10.8 GB | Dependencies เปลี่ยน (นานๆ ครั้ง) |
| `kk-transcription:release-v1.0.0` | ~3 MB | Code เปลี่ยน (CI/CD auto) |

ดูรายละเอียด Build/Push/Deploy: [DEPLOYMENT.md](DEPLOYMENT.md)

---

## Architecture

```
Server /deploy (10.200.22.64)
├── docker-compose.yml
├── .env.runpod
│
├── [Container] transcription-service
│   ├── Image: kk-transcription (code)
│   ├──   on: kk-base (OS + CUDA + dependencies)
│   ├── Main API         :8010
│   ├── Whisper API      :8002
│   ├── RQ GPU Workers   (per GPU)
│   ├── RQ Preprocess    (chunking)
│   └── RQ CPU Workers   (aggregator)
│
├── [Container] redis
│   └── Redis            :6379
│
├── [Volume] uploads/    → video/audio files
├── [Volume] storage/    → transcription results
├── [Volume] models/     → AI models
└── [Volume] temp/       → temporary files

Connections:
  VM 61 RabbitMQ :5672  → รับ task จาก senate-backend
  VM 57 Frontend        → HTTP/WebSocket
```

---

## Folder Structure

```
transcription-close-caption-service/
├── app/                              # Application code
│   ├── main.py                       # FastAPI entry point
│   ├── api/                          # API endpoints
│   │   ├── transcribe.py             #   POST /api/transcribe/
│   │   ├── v2/unified_tasks.py       #   GET  /api/v2/tasks/
│   │   ├── webhook.py                #   Webhook subscriptions
│   │   ├── websocket.py              #   WebSocket connections
│   │   ├── realtime_caption.py       #   Live caption streaming
│   │   ├── monitoring.py             #   System monitoring
│   │   └── ...
│   ├── services/                     # Business logic
│   │   ├── transcription_service.py
│   │   ├── redis_queue_service.py
│   │   ├── whisper_providers/        #   faster-whisper, nemo, etc.
│   │   ├── typhoon_asr_service.py    #   TyPhoon ASR (live caption)
│   │   └── ...
│   ├── workers/                      # Background workers
│   │   ├── video_worker.py
│   │   └── rq_worker.py
│   ├── models/                       # Pydantic models
│   └── utils/                        # Utilities
│
├── whisper-service/                  # Whisper API (standalone)
│   └── whisper_api.py
│
├── scripts/
│   ├── pod/                          # Production scripts
│   │   ├── start-pod.sh              #   Start all services
│   │   ├── start-rq-workers.sh       #   Start RQ workers
│   │   ├── restart-main-api.sh
│   │   ├── restart-rq-workers.sh
│   │   ├── check-worker-health.sh
│   │   └── check-gpu-usage.sh
│   └── utility/                      # Setup & diagnostic
│       ├── setup-cudnn-env.sh
│       └── verify-ctranslate2-gpu.sh
│
├── config/                           # Configuration
├── data/                             # Static data (fuzzy match)
├── static/                           # Web UI dashboards
├── tests/                            # Test suite
│
├── Dockerfile.base                   # kk-base image
├── Dockerfile                        # kk-transcription image
├── docker-compose.prod.yml           # Production compose
├── .dockerignore
├── .env.runpod                       # Environment config
├── requirements.txt                  # Python dependencies
├── .github/workflows/                # CI/CD
│   └── build-push-acr.yml
├── DEPLOYMENT.md                # Build/Push/Deploy guide
└── README.md
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
NUM_GPUS=2

# FE Live Caption
FE_CC_PROVIDER=typhoon
FE_CC_TYPHOON_MODEL=typhoon-ai/typhoon-asr-realtime
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI |
| `/api/transcribe/` | POST | เริ่ม transcription job |
| `/api/v2/tasks/{task_id}` | GET | สถานะ task |
| `/api/v2/tasks/` | GET | รายการ tasks |
| `/api/v2/tasks/stats/summary` | GET | สถิติสรุป |
| `/api/monitoring/` | GET | System monitoring |
| `WS /api/ws/ingest-audio` | WS | Live caption streaming |

---

## Maintenance

```bash
# Logs
docker compose logs -f transcription

# Restart
docker compose restart transcription

# เข้า container
docker exec -it transcription-service bash
bash scripts/pod/check-worker-health.sh
bash scripts/pod/check-gpu-usage.sh
```

---

## Development: RunPod Cloud

```bash
# First setup
apt-get update && apt-get install -y ffmpeg && \
pip install -r requirements.txt && \
./scripts/utility/setup-cudnn-env.sh && \
./scripts/pod/start-pod.sh && \
./scripts/pod/start-rq-workers.sh

# Restart
./scripts/pod/start-pod.sh && ./scripts/pod/start-rq-workers.sh
```

---

Last Updated: 2026-03-28
