# 📘 คู่มือสร้าง Dockerfile สำหรับ Z2

คู่มือนี้สรุปทุกอย่างที่ต้องรู้เพื่อสร้าง Docker Image สำหรับ HP Z2 Workstation จาก Environment ที่ทำงานได้บน RunPod

---

## 📋 สรุป Environment ที่ทำงานได้

### Base Image
- **Recommended**: `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime`
- **Alternative**: `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`

### Python Packages (Core)

```
torch==2.1.0+cu118
torchaudio==2.1.0+cu118
torchvision==0.16.0+cu118
ctranslate2==4.4.0          # ⚠️ สำคัญ: ใช้ 4.4.0 (ไม่ใช่ 4.5.0)
faster-whisper==1.0.2
numpy==1.26.4
```

### System Packages

- ffmpeg (แปลงวิดีโอ/เสียง)
- git, git-lfs
- build-essential, cmake
- wget, curl
- redis-server

### Environment Variables

```bash
CT2_USE_CUDA_GRAPH=0
OMP_NUM_THREADS=4
MKL_NUM_THREADS=4
CUDA_VISIBLE_DEVICES=0
LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/torch/lib:/usr/local/cuda-11.8/targets/x86_64-linux/lib
```

### Symlinks ที่ต้องสร้าง

```bash
ln -sf libcublas.so.11.11.3.6 libcublas.so.12
```

---

## 🐳 Dockerfile Template สำหรับ Z2

ไฟล์: `Dockerfile.z2-base`

ดูรายละเอียดได้ที่ไฟล์ `Dockerfile.z2-base` ที่สร้างไว้แล้ว

### Key Points

1. **Base Image**: ใช้ `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime`
2. **CTranslate2**: ใช้เวอร์ชัน 4.4.0 (รองรับ cuDNN 8.7)
3. **Library Paths**: ตั้งค่า LD_LIBRARY_PATH ให้หา cuDNN ได้
4. **Symlink**: สร้าง libcublas.so.12 เพื่อให้ CTranslate2 ใช้งานได้

---

## 🚀 Build และใช้งาน

### Build Image

```bash
docker build -f Dockerfile.z2-base -t kk-transcription-z2-base:latest .
```

### Run Container

```bash
docker run --gpus all -it \
    -v /path/to/workspace:/workspace \
    kk-transcription-z2-base:latest
```

### ตั้งค่า GPU Environment

```bash
source scripts/pod/setup-gpu-env.sh
```

---

## ✅ Checklist

ก่อน Build Image ให้ตรวจสอบ:

- [ ] Base image มี PyTorch 2.1.0+cu118
- [ ] ติดตั้ง CTranslate2 4.4.0 (ไม่ใช่ 4.5.0)
- [ ] ติดตั้ง faster-whisper 1.0.2
- [ ] ติดตั้ง numpy 1.26.4
- [ ] ติดตั้ง ffmpeg
- [ ] ตั้งค่า environment variables
- [ ] ตั้งค่า LD_LIBRARY_PATH
- [ ] สร้าง symlink libcublas.so.12
- [ ] สร้าง directories structure

---

## 🔍 ทดสอบหลัง Build

```bash
# ตรวจสอบ CUDA
python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"

# ตรวจสอบ packages
python3 -c "import ctranslate2, faster_whisper; print('OK')"

# ทดสอบ GPU transcription
source scripts/pod/setup-gpu-env.sh
python3 scripts/pod/test-faster-whisper-gpu.py
```

---

## 📝 เอกสารอ้างอิง

- `ENVIRONMENT_SUMMARY.md` - สรุป Environment ทั้งหมด
- `Dockerfile.z2-base` - Dockerfile template
- `setup-gpu-env.sh` - Script ตั้งค่า GPU environment
- `FIX_CUDA_MISMATCH_ON_SERVER.md` - วิธีแก้ปัญหา CUDA mismatch

---

**Last Updated**: 2025-12-02

