# 📋 Next Steps - หลังจาก Test GPU

หลังจากรัน `test-runpod-gpu.sh` และเห็นว่า GPU ทำงานได้แล้ว ขั้นตอนถัดไป:

---

## ✅ สถานะปัจจุบัน

- ✅ GPU ทำงานได้ (RTX 4080, CUDA 13.0)
- ❌ Docker daemon ไม่ทำงาน (ปกติ - เพราะ Pod Container ไม่สามารถรัน Docker-in-Docker ได้)
- ❌ Services ยังไม่ start

---

## 🚀 ขั้นตอนถัดไป

### Step 1: Clone Repository

```bash
cd /workspace
git clone <repo-url> transcription-service
```

**หมายเหตุ:** แทนที่ `<repo-url>` ด้วย URL ของ repository จริง

---

### Step 2: Build Custom Base Image ใหม่ (ถ้ายังไม่ได้ build)

**บน MacOS:**

```bash
cd /Users/athip-ch/Work/Korrakang/KK_Client_Work/KSC/บันทึกการประชุม-สว/Code/transcription-close-caption-service

# Build และ Push Custom Base Image
bash scripts/pod/build-and-push-runpod-base.sh
```

**หมายเหตุ:** Image ใหม่จะใช้ `start-services-direct.sh` แทน `start-runpod-services.sh` (ไม่ใช้ Docker Compose)

---

### Step 3: Restart Pod ด้วย Image ใหม่

1. ไปที่ RunPod Console → **"Pods"**
2. **Stop** Pod ปัจจุบัน
3. **Deploy** Pod ใหม่ด้วย Custom Template (จะ pull image ใหม่อัตโนมัติ)

**หรือ** Pull image ใหม่ใน Pod:

```bash
# Login ACR
az acr login --name kksenateacr

# Pull image ใหม่
docker pull kksenateacr.azurecr.io/kk-transcription-runpod-base:latest

# Restart container (ถ้าใช้ Docker)
# หรือ restart Pod จาก RunPod Console
```

---

### Step 4: Clone Repository ใน Pod

```bash
cd /workspace
git clone <repo-url> transcription-service
```

**หมายเหตุ:** Custom Base Image จะ start services อัตโนมัติเมื่อมี repository แล้ว

---

### Step 5: ตรวจสอบ Services

```bash
# ตรวจสอบ processes
ps aux | grep -E "(python|redis)"

# ตรวจสอบ API health
curl http://localhost:8001/health

# ตรวจสอบ Whisper health
curl http://localhost:8002/health

# ตรวจสอบ Redis
redis-cli ping
```

---

### Step 6: Test Transcription

```bash
# Test GPU
bash scripts/pod/test-runpod-gpu.sh

# Test Transcription (ถ้ามี test file)
curl -X POST http://localhost:8001/api/transcription/upload \
  -F 'file=@test_audio.wav' \
  -F 'language=th' \
  -F 'model_size=small'
```

---

## 🔧 Manual Start (ถ้า Services ไม่ Start อัตโนมัติ)

```bash
cd /workspace/transcription-service
bash scripts/pod/start-services-direct.sh
```

---

## 📝 สรุปการเปลี่ยนแปลง

### Direct Mode vs Docker Compose

| Aspect | Docker Compose (เดิม) | Direct Mode (ใหม่) |
|--------|----------------------|-------------------|
| **Architecture** | Multiple containers | Single container |
| **Docker Required** | ✅ Yes | ❌ No |
| **Complexity** | Higher | Lower |
| **Resource Usage** | Higher (overhead) | Lower |
| **Suitable For** | Full VM/Server | Pod Container |

### ไฟล์ที่เปลี่ยนแปลง

1. **`Dockerfile.runpod-base`**
   - เพิ่ม `redis-server` และ `jq`
   - เปลี่ยนจาก `start-runpod-services.sh` → `start-services-direct.sh`

2. **`scripts/pod/start-services-direct.sh`** (ใหม่)
   - รัน services โดยตรง (ไม่ใช้ Docker Compose)
   - รัน Redis, Whisper API, Video Worker, Main API ใน container เดียวกัน

3. **`scripts/pod/test-runpod-gpu.sh`**
   - อัปเดตให้รองรับ Direct Mode
   - ตรวจสอบ processes แทน Docker containers

---

## 🔗 Related Documents

- **Direct Mode Setup:** [DIRECT_MODE_SETUP.md](./DIRECT_MODE_SETUP.md)
- **Custom Template Configuration:** [CUSTOM_TEMPLATE_CONFIGURATION.md](./CUSTOM_TEMPLATE_CONFIGURATION.md)
- **Registry Auth Setup:** [RUNPOD_REGISTRY_AUTH_SETUP.md](./RUNPOD_REGISTRY_AUTH_SETUP.md)

---

**Last Updated:** 2024-12-19

