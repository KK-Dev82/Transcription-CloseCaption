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
**Setup Local Direct Mode Testing**
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

## 🔗 Related Files

- `docker-compose.local.yml` - Docker Compose สำหรับ local
- `docker-compose.local-direct.yml` - Docker Compose สำหรับ Local Direct Mode
- `docker-compose.minimal.yml` - Docker Compose สำหรับ minimal server
- `docker-compose.dev.yml` - Docker Compose สำหรับ development
- `Dockerfile.local-base` - Base image สำหรับ Local Direct Mode (ไม่ใช้ CUDA)
- `LOCAL_DIRECT_MODE.md` - คู่มือ Local Direct Mode Testing

