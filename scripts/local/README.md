# 📁 Local Scripts

Scripts สำหรับการพัฒนาและทดสอบใน Local Environment (MacOS/Linux)

## 📋 Scripts

### `build-run-local.sh`
**Build และ Run services พร้อมกัน**
- Build Main API image
- Build Whisper service image
- Start services ด้วย docker-compose.local.yml

**Usage:**
```bash
bash scripts/local/build-run-local.sh
```

---

### `build-local.sh`
**Build images และทดสอบ permission**
- Build images พร้อม layer caching
- ทดสอบ permission ของ directories
- สร้าง test container

**Usage:**
```bash
bash scripts/local/build-local.sh
```

---

### `start-minimal.sh`
**Start services บน Minimal Server (2 CPU, 2GB RAM)**
- ตรวจสอบ system resources
- Download models (ถ้ายังไม่มี)
- Start services ด้วย docker-compose.minimal.yml

**Usage:**
```bash
bash scripts/local/start-minimal.sh
```

**หมายเหตุ:** ต้องมีไฟล์ `docker-compose.minimal.yml`

---

### `dev-setup.sh`
**Setup Development Environment**
- Build และ start services ด้วย docker-compose.dev.yml
- ใช้สำหรับ development workflow

**Usage:**
```bash
bash scripts/local/dev-setup.sh
```

**หมายเหตุ:** ต้องมีไฟล์ `docker-compose.dev.yml`

---

### `stop-transcription-containers.sh`
**Stop Transcription Containers เดิม**
- หาและ stop transcription containers ทั้งหมด
- ใช้ก่อน setup Local Direct Mode

**Usage:**
```bash
bash scripts/local/stop-transcription-containers.sh
```

---

### `setup-local-direct.sh`
**Setup Local Direct Mode Testing (First Time)**
- Stop containers เดิม
- Build base image (ไม่ใช้ CUDA)
- Start container สำหรับ Direct Mode
- Setup dependencies และ environment

**Usage:**
```bash
bash scripts/local/setup-local-direct.sh
```

**หมายเหตุ:** ใช้แนวทางเดียวกับ RunPod - ดูรายละเอียดใน `LOCAL_DIRECT_MODE.md`

---

### `start-local.sh` ⭐ **แนะนำสำหรับการทดสอบ**
**Start Local Docker Services**
- ตรวจสอบ Docker และ container
- Start services (Main API, Whisper API, Video Worker, Redis)
- แสดงคำสั่งที่มีประโยชน์

**Usage:**
```bash
bash scripts/local/start-local.sh
```

**หมายเหตุ:** ใช้หลังจาก `setup-local-direct.sh` (ครั้งแรก) หรือเมื่อต้องการ start services ใหม่

---

### `stop-local.sh`
**Stop Local Docker Services**
- Stop services ภายใน container
- ตัวเลือก: Stop container ด้วย (optional)

**Usage:**
```bash
bash scripts/local/stop-local.sh
```

---

### `restart-local.sh`
**Restart Local Docker Services**
- Stop และ start services ใหม่

**Usage:**
```bash
bash scripts/local/restart-local.sh
```

---

### `logs-local.sh` ⭐ **แนะนำสำหรับการ debug**
**View Logs ของ Local Docker Services**
- ดู logs ของ services ต่างๆ
- รองรับ: api, whisper, worker, redis, หรือ all

**Usage:**
```bash
# View all logs (default: 50 lines)
bash scripts/local/logs-local.sh

# View specific service
bash scripts/local/logs-local.sh worker

# View with custom lines
bash scripts/local/logs-local.sh worker 100

# Real-time logs (inside container)
docker exec -it transcription-local-base bash -c 'tail -f /tmp/video-worker.log'
```

---

### `test-local.sh` ⭐ **แนะนำสำหรับการทดสอบ**
**Test Transcription บน Local Docker**
- ทดสอบ transcription ด้วย video file
- รองรับ parallel processing

**Usage:**
```bash
# Basic test
bash scripts/local/test-local.sh uploads/test.mp4 base

# With custom model and chunk duration
bash scripts/local/test-local.sh uploads/test.mp4 medium 30
```

---

## 🔗 Related Files

- `docker-compose.local.yml` - Docker Compose สำหรับ local
- `docker-compose.local-direct.yml` - Docker Compose สำหรับ Local Direct Mode
- `docker-compose.minimal.yml` - Docker Compose สำหรับ minimal server
- `docker-compose.dev.yml` - Docker Compose สำหรับ development
- `Dockerfile.local-base` - Base image สำหรับ Local Direct Mode (ไม่ใช้ CUDA)
- `LOCAL_DIRECT_MODE.md` - คู่มือ Local Direct Mode Testing

