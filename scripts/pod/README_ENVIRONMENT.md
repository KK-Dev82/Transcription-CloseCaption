# 📚 README: Environment Documentation

เอกสารทั้งหมดเกี่ยวกับ Environment, Libraries, และ Configuration สำหรับ Transcription Service

---

## 📋 เอกสารที่เกี่ยวข้อง

### 1. Environment Summary

- **`ENVIRONMENT_SUMMARY.md`** - สรุป Environment แบบละเอียด
  - Python packages
  - System packages
  - CUDA configuration
  - Environment variables
  - Directory structure

- **`CONTAINER_ENV_COMPLETE.md`** - สรุป Environment แบบครบถ้วน
  - รายละเอียดทุกขั้นตอน
  - Troubleshooting guide
  - Complete checklist

### 2. Docker Images

- **`DOCKER_IMAGE_COMPARISON.md`** - เปรียบเทียบ Base Images
  - RunPod Template vs PyTorch Official
  - ข้อดีข้อเสียแต่ละแบบ
  - คำแนะนำ

- **`Dockerfile.z2-base`** - Dockerfile สำหรับ Z2
  - Template ที่ทำงานได้
  - พร้อม configuration ทั้งหมด

- **`Dockerfile.runpod-base`** - Dockerfile สำหรับ RunPod (PyTorch Official)
- **`Dockerfile.runpod-template`** - Dockerfile สำหรับ RunPod (RunPod Template)

### 3. Build Scripts

- **`build-and-push-runpod-base.sh`** - Build และ Push image สำหรับ RunPod
  - รองรับ: base, template, หรือ all
  - Push ไป Azure Container Registry

- **`build-z2-image.sh`** - Build image สำหรับ Z2
  - ใช้ Dockerfile.z2-base
  - Build สำหรับ local use

- **`BUILD_IMAGES_README.md`** - คู่มือ Build Images

### 4. GPU Setup & Troubleshooting

- **`setup-gpu-env.sh`** - ตั้งค่า GPU environment
  - Environment variables
  - Library paths
  - Symlinks

- **`fix-cuda-mismatch-on-server.sh`** - แก้ปัญหา CUDA mismatch
  - อัพเกรด CUDA เป็น 12.1
  - Reinstall packages

- **`fix-cuda-mismatch-alternative.sh`** - ทางเลือกอื่นๆ
  - CPU mode
  - Compatibility mode
  - Clean cache

- **`FIX_CUDA_MISMATCH_ON_SERVER.md`** - คู่มือแก้ปัญหา CUDA

### 5. Export & Documentation

- **`export-environment.sh`** - Export environment ทั้งหมด
  - Packages list
  - CUDA info
  - Environment variables
  - Directory structure

---

## 🚀 Quick Start

### สำหรับ RunPod

1. **Build Image**:
   ```bash
   bash scripts/pod/build-and-push-runpod-base.sh template
   ```

2. **ใช้ใน RunPod**: ตั้งค่า Container Image เป็น image ที่ build แล้ว

3. **Setup**:
   ```bash
   git clone <repo> /workspace/transcription-service
   source scripts/pod/setup-gpu-env.sh
   ```

### สำหรับ Z2

1. **Build Image**:
   ```bash
   bash scripts/pod/build-z2-image.sh
   ```

2. **Run Container**:
   ```bash
   docker run --gpus all -it \
       -v /path/to/workspace:/workspace \
       kk-transcription-z2-base:latest
   ```

3. **Setup**:
   ```bash
   git clone <repo> /workspace/transcription-service
   source scripts/pod/setup-gpu-env.sh
   ```

---

## 📊 Environment ที่ทำงานได้

### Python Packages

```
torch==2.1.0+cu118
torchaudio==2.1.0+cu118
ctranslate2==4.4.0
faster-whisper==1.0.2
numpy==1.26.4
```

### Key Configuration

- **CUDA**: 11.8
- **cuDNN**: 8.7 (8700)
- **CTranslate2**: 4.4.0 (รองรับ cuDNN 8.7)
- **CT2_USE_CUDA_GRAPH**: 0 (ป้องกัน freeze)
- **LD_LIBRARY_PATH**: ตั้งค่าให้หา cuDNN ได้
- **Symlink**: libcublas.so.12 → libcublas.so.11.11.3.6

---

## ✅ Test Results

### Tiny Model (GPU)

- 5s video: 0.83s (~6x real-time)

### Medium Model (GPU)

- 10 min video: 23.80s (~25x real-time)

---

## 📝 Notes

1. ใช้ CTranslate2 4.4.0 (ไม่ใช่ 4.5.0) เพราะรองรับ cuDNN 8.7
2. ต้องตั้งค่า LD_LIBRARY_PATH เพื่อหา cuDNN libraries
3. ต้องสร้าง symlink libcublas.so.12
4. ตั้งค่า CT2_USE_CUDA_GRAPH=0 เพื่อป้องกัน freeze

---

**Last Updated**: 2025-12-02

