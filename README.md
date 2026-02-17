# 🎙️ Transcription Service

บริการ Transcription สำหรับวิดีโอ/เสียง โดยใช้ Whisper, faster-whisper และ TyPhoon ASR พร้อม Multi-GPU Support

## 🚀 RunPod Quick Start

### First Setup (หลัง clone / container ใหม่)

```bash
apt-get update && apt-get install -y ffmpeg && \
pip install -r requirements.runpod-unified.txt && \
./scripts/utility/setup-cudnn-env.sh && \
./scripts/pod/start-pod.sh && \
./scripts/pod/start-rq-workers.sh
```

> **หมายเหตุ**: `requirements.runpod-unified.txt` รวม NeMo 2.5.3 สำหรับ TyPhoon ASR (FE Live Caption) — ไม่ต้องติดตั้ง `nemo-toolkit` แยก

### ตรวจสอบ CTranslate2 + GPU
```bash
./scripts/utility/verify-ctranslate2-gpu.sh
```

### Restart (เมื่อแก้ไข config หรือต้องการ restart services)

```bash
./scripts/pod/restart-main-api.sh && ./scripts/pod/restart-rq-workers.sh
```

> **หมายเหตุ**: สำหรับ RunPod container `cu1281-torch280` (CUDA 12.8), ถ้า `setup-cudnn-env.sh` แจ้ง path ไม่พบ ให้ตรวจสอบ `.env.runpod` มี `LD_LIBRARY_PATH` ที่ถูกต้องแล้ว และ start scripts จะโหลดจาก `.env.runpod` อัตโนมัติ

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
   - cuDNN 8.9.0.2 ติดตั้งแล้ว (compatible กับ CUDA 12.1)
   - `libcudnn_ops_infer.so.8` อยู่ใน `/usr/lib/x86_64-linux-gnu/`
   - Scripts จะตั้งค่า `LD_LIBRARY_PATH` อัตโนมัติ

4. **Redis** (สำหรับ job queue)
   - ใช้ Redis Cloud หรือ local Redis
   - ต้องมี Redis URL สำหรับเชื่อมต่อ (ระบุใน `.env.runpod`)

5. **System Libraries** (สำหรับ audio processing)
   - `libmagic1` - File type detection (optional, สำหรับ python-magic)
   - `libsndfile1` - Audio file I/O (required สำหรับ soundfile)
   - `tzdata` - Timezone data (required สำหรับ PyThaiNLP)

### Python Dependencies

ติดตั้งผ่าน `pip install -r requirements.txt`  
(ถ้าเคยเจอ `ModuleNotFoundError: No module named 'pkg_resources'` — ตอนนี้แก้แล้ว: ใส่ setuptools/wheel ใน requirements และเอา openai-whisper ออกจากรายการหลัก เพราะใช้ faster-whisper เป็น default)

**Dependencies หลัก** (ดูรายละเอียดทั้งหมดใน `requirements.txt`):

#### Web Framework
- `fastapi==0.104.1` - FastAPI framework
- `uvicorn[standard]==0.24.0` - ASGI server
- `python-multipart==0.0.6` - Form data handling
- `websockets==12.0` - WebSocket support

#### Whisper & Transcription
- `openai-whisper==20231117` - OpenAI Whisper
- `faster-whisper==1.2.1` - Faster Whisper (GPU accelerated)
- `ctranslate2==4.4.0` - CTranslate2 backend (รองรับ cuDNN 8.x)

#### Audio Processing
- `librosa==0.10.1` - Audio analysis
- `soundfile==0.12.1` - Audio file I/O
- `pydub==0.25.1` - Audio manipulation
- `ffmpeg-python==0.2.0` - FFmpeg Python wrapper

#### Job Queue & Database
- `redis[hiredis]==5.0.1` - Redis client
- `rq==1.15.1` - Redis Queue for job management
- `sqlalchemy==2.0.23` - SQL toolkit and ORM

#### Networking & Messaging
- `aiohttp==3.9.1` - Async HTTP client/server
- `requests==2.31.0` - HTTP library
- `httpx==0.25.2` - Async HTTP client
- `pika==1.3.2` - RabbitMQ client
- `aio-pika==9.3.0` - Async RabbitMQ client

#### Thai NLP
- `pythainlp==4.0.2` - Thai NLP library
- `attacut==1.0.6` - Thai word segmentation
- `tzdata>=2024.1` - Timezone data (required for PyThaiNLP)

#### Utilities
- `python-dotenv==1.0.0` - Environment variables
- `aiofiles==23.2.1` - Async file operations
- `pydantic==2.5.0` - Data validation
- `python-magic==0.4.27` - File type detection
- `psutil==5.9.6` - System and process utilities
- `jinja2==3.1.2` - Template engine

#### Security & Authentication
- `python-jose[cryptography]==3.3.0` - JWT handling
- `passlib[bcrypt]==1.7.4` - Password hashing

**หมายเหตุ**: 
- `torch` และ `torchaudio` ใช้จาก base image (2.2.0+cu121) ไม่ต้องติดตั้งใหม่
- Development dependencies (pytest, black, flake8) รวมอยู่ใน requirements.txt

### Models (Whisper Models)

⚠️ **สำคัญ**: โฟลเดอร์ `models/` ไม่ได้ถูก commit ใน Git repository เพราะมีขนาดใหญ่เกินไป (2.1GB+) และ GitHub มีไฟล์ size limit 100MB

Models จะถูกดาวน์โหลดอัตโนมัติเมื่อ:
- ใช้ `faster-whisper`: Models จะถูกดาวน์โหลดจาก Hugging Face Hub เมื่อเรียกใช้ครั้งแรก
- ตั้งค่า `WHISPER_DOWNLOAD_ROOT` environment variable เป็น `/workspace/transcription-service/models` เพื่อเก็บ models แบบถาวร

**Model Paths**:
- Default: `models/` (ใน working directory)
- สามารถกำหนดผ่าน: `WHISPER_DOWNLOAD_ROOT` environment variable

**หมายเหตุ**: สำหรับการ deploy ครั้งแรก Models จะต้องถูกดาวน์โหลดก่อนใช้งาน (อาจใช้เวลา 5-15 นาที ขึ้นอยู่กับ model size)

### NeMo + TyPhoon ASR (FE Live Caption)

ใช้สำหรับ **FE Live Caption** (WebSocket `/api/ws/ingest-audio`) เมื่อ `FE_CC_PROVIDER=typhoon`:

| รายการ | รายละเอียด |
|--------|-------------|
| **Package** | `nemo-toolkit[asr]==2.5.3` + `typhoon-asr>=0.1.1` |
| **โมเดล** | typhoon-ai/typhoon-asr-realtime (FastConformer-Transducer) |
| **ภาษา** | ไทย |
| **Use case** | Real-time caption streaming จาก browser |

⚠️ **NeMo Version**: ต้องใช้ **2.5.3** — NeMo 2.6.x มี CUDA error 35 (RNNT + CUDA 12.8)  
ref: [NVIDIA NeMo Issue #15145](https://github.com/NVIDIA-NeMo/NeMo/issues/15145)

**การตั้งค่า** `.env.runpod`:
```bash
FE_CC_PROVIDER=typhoon
FE_CC_TYPHOON_MODEL=typhoon-ai/typhoon-asr-realtime
FE_CC_TYPHOON_DEVICE=auto
```

**Real-time (ความเร็วขึ้น)**:
```bash
FE_CC_WINDOW_SECONDS=1.5
FE_CC_STEP_SECONDS=1.0
FE_CC_MIN_WINDOW_SECONDS=1.5
FE_CC_SILENCE_THRESHOLD=0.4
FE_CC_REALTIME_LOW_LATENCY=true   # ข้าม postprocess ลด latency ~100–300ms
```

**ทางเลือก**: ถ้า NeMo มีปัญหา ให้เปลี่ยนเป็น `FE_CC_PROVIDER=faster-whisper` (ใช้ CTranslate2 ไม่มี CUDA 35 bug)

---

## 🚀 Quick Start (หลังจาก Restart Pod Container)

เมื่อ restart pod container ใหม่ ต้องทำตามขั้นตอนนี้:

> **สรุป**: `pip install -r requirements.runpod-unified.txt` ติดตั้งทุกอย่างรวม NeMo 2.5.3 — **ไม่ต้องรัน `pip install "nemo-toolkit[asr]==2.5.3"` แยก**

### 1. Environment ตามจำนวน GPU (อัตโนมัติ)

Project โหลด config ตามจำนวน GPU โดยอัตโนมัติ เพื่อป้องกัน OOM:
- **1 GPU** → `.env.runpod-1GPU` (ลด workers, chunk limits)
- **2+ GPUs** → `.env.runpod-2GPU`

ดูรายละเอียด: [docs/ENV_PROFILE_BY_GPU.md](docs/ENV_PROFILE_BY_GPU.md)

**Override ด้วยมือ**:
```bash
ENV_PROFILE=1gpu ./scripts/pod/start-rq-workers.sh   # บังคับใช้ 1 GPU profile
```

### 2. ตรวจสอบ NUM_GPUS (ถ้าไม่ใช้ auto)

```bash
# ตรวจสอบจำนวน GPU จริง
nvidia-smi -L

# ตรวจสอบค่า NUM_GPUS ที่โหลด
grep NUM_GPUS .env.runpod
grep NUM_GPUS .env.runpod-1GPU
grep NUM_GPUS .env.runpod-2GPU
```

**หมายเหตุ**: 
- `start-rq-workers.sh` โหลด env ตาม GPU อัตโนมัติ
- ถ้าต้องการ override: ตั้ง `ENV_PROFILE=1gpu` หรือ `2gpu`

### 3. ติดตั้ง System Dependencies

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

### 4. ติดตั้ง Python Dependencies

```bash
cd /workspace/transcription-service
pip install -r requirements.runpod-unified.txt
```

**หมายเหตุ**: 
- `requirements.runpod-unified.txt` รวม faster-whisper, NeMo 2.5.3, typhoon-asr — **ไม่ต้องติดตั้ง NeMo แยก**
- Scripts จะจัดการ cuDNN และ CTranslate2 libraries อัตโนมัติผ่าน `LD_LIBRARY_PATH`
- cuDNN 8.9.0.2 ติดตั้งแล้ว (ไม่ต้องติดตั้งเพิ่ม)
- `whisper_api.py` จะตั้งค่า `LD_LIBRARY_PATH` และ pre-load cuDNN library อัตโนมัติ

### 5. ตั้งค่า GPU/CUDA (แนะนำ)

⚠️ **สำคัญ**: ขั้นตอนนี้แนะนำให้ทำเพื่อตรวจสอบว่า GPU/CUDA ทำงานได้ถูกต้อง

```bash
# ตั้งค่า cuDNN/CTranslate2 (persist LD_LIBRARY_PATH + ตรวจสอบ GPU)
bash scripts/utility/setup-cudnn-env.sh
```

**หมายเหตุ**: `setup-cudnn-env.sh` จะ ตั้งค่าและ persist `LD_LIBRARY_PATH` ตรวจสอบ cuDNN libraries และทดสอบ ctranslate2/faster-whisper

### 6. Start Services

```bash
bash scripts/pod/start-pod.sh
```

Script นี้จะ:
- ✅ ตั้งค่า `LD_LIBRARY_PATH` สำหรับ cuDNN และ CTranslate2
- ✅ ตรวจสอบ GPU
- ✅ สร้าง directories ที่จำเป็น
- ✅ โหลด environment variables จาก `.env.runpod`
- ✅ ตรวจสอบและติดตั้ง FFmpeg (ถ้ายังไม่มี)
- ✅ ตรวจสอบและติดตั้ง Python dependencies (ถ้ายังไม่มี)
- ✅ Start Whisper API (port 8002) พร้อม cuDNN support
- ✅ Start Main API (port 8010)

### 7. Start RQ Workers

```bash
# สำหรับ start ครั้งแรก (หรือถ้าไม่มี workers ทำงานอยู่)
bash scripts/pod/start-rq-workers.sh

# หรือ สำหรับ restart workers (หยุด workers เดิมก่อน แล้ว start ใหม่)
bash scripts/pod/restart-rq-workers.sh
```

Script นี้จะ:
- ✅ หยุด workers เดิม (ถ้ามี - สำหรับ `restart-rq-workers.sh`)
- ✅ ตั้งค่า `LD_LIBRARY_PATH` สำหรับ CUDA, cuDNN และ CTranslate2
  - **Order**: cuDNN → System path (`/usr/lib/x86_64-linux-gnu`) → CUDA → CTranslate2
  - ⚠️ **สำคัญ**: System path จำเป็นเพื่อให้ CTranslate2 หา `libcudnn_ops_infer.so.8` ได้
- ✅ อ่าน `NUM_GPUS` จาก `.env.runpod` อัตโนมัติ
- ✅ Start workers สำหรับทุก queue:
  - `transcription_priority` (priority queue สำหรับ realtime chunks)
  - `transcription_gpu0`, `transcription_gpu1`, ... (ตาม `NUM_GPUS`)
  - `transcription_preprocess` (สำหรับ audio extraction + chunking)
  - `transcription_cpu` (สำหรับ aggregator jobs)

---

## 📋 เกี่ยวกับ cuDNN และ CTranslate2

### การจัดการอัตโนมัติ

Scripts และ code จัดการ cuDNN และ CTranslate2 ให้อัตโนมัติ:

1. **cuDNN Libraries**: 
   - PyTorch cuDNN (หลัก): `/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib/libcudnn_ops_infer.so.8` (cuDNN 8.9.0.2)
   - System cuDNN (optional): `/usr/lib/x86_64-linux-gnu/libcudnn_ops_infer.so.8` (อาจไม่มี - ไม่เป็นปัญหา)
   - ⚠️ **สำคัญ**: CTranslate2 มองหา cuDNN libraries ใน system path (`/usr/lib/x86_64-linux-gnu/`)
   - **วิธีแก้ไข**: Scripts จะเพิ่ม system path เข้าไปใน `LD_LIBRARY_PATH` อัตโนมัติ
   - Compatible กับ CUDA 12.1 และ CTranslate2 4.4.0

2. **CTranslate2 Libraries**: อยู่ใน `/usr/local/lib/python3.10/dist-packages/ctranslate2.libs`
   - ติดตั้งผ่าน `pip install ctranslate2==4.4.0` (ใน requirements.txt)
   - รองรับ cuDNN 8.x

3. **Auto Configuration**:
   - `whisper_api.py` ตั้งค่า `LD_LIBRARY_PATH` และ pre-load cuDNN library อัตโนมัติ
   - `start-pod.sh` ตั้งค่า `LD_LIBRARY_PATH` สำหรับ Whisper API
   - `start-rq-workers.sh` ตั้งค่า `LD_LIBRARY_PATH` สำหรับ workers
   - **Order ของ LD_LIBRARY_PATH** (สำคัญมาก!):
     1. cuDNN path (PyTorch): `/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib`
     2. System path: `/usr/lib/x86_64-linux-gnu` ⚠️ **จำเป็น!** CTranslate2 มองหา cuDNN libraries ใน path นี้
     3. CUDA path: `/usr/local/cuda-12.1/lib64`
     4. CTranslate2 path: `/usr/local/lib/python3.10/dist-packages/ctranslate2.libs`

4. **Error Handling**:
   - ถ้า cuDNN error → auto-fallback เป็น CPU (แต่ไม่แนะนำ - ใช้ GPU เป็นหลัก)
   - Warning "Could not load library" อาจแสดง แต่ไม่กระทบการทำงาน

### ตรวจสอบว่าใช้งานได้

```bash
# 1. ทดสอบ CTranslate2 GPU Support และ GPU Visibility (แนะนำ - ทดสอบครบถ้วน)
bash scripts/utility/test-ctranslate2-gpu.sh

# 2. ตรวจสอบ Worker Health
bash scripts/pod/check-worker-health.sh

# 3. ตรวจสอบ GPU Usage
bash scripts/pod/check-gpu-usage.sh
```

**สคริปต์ทดสอบ `test-ctranslate2-gpu.sh` จะตรวจสอบ:**
- ✅ nvidia-smi (GPU hardware)
- ✅ PyTorch CUDA support
- ✅ CTranslate2 installation และ CUDA module
- ✅ CTranslate2 CUDA compute types
- ✅ LD_LIBRARY_PATH และ cuDNN libraries
- ✅ WhisperModel กับ CUDA (ทดสอบสร้าง model)
- ✅ GPU visibility ใน process

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

- **chunk_duration**: แนะนำ ≤ 30 วินาทีเมื่อใช้ faster-whisper (model มีข้อจำกัด ~30s ต่อหน้าต่าง)
- **CHUNK_OVERLAP_SECONDS** (env, default 5): จำนวนวินาทีที่ทับกันระหว่าง chunk เพื่อลดการหายของข้อความช่วงท้าย ตั้งเป็น `0` เพื่อปิด

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

# WS ingest|TyPhoon|CUDA FE LiveCaption
tail -f /tmp/main-api.log | grep -E "WS ingest|TyPhoon|CUDA"

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

2. ตรวจสอบ NUM_GPUS:
   ```bash
   # ตรวจสอบจำนวน GPU จริง
   nvidia-smi -L
   
   # ตรวจสอบค่า NUM_GPUS ใน .env.runpod
   grep NUM_GPUS .env.runpod
   
   # ตรวจสอบ CUDA_VISIBLE_DEVICES
   grep CUDA_VISIBLE_DEVICES .env.runpod
   ```
   ⚠️ **สำคัญ**: `NUM_GPUS` ต้องตรงกับจำนวน GPU จริง

3. Restart Workers:
   ```bash
   # สำหรับ start ครั้งแรก
   bash scripts/pod/start-rq-workers.sh
   
   # หรือสำหรับ restart
   bash scripts/pod/restart-rq-workers.sh
   ```

### Transcription ถูกตัดกลางประโยค

**อาการ**: ข้อความ transcription ถูกตัดกลางคำ (เช่น "ระดั" แทน "ระดับ") แม้เสียงจะไม่ขาดหาย

**สาเหตุ**: Whisper decoder มีขีดจำกัด **448 tokens** ต่อ segment — 30 วินาทีของภาษาไทยพูดหนาแน่นอาจเกิน limit

**วิธีแก้**: ตั้งค่า `WHISPER_CHUNK_LENGTH=15` ใน `.env.runpod` (default 15 แล้ว)
- ลดจาก 30s → 15s = sub-segment เล็กกว่า → แต่ละ segment ไม่เกิน token limit
- ถ้ายังตัดอยู่ ลองลดเป็น 12 หรือ 10 วินาที

### cuDNN/CTranslate2 Issues

**🔍 วิธีทดสอบ CTranslate2 และ GPU:**

ก่อนแก้ไขปัญหา ให้ทดสอบก่อน:
```bash
# ทดสอบครบถ้วน: CTranslate2 GPU support และ GPU visibility
bash scripts/utility/test-ctranslate2-gpu.sh
```

สคริปต์นี้จะตรวจสอบ:
- ✅ nvidia-smi (GPU hardware)
- ✅ PyTorch CUDA support
- ✅ CTranslate2 installation และ CUDA module
- ✅ CTranslate2 CUDA compute types
- ✅ LD_LIBRARY_PATH และ cuDNN libraries
- ✅ WhisperModel กับ CUDA (ทดสอบสร้าง model)
- ✅ GPU visibility ใน process

⚠️ **ปัญหาเรื่อง LD_LIBRARY_PATH ที่เคยพบ**:
- CTranslate2 ต้องการ cuDNN libraries (`libcudnn_ops_infer.so.8`) ใน `LD_LIBRARY_PATH`
- **ปัญหาหลัก**: CTranslate2 มองหา cuDNN libraries ใน system path (`/usr/lib/x86_64-linux-gnu/`) แต่ไฟล์อยู่ใน PyTorch path (`/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib/`)
- **วิธีแก้ไข**: เพิ่ม system path (`/usr/lib/x86_64-linux-gnu`) เข้าไปใน `LD_LIBRARY_PATH` (แก้ไขแล้วใน `start-rq-workers.sh`)
- อาการ: Transcription ใช้เวลา >2 นาที สำหรับไฟล์ 30 นาที (ควรใช้ 1-2 นาที), GPU ไม่ทำงาน (CPU fallback)

**วิธีแก้ไข**:

1. **ใช้ setup-cudnn-env.sh**:
   ```bash
   bash scripts/utility/setup-cudnn-env.sh
   ```
   Script นี้จะ: ตั้งค่าและ persist `LD_LIBRARY_PATH` ตรวจสอบ cuDNN libraries และทดสอบ ctranslate2/faster-whisper

2. ตรวจสอบ cuDNN installation (ถ้าต้องการตรวจสอบเอง):
   ```bash
   # ตรวจสอบ cuDNN ใน PyTorch path (หลัก)
   ls -la /usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib/libcudnn_ops_infer.so.8
   
   # ตรวจสอบ cuDNN ใน system path (อาจไม่มี - ไม่เป็นปัญหา)
   ls -la /usr/lib/x86_64-linux-gnu/libcudnn_ops_infer.so.8
   # ⚠️ ถ้าไม่มีใน system path ไม่เป็นปัญหา - scripts จะเพิ่ม path นี้เข้าไปใน LD_LIBRARY_PATH
   ```

3. ตรวจสอบ `LD_LIBRARY_PATH` ใน workers:
   ```bash
   # ตรวจสอบ LD_LIBRARY_PATH ใน worker process
   ps aux | grep "rq worker" | grep -v grep | head -1 | awk '{print $2}' | xargs -I {} cat /proc/{}/environ | tr '\0' '\n' | grep LD_LIBRARY_PATH
   
   # ควรมี (ในลำดับนี้):
   # 1. /usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib
   # 2. /usr/lib/x86_64-linux-gnu  ⚠️ สำคัญ!
   # 3. /usr/local/cuda-12.1/lib64
   # 4. /usr/local/lib/python3.10/dist-packages/ctranslate2.libs
   ```

3. ตรวจสอบว่า workers ใช้ GPU จริงหรือไม่:
   ```bash
   # ตรวจสอบ GPU usage (ควรเห็น processes เมื่อ transcription ทำงาน)
   nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
   
   # ถ้าไม่เห็น processes = workers ใช้ CPU (ช้ามาก!)
   ```

5. ตรวจสอบ Libraries:
   ```bash
   ls -la /usr/lib/x86_64-linux-gnu/libcudnn*.so.8  # อาจไม่มี - ไม่เป็นปัญหา
   ls -la /usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib/
   ls -la /usr/local/lib/python3.10/dist-packages/ctranslate2.libs/
   ```

5. ตั้งค่า GPU/CUDA (แนะนำ):
   ```bash
   bash scripts/utility/setup-cudnn-env.sh
   ```

6. Restart Services:
   ```bash
   bash scripts/pod/start-pod.sh
   bash scripts/pod/start-rq-workers.sh  # หรือ restart-rq-workers.sh
   ```

6. ตรวจสอบ Worker logs:
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

- [ ] **ตรวจสอบและปรับ NUM_GPUS**: ตรวจสอบว่า `NUM_GPUS` ใน `.env.runpod` ตรงกับจำนวน GPU จริง
  ```bash
  nvidia-smi -L  # ตรวจสอบจำนวน GPU จริง
  grep NUM_GPUS .env.runpod  # ตรวจสอบค่าใน .env.runpod
  ```
- [ ] **ติดตั้ง FFmpeg**: `apt-get update && apt-get install -y ffmpeg` (ใน container ไม่ต้องใช้ sudo)
- [ ] **ตรวจสอบ FFmpeg**: `ffmpeg -version`
- [ ] **ติดตั้ง Python Dependencies**: `pip install -r requirements.txt`
- [ ] **ตั้งค่า GPU/CUDA** (แนะนำ): `bash scripts/utility/setup-cudnn-env.sh`
- [ ] **ทดสอบ CTranslate2 และ GPU**: `bash scripts/utility/test-ctranslate2-gpu.sh` (ตรวจสอบว่าทุกอย่างทำงานได้)
- [ ] **Start Services**: `bash scripts/pod/start-pod.sh`
- [ ] **Start RQ Workers**: `bash scripts/pod/start-rq-workers.sh` (หรือ `restart-rq-workers.sh` สำหรับ restart)
- [ ] **ตรวจสอบ Worker Health**: `bash scripts/pod/check-worker-health.sh`
- [ ] **ตรวจสอบ GPU Usage**: `nvidia-smi --query-compute-apps` (ควรเห็น processes เมื่อ transcription ทำงาน)
- [ ] **ตรวจสอบ LD_LIBRARY_PATH ใน workers**:
  ```bash
  ps aux | grep "rq worker" | grep -v grep | head -1 | awk '{print $2}' | xargs -I {} cat /proc/{}/environ | tr '\0' '\n' | grep LD_LIBRARY_PATH
  # ควรมี: /usr/lib/x86_64-linux-gnu (system path) ⚠️ สำคัญ!
  ```
- [ ] **ทดสอบ API**: `curl https://0b3x44foetagtu-8010.proxy.runpod.net/health`
- [ ] **ตรวจสอบระบบครบ (Port + GPU + Process)**: `bash scripts/pod/check-system.sh`

**หมายเหตุ**: 
- Scripts (`start-rq-workers.sh`) จะตั้งค่า LD_LIBRARY_PATH อัตโนมัติ (รวม system path) - ไม่ต้องตั้งค่าเอง
- `start-rq-workers.sh` จะอ่าน `NUM_GPUS` จาก `.env.runpod` อัตโนมัติ - ต้องตรวจสอบให้ตรงกับจำนวน GPU จริง

---

**Last Updated**: 2026-01-03