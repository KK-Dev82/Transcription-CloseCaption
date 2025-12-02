# 🖥️ Environment สำหรับ Z2 - สรุปทั้งหมด

เอกสารนี้สรุป Environment ทั้งหมดจาก Container ที่ทำงานได้ เพื่อใช้สร้าง Container Image สำหรับ HP Z2 Workstation

---

## 📋 Quick Reference

### Base Image
```
pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime
```

### Python Packages (Core)
```bash
torch==2.1.0+cu118
torchaudio==2.1.0+cu118
ctranslate2==4.4.0              # ⚠️ สำคัญ: ใช้ 4.4.0
faster-whisper==1.0.2
numpy==1.26.4
```

### Environment Variables
```bash
CT2_USE_CUDA_GRAPH=0
OMP_NUM_THREADS=4
MKL_NUM_THREADS=4
CUDA_VISIBLE_DEVICES=0
LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/torch/lib:/usr/local/cuda-11.8/targets/x86_64-linux/lib
```

### Symlink ที่ต้องสร้าง
```bash
ln -sf libcublas.so.11.11.3.6 libcublas.so.12
```

---

## 🐳 Dockerfile สำหรับ Z2

### ใช้ไฟล์: `Dockerfile.z2-base`

หรือ copy จาก template นี้:

```dockerfile
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

# Install system packages
RUN apt-get update && apt-get install -y \
    build-essential cmake git git-lfs wget curl ffmpeg \
    redis-server ca-certificates gnupg lsb-release \
    netcat telnet jq \
    && rm -rf /var/lib/apt/lists/*

RUN git lfs install

# Install PyTorch (base image มีอยู่แล้ว แต่ upgrade ถ้าต้องการ)
RUN pip3 install --no-cache-dir \
    torch==2.1.0 \
    torchaudio==2.1.0 \
    --index-url https://download.pytorch.org/whl/cu118 || true

# Install faster-whisper (⚠️ ใช้ CTranslate2 4.4.0)
RUN pip3 install --no-cache-dir \
    numpy==1.26.4 \
    "ctranslate2==4.4.0" \
    "faster-whisper==1.0.2"

# Install app dependencies
RUN pip3 install --no-cache-dir \
    fastapi uvicorn pydantic requests aiohttp aiofiles \
    redis pika python-dotenv tzdata ffmpeg-python

WORKDIR /workspace
RUN mkdir -p transcription-service/{uploads,temp,storage} && \
    mkdir -p .cache/huggingface && \
    chmod -R 777 /workspace

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV CUDA_VISIBLE_DEVICES=0
ENV CT2_USE_CUDA_GRAPH=0
ENV OMP_NUM_THREADS=4
ENV MKL_NUM_THREADS=4
ENV HF_HOME=/workspace/.cache/huggingface

# Library paths
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/torch/lib:/usr/local/cuda-11.8/targets/x86_64-linux/lib:$LD_LIBRARY_PATH

# Create symlink
RUN cd /usr/local/cuda-11.8/targets/x86_64-linux/lib && \
    ln -sf libcublas.so.11.11.3.6 libcublas.so.12 || true

EXPOSE 8001 8002 6379
CMD ["/bin/bash"]
```

---

## 🚀 Build และใช้งาน

### Build Image

```bash
# Build
docker build -f Dockerfile.z2-base -t kk-transcription-z2-base:latest .

# หรือใช้ script
bash scripts/pod/build-z2-image.sh
```

### Run Container

```bash
docker run --gpus all -it \
    -v /path/to/local/workspace:/workspace \
    -p 8001:8001 \
    -p 8002:8002 \
    kk-transcription-z2-base:latest
```

### Setup ใน Container

```bash
# 1. Clone repository
cd /workspace
git clone <repo-url> transcription-service

# 2. Setup GPU environment
cd transcription-service
source scripts/pod/setup-gpu-env.sh

# 3. Test
python3 -c "from faster_whisper import WhisperModel; m = WhisperModel('tiny', device='cuda'); print('OK')"
```

---

## 📊 สรุป Packages และ Versions

### Python Packages

| Package | Version | Notes |
|---------|---------|-------|
| PyTorch | 2.1.0+cu118 | CUDA 11.8 |
| CTranslate2 | 4.4.0 | ⚠️ ไม่ใช่ 4.5.0 |
| Faster-Whisper | 1.0.2 | |
| NumPy | 1.26.4 | |

### System Packages

- `ffmpeg` - แปลงวิดีโอ/เสียง
- `git`, `git-lfs` - Version control
- `build-essential`, `cmake` - Build tools
- `wget`, `curl` - Download tools
- `redis-server` - Cache/Queue

---

## ⚙️ Configuration ที่สำคัญ

### 1. CTranslate2 Version

**⚠️ สำคัญมาก**: ใช้ `ctranslate2==4.4.0` (ไม่ใช่ 4.5.0)

**เหตุผล**:
- CTranslate2 4.5.0 ต้องการ cuDNN 9.x
- แต่ระบบมี cuDNN 8.7 (8700)
- CTranslate2 4.4.0 รองรับ cuDNN 8.7

### 2. Library Paths

```bash
LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/torch/lib:/usr/local/cuda-11.8/targets/x86_64-linux/lib
```

### 3. Symlink

```bash
ln -sf libcublas.so.11.11.3.6 libcublas.so.12
```

**เหตุผล**: CTranslate2 ต้องการ `libcublas.so.12` แต่ระบบมี `libcublas.so.11`

### 4. Environment Variables

```bash
CT2_USE_CUDA_GRAPH=0    # ป้องกัน freeze
OMP_NUM_THREADS=4       # Thread management
MKL_NUM_THREADS=4       # Thread management
CUDA_VISIBLE_DEVICES=0  # ใช้ GPU ตัวแรก
```

---

## ✅ Checklist สำหรับ Z2

### ก่อน Build

- [ ] ตรวจสอบ NVIDIA drivers บน Z2 (ต้องรองรับ CUDA 12.x)
- [ ] ตรวจสอบ `nvidia-container-toolkit` ติดตั้งแล้ว
- [ ] เตรียม `Dockerfile.z2-base`

### Build

- [ ] Build image: `docker build -f Dockerfile.z2-base -t kk-transcription-z2-base:latest .`
- [ ] ทดสอบ image: `docker run --gpus all -it kk-transcription-z2-base:latest`

### Setup

- [ ] Clone repository
- [ ] ตั้งค่า GPU environment: `source scripts/pod/setup-gpu-env.sh`
- [ ] ทดสอบ GPU transcription
- [ ] ตั้งค่า services (ถ้าต้องการ)

---

## 📁 Files ที่เกี่ยวข้อง

### Dockerfiles

- `Dockerfile.z2-base` - สำหรับ Z2
- `Dockerfile.runpod-base` - สำหรับ RunPod (PyTorch Official)
- `Dockerfile.runpod-template` - สำหรับ RunPod (RunPod Template)

### Scripts

- `build-z2-image.sh` - Build image สำหรับ Z2
- `setup-gpu-env.sh` - ตั้งค่า GPU environment
- `export-environment.sh` - Export environment

### Documentation

- `ENVIRONMENT_SUMMARY.md` - สรุป Environment
- `CONTAINER_ENV_COMPLETE.md` - สรุปครบถ้วน
- `FIX_CUDA_MISMATCH_ON_SERVER.md` - วิธีแก้ปัญหา

---

## 🔍 ตรวจสอบหลัง Build

```bash
# 1. ตรวจสอบ CUDA
python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"

# 2. ตรวจสอบ packages
python3 -c "import ctranslate2, faster_whisper; print(f'CT2: {ctranslate2.__version__}, FW: {faster_whisper.__version__}')"

# 3. ทดสอบ GPU transcription
source scripts/pod/setup-gpu-env.sh
python3 scripts/pod/test-faster-whisper-gpu.py
```

---

## 📝 Notes

1. **CTranslate2**: ใช้ 4.4.0 เท่านั้น (4.5.0 จะมีปัญหา cuDNN)
2. **CUDA**: PyTorch 11.8 ทำงานได้กับ CUDA 12.x driver
3. **Symlinks**: ต้องสร้าง libcublas.so.12
4. **Library Paths**: ต้องตั้งค่า LD_LIBRARY_PATH

---

**Last Updated**: 2025-12-02  
**Status**: ✅ Verified on RunPod, Ready for Z2

