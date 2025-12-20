# 📋 ตรวจสอบ Dependencies ของ Container

## 🐳 Container Base Image
**Image**: `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`

---

## ✅ สิ่งที่มีอยู่แล้วใน Container (Default)

### System Dependencies
- ✅ **Python**: 3.10.12
- ✅ **CUDA Toolkit**: 11.8 (ครบถ้วน)
  - cuda-cudart-11-8
  - cuda-compiler-11-8
  - cuda-libraries-11-8
  - และ packages อื่นๆ ครบชุด
- ✅ **cuDNN**: 8.7 (8700)
- ✅ **Build Tools**: gcc, cmake, git (devel image)

### Python Packages ที่มีอยู่แล้ว
- ✅ **PyTorch**: 2.1.0+cu118 (พร้อม CUDA support)
- ✅ **torchaudio**: 2.1.0+cu118
- ✅ **torchvision**: 0.16.0+cu118
- ✅ **Jupyter/IPython**: ครบชุด (Jupyter Notebook, IPython, และ extensions)
- ✅ **Python packages อื่นๆ**: ~140 packages (ส่วนใหญ่เป็น Jupyter ecosystem)

### GPU Support
- ✅ **CUDA Available**: True
- ✅ **CUDA Version**: 11.8
- ✅ **cuDNN Version**: 8.7
- ✅ **GPU**: NVIDIA RTX 4000 Ada Generation (20GB VRAM)

---

## ❌ Dependencies ที่ยังขาด (ต้องติดตั้ง)

### System Dependencies
- ❌ **FFmpeg**: ไม่พบใน PATH (ต้องติดตั้ง)

### Python Packages (จาก `requirements.txt`)

#### Web Framework
- ❌ `fastapi==0.104.1`
- ❌ `uvicorn[standard]==0.24.0`
- ❌ `python-multipart==0.0.6`
- ❌ `websockets==12.0`

#### Whisper & Transcription
- ❌ `openai-whisper==20231117`
- ❌ `faster-whisper==1.0.3`
- ❌ `ctranslate2` (dependency ของ faster-whisper)

#### Audio Processing
- ❌ `librosa==0.10.1`
- ❌ `soundfile==0.12.1`
- ❌ `pydub==0.25.1`
- ❌ `ffmpeg-python==0.2.0`

#### Networking & Messaging
- ❌ `redis[hiredis]==5.0.1`
- ❌ `aiohttp==3.9.1`
- ❌ `pika==1.3.2` (RabbitMQ client)
- ❌ `aio-pika==9.3.0` (Async RabbitMQ client)

#### File Handling
- ❌ `aiofiles==23.2.1`
- ❌ `python-magic==0.4.27`

#### Data Handling
- ❌ `pydantic==2.5.0`
- ❌ `python-json-logger==2.0.7`
- ❌ `requests==2.31.0`
- ❌ `httpx==0.25.2`

#### Thai NLP
- ❌ `pythainlp==4.0.2`
- ❌ `attacut==1.0.6`

#### Utilities
- ❌ `python-dotenv==1.0.0`
- ❌ `click==8.1.7`
- ❌ `tqdm==4.66.1`
- ❌ `psutil==5.9.6`
- ❌ `jinja2==3.1.2`

#### Other
- ❌ `asyncio-mqtt==0.16.1`
- ❌ `docker==6.1.3`
- ❌ `sqlalchemy==2.0.23`
- ❌ `python-jose[cryptography]==3.3.0`
- ❌ `passlib[bcrypt]==1.7.4`

#### Development (Optional)
- ❌ `pytest==7.4.3`
- ❌ `pytest-asyncio==0.21.1`
- ❌ `black==23.11.0`
- ❌ `flake8==6.1.0`

---

## 📊 สรุป

### ✅ มีอยู่แล้ว (ไม่ต้องติดตั้ง)
- PyTorch 2.1.0+cu118 (พร้อม CUDA 11.8)
- cuDNN 8.7
- CUDA Toolkit 11.8 (ครบชุด)
- Jupyter/IPython ecosystem

### ❌ ต้องติดตั้ง
- **FFmpeg** (system package)
- **Python packages ทั้งหมดจาก `requirements.txt`** (~50+ packages)

---

## 🔧 วิธีติดตั้ง (เมื่อพร้อม)

### 1. ติดตั้ง FFmpeg
```bash
# วิธีที่ 1: จาก apt (แนะนำ)
sudo apt-get update && sudo apt-get install -y ffmpeg

# วิธีที่ 2: Static binary (ถ้า apt ไม่ได้)
# ใช้ script: scripts/pod/install-ffmpeg-persistent.sh
```

### 2. ติดตั้ง Python Dependencies
```bash
# ติดตั้งจาก requirements.txt
pip3 install -r requirements.txt

# หรือติดตั้งเฉพาะที่จำเป็น (ถ้าไม่ต้องการ development packages)
pip3 install fastapi uvicorn faster-whisper openai-whisper redis aiohttp pika librosa soundfile pydub ffmpeg-python aiofiles python-dotenv pydantic requests
```

### 3. ติดตั้ง CTranslate2 (สำหรับ faster-whisper)
```bash
# สำหรับ CUDA 11.8
pip3 install ctranslate2==4.4.0

# หรือใช้ script: scripts/pod/fix-ctranslate2-cuda.sh
```

---

## 📝 หมายเหตุ

- Container นี้เป็น **devel** image จึงมี build tools ครบถ้วน
- PyTorch และ CUDA พร้อมใช้งานแล้ว ไม่ต้องติดตั้งเพิ่ม
- Jupyter/IPython มีอยู่แล้ว แต่ไม่จำเป็นสำหรับ transcription service
- **ยังไม่ต้องติดตั้งอะไรเพิ่ม** ตามที่ผู้ใช้ระบุ

