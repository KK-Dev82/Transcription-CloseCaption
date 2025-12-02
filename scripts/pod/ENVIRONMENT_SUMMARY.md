# 📋 สรุป Environment ทั้งหมดจาก Container

เอกสารนี้สรุป Environment, Libraries, Resources, และ Models ทั้งหมดจาก Container ที่ทำงานได้สำเร็จ เพื่อใช้ในการสร้าง Container Image สำหรับ Z2

---

## 📦 Python Packages

### Core Packages (ที่สำคัญ)

```bash
torch==2.1.0+cu118
torchaudio==2.1.0+cu118
torchvision==0.16.0+cu118
ctranslate2==4.4.0
faster-whisper==1.0.2
numpy==1.26.4
```

### Command สำหรับติดตั้ง:

```bash
pip3 install --no-cache-dir \
    torch==2.1.0 \
    torchaudio==2.1.0 \
    --index-url https://download.pytorch.org/whl/cu118

pip3 install --no-cache-dir \
    numpy==1.26.4 \
    "ctranslate2==4.4.0" \
    "faster-whisper==1.0.2"
```

**⚠️ สำคัญ**: ใช้ `ctranslate2==4.4.0` (ไม่ใช่ 4.5.0) เพราะรองรับ cuDNN 8.7

### Dependencies อื่นๆ

```bash
fastapi
uvicorn
pydantic
requests
aiohttp
aiofiles
redis
pika
python-dotenv
tzdata
ffmpeg-python
```

---

## 🔧 System Packages

### ที่ติดตั้งแล้ว

- `ffmpeg` - สำหรับแปลงวิดีโอ/เสียง
- `git` - สำหรับ clone repository
- `git-lfs` - สำหรับโมเดล/ไฟล์ใหญ่
- `wget` / `curl` - สำหรับดาวน์โหลด
- `build-essential` - สำหรับ build packages
- `cmake` - สำหรับ build dependencies

### Command สำหรับติดตั้ง:

```bash
apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    git-lfs \
    wget \
    curl \
    ffmpeg \
    ca-certificates \
    gnupg \
    lsb-release \
    netcat \
    telnet \
    jq \
    && rm -rf /var/lib/apt/lists/*
```

---

## 🎮 CUDA และ GPU Configuration

### Versions

- **PyTorch CUDA Version**: 11.8
- **cuDNN Version**: 8700 (cuDNN 8.7)
- **CUDA Driver Version**: 12.8 (จาก host)
- **GPU**: NVIDIA GeForce RTX 4080 SUPER

### Library Paths

```bash
LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/torch/lib:/usr/local/cuda-11.8/targets/x86_64-linux/lib:$LD_LIBRARY_PATH
```

### Symlinks ที่ต้องสร้าง

```bash
# สร้าง symlink สำหรับ libcublas.so.12
cd /usr/local/cuda-11.8/targets/x86_64-linux/lib
ln -sf libcublas.so.11.11.3.6 libcublas.so.12
```

---

## 🌍 Environment Variables

### สำหรับ CTranslate2 และ CUDA

```bash
export CT2_USE_CUDA_GRAPH=0
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export CUDA_VISIBLE_DEVICES=0
```

### สำหรับ Python

```bash
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
export DEBIAN_FRONTEND=noninteractive
```

### สำหรับ Hugging Face Cache

```bash
export HF_HOME=/workspace/.cache/huggingface
```

---

## 📁 Directory Structure

```
/workspace/
└── transcription-service/
    ├── uploads/          # วิดีโอ/เสียงที่อัปโหลด
    ├── temp/             # ไฟล์ชั่วคราว
    ├── storage/          # เก็บผลลัพธ์
    └── .cache/
        └── huggingface/  # Whisper models cache
```

---

## 🤖 Whisper Models

### Models ที่ดาวน์โหลดแล้ว (ใน cache)

- `faster-whisper-tiny` - Model เล็ก (39M)
- `faster-whisper-medium` - Model กลาง (769M)

### Path

```
/root/.cache/huggingface/hub/models--Systran--faster-whisper-{model}/
```

### การดาวน์โหลด

Models จะดาวน์โหลดอัตโนมัติเมื่อใช้งานครั้งแรก หรือใช้ Hugging Face cache

---

## 🔧 Scripts ที่สำคัญ

### 1. `setup-gpu-env.sh`

ตั้งค่า GPU environment variables และ library paths

```bash
source scripts/pod/setup-gpu-env.sh
```

### 2. `fix-cuda-mismatch-on-server.sh`

แก้ไขปัญหา CUDA version mismatch (ถ้ามี)

```bash
bash scripts/pod/fix-cuda-mismatch-on-server.sh
```

---

## 📝 สรุปสำหรับสร้าง Dockerfile

### Base Image

```dockerfile
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime
```

หรือ

```dockerfile
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04
```

### Installation Steps

```dockerfile
# 1. Install system packages
RUN apt-get update && apt-get install -y \
    build-essential cmake git git-lfs wget curl ffmpeg \
    ca-certificates gnupg lsb-release netcat telnet jq \
    && rm -rf /var/lib/apt/lists/*

# 2. Initialize git-lfs
RUN git lfs install

# 3. Install PyTorch (ถ้า base image ยังไม่มี)
RUN pip3 install --no-cache-dir \
    torch==2.1.0 \
    torchaudio==2.1.0 \
    --index-url https://download.pytorch.org/whl/cu118

# 4. Install faster-whisper dependencies
RUN pip3 install --no-cache-dir \
    numpy==1.26.4 \
    "ctranslate2==4.4.0" \
    "faster-whisper==1.0.2"

# 5. Install other Python dependencies
RUN pip3 install --no-cache-dir \
    fastapi uvicorn pydantic requests aiohttp aiofiles \
    redis pika python-dotenv tzdata ffmpeg-python

# 6. Create directories
RUN mkdir -p /workspace/transcription-service/{uploads,temp,storage}
RUN mkdir -p /workspace/.cache/huggingface

# 7. Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV CUDA_VISIBLE_DEVICES=0
ENV CT2_USE_CUDA_GRAPH=0
ENV OMP_NUM_THREADS=4
ENV MKL_NUM_THREADS=4
ENV HF_HOME=/workspace/.cache/huggingface

# 8. Set library paths
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/torch/lib:/usr/local/cuda-11.8/targets/x86_64-linux/lib:$LD_LIBRARY_PATH

# 9. Create symlink สำหรับ libcublas
RUN cd /usr/local/cuda-11.8/targets/x86_64-linux/lib && \
    ln -sf libcublas.so.11.11.3.6 libcublas.so.12 || true
```

---

## ✅ Checklist สำหรับ Z2

- [ ] Base image มี PyTorch 2.1.0+cu118
- [ ] ติดตั้ง CTranslate2 4.4.0 (ไม่ใช่ 4.5.0)
- [ ] ติดตั้ง faster-whisper 1.0.2
- [ ] ติดตั้ง numpy 1.26.4
- [ ] ติดตั้ง ffmpeg และ system packages
- [ ] ตั้งค่า environment variables
- [ ] ตั้งค่า LD_LIBRARY_PATH
- [ ] สร้าง symlink libcublas.so.12
- [ ] สร้าง directories structure
- [ ] ตั้งค่า Hugging Face cache path

---

## 🔍 ตรวจสอบ Environment

### สคริปต์ตรวจสอบ

```bash
python3 << 'PYEOF'
import torch
import ctranslate2
import faster_whisper
import numpy as np

print(f'PyTorch: {torch.__version__}')
print(f'PyTorch CUDA: {torch.version.cuda}')
print(f'CTranslate2: {ctranslate2.__version__}')
print(f'Faster-Whisper: {faster_whisper.__version__}')
print(f'NumPy: {np.__version__}')
print(f'CUDA Available: {torch.cuda.is_available()}')
print(f'cuDNN Version: {torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else "N/A"}')
PYEOF
```

---

## 📊 Test Results

### Tiny Model (GPU)

- เวลา transcription (5s video): 0.83s
- อัตราการประมวลผล: ~6x real-time

### Medium Model (GPU)

- เวลา transcription (10 min video): 23.80s
- อัตราการประมวลผล: ~25x real-time

---

## 📝 Notes

1. **CTranslate2 Version**: ใช้ 4.4.0 เพราะรองรับ cuDNN 8.7 (4.5.0 ต้องการ cuDNN 9.x)
2. **CUDA Version**: PyTorch ใช้ CUDA 11.8 ซึ่ง backward compatible กับ CUDA 12.x driver
3. **Symlink**: ต้องสร้าง libcublas.so.12 เพื่อให้ CTranslate2 ใช้งานได้
4. **Environment Variables**: ตั้ง CT2_USE_CUDA_GRAPH=0 เพื่อป้องกัน freeze

---

**Last Updated**: 2025-12-02
**Container**: pytorch-pod (RunPod)
**Status**: ✅ Working (GPU Mode)

