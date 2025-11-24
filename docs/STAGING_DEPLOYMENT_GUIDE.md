# 🚀 คู่มือ Deploy Transcription Service ไปยัง Staging

## 📋 สรุปปัญหา

**ปัญหา:** Transcription service บน Staging ทำงานไม่ได้ แต่ Local ทำงานได้

**สาเหตุ:**
- Image บน Staging (`kksenateacr.azurecr.io/kk-transcription:alpha-dev`) ไม่มี code ล่าสุด
- Image เก่ายังมี `_notify_api_server()` ที่พยายามเชื่อมต่อ WebSocket (ซึ่งถูกลบออกแล้ว)

## ✅ วิธีแก้ไข: Build และ Push Image ใหม่

### ขั้นตอนที่ 1: Build และ Push Image ใหม่

```bash
# 1. ไปที่ directory ของ transcription service
cd transcription-close-caption-service

# 2. ตรวจสอบว่า script มี execute permission
chmod +x scripts/build-and-push-acr.sh

# 3. รัน script เพื่อ build และ push image ไปยัง ACR
./scripts/build-and-push-acr.sh
```

**สิ่งที่ script จะทำ:**
- ✅ ตรวจสอบ Azure CLI และ Docker
- ✅ Login ไปยัง Azure Container Registry
- ✅ Build image สำหรับ `linux/amd64` platform
- ✅ Push ทั้ง `kk-transcription:alpha-dev` และ `kk-transcription-whisper:alpha-dev`
- ✅ Verify image manifest

**หมายเหตุ:** 
- Script จะใช้ `alpha-dev` tag (ตามที่กำหนดใน script)
- Image จะถูก build จาก code ปัจจุบันใน local repository
- ต้องมี Azure CLI และ login ไปยัง Azure ก่อน

### ขั้นตอนที่ 2: Pull และ Restart บน Staging Server

```bash
# บน Staging server (10.200.22.63 หรือ VM ที่รัน transcription service)
cd transcription-close-caption-service

# 1. Pull image ใหม่จาก ACR
docker-compose -f docker-compose.staging.yml pull

# 2. Restart containers เพื่อใช้ image ใหม่
docker-compose -f docker-compose.staging.yml up -d --force-recreate

# 3. ตรวจสอบ logs
docker logs transcription-api -f
docker logs video-worker-1 -f
```

### ขั้นตอนที่ 3: ตรวจสอบการทำงาน

```bash
# 1. ตรวจสอบว่า containers ทำงานปกติ
docker-compose -f docker-compose.staging.yml ps

# 2. ตรวจสอบ logs เพื่อดูว่ามี error หรือไม่
docker logs video-worker-1 | grep -i error
docker logs video-worker-1 | grep -i websocket
docker logs video-worker-1 | grep -i callback

# 3. ทดสอบ transcription endpoint
curl -X POST http://localhost:8001/transcribe/ \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "http://10.200.22.60:5182/api/files/{fileId}",
    "language": "th",
    "model_size": "base",
    "callback_url": "http://10.200.22.61:5173/api/transcription/webhook/completed"
  }'
```

## 🔍 ตรวจสอบความแตกต่างระหว่าง Local และ Staging

### Image Source

| Environment | Image Source | Status |
|-------------|--------------|--------|
| **Local** | Build from Dockerfile | ✅ มี code ล่าสุด |
| **Staging** | Pull from ACR (`kksenateacr.azurecr.io/kk-transcription:alpha-dev`) | ⚠️ อาจไม่มี code ล่าสุด |

### Network Configuration

| Configuration | Local | Staging |
|---------------|-------|---------|
| **Networks** | `app-network`, `senate-backend_kk-network` | Default network |
| **Extra Hosts** | `host.docker.internal` | ไม่มี |
| **RabbitMQ** | `rabbitmq` (container name) | `10.200.22.61` (IP) |
| **Callback URL** | `http://host.docker.internal:5173` | `http://10.200.22.61:5173` |

### Resources

| Service | Local | Staging |
|---------|-------|---------|
| **API** | 6G RAM, 2.0 CPU | 1.5G RAM, 1.0 CPU |
| **Worker** | 4G RAM, 1.0 CPU | 1G RAM, 0.4 CPU |
| **Whisper** | 8G RAM, 2.0 CPU | 1.5G RAM, 1.0 CPU |

## 🐛 Troubleshooting

### ปัญหา: Build failed

```bash
# ตรวจสอบว่า Docker ทำงาน
docker info

# ตรวจสอบว่า Azure CLI login แล้ว
az account show

# ตรวจสอบว่า ACR accessible
az acr login --name kksenateacr
```

### ปัญหา: Push failed

```bash
# ตรวจสอบ ACR permissions
az acr repository list --name kksenateacr

# ตรวจสอบว่า image tag ถูกต้อง
docker images | grep kksenateacr
```

### ปัญหา: Staging ไม่สามารถ pull image ได้

```bash
# บน Staging server - ตรวจสอบ network connectivity
ping kksenateacr.azurecr.io

# ตรวจสอบว่า Docker login ไปยัง ACR แล้ว
docker login kksenateacr.azurecr.io
```

### ปัญหา: Callback ไม่ทำงาน

```bash
# ตรวจสอบว่า transcription service สามารถเชื่อมต่อกับ senate-backend ได้
docker exec -it video-worker-1 curl -v http://10.200.22.61:5173/api/transcription/webhook/completed

# ตรวจสอบ logs
docker logs video-worker-1 | grep callback
```

## 📝 Checklist

### ก่อน Build
- [ ] Code ล่าสุดถูก commit และ push ไปยัง repository
- [ ] Azure CLI ติดตั้งและ login แล้ว
- [ ] Docker ทำงานปกติ
- [ ] มี permission ในการ push ไปยัง ACR

### หลัง Build
- [ ] Image build สำเร็จ
- [ ] Image push ไปยัง ACR สำเร็จ
- [ ] Image manifest ถูกต้อง (linux/amd64)

### บน Staging
- [ ] Pull image ใหม่สำเร็จ
- [ ] Containers restart สำเร็จ
- [ ] Logs ไม่มี error
- [ ] Transcription endpoint ทำงานได้
- [ ] Callback ไปยัง senate-backend ทำงานได้

## 🔗 Related Documents

- [STAGING_VS_LOCAL_DIFFERENCES.md](./STAGING_VS_LOCAL_DIFFERENCES.md) - ความแตกต่างระหว่าง Local และ Staging
- [build-and-push-acr.sh](../scripts/build-and-push-acr.sh) - Script สำหรับ build และ push image

## 📞 Support

ถ้ามีปัญหาเพิ่มเติม:
1. ตรวจสอบ logs: `docker logs <container-name> -f`
2. ตรวจสอบ network: `docker network ls` และ `docker network inspect <network-name>`
3. ตรวจสอบ configuration: `docker-compose -f docker-compose.staging.yml config`





