# Docker Pipeline: Build, Push, Deploy

## Image Architecture

```
ACR (kksenateacr.azurecr.io)
├── kk-base:ubuntu2404-cuda128-torch280    10.8 GB  (OS + CUDA + dependencies)
└── kk-transcription:release-v1.0.0       ~3 MB    (application code only)

Server /deploy
├── docker-compose.yml
├── .env.runpod
├── uploads/     (volume)
├── storage/     (volume)
├── models/      (volume)
└── temp/        (volume)
```

| Image | ขนาด | Build เมื่อ | วิธี Build |
|---|---|---|---|
| kk-base | 10.8 GB | Dependencies เปลี่ยน (นานๆ ครั้ง) | Manual บน Mac |
| kk-transcription | ~3 MB | Code เปลี่ยน (บ่อย) | CI/CD หรือ Manual |

---

## 1. kk-base (Manual Build บน Mac)

เมื่อ dependencies เปลี่ยน (CUDA, PyTorch, pip packages):

```bash
# Build
docker buildx build --platform linux/amd64 \
  -f Dockerfile.base \
  -t kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch280 \
  --load .

# Push to ACR
az acr login --name kksenateacr
docker push kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch280

# Save เป็นไฟล์ (ทางเลือก)
docker save kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch280 \
  | gzip > kk-base-ubuntu2404-cuda128-torch280.tar.gz

# Cleanup Mac
docker rmi kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch280
docker system prune -f
```

Build ~20-40 นาที (QEMU emulation บน Mac)

### สิ่งที่อยู่ใน kk-base

| Layer | รายการ | ขนาด |
|---|---|---|
| Base | Ubuntu 24.04 + CUDA 12.8.1 + cuDNN 9 | ~5.5 GB |
| PyTorch | torch 2.8.0 + torchaudio (cu128) | ~2.8 GB |
| System | ffmpeg, sox, libsndfile, libmagic, cmake | ~0.5 GB |
| Python | faster-whisper, nemo-toolkit, pyannote, pythainlp, etc. | ~2 GB |

---

## 2. kk-transcription (CI/CD Auto Build)

### CI/CD: Push to `production` branch -> Auto build + push

Workflow: `.github/workflows/build-push-acr.yml`

```
git push production → GitHub Actions → build kk-transcription → push ACR
                        (~1-2 นาที)         (~3 MB)
```

#### Setup GitHub Secrets

```bash
# สร้าง Service Principal
az ad sp create-for-rbac \
  --name "github-actions-transcription" \
  --role contributor \
  --scopes /subscriptions/<subscription-id>/resourceGroups/<resource-group> \
  --json-auth
```

เพิ่ม JSON output เป็น secret `AZURE_CREDENTIALS` ใน GitHub repo Settings → Secrets → Actions

### Manual Build (ทางเลือก)

```bash
docker buildx build --platform linux/amd64 \
  -t kksenateacr.azurecr.io/kk-transcription:release-v1.0.0 \
  -t kksenateacr.azurecr.io/kk-transcription:latest \
  --load .

az acr login --name kksenateacr
docker push kksenateacr.azurecr.io/kk-transcription:release-v1.0.0
docker push kksenateacr.azurecr.io/kk-transcription:latest
```

---

## 3. Deploy บน Server (10.200.22.64)

### Initial Setup

```bash
# Docker permission + Azure CLI
sudo usermod -aG docker athipc
newgrp docker
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login
az login
az acr login --name kksenateacr

# สร้าง deploy directory
sudo mkdir -p /deploy
sudo chown athipc:athipc /deploy
cd /deploy

# วาง docker-compose.yml และ .env.runpod
# สร้าง data directories
mkdir -p uploads storage models temp

# Pull + Start
docker compose pull
docker compose up -d

# Verify
curl http://localhost:8010/health
docker compose logs -f transcription
```

### Update Code

```bash
cd /deploy
az acr login --name kksenateacr
docker compose pull transcription
docker compose up -d
```

### Update Dependencies (kk-base เปลี่ยน)

```bash
cd /deploy
az acr login --name kksenateacr
docker compose pull    # pull ทั้ง base + transcription
docker compose up -d
```

### Rollback

```bash
# แก้ docker-compose.yml → เปลี่ยน tag กลับ version เดิม
# image: kksenateacr.azurecr.io/kk-transcription:release-v1.0.0
docker compose pull transcription
docker compose up -d
```

---

## 4. Maintenance

```bash
# Logs
docker compose logs -f transcription

# Restart
docker compose restart transcription

# เข้า container
docker exec -it transcription-service bash

# Stop
docker compose down
```
