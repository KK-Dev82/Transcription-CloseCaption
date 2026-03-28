# Docker Image: Build, Push, Deploy

## Image Strategy

```
Docker Image (Dockerfile.base)         Server (/workspace/transcription-service)
  OS + CUDA + PyTorch + pip packages     Application code (git pull)
  Build ครั้งเดียว (~10 GB)              อัพเดทบ่อย (git pull + restart)
  Rebuild เมื่อ dependencies เปลี่ยน     ไม่ต้อง rebuild image
```

---

## 1. Build (บน Mac)

```bash
cd /path/to/transcription-close-caption-service

docker buildx build --platform linux/amd64 \
  -f Dockerfile.base \
  -t kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch280 \
  --load .
```

Build ใช้เวลา ~20-40 นาที (ครั้งแรก) เพราะ QEMU emulation บน Mac

---

## 2. Push to Azure Container Registry

```bash
az login
az acr login --name kksenateacr
docker push kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch280
```

---

## 3. Save เป็นไฟล์ (ทางเลือก สำหรับ transfer ด้วยมือ)

```bash
docker save kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch280 \
  | gzip > /Volumes/TS960GJDM850-Media/KK_Client_Work/KSC/บันทึกการประชุม-สว/Code/transcription-close-caption-service-docker-image/kk-base-ubuntu2404-cuda128-torch280.tar.gz
```

---

## 4. Deploy บน Server (10.200.22.64)

### ครั้งแรก (Initial Setup)

```bash
# Pull image จาก ACR
az acr login --name kksenateacr
docker pull kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch280

# หรือ Load จาก tar.gz
docker load -i kk-base-ubuntu2404-cuda128-torch280.tar.gz

# Clone code
git clone <repo-url> /workspace/transcription-service
cd /workspace/transcription-service

# สร้าง directories สำหรับ data
mkdir -p uploads storage models temp

# Start
docker compose -f docker-compose.prod.yml up -d

# ตรวจสอบ
docker compose -f docker-compose.prod.yml logs -f transcription
curl http://localhost:8010/health
```

### อัพเดทโค้ด (ไม่ต้อง rebuild image)

```bash
cd /workspace/transcription-service
git pull
docker compose -f docker-compose.prod.yml restart transcription
```

### อัพเดท Dependencies (ต้อง rebuild image)

```bash
# บน Mac: rebuild + push
docker buildx build --platform linux/amd64 \
  -f Dockerfile.base \
  -t kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch281 \
  --load .
docker push kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch281

# บน Server: pull image ใหม่ + แก้ docker-compose.prod.yml ให้ชี้ tag ใหม่
docker pull kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch281
docker compose -f docker-compose.prod.yml up -d
```

---

## 5. Cleanup (คืนพื้นที่ Mac)

```bash
docker rmi kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch280
docker system prune -f
```

---

## Dockerfile.base สิ่งที่มีใน Image

| Layer | รายการ | ขนาดโดยประมาณ |
|-------|--------|---------------|
| Base | Ubuntu 24.04 + CUDA 12.8.1 + cuDNN 9 | ~5.5 GB |
| PyTorch | torch 2.8.0 + torchaudio (cu128) | ~2.8 GB |
| System | ffmpeg, sox, libsndfile, libmagic, cmake | ~0.5 GB |
| Python | faster-whisper, nemo-toolkit, pyannote, pythainlp, etc. | ~2 GB |
| **Total** | | **~10.8 GB** |
