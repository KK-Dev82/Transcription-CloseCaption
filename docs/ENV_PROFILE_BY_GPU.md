# โหลด Environment ตามจำนวน GPU อัตโนมัติ

Project นี้ปรับให้โหลดการตั้งค่าตามจำนวน GPU เพื่อป้องกัน CPU, RAM, GPU OOM

## วิธีทำงาน

| จำนวน GPU | ไฟล์ที่โหลด | โปรไฟล์ |
|-----------|-------------|---------|
| 1 GPU | `.env.runpod` → `.env.runpod-1GPU` | 1GPU |
| 2+ GPUs | `.env.runpod` เท่านั้น | 2GPU |

- **`.env.runpod`** = config ล่าสุดสำหรับ 2 GPU (รวม Diarization, Chunk Duration)
- **`.env.runpod-1GPU`** = override สำหรับ 1 GPU (ลด workers, chunk limits ป้องกัน OOM)
- **`.env.runpod-2GPU`** = เก่าแล้ว ไม่โหลดแล้ว (เก็บไว้เป็น reference)

## ไฟล์ที่เกี่ยวข้อง

- **`scripts/utility/load-env-by-gpu.sh`** — สำหรับ Shell scripts (start-rq-workers.sh, start-pod.sh)
- **`app/utils/load_env_by_gpu.py`** — สำหรับ Python (main.py, redis_queue_service)
- **`.env.runpod`** — base config (2 GPU)
- **`.env.runpod-1GPU`** — override สำหรับ 1 GPU (ลด workers, chunk limits)

## การ Override ด้วยมือ

บังคับใช้โปรไฟล์ด้วย `ENV_PROFILE`:

```bash
# บังคับใช้ 1 GPU profile (แม้มี 2 GPUs)
ENV_PROFILE=1gpu ./scripts/pod/start-rq-workers.sh

# บังคับใช้ 2 GPU profile
ENV_PROFILE=2gpu ./scripts/pod/start-rq-workers.sh
```

สำหรับ Python:
```bash
ENV_PROFILE=1gpu python -m uvicorn app.main:app ...
```

## ความแตกต่างหลัก 1 GPU vs 2 GPUs (ป้องกัน OOM)

| ตัวแปร | 1 GPU | 2 GPUs |
|--------|-------|--------|
| NUM_GPUS | 1 | 2 |
| CUDA_VISIBLE_DEVICES | 0 | 0,1 |
| GPU_WORKERS_PER_GPU | 2 | 10 |
| NUM_PREPROCESS_WORKERS | 2 | 3 |
| NUM_CPU_WORKERS | 2 | 4 |
| CHUNK_INFLIGHT_LIMIT_PER_JOB | 2 | 6 |
| CHUNK_ENQUEUE_WINDOW_SIZE | 2 | 8 |
| TRANSCRIPTION_CHUNK_DURATION | 150 | 150 (ใน .env.runpod) |

## Scripts ที่ใช้ load-env-by-gpu

- `scripts/pod/start-rq-workers.sh`
- `scripts/pod/start-pod.sh`
- `scripts/pod/restart-rq-workers.sh`
- `app/main.py` (ผ่าน load_env_by_gpu)
- `app/services/redis_queue_service.py`
