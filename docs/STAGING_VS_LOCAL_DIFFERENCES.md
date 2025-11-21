# ความแตกต่างระหว่าง Local และ Staging Environment

## 📊 สรุปความแตกต่าง

### 1. **Environment Variables**

| Variable | Local | Staging |
|----------|-------|---------|
| `ENVIRONMENT` | `local` | `staging` |
| `RABBITMQ_HOST` | `rabbitmq` (container name) | `10.200.22.61` (IP address) |
| `RABBITMQ_PORT` | `5672` | `5672` |
| `WHISPER_API_URL` | `http://whisper:8002` | `http://whisper:8002` |
| `REDIS_URL` | `redis://redis:6379` | `redis://redis:6379` |

### 2. **Docker Networks**

**Local:**
- ✅ มี `networks` กำหนดชัดเจน:
  - `app-network` (bridge)
  - `senate-backend_kk-network` (external)
- ✅ มี `extra_hosts` สำหรับ `host.docker.internal`

**Staging:**
- ❌ ไม่มี `networks` กำหนด (ใช้ default network)
- ❌ ไม่มี `extra_hosts`

### 3. **Image Source**

**Local:**
- Build จาก Dockerfile (`build: context: .`)
- Image: `kk-transcription:local-dev`

**Staging:**
- Pull จาก Azure Container Registry
- Image: `kksenateacr.azurecr.io/kk-transcription:alpha-dev`
- ⚠️ **อาจไม่มีการแก้ไขล่าสุด** (เช่น การลบ `_notify_api_server()`)

### 4. **Resources**

**Local:**
- API: 6G RAM, 2.0 CPU
- Worker: 4G RAM, 1.0 CPU
- Whisper: 8G RAM, 2.0 CPU

**Staging:**
- API: 1.5G RAM, 1.0 CPU
- Worker: 1G RAM, 0.4 CPU
- Whisper: 1.5G RAM, 1.0 CPU
- ⚠️ **Resources น้อยกว่า Local มาก**

## 🔍 ปัญหาที่เป็นไปได้

### 1. **Image ไม่มี Code ล่าสุด**

**ปัญหา:**
- Staging ใช้ pre-built image จาก ACR
- Image อาจไม่มีการแก้ไขล่าสุด (เช่น การลบ `_notify_api_server()`)

**วิธีแก้:**
```bash
# 1. Build image ใหม่
cd transcription-close-caption-service
docker build -t kksenateacr.azurecr.io/kk-transcription:alpha-dev .

# 2. Push ไปยัง ACR
docker push kksenateacr.azurecr.io/kk-transcription:alpha-dev

# 3. Pull image ใหม่บน Staging
docker-compose -f docker-compose.staging.yml pull

# 4. Restart containers
docker-compose -f docker-compose.staging.yml up -d --force-recreate
```

### 2. **Network Connectivity**

**ปัญหา:**
- Staging containers อาจไม่สามารถเชื่อมต่อกับ RabbitMQ (`10.200.22.61:5672`) ได้
- Staging containers อาจไม่สามารถเชื่อมต่อกับ senate-backend สำหรับ callback ได้

**วิธีตรวจสอบ:**
```bash
# ตรวจสอบ network connectivity จาก container
docker exec -it video-worker-1 ping 10.200.22.61
docker exec -it video-worker-1 curl -v http://10.200.22.61:5672

# ตรวจสอบ callback URL accessibility
docker exec -it video-worker-1 curl -v http://10.200.22.61:5173/api/transcription/webhook/completed
```

### 3. **Callback URL Configuration**

**ปัญหา:**
- Transcription service ต้องส่ง callback ไปที่ senate-backend
- Callback URL มาจาก `TranscriptionCallbackBaseUrl` ใน senate-backend config

**ตรวจสอบ:**
```bash
# ตรวจสอบ callback URL ใน senate-backend config
grep -r "TranscriptionCallbackBaseUrl" senate-backend/src/Shorthand.Api/appsettings*.json

# ตรวจสอบว่า transcription service ได้รับ callback_url หรือไม่
docker logs video-worker-1 | grep callback_url
```

### 4. **Resources ไม่เพียงพอ**

**ปัญหา:**
- Staging มี resources น้อยกว่า Local มาก
- อาจทำให้ transcription process ล้มเหลวหรือช้า

**วิธีแก้:**
- เพิ่ม resources ใน `docker-compose.staging.yml` (ถ้า server มี resources เพียงพอ)

## ✅ Checklist สำหรับ Staging

### 1. **ตรวจสอบ Image Version**
- [ ] Build และ push image ใหม่ที่มี code ล่าสุด
- [ ] Pull image ใหม่บน Staging server
- [ ] Restart containers

### 2. **ตรวจสอบ Network**
- [ ] RabbitMQ accessible จาก containers (`10.200.22.61:5672`)
- [ ] senate-backend accessible สำหรับ callback
- [ ] Whisper service accessible (`whisper:8002`)

### 3. **ตรวจสอบ Configuration**
- [ ] `ENVIRONMENT=staging` ถูกต้อง
- [ ] `RABBITMQ_HOST=10.200.22.61` ถูกต้อง
- [ ] `callback_url` ถูกส่งมาจาก senate-backend

### 4. **ตรวจสอบ Logs**
```bash
# ดู logs ของ transcription service
docker logs transcription-api -f
docker logs video-worker-1 -f
docker logs video-worker-2 -f

# ตรวจสอบ error messages
docker logs video-worker-1 | grep -i error
docker logs video-worker-1 | grep -i failed
docker logs video-worker-1 | grep -i callback
```

### 5. **ทดสอบ Transcription**
```bash
# ทดสอบ transcription endpoint
curl -X POST http://localhost:8001/transcribe/ \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "http://10.200.22.60:5182/api/files/{fileId}",
    "language": "th",
    "model_size": "base",
    "callback_url": "http://10.200.22.61:5173/api/transcription/webhook/completed"
  }'
```

## 🔧 Quick Fix

### ถ้า Image ไม่มี Code ล่าสุด:

```bash
# บน Local machine
cd transcription-close-caption-service
docker build -t kksenateacr.azurecr.io/kk-transcription:alpha-dev .
docker push kksenateacr.azurecr.io/kk-transcription:alpha-dev

# บน Staging server
cd transcription-close-caption-service
docker-compose -f docker-compose.staging.yml pull
docker-compose -f docker-compose.staging.yml up -d --force-recreate
```

### ถ้า Network มีปัญหา:

```bash
# เพิ่ม networks ใน docker-compose.staging.yml
networks:
  default:
    external: true
    name: kk-network  # หรือ network name ที่ senate-backend ใช้
```

## 📝 สรุป

**ปัญหาหลักที่อาจเกิดขึ้น:**
1. ⚠️ **Image ไม่มี code ล่าสุด** - ต้อง build และ push ใหม่
2. ⚠️ **Network connectivity** - ตรวจสอบว่า containers เชื่อมต่อกับ services อื่นได้
3. ⚠️ **Callback URL** - ตรวจสอบว่า transcription service ได้รับ callback_url จาก senate-backend
4. ⚠️ **Resources** - Staging มี resources น้อยกว่า Local มาก

**แนะนำ:**
- Build และ push image ใหม่ที่มี code ล่าสุด
- ตรวจสอบ network connectivity
- ตรวจสอบ logs เพื่อหาสาเหตุที่แท้จริง

