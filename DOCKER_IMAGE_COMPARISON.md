# เปรียบเทียบ Base Image สำหรับ RunPod

## ตัวเลือกที่ 1: RunPod Template Image
```dockerfile
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04
```

### ข้อดี ✅
1. **Optimized สำหรับ RunPod** - ตั้งค่ามาแล้วสำหรับ RunPod environment
2. **ไม่ต้องติดตั้ง PyTorch** - มีพร้อมแล้ว เวอร์ชันตรงตามที่ต้องการ
3. **CUDA ตรงเวอร์ชัน** - CUDA 11.8.0 ตรงกับ PyTorch 2.1.0+cu118
4. **ขนาดเล็กกว่า** - ไม่ต้องติดตั้ง CUDA toolkit เพิ่ม (ใช้ driver จาก host)
5. **Build เร็ว** - ลดขั้นตอนการติดตั้ง
6. **รองรับ RunPod features** - อาจมี optimizations เฉพาะ RunPod

### ข้อเสีย ⚠️
1. **ผูกกับ RunPod** - ถ้าต้องการใช้ที่อื่นอาจมีปัญหา
2. **Vendor lock-in** - ขึ้นกับ RunPod template updates
3. **Customization น้อยกว่า** - ควบคุมรายละเอียดได้น้อยกว่า

---

## ตัวเลือกที่ 2: Custom Image + ติดตั้ง PyTorch เอง
```dockerfile
FROM nvidia/cuda:11.8.0-base-ubuntu22.04
# หรือ
FROM ubuntu:22.04
```

### ข้อดี ✅
1. **ควบคุมได้เต็มที่** - เลือกทุกอย่างเอง
2. **Portable** - ใช้ได้ทุกที่ (ไม่ผูกกับ RunPod)
3. **Flexible** - ปรับแต่งได้ตามต้องการ
4. **ไม่ขึ้นกับ vendor** - ไม่ต้องพึ่ง template

### ข้อเสีย ⚠️
1. **ต้องติดตั้งเองทั้งหมด** - PyTorch, CUDA dependencies, cuDNN
2. **Build ช้ากว่า** - ขั้นตอนการติดตั้งมากขึ้น
3. **ขนาดใหญ่กว่า** - อาจต้องติดตั้ง CUDA toolkit เต็ม
4. **จัดการยากกว่า** - ต้องรู้รายละเอียด dependencies

---

## ตัวเลือกที่ 3: PyTorch Official Image (ปัจจุบัน)
```dockerfile
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime
```

### ข้อดี ✅
1. **Official PyTorch** - รองรับจาก PyTorch team
2. **Portable** - ใช้ได้ทุกที่
3. **มี PyTorch พร้อมแล้ว** - ไม่ต้องติดตั้งเพิ่ม
4. **CUDA version ตรง** - ตรงกับ requirements

### ข้อเสีย ⚠️
1. **ไม่ได้ optimize สำหรับ RunPod** - แต่ก็ใช้ได้
2. **อาจใหญ่กว่า** - มี dependencies เยอะ

---

## คำแนะนำ: ใช้ RunPod Template Image 🎯

**สำหรับ RunPod production แนะนำใช้:**
```dockerfile
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04
```

### เหตุผล:
1. **เร็วที่สุด** - ไม่ต้องติดตั้ง PyTorch (ประหยัดเวลา build)
2. **จัดการง่าย** - RunPod optimize มาแล้ว
3. **ขนาดเล็ก** - ใช้ CUDA จาก host driver
4. **เสถียร** - ผ่านการทดสอบจาก RunPod

### ตัวอย่าง Dockerfile แก้ไข:
```dockerfile
# ใช้ RunPod template ที่มี PyTorch พร้อมแล้ว
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

# Install system dependencies (PyTorch และ CUDA มีอยู่แล้ว)
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    git-lfs \
    wget \
    curl \
    redis-server \
    ffmpeg \
    netcat \
    telnet \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Initialize git-lfs
RUN git lfs install

# ตรวจสอบ PyTorch (ควรมีอยู่แล้ว)
# RUN python3 -c "import torch; print(f'PyTorch: {torch.__version__}, CUDA: {torch.version.cuda}')"

# Install faster-whisper with compatible versions (CUDA 11.8)
RUN pip3 install --no-cache-dir \
    numpy==1.26.4 \
    "ctranslate2==4.5.0" \
    "faster-whisper==1.0.2"

# Install Python dependencies
RUN pip3 install --no-cache-dir \
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

# Create working directory
WORKDIR /workspace
RUN mkdir -p /workspace && chmod -R 777 /workspace

# Setup Hugging Face cache
ENV HF_HOME=/workspace/.cache/huggingface
RUN mkdir -p $HF_HOME

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV CUDA_VISIBLE_DEVICES=0
ENV CT2_USE_CUDA_GRAPH=0
ENV OMP_NUM_THREADS=4
ENV MKL_NUM_THREADS=4
ENV WHISPER_PROVIDER=faster-whisper
ENV WHISPER_MODEL=medium
ENV WHISPER_DEVICE=auto
ENV WHISPER_VAD_FILTER=false

# Expose ports
EXPOSE 8001 8002 6379

CMD ["/bin/bash", "-c", "echo '🚀 RunPod Base Image Ready'; echo '📋 Next steps:'; echo '   1. Clone repo: git clone <repo> /workspace/transcription-service'; echo '   2. Start services: bash scripts/pod/restart-pod-services.sh'; echo ''; tail -f /dev/null"]
```

---

## เปรียบเทียบเวลา Build

| ตัวเลือก | เวลา Build (ประมาณ) | ขนาด Image |
|---------|-------------------|------------|
| RunPod Template | **~5-10 นาที** ⚡ | ~8-10 GB |
| PyTorch Official | ~10-15 นาที | ~10-12 GB |
| Custom + Install | **~20-30 นาที** 🐢 | ~12-15 GB |

---

## สรุป

**ใช้ RunPod Template Image ถ้า:**
- ✅ ใช้กับ RunPod เป็นหลัก
- ✅ ต้องการความเร็วในการ build
- ✅ ต้องการจัดการง่าย

**ใช้ Custom Image ถ้า:**
- ✅ ต้องใช้ในหลาย environment (ไม่ใช่แค่ RunPod)
- ✅ ต้องการควบคุมทุกอย่างเอง
- ✅ มี requirements พิเศษ

**สำหรับโปรเจกต์นี้: แนะนำ RunPod Template Image** 🎯

