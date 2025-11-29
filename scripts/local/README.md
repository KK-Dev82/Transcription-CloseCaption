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

## 🔗 Related Files

- `docker-compose.local.yml` - Docker Compose สำหรับ local
- `docker-compose.minimal.yml` - Docker Compose สำหรับ minimal server
- `docker-compose.dev.yml` - Docker Compose สำหรับ development

