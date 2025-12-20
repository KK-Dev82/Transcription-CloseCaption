# 🐳 Build Base Image ใหม่สำหรับ Transcription Service

## 📋 สรุป

Base Image ใหม่ที่สร้างจาก **`pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`** และมี **dependencies ทั้งหมดติดตั้งไว้แล้ว** ใน image

---

## 🎯 Base Image

**Base Image**: `pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`

### สิ่งที่มีใน Base Image
- ✅ **Python**: 3.10
- ✅ **PyTorch**: 2.1.0+cu118 (พร้อม CUDA support)
- ✅ **CUDA**: 11.8.0
- ✅ **cuDNN**: 8.7 (8700)
- ✅ **Build Tools**: gcc, cmake, git (devel image)
- ✅ **Ubuntu**: 22.04

---

## ✅ Dependencies ที่ติดตั้งใน Image

### System Dependencies
- ✅ **FFmpeg** - Video/audio processing
- ✅ **tzdata** - Timezone data (required for pythainlp)
- ✅ **Redis** - Local Redis service
- ✅ **Audio Libraries**: libmagic1, libsndfile1, libportaudio2, libasound2-dev, portaudio19-dev
- ✅ **Build Tools**: build-essential, cmake, git, git-lfs, wget, curl
- ✅ **Utilities**: ca-certificates, gnupg, lsb-release, netcat, telnet, jq

### Python Libraries (จาก `requirements.txt`)

#### Web Framework
- ✅ `fastapi==0.104.1`
- ✅ `uvicorn[standard]==0.24.0`
- ✅ `python-multipart==0.0.6`
- ✅ `websockets==12.0`
- ✅ `pydantic==2.5.0`

#### Whisper & Transcription
- ✅ `openai-whisper==20231117`
- ✅ `faster-whisper==1.0.3`
- ✅ `ctranslate2==4.4.0` ⚠️ **ใช้ 4.4.0 เพื่อรองรับ cuDNN 8**

#### Audio Processing
- ✅ `librosa==0.10.1`
- ✅ `soundfile==0.12.1`
- ✅ `pydub==0.25.1`
- ✅ `ffmpeg-python==0.2.0`

#### Networking & Messaging
- ✅ `redis[hiredis]==5.0.1`
- ✅ `aiohttp==3.9.1`
- ✅ `pika==1.3.2`
- ✅ `aio-pika==9.3.0`

#### File Handling
- ✅ `aiofiles==23.2.1`
- ✅ `python-magic==0.4.27`

#### Data Handling
- ✅ `python-json-logger==2.0.7`
- ✅ `requests==2.31.0`
- ✅ `httpx==0.25.2`

#### Thai NLP
- ✅ `pythainlp==4.0.2`
- ✅ `attacut==1.0.6`

#### Utilities
- ✅ `python-dotenv==1.0.0`
- ✅ `click==8.1.7`
- ✅ `tqdm==4.66.1`
- ✅ `psutil==5.9.6`
- ✅ `jinja2==3.1.2`

#### Other
- ✅ `asyncio-mqtt==0.16.1`
- ✅ `docker==6.1.3`
- ✅ `sqlalchemy==2.0.23`
- ✅ `python-jose[cryptography]==3.3.0`
- ✅ `passlib[bcrypt]==1.7.4`

#### Development (Optional)
- ✅ `pytest==7.4.3`
- ✅ `pytest-asyncio==0.21.1`
- ✅ `black==23.11.0`
- ✅ `flake8==6.1.0`

---

## 🚀 วิธี Build Base Image

### 1. Build Image

```bash
cd /workspace/transcription-service

# Build image
docker build -f Dockerfile.base-new -t your-registry/transcription-base:latest .

# หรือระบุ tag
docker build -f Dockerfile.base-new -t your-registry/transcription-base:v1.0.0 .
```

### 2. ใช้ Script (แนะนำ)

```bash
# Build image
bash scripts/build-custom-image.sh --name transcription-base --tag latest

# Build และ push
bash scripts/build-custom-image.sh \
  --registry your-registry.io \
  --name transcription-base \
  --tag v1.0.0 \
  --push
```

### 3. Push Image (ถ้าต้องการ)

```bash
# Login to registry
docker login your-registry

# Push image
docker push your-registry/transcription-base:latest
```

---

## 📊 เปรียบเทียบ: Base Image vs Custom Image

| Feature | Base Image (pytorch/pytorch) | Custom Image (runpod/pytorch) |
|---------|----------------------------|------------------------------|
| **Source** | PyTorch Official | RunPod Template |
| **FFmpeg** | ❌ ต้องติดตั้ง | ❌ ต้องติดตั้ง |
| **tzdata** | ❌ ต้องติดตั้ง | ❌ ต้องติดตั้ง |
| **Python packages** | ❌ ต้องติดตั้ง | ❌ ต้องติดตั้ง |
| **CTranslate2** | ❌ ต้องติดตั้ง | ❌ ต้องติดตั้ง |
| **faster-whisper** | ❌ ต้องติดตั้ง | ❌ ต้องติดตั้ง |
| **FastAPI, Uvicorn** | ❌ ต้องติดตั้ง | ❌ ต้องติดตั้ง |
| **Restart time** | ~5-10 นาที | ~5-10 นาที |

**หลังจาก Build Base Image ใหม่**:
| Feature | Base Image (pytorch/pytorch) | Custom Image (runpod/pytorch) |
|---------|----------------------------|------------------------------|
| **FFmpeg** | ✅ มีใน image | ✅ มีใน image |
| **tzdata** | ✅ มีใน image | ✅ มีใน image |
| **Python packages** | ✅ มีใน image | ✅ มีใน image |
| **CTranslate2** | ✅ มีใน image | ✅ มีใน image |
| **faster-whisper** | ✅ มีใน image | ✅ มีใน image |
| **FastAPI, Uvicorn** | ✅ มีใน image | ✅ มีใน image |
| **Restart time** | ~30 วินาที | ~30 วินาที |

---

## ✅ ข้อดีของ Base Image ใหม่

1. **ไม่ต้องติดตั้ง dependencies** - ทุกอย่างมีใน image แล้ว
2. **Restart เร็ว** - ไม่ต้องรอ install packages (~30 วินาที vs ~5-10 นาที)
3. **ลดความเสี่ยง** - ไม่มีปัญหา network timeout, connection reset
4. **Consistent** - ทุก Pod ใช้ dependencies เวอร์ชันเดียวกัน
5. **Ready to use** - Clone repo และ start services ได้ทันที
6. **ใช้ PyTorch Official Image** - เสถียรและได้รับการดูแลจาก PyTorch team

---

## ⚠️ หมายเหตุสำคัญ

### CTranslate2 Version
- **ใช้ CTranslate2 4.4.0** (ไม่ใช่ 4.5.0+) เพื่อรองรับ cuDNN 8
- CTranslate2 4.5.0+ ต้องการ cuDNN 9 แต่ base image มี cuDNN 8.7
- ⚠️ **สำคัญ**: ต้องใช้ `ctranslate2==4.4.0` เท่านั้น

### PyTorch Version
- Base image มี PyTorch 2.1.0+cu118 อยู่แล้ว
- ไม่ต้อง upgrade (เว้นแต่ต้องการ 2.1.1)

### System Dependencies
- FFmpeg และ tzdata ติดตั้งใน image แล้ว **ไม่หายหลัง restart**
- cuDNN libraries อยู่ใน image แล้ว

---

## 🔍 ตรวจสอบ Image

```bash
# ตรวจสอบ packages ที่ติดตั้ง
docker run --rm your-registry/transcription-base:latest \
  pip3 list | grep -E "(fastapi|uvicorn|faster-whisper|ctranslate2)"

# ตรวจสอบ FFmpeg
docker run --rm your-registry/transcription-base:latest \
  ffmpeg -version

# ตรวจสอบ CUDA/cuDNN
docker run --rm --gpus all your-registry/transcription-base:latest \
  python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, cuDNN: {torch.backends.cudnn.version()}')"

# ตรวจสอบ CTranslate2 version
docker run --rm --gpus all your-registry/transcription-base:latest \
  python3 -c "import ctranslate2; print(f'CTranslate2: {ctranslate2.__version__}')"
```

---

## 📝 วิธีใช้งานใน RunPod

### 1. ใช้ Custom Image ใน RunPod

1. ไปที่ RunPod Dashboard
2. สร้าง Pod ใหม่
3. เลือก **Custom Image**: `your-registry/transcription-base:latest`
4. Clone repository:
   ```bash
   git clone <repo> /workspace/transcription-service
   ```
5. Start services:
   ```bash
   cd /workspace/transcription-service
   bash scripts/pod/start-pod.sh
   ```

### 2. หลังจาก Restart POD

```bash
# Dependencies มีอยู่แล้วใน image - ไม่ต้อง install
cd /workspace/transcription-service
bash scripts/pod/start-pod.sh
```

---

## 📝 Files ที่เกี่ยวข้อง

- `Dockerfile.base-new` - Base Image Dockerfile (ใช้ pytorch/pytorch base)
- `scripts/build-custom-image.sh` - Script สำหรับ build image
- `requirements.txt` - Python dependencies list
- `docs/SYSTEM_LEVEL_DEPENDENCIES.md` - System dependencies ที่ reset เมื่อ restart

---

## 🎯 สรุป

**Base Image ใหม่**:
- ✅ ใช้ `pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`
- ✅ มี dependencies ทั้งหมดติดตั้งไว้แล้ว
- ✅ ไม่ต้อง install ใหม่หลัง restart POD
- ✅ Restart เร็ว (~30 วินาที)
- ✅ Ready to use - Clone repo และ start services ได้ทันที

---

**Last Updated**: 2025-01-XX  
**Base Image**: `pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`

