# คู่มือ Setup RTX 5080 (ใช้ Git Pull)

## 📋 สรุป

สำหรับ RTX 5080 ที่ใช้ Git pull ตรงๆ ใน Pod Container **ไม่จำเป็นต้อง build Dockerfile** แค่เปลี่ยน base image ใน RunPod Template และใช้ install script ที่ถูกต้อง

## 🚀 ขั้นตอน Setup

### 1. ตั้งค่า Base Image ใน RunPod Template

**เปลี่ยน Container Image:**
- **เดิม**: `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`
- **ใหม่**: `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`

**ทำใน RunPod Dashboard:**
1. ไปที่ Pod Template
2. แก้ไข "Container Image"
3. เปลี่ยนเป็น `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`
4. Save Template

### 2. Start Pod และ Git Pull

```bash
# SSH เข้า Pod
ssh <pod-host>

# Git pull (หรือ clone ถ้ายังไม่มี)
cd /workspace/transcription-service
git pull
```

### 3. Install Dependencies (สำคัญ!)

**⚠️ ใช้ script สำหรับ CUDA 12.x:**

```bash
bash scripts/pod/install-dependencies-cuda12.sh
```

**ไม่ใช่** `install-dependencies.sh` (สำหรับ CUDA 11.8)

### 4. Setup และ Start Services

```bash
bash scripts/pod/setup-pod.sh
bash scripts/pod/start-pod.sh
```

### 5. ตรวจสอบ

```bash
bash scripts/pod/check-pod.sh
```

## ⚠️ สิ่งที่ต้องระวัง

### 1. ใช้ Script ที่ถูกต้อง
- ❌ **ผิด**: `bash scripts/pod/install-dependencies.sh` (สำหรับ CUDA 11.8)
- ✅ **ถูก**: `bash scripts/pod/install-dependencies-cuda12.sh` (สำหรับ CUDA 12.x)

### 2. Base Image ต้องถูกต้อง
- ✅ `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`
- ❌ `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04` (สำหรับ RTX 4080/4000)

### 3. Driver Version
- RTX 5080 ต้องการ Driver 550.54.15+ (รองรับ Blackwell)
- ตรวจสอบ: `nvidia-smi`

## 🔍 ตรวจสอบว่า Setup ถูกต้อง

```bash
# ตรวจสอบ CUDA version
python3 -c "import torch; print(f'PyTorch: {torch.__version__}, CUDA: {torch.version.cuda}')"
# ควรแสดง: PyTorch: 2.4.0, CUDA: 12.4

# ตรวจสอบ GPU
nvidia-smi
# ควรแสดง: RTX 5080

# ตรวจสอบ faster-whisper
python3 -c "from faster_whisper import WhisperModel; print('✅ faster-whisper OK')"
```

## 📊 เปรียบเทียบกับ RTX 4080/4000

| ขั้นตอน | RTX 4080/4000 | RTX 5080 |
|---------|---------------|----------|
| **Base Image** | `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04` | `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` |
| **Install Script** | `install-dependencies.sh` | `install-dependencies-cuda12.sh` |
| **PyTorch** | 2.1.0/2.1.1 | 2.4.0 |
| **CUDA** | 11.8 | 12.4.1 |
| **Python** | 3.10 | 3.11 |

## ❓ FAQ

### Q: ต้อง build Dockerfile.runpod-rtx5080 ไหม?
**A**: ไม่จำเป็น ถ้าใช้ Git pull ตรงๆ แค่เปลี่ยน base image ใน RunPod Template

### Q: Dockerfile.runpod-rtx5080 ใช้เมื่อไหร่?
**A**: ใช้เมื่อต้องการ build custom image ที่มี dependencies ติดตั้งไว้แล้ว และ push ไป ACR เพื่อใช้ใน RunPod Template

### Q: ถ้าใช้ Dockerfile.runpod-rtx5080 จะต้องทำอะไร?
**A**: 
1. Build image: `docker build -f Dockerfile.runpod-rtx5080 -t kk-transcription-rtx5080:latest .`
2. Push ไป ACR: `docker push kk-transcription-rtx5080:latest`
3. ตั้งค่า Container Image ใน RunPod Template เป็น `kk-transcription-rtx5080:latest`
4. Git pull และ setup ตามปกติ (dependencies ติดตั้งไว้แล้วใน image)

### Q: ใช้ base image เดียวกันได้ไหม?
**A**: 
- **RTX 4080/4000**: ใช้ CUDA 11.8 ได้ดี
- **RTX 5080**: ควรใช้ CUDA 12.x เพื่อประสิทธิภาพเต็มที่ (แต่ใช้ CUDA 11.8 ได้)

## 📚 เอกสารที่เกี่ยวข้อง

- [GPU Base Image Recommendations](./GPU_BASE_IMAGE_RECOMMENDATIONS.md)
- [GPU Performance Comparison Plan](./GPU_PERFORMANCE_COMPARISON_PLAN.md)
- [Pod Scripts README](../scripts/pod/README.md)

