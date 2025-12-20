# 🐳 คู่มือ Build และ Push Image ไป ACR

## 📋 สรุป

คู่มือนี้อธิบายวิธีการ pull code, build Docker image, และ push ไปยัง Azure Container Registry (ACR) `kksenateacr`

---

## 🚀 ขั้นตอนการ Build และ Push

### 1. Pull Code จาก Git

```bash
# Clone repository (ถ้ายังไม่มี)
git clone <repo-url> transcription-service
cd transcription-service

# หรือ pull branch ที่ต้องการ
git checkout job-based-workers
git pull origin job-based-workers
```

### 2. Login ACR

```bash
# Login Azure (ถ้ายังไม่ได้ login)
az login

# Login ACR
az acr login --name kksenateacr
```

### 3. Build Image

```bash
# วิธีที่ 1: Build โดยตรง
docker build -f Dockerfile.base-new -t kksenateacr.azurecr.io/kk-transcription-base:latest .

# วิธีที่ 2: ใช้ Script (แนะนำ)
bash scripts/pod/build-and-push-base-new.sh
```

### 4. Push Image

```bash
# วิธีที่ 1: Push โดยตรง
docker push kksenateacr.azurecr.io/kk-transcription-base:latest

# วิธีที่ 2: ใช้ Script (จะ push อัตโนมัติ)
bash scripts/pod/build-and-push-base-new.sh
```

---

## 📦 Images ที่จะถูก Push

- `kksenateacr.azurecr.io/kk-transcription-base:latest`
- `kksenateacr.azurecr.io/kk-transcription-base:v1.0.0` (timestamp version)

---

## ✅ ข้อกำหนด

### ต้องมี:
- ✅ **Docker** - สำหรับ build image
- ✅ **Azure CLI** - สำหรับ login และ push
- ✅ **ACR Access** - permissions สำหรับ push

### ตรวจสอบ:

```bash
# ตรวจสอบ Docker
docker --version

# ตรวจสอบ Azure CLI
az --version

# ตรวจสอบ ACR access
az acr repository list --name kksenateacr
```

---

## 🔍 ตรวจสอบ Images

### List Images

```bash
az acr repository list --name kksenateacr
```

### List Tags

```bash
az acr repository show-tags --name kksenateacr --repository kk-transcription-base
```

### View Image Details

```bash
az acr repository show --name kksenateacr --repository kk-transcription-base
```

---

## 📝 วิธีใช้ใน RunPod

### 1. สร้าง Pod ใหม่

1. ไปที่ RunPod Dashboard
2. สร้าง Pod ใหม่
3. เลือก **Custom Image**: `kksenateacr.azurecr.io/kk-transcription-base:latest`

### 2. Clone Repository

```bash
git clone <repo-url> /workspace/transcription-service
cd /workspace/transcription-service
git checkout job-based-workers
```

### 3. Start Services

```bash
cd /workspace/transcription-service
bash scripts/start-all-nohup.sh
```

---

## ⚠️ หมายเหตุ

### Build Time
- **ประมาณ 20-30 นาที** (ขึ้นอยู่กับ network speed)
- ต้อง download base image และ dependencies

### Image Size
- **ประมาณ 8-12 GB** (รวม PyTorch, CUDA, cuDNN, และ dependencies)

### Network Requirements
- ต้องมี internet connection สำหรับ download packages
- ACR access สำหรับ push image

---

## 🔧 Troubleshooting

### Error: Docker not found
```bash
# Install Docker (ถ้ายังไม่มี)
# Ubuntu/Debian:
sudo apt-get update && sudo apt-get install -y docker.io

# หรือใช้ Azure Cloud Shell (มี Docker พร้อมแล้ว)
```

### Error: Azure CLI not found
```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### Error: ACR login failed
```bash
# Login Azure ก่อน
az login

# Login ACR
az acr login --name kksenateacr
```

### Error: Permission denied
```bash
# ตรวจสอบ permissions
az acr show --name kksenateacr --query permissions

# ตรวจสอบ role assignments
az role assignment list --scope /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.ContainerRegistry/registries/kksenateacr
```

---

## 📊 Build Process

1. **Pull Code** - ดึง code จาก Git repository
2. **Login ACR** - Authenticate กับ Azure Container Registry
3. **Build Image** - Build จาก `Dockerfile.base-new`
4. **Tag Image** - Tag ด้วย version (timestamp)
5. **Push Images** - Push ทั้ง `latest` และ version tag

---

## 🎯 สรุป

**Base Image**:
- ✅ มี dependencies ทั้งหมดติดตั้งไว้แล้ว
- ✅ ไม่ต้อง install ใหม่หลัง restart POD
- ✅ Ready to use - Clone repo และ start services ได้ทันที

**ACR Images**:
- `kksenateacr.azurecr.io/kk-transcription-base:latest`
- `kksenateacr.azurecr.io/kk-transcription-base:v1.0.0`

---

**Last Updated**: 2025-01-XX  
**ACR**: `kksenateacr.azurecr.io`  
**Repository**: `kk-transcription-base`  
**Branch**: `job-based-workers`

