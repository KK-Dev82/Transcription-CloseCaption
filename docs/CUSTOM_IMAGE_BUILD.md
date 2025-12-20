# 🐳 Build Custom Image สำหรับ Pod Container

## 📋 สรุป

Custom Image นี้มี **dependencies ทั้งหมดติดตั้งไว้แล้ว** ใน image ไม่ต้องติดตั้งใหม่ทุกครั้งที่ restart POD

---

## ✅ Python Libraries ที่ติดตั้งใน Image

### Core Dependencies (จาก `requirements.txt`)

#### Web Framework
- ✅ `fastapi==0.104.1`
- ✅ `uvicorn[standard]==0.24.0`
- ✅ `python-multipart==0.0.6`
- ✅ `websockets==12.0` ⚠️ **เพิ่มใน Dockerfile.runpod-custom**

#### Whisper & Transcription
- ✅ `openai-whisper==20231117`
- ✅ `faster-whisper==1.0.3`
- ✅ `ctranslate2==4.4.0` (compatible กับ cuDNN 8)

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
- ✅ `pydantic==2.5.0`
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

### System Dependencies

- ✅ **FFmpeg** (ติดตั้งใน image)
- ✅ **tzdata** (ติดตั้งใน image)
- ✅ **cuDNN 8.7** (มีใน base image)
- ✅ **CUDA 11.8** (มีใน base image)
- ✅ **PyTorch 2.1.0+cu118** (มีใน base image, upgrade เป็น 2.1.1)
- ✅ **Audio libraries**: libmagic1, libsndfile1, libportaudio2, libasound2-dev, portaudio19-dev

---

## 🚀 วิธี Build Custom Image

### 1. Build Image

```bash
cd /workspace/transcription-service

# Build image
docker build -f Dockerfile.runpod-custom -t your-registry/transcription-service:latest .

# หรือระบุ tag
docker build -f Dockerfile.runpod-custom -t your-registry/transcription-service:v1.0.0 .
```

### 2. Push Image (ถ้าต้องการ)

```bash
# Login to registry
docker login your-registry

# Push image
docker push your-registry/transcription-service:latest
```

### 3. ใช้ Image ใน RunPod

1. ไปที่ RunPod Dashboard
2. สร้าง Pod ใหม่
3. เลือก Custom Image: `your-registry/transcription-service:latest`
4. Clone repository:
   ```bash
   git clone <repo> /workspace/transcription-service
   ```
5. Start services:
   ```bash
   cd /workspace/transcription-service
   bash scripts/pod/start-pod.sh
   ```

---

## 📊 เปรียบเทียบ: Base Image vs Custom Image

| Feature | Base Image | Custom Image |
|---------|-----------|--------------|
| **FFmpeg** | ❌ ต้องติดตั้ง | ✅ มีใน image |
| **tzdata** | ❌ ต้องติดตั้ง | ✅ มีใน image |
| **Python packages** | ❌ ต้องติดตั้ง | ✅ มีใน image |
| **CTranslate2** | ❌ ต้องติดตั้ง | ✅ มีใน image (4.4.0) |
| **faster-whisper** | ❌ ต้องติดตั้ง | ✅ มีใน image |
| **FastAPI, Uvicorn** | ❌ ต้องติดตั้ง | ✅ มีใน image |
| **Restart time** | ~5-10 นาที | ~30 วินาที |

---

## ✅ ข้อดีของ Custom Image

1. **ไม่ต้องติดตั้ง dependencies** - ทุกอย่างมีใน image แล้ว
2. **Restart เร็ว** - ไม่ต้องรอ install packages
3. **ลดความเสี่ยง** - ไม่มีปัญหา network timeout, connection reset
4. **Consistent** - ทุก Pod ใช้ dependencies เวอร์ชันเดียวกัน
5. **Ready to use** - Clone repo และ start services ได้ทันที

---

## ⚠️ หมายเหตุ

### CTranslate2 Version
- **ใช้ CTranslate2 4.4.0** (ไม่ใช่ 4.5.0+) เพื่อรองรับ cuDNN 8
- CTranslate2 4.5.0+ ต้องการ cuDNN 9 แต่ base image มี cuDNN 8.7

### PyTorch Version
- Base image มี PyTorch 2.1.0+cu118
- Dockerfile จะ upgrade เป็น 2.1.1 (ถ้า upgrade ไม่ได้ จะใช้ 2.1.0)

### System Dependencies
- FFmpeg และ tzdata ติดตั้งใน image แล้ว **ไม่หายหลัง restart**
- cuDNN libraries อยู่ใน image แล้ว

---

## 🔍 ตรวจสอบ Image

```bash
# ตรวจสอบ packages ที่ติดตั้ง
docker run --rm your-registry/transcription-service:latest \
  pip3 list | grep -E "(fastapi|uvicorn|faster-whisper|ctranslate2)"

# ตรวจสอบ FFmpeg
docker run --rm your-registry/transcription-service:latest \
  ffmpeg -version

# ตรวจสอบ CUDA/cuDNN
docker run --rm --gpus all your-registry/transcription-service:latest \
  python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, cuDNN: {torch.backends.cudnn.version()}')"
```

---

## 📝 Files ที่เกี่ยวข้อง

- `Dockerfile.runpod-custom` - Custom Image Dockerfile
- `requirements.txt` - Python dependencies list
- `docs/SYSTEM_LEVEL_DEPENDENCIES.md` - System dependencies ที่ reset เมื่อ restart

---

**Last Updated**: 2025-01-XX  
**Base Image**: `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`

