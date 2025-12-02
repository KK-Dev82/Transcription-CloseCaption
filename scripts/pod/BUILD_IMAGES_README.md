# Build Script สำหรับ Docker Images

## 📋 Overview

Script นี้ใช้สำหรับ build และ push Docker images สำหรับ RunPod ไปยัง Azure Container Registry (ACR)

มี 2 แบบให้เลือก:
1. **Base Image** - ใช้ PyTorch Official image (`Dockerfile.runpod-base`)
2. **Template Image** - ใช้ RunPod Template image (`Dockerfile.runpod-template`) ⭐ **แนะนำ**

## 🚀 วิธีใช้งาน

### 1. Login ACR ก่อน

```bash
az acr login --name kksenateacr
```

### 2. Build Images

#### Build Base Image (PyTorch Official)
```bash
bash scripts/pod/build-and-push-runpod-base.sh base
```

หรือไม่ระบุ parameter (default จะเป็น base):
```bash
bash scripts/pod/build-and-push-runpod-base.sh
```

#### Build Template Image (RunPod Template) - **แนะนำ** ⭐
```bash
bash scripts/pod/build-and-push-runpod-base.sh template
```

#### Build ทั้งสองแบบ
```bash
bash scripts/pod/build-and-push-runpod-base.sh all
```

## 📦 Image Names

### Base Image
- `kksenateacr.azurecr.io/kk-transcription-runpod-base:latest`
- `kksenateacr.azurecr.io/kk-transcription-runpod-base:<VERSION>`

### Template Image (แนะนำ)
- `kksenateacr.azurecr.io/kk-transcription-runpod-template:latest`
- `kksenateacr.azurecr.io/kk-transcription-runpod-template:<VERSION>`

## ⚡ เปรียบเทียบ

| ตัวเลือก | Build Time | ขนาด Image | ข้อดี |
|---------|-----------|-----------|-------|
| **Template** ⭐ | ~5-10 นาที | ~8-10 GB | Build เร็ว, Optimized สำหรับ RunPod |
| Base | ~10-15 นาที | ~10-12 GB | Official PyTorch, Portable |

## 🔧 ใช้ใน RunPod

### Template Image (แนะนำ)
```
Container Image: kksenateacr.azurecr.io/kk-transcription-runpod-template:latest
```

### Base Image
```
Container Image: kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
```

## 📝 หลังจาก Pod Start

1. **Clone repository:**
   ```bash
   cd /workspace
   git clone <repo-url> transcription-service
   ```

2. **Setup Pod (first time):**
   ```bash
   cd /workspace/transcription-service
   bash scripts/pod/setup-pod.sh
   ```

3. **Start services (Direct mode):**
   ```bash
   bash scripts/pod/start-pod.sh
   ```

4. **Check status:**
   ```bash
   bash scripts/pod/check-pod.sh
   ```

## ⚠️ หมายเหตุ

- Services **ไม่** start อัตโนมัติ (ป้องกัน duplicate workers)
- Image นี้เป็น minimal base - มีแค่ CUDA + dependencies
- ต้อง clone repo และ start services เอง

## 🔍 Troubleshooting

### Build fail บน ARM64 (Mac M1/M2)
Script จะ auto-detect และใช้ `--platform=linux/amd64` อัตโนมัติ

### ACR Login failed
```bash
az login
az acr login --name kksenateacr
```

### Permission denied
```bash
chmod +x scripts/pod/build-and-push-runpod-base.sh
```

