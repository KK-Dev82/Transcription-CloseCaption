# 🎙️ Transcription Service

บริการ Transcription สำหรับวิดีโอ/เสียง โดยใช้ Whisper และ faster-whisper พร้อม Multi-GPU Support

---

## 📦 Prerequisites (สิ่งที่ต้องมีก่อนเริ่ม)

### System Requirements

1. **FFmpeg** (จำเป็นสำหรับ video/audio processing)
   ```bash
   # Ubuntu/Debian (ใน container - ไม่ต้องใช้ sudo)
   apt-get update
   apt-get install -y ffmpeg
   
   # ตรวจสอบว่าติดตั้งสำเร็จ
   ffmpeg -version
   ```
   
   **หมายเหตุ**: ใน container environment มักจะรันเป็น root อยู่แล้ว ไม่ต้องใช้ `sudo`

2. **Python 3.10+**
   ```bash
   python3 --version
   ```

3. **CUDA 12.1+ และ cuDNN** (สำหรับ GPU acceleration)
   - ใช้ base image: `runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04`
   - cuDNN 8.9.7 ติดตั้งแล้ว (compatible กับ CUDA 12.1)
   - `libcudnn_ops_infer.so.8` อยู่ใน `/usr/lib/x86_64-linux-gnu/`
   - Scripts จะตั้งค่า `LD_LIBRARY_PATH` อัตโนมัติ

4. **Redis** (สำหรับ job queue)
   - ใช้ Redis Cloud หรือ local Redis

### Python Dependencies

ติดตั้งผ่าน `pip install -r requirements.txt` (ดูรายละเอียดใน requirements.txt)

---

## 🚀 Quick Start (หลังจาก Restart Pod Container)

เมื่อ restart pod container ใหม่ ต้องทำตามขั้นตอนนี้:

### 1. ติดตั้ง System Dependencies

```bash
# อัปเดต package list (ใน container - ไม่ต้องใช้ sudo)
apt-get update

# ติดตั้ง FFmpeg (จำเป็นสำหรับ video/audio processing)
apt-get install -y ffmpeg

# ตรวจสอบว่า FFmpeg ติดตั้งสำเร็จ
ffmpeg -version
```

**หมายเหตุ**: 
- ใน container environment มักจะรันเป็น root อยู่แล้ว ไม่ต้องใช้ `sudo`
- ถ้า `apt-get install -y ffmpeg` ไม่พบ package:
  ```bash
  # ลองติดตั้งจาก universe repository
  apt-get install -y software-properties-common
  add-apt-repository universe
  apt-get update
  apt-get install -y ffmpeg
  ```

### 2. ติดตั้ง Python Dependencies

```bash
cd /workspace/transcription-service
pip install -r requirements.txt
```

**หมายเหตุ**: 
- Scripts จะจัดการ cuDNN และ CTranslate2 libraries อัตโนมัติผ่าน `LD_LIBRARY_PATH`
- cuDNN 8.9.7 ติดตั้งแล้ว (ไม่ต้องติดตั้งเพิ่ม)
- `whisper_api.py` จะตั้งค่า `LD_LIBRARY_PATH` และ pre-load cuDNN library อัตโนมัติ

### 3. Start Services

```bash
bash scripts/pod/start-pod.sh
```

Script นี้จะ:
- ✅ ตั้งค่า `LD_LIBRARY_PATH` สำหรับ cuDNN และ CTranslate2
- ✅ ตรวจสอบ GPU
- ✅ สร้าง directories ที่จำเป็น
- ✅ โหลด environment variables จาก `.env.runpod`
- ✅ Start Whisper API (port 8002) พร้อม cuDNN support
- ✅ Start Main API (port 8010)

### 4. Start RQ Workers

```bash
bash scripts/pod/restart-rq-workers.sh
```

Script นี้จะ:
- ✅ หยุด workers เดิม (ถ้ามี)
- ✅ ตั้งค่า `LD_LIBRARY_PATH` สำหรับ CUDA, cuDNN และ CTranslate2
- ✅ Start workers สำหรับทุก queue:
  - `transcription_preprocess` (6 workers)
  - `transcription_gpu0`, `transcription_gpu1` (2 workers)
  - `transcription_cpu` (2 workers)

---

## 📋 เกี่ยวกับ cuDNN และ CTranslate2

### การจัดการอัตโนมัติ

Scripts และ code จัดการ cuDNN และ CTranslate2 ให้อัตโนมัติ:

1. **cuDNN Libraries**: 
   - System cuDNN: `/usr/lib/x86_64-linux-gnu/libcudnn_ops_infer.so.8` (cuDNN 8.9.7)
   - PyTorch cuDNN: `/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib`
   - ติดตั้งแล้วผ่าน `apt-get install libcudnn8` (cuDNN 8.9.7 สำหรับ CUDA 12.2)
   - Compatible กับ CUDA 12.1 และ CTranslate2 4.4.0

2. **CTranslate2 Libraries**: อยู่ใน `/usr/local/lib/python3.10/dist-packages/ctranslate2.libs`
   - ติดตั้งผ่าน `pip install ctranslate2==4.4.0` (ใน requirements.txt)
   - รองรับ cuDNN 8.x

3. **Auto Configuration**:
   - `whisper_api.py` ตั้งค่า `LD_LIBRARY_PATH` และ pre-load cuDNN library อัตโนมัติ
   - `start-pod.sh` ตั้งค่า `LD_LIBRARY_PATH` สำหรับ Whisper API
   - `start-rq-workers.sh` ตั้งค่า `LD_LIBRARY_PATH` สำหรับ workers (order: cuDNN → CUDA → CTranslate2)

4. **Error Handling**:
   - ถ้า cuDNN error → auto-fallback เป็น CPU (แต่ไม่แนะนำ - ใช้ GPU เป็นหลัก)
   - Warning "Could not load library" อาจแสดง แต่ไม่กระทบการทำงาน

### ตรวจสอบว่าใช้งานได้

```bash
# ตรวจสอบ Worker Health
bash scripts/pod/check-worker-health.sh

# ตรวจสอบ GPU Usage
bash scripts/pod/check-gpu-usage.sh
```

---

## 🌐 Ports และ Services

### Main API (Port 8010)

**Public URL**: `https://0b3x44foetagtu-8010.proxy.runpod.net/`

**Endpoints หลัก**:

### Core Transcription
- `GET /health` - Health check
- `GET /docs` - API Documentation (Swagger UI)
- `POST /api/transcribe/` - เริ่ม transcription job
- `POST /api/transcribe-enhanced/start` - Enhanced transcription (base model + Thai processing)
- `GET /api/transcribe/debug/queue` - Debug Redis queue status

### Tasks & Status (V2 Unified API - แนะนำ)
- `GET /api/v2/tasks/{task_id}` - ดูรายละเอียด task (unified endpoint)
- `GET /api/v2/tasks/` - รายการ tasks พร้อม filter (status, date, limit, offset)
- `GET /api/v2/tasks/stats/summary` - สถิติสรุป
- `GET /api/v2/tasks/stats/available-dates` - รายการวันที่ที่มี tasks

### Tasks & Status (Legacy)
- `GET /api/tasks/{task_id}` - ตรวจสอบสถานะ task
- `GET /api/tasks/by-date` - Tasks ตามวันที่
- `GET /api/tasks/summary` - สรุป tasks ตามวันที่
- `GET /api/tasks/available-dates` - รายการวันที่ที่มี tasks
- `GET /api/progress/transcription/{task_id}` - Progress ของ task
- `GET /api/progress/all-active` - รายการ tasks ที่กำลังทำงาน
- `GET /api/progress/stats` - สถิติ progress

### History
- `GET /api/history/transcriptions` - รายการ transcriptions (filter by status, days_ago)
- `GET /api/history/transcriptions/{task_id}` - รายละเอียด transcription
- `GET /api/history/stats` - สถิติการ transcription
- `DELETE /api/history/transcriptions/{task_id}` - ลบ transcription
- `WS /api/history/ws/realtime` - WebSocket สำหรับ realtime updates

### Webhook & Callback
- `POST /api/webhook/subscribe` - Subscribe webhook
- `GET /api/webhook/subscriptions` - รายการ subscriptions
- `GET /api/webhook/subscribe/{subscription_id}` - ดู subscription
- `DELETE /api/webhook/subscribe/{subscription_id}` - ยกเลิก subscription
- `POST /api/webhook/test` - ทดสอบ webhook
- `GET /api/webhook/stats` - สถิติ webhook

### Monitoring & System
- `GET /api/monitoring/` - Monitoring stats (รวม)
- `GET /api/monitoring/redis` - Redis stats
- `GET /api/monitoring/queues` - Queue stats
- `GET /api/monitoring/system` - System stats
- `GET /api/queue/info` - Queue information
- `GET /api/queue/status` - Queue status
- `GET /api/queue/stats` - Queue statistics

### Enhanced Transcription
- `GET /api/transcribe-enhanced/status/{task_id}` - สถานะ enhanced transcription
- `POST /api/transcribe-enhanced/apply-thai-processing/{task_id}` - ใช้ Thai processing
- `GET /api/transcribe-enhanced/compare/{task_id}` - เปรียบเทียบก่อน/หลัง Thai processing

### Whisper API (Port 8002)

**Internal Service** (ใช้โดย workers):
- `GET /health` - Health check
- `POST /transcribe` - Transcription endpoint

---

## 📡 API Usage

### API Versions

- **V2 Unified API** (`/api/v2/tasks/*`): ✅ **แนะนำ** - รวม endpoints ที่ซ้ำซ้อนไว้ที่เดียว
  - รองรับ format: `full`, `progress`, `minimal`
  - Filtering ที่ดีกว่า (status, date, pagination)
  - Response format ที่สม่ำเสมอ
- **Legacy API**: ⚠️ **DEPRECATED** - ยังใช้งานได้ แต่จะถูก deprecate ในอนาคต
  - `GET /api/tasks/{task_id}` → ใช้ `GET /api/v2/tasks/{task_id}` แทน
  - `GET /api/progress/transcription/{task_id}` → ใช้ `GET /api/v2/tasks/{task_id}?format=progress` แทน
  - `GET /api/polling/task/{task_id}` → ใช้ `GET /api/v2/tasks/{task_id}?format=minimal` แทน
  - `GET /api/history/transcriptions` → ใช้ `GET /api/v2/tasks/` แทน

### 1. เริ่ม Transcription

```bash
curl -X POST "https://0b3x44foetagtu-8010.proxy.runpod.net/api/transcribe/" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "https://example.com/video.mp4",
    "language": "th",
    "model_size": "base",
    "chunk_duration": 30,
    "callback_url": "https://your-server.com/webhook"
  }'
```

**Response**:
```json
{
  "task_id": "abc123...",
  "status": "queued",
  "message": "Transcription job queued"
}
```

### 2. ตรวจสอบสถานะ

**✅ แนะนำ: ใช้ V2 Unified API** (Legacy endpoints ถูก deprecate แล้ว)

**Full Format** (ข้อมูลครบถ้วน):
```bash
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/v2/tasks/{task_id}?format=full&include_chunks=true"
```

**Progress Format** (สำหรับติดตาม progress):
```bash
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/v2/tasks/{task_id}?format=progress"
```

**Minimal Format** (สำหรับ polling - เร็วที่สุด):
```bash
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/v2/tasks/{task_id}?format=minimal"
```

**Response (Progress Format)**:
```json
{
  "task_id": "abc123...",
  "status": "in_progress",
  "progress": 45,
  "current_stage": "transcribing",
  "current_stage_description": "Transcribing audio chunks",
  "stage_progress": 3,
  "elapsed_seconds": 120,
  "elapsed_formatted": "2:00",
  "estimated_remaining_seconds": 150,
  "estimated_remaining_formatted": "2:30"
}
```

**หรือใช้ Legacy API**
```bash
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/tasks/{task_id}"
```

### 3. ดึงผลลัพธ์

**แนะนำ: ใช้ V2 Unified API**
```bash
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/v2/tasks/{task_id}"
```

**หรือใช้ History API**
```bash
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/history/transcriptions/{task_id}"
```

### 4. รายการ Tasks (Filter by Status)

**แนะนำ: ใช้ V2 Unified API**
```bash
# ทั้งหมด
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/v2/tasks/"

# Filter by status
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/v2/tasks/?status=completed"

# Filter by date
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/v2/tasks/?date=2024-12-24"

# Pagination
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/v2/tasks/?limit=20&offset=0"
```

**หรือใช้ History API (Legacy)**
```bash
# ทั้งหมด
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/history/transcriptions"

# In-progress
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/history/transcriptions?status=processing"

# Completed
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/history/transcriptions?status=completed"

# Failed
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/history/transcriptions?status=failed"

# Last 7 days
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/history/transcriptions?days_ago=7"
```

### 5. สถิติรวม

**แนะนำ: ใช้ V2 Unified API**
```bash
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/v2/tasks/stats/summary"
```

**หรือใช้ History API (Legacy)**
```bash
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/history/stats"
```

### 6. รายการวันที่ที่มี Tasks

```bash
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/v2/tasks/stats/available-dates"
```

---

## 🔔 Webhook และ Callback

### Webhook Subscription

```bash
curl -X POST "https://0b3x44foetagtu-8010.proxy.runpod.net/api/webhook/subscribe" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-server.com/webhook",
    "events": ["transcription.progress", "transcription.completed", "transcription.failed"]
  }'
```

### Callback URL (ใน Request)

เมื่อส่ง request transcription สามารถระบุ `callback_url`:

```json
{
  "file_path": "https://example.com/video.mp4",
  "callback_url": "https://your-server.com/callback"
}
```

Service จะส่ง POST request ไปที่ `callback_url` เมื่อ:
- ✅ Transcription เสร็จสิ้น
- ❌ Transcription ล้มเหลว

**Callback Payload**:
```json
{
  "task_id": "abc123...",
  "status": "completed",
  "progress": 100,
  "full_text": "...",
  "segments": [...]
}
```

---

## 🛠️ Maintenance Scripts

### ตรวจสอบ Worker Health

```bash
bash scripts/pod/check-worker-health.sh
```

### Restart Workers

```bash
bash scripts/pod/restart-rq-workers.sh
```

### ตรวจสอบ GPU Usage

```bash
bash scripts/pod/check-gpu-usage.sh
```

### ดู Logs

```bash
# Main API
tail -f /tmp/main-api.log

# Whisper API
tail -f /tmp/whisper.log

# Workers
tail -f /tmp/rq-worker-*.log
```

---

## 📊 Monitoring

### Dashboard

เข้าถึงผ่าน: `https://0b3x44foetagtu-8010.proxy.runpod.net/dashboard/`

### API Monitoring

```bash
curl "https://0b3x44foetagtu-8010.proxy.runpod.net/api/monitoring/"
```

---

## 🔧 Troubleshooting

### Workers ไม่ทำงาน

1. ตรวจสอบ Worker Health:
   ```bash
   bash scripts/pod/check-worker-health.sh
   ```

2. Restart Workers:
   ```bash
   bash scripts/pod/restart-rq-workers.sh
   ```

### cuDNN/CTranslate2 Issues

1. ตรวจสอบ cuDNN installation:
   ```bash
   # ตรวจสอบว่า cuDNN ติดตั้งแล้ว
   ls -la /usr/lib/x86_64-linux-gnu/libcudnn_ops_infer.so.8
   
   # ถ้าไม่มี ให้ติดตั้ง
   apt-get update
   apt-get install -y libcudnn8
   ```

2. ตรวจสอบ `LD_LIBRARY_PATH`:
   ```bash
   echo $LD_LIBRARY_PATH
   # ควรมี: /usr/lib/x86_64-linux-gnu, /usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib
   ```

3. ตรวจสอบ Libraries:
   ```bash
   ls -la /usr/lib/x86_64-linux-gnu/libcudnn*.so.8
   ls -la /usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib/
   ls -la /usr/local/lib/python3.10/dist-packages/ctranslate2.libs/
   ```

4. Restart Services:
   ```bash
   bash scripts/pod/start-pod.sh
   bash scripts/pod/restart-rq-workers.sh
   ```

5. ตรวจสอบ Whisper API logs:
   ```bash
   tail -f /tmp/whisper.log | grep -E "cuDNN|Model loaded|ops_infer"
   ```

### API ไม่ตอบสนอง

1. ตรวจสอบ Process:
   ```bash
   ps aux | grep uvicorn
   ```

2. ตรวจสอบ Logs:
   ```bash
   tail -50 /tmp/main-api.log
   ```

3. Restart API:
   ```bash
   # วิธีที่ 1: ใช้ script restart-main-api.sh (แนะนำ)
   bash scripts/pod/restart-main-api.sh
   
   # วิธีที่ 2: Restart manual
   pkill -f "uvicorn.*app.main"
   bash scripts/pod/start-pod.sh
   ```

---

## 📝 Environment Variables

ไฟล์ `.env.runpod` ประกอบด้วย:

```bash
REDIS_URL=redis://default:...@redis-12598.c252.ap-southeast-1-1.ec2.cloud.redislabs.com:12598
WHISPER_PROVIDER=faster-whisper
WHISPER_MODEL=base
WHISPER_DEVICE=cuda
CUDA_VISIBLE_DEVICES=0
CUDNN_DISABLE=0
```

---

## 📚 Documentation

- [API Documentation](https://0b3x44foetagtu-8010.proxy.runpod.net/docs) - Swagger UI
- [Realtime API Guide](docs/REALTIME_API_GUIDE.md)
- [Faster Whisper Setup](docs/FASTER_WHISPER_SETUP.md)

---

## ✅ Checklist หลัง Restart Pod

- [ ] ติดตั้ง FFmpeg: `apt-get update && apt-get install -y ffmpeg` (ใน container ไม่ต้องใช้ sudo)
- [ ] ตรวจสอบ FFmpeg: `ffmpeg -version`
- [ ] `pip install -r requirements.txt`
- [ ] `bash scripts/pod/start-pod.sh`
- [ ] `bash scripts/pod/restart-rq-workers.sh`
- [ ] ตรวจสอบ Worker Health: `bash scripts/pod/check-worker-health.sh`
- [ ] ทดสอบ API: `curl https://0b3x44foetagtu-8010.proxy.runpod.net/health`

---

**Last Updated**: 2026-01-03

