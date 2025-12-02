# 📋 สรุป Environment Container อย่างละเอียด

เอกสารนี้สรุป Environment ทั้งหมดจาก Container ที่ทำงานได้สำเร็จ เพื่อใช้สร้าง Container Image สำหรับ Z2

---

## 📦 Python Packages

### Core Packages (ติดตั้งตามลำดับ)

#### 1. PyTorch และ CUDA

```bash
pip3 install --no-cache-dir \
    torch==2.1.0 \
    torchaudio==2.1.0 \
    --index-url https://download.pytorch.org/whl/cu118
```

**ผลลัพธ์**:
- `torch==2.1.0+cu118`
- `torchaudio==2.1.0+cu118`
- `torchvision==0.16.0+cu118` (auto-installed)

#### 2. Faster-Whisper Dependencies

```bash
pip3 install --no-cache-dir \
    numpy==1.26.4 \
    "ctranslate2==4.4.0" \
    "faster-whisper==1.0.2"
```

**⚠️ สำคัญ**:
- `ctranslate2==4.4.0` (ไม่ใช่ 4.5.0) - รองรับ cuDNN 8.7
- `numpy==1.26.4` - ตรงกับ requirements

#### 3. Application Dependencies

```bash
pip3 install --no-cache-dir \
    fastapi \
    uvicorn \
    pydantic \
    requests \
    aiohttp \
    aiofiles \
    redis \
    pika \
    python-dotenv \
    tzdata \
    ffmpeg-python
```

### รายการ Packages ทั้งหมด (สำคัญ)

```
ctranslate2==4.4.0
faster-whisper==1.0.2
numpy==1.26.4
torch==2.1.0+cu118
torchaudio==2.1.0+cu118
torchvision==0.16.0+cu118
```

---

## 🔧 System Packages

### Package List

```bash
apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    git-lfs \
    wget \
    curl \
    redis-server \
    ca-certificates \
    gnupg \
    lsb-release \
    ffmpeg \
    netcat \
    telnet \
    jq \
    && rm -rf /var/lib/apt/lists/*
```

### ตรวจสอบที่ติดตั้ง

- ✅ `ffmpeg` - แปลงวิดีโอ/เสียง
- ✅ `git` - Clone repository
- ✅ `git-lfs` - สำหรับโมเดล/ไฟล์ใหญ่
- ✅ `wget`, `curl` - ดาวน์โหลด
- ✅ `build-essential`, `cmake` - Build dependencies

---

## 🎮 CUDA และ GPU Configuration

### Versions

- **PyTorch**: 2.1.0+cu118
- **PyTorch CUDA**: 11.8
- **cuDNN**: 8700 (cuDNN 8.7)
- **CUDA Driver**: 12.8 (จาก host)
- **GPU**: NVIDIA GeForce RTX 4080 SUPER

### Library Paths

**LD_LIBRARY_PATH ต้องมี**:

```bash
/usr/local/lib/python3.10/dist-packages/torch/lib
/usr/local/cuda-11.8/targets/x86_64-linux/lib
```

**Full LD_LIBRARY_PATH**:
```bash
LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/torch/lib:/usr/local/cuda-11.8/targets/x86_64-linux/lib:$LD_LIBRARY_PATH
```

### Symlinks ที่ต้องสร้าง

```bash
cd /usr/local/cuda-11.8/targets/x86_64-linux/lib
ln -sf libcublas.so.11.11.3.6 libcublas.so.12
```

**เหตุผล**: CTranslate2 ต้องการ `libcublas.so.12` แต่ระบบมี `libcublas.so.11.11.3.6`

---

## 🌍 Environment Variables

### สำหรับ CTranslate2

```bash
CT2_USE_CUDA_GRAPH=0          # ป้องกัน freeze
```

### สำหรับ Thread Management

```bash
OMP_NUM_THREADS=4
MKL_NUM_THREADS=4
```

### สำหรับ CUDA

```bash
CUDA_VISIBLE_DEVICES=0
CUDA_MODULE_LOADING=LAZY      # Optional
```

### สำหรับ Python

```bash
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1
DEBIAN_FRONTEND=noninteractive
```

### สำหรับ Hugging Face

```bash
HF_HOME=/workspace/.cache/huggingface
```

---

## 📁 Directory Structure

```
/workspace/
└── transcription-service/
    ├── uploads/          # วิดีโอ/เสียงที่อัปโหลด
    ├── temp/             # ไฟล์ชั่วคราว (converted audio)
    ├── storage/          # เก็บผลลัพธ์
    └── .cache/
        └── huggingface/  # Whisper models cache
            └── hub/
                └── models--Systran--faster-whisper-*/
```

### Permissions

```bash
chmod -R 777 /workspace
```

---

## 🤖 Whisper Models

### Models ที่ใช้งานได้

- `tiny` - Model เล็ก (39M) - เร็วที่สุด
- `medium` - Model กลาง (769M) - แม่นยำกว่า

### Cache Location

```
/root/.cache/huggingface/hub/models--Systran--faster-whisper-{model}/
```

### การดาวน์โหลด

- Models จะดาวน์โหลดอัตโนมัติเมื่อใช้งานครั้งแรก
- หรือใช้ Hugging Face cache จากที่อื่น

---

## 🔧 Scripts ที่สำคัญ

### 1. `setup-gpu-env.sh`

ตั้งค่า GPU environment variables และ library paths

```bash
source scripts/pod/setup-gpu-env.sh
```

**สิ่งที่ทำ**:
- ตั้งค่า environment variables
- เพิ่ม library paths ใน LD_LIBRARY_PATH
- สร้าง symlink libcublas.so.12

### 2. `fix-cuda-mismatch-on-server.sh`

แก้ไขปัญหา CUDA version mismatch (ถ้ามี)

```bash
bash scripts/pod/fix-cuda-mismatch-on-server.sh
```

---

## 📊 Test Results

### Tiny Model (GPU)

- **Video**: 5 วินาที
- **Time**: 0.83s
- **Speed**: ~6x real-time

### Medium Model (GPU)

- **Video**: 10 นาที (600s)
- **Time**: 23.80s
- **Speed**: ~25x real-time

---

## 🐳 Dockerfile Template

### Base Image

**Option 1** (แนะนำ):
```dockerfile
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime
```

**Option 2** (ถ้าใช้ RunPod template):
```dockerfile
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04
```

### Complete Dockerfile

ดูไฟล์ `Dockerfile.z2-base` สำหรับ Dockerfile แบบสมบูรณ์

---

## ✅ Checklist สำหรับ Z2

### Pre-build

- [ ] ตรวจสอบ NVIDIA drivers บน Z2 (ต้องรองรับ CUDA 12.x)
- [ ] ตรวจสอบ nvidia-container-toolkit ติดตั้งแล้ว
- [ ] เตรียม Dockerfile.z2-base

### Build

- [ ] Build image: `docker build -f Dockerfile.z2-base -t kk-transcription-z2-base:latest .`
- [ ] ทดสอบ image: `docker run --gpus all -it kk-transcription-z2-base:latest`

### Post-build

- [ ] Clone repository
- [ ] ตั้งค่า GPU environment (`source scripts/pod/setup-gpu-env.sh`)
- [ ] ทดสอบ GPU transcription
- [ ] ตั้งค่า services (ถ้าต้องการ)

---

## 🔍 Troubleshooting

### ปัญหา: cuDNN library not found

**แก้ไข**:
1. ตั้งค่า LD_LIBRARY_PATH
2. ตรวจสอบว่ามี cuDNN libraries ใน torch/lib

### ปัญหา: libcublas.so.12 not found

**แก้ไข**:
1. สร้าง symlink: `ln -sf libcublas.so.11.11.3.6 libcublas.so.12`
2. ตั้งค่า LD_LIBRARY_PATH ให้ชี้ไปที่ cuda-11.8/lib

### ปัญหา: CTranslate2 freeze

**แก้ไข**:
1. ตั้งค่า `CT2_USE_CUDA_GRAPH=0`
2. ใช้ CTranslate2 4.4.0 (ไม่ใช่ 4.5.0)

---

## 📝 Notes

1. **CTranslate2 Version**: ใช้ 4.4.0 เพราะรองรับ cuDNN 8.7
2. **CUDA Compatibility**: PyTorch CUDA 11.8 ทำงานได้กับ CUDA 12.x driver
3. **Symlinks**: ต้องสร้าง libcublas.so.12 เพื่อให้ CTranslate2 ใช้งานได้
4. **Library Paths**: ต้องตั้งค่า LD_LIBRARY_PATH ให้ถูกต้อง

---

**Last Updated**: 2025-12-02  
**Source Container**: pytorch-pod (RunPod)  
**Status**: ✅ Working (GPU Mode)

