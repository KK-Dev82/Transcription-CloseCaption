# 🔨 Build vs Direct Mode - คำถามที่พบบ่อย

คำถาม: **ต้อง Build Docker Image ใหม่หรือไม่?** เมื่อมีการอัปเดต code

---

## 📋 คำตอบสั้นๆ

### Direct Mode (ปัจจุบัน)
**ไม่ต้อง Build Docker Image ใหม่** ✅

**เหตุผล:**
- ใช้ **Direct Mode** = รัน services จาก source code ตรงๆ
- Code ถูก clone จาก Git → รันโดยตรง
- ไม่ใช้ Docker containers สำหรับ services

### Docker Compose Mode (เดิม)
**ต้อง Build Docker Image ใหม่** ⚠️

**เหตุผล:**
- ใช้ Docker containers สำหรับ services
- Code ถูก build เป็น Docker image
- ต้อง rebuild image เมื่อ code เปลี่ยน

---

## 🔄 เปรียบเทียบ

| Aspect | Direct Mode (ปัจจุบัน) | Docker Compose Mode (เดิม) |
|--------|----------------------|---------------------------|
| **Code Update** | `git pull` → Restart services | `git pull` → Rebuild image → Restart |
| **Build Required?** | ❌ ไม่ต้อง | ✅ ต้อง |
| **Speed** | ⚡ เร็ว (pull + restart) | 🐌 ช้า (pull + build + restart) |
| **Complexity** | 🟢 ง่าย | 🟡 ซับซ้อนกว่า |

---

## 🚀 Workflow: Direct Mode

### เมื่อมีการอัปเดต Code

```bash
# 1. Pull latest code
cd /workspace/transcription-service
git pull origin staging

# 2. Reinstall dependencies (ถ้า requirements.txt เปลี่ยน)
pip3 install --no-cache-dir -r requirements.txt

# 3. Restart services
bash scripts/pod/start-services-direct.sh
```

**หรือใช้ script อัตโนมัติ:**

```bash
bash scripts/pod/update-code.sh staging
```

---

## 🔨 Workflow: Docker Compose Mode (ถ้ายังใช้)

### เมื่อมีการอัปเดต Code

```bash
# 1. Pull latest code
cd /workspace/transcription-service
git pull origin staging

# 2. Rebuild Docker images
docker compose -f docker-compose.runpod.yml build

# 3. Restart services
docker compose -f docker-compose.runpod.yml up -d
```

---

## ❓ เมื่อไหร่ต้อง Build Docker Image?

### ต้อง Build เมื่อ:

1. **อัปเดต Custom Base Image** (`Dockerfile.runpod-base`)
   - เปลี่ยน system dependencies
   - เปลี่ยน Python version
   - เปลี่ยน CUDA version

2. **เปลี่ยน Dockerfile ของ services**
   - `Dockerfile` (Main API)
   - `whisper-service/Dockerfile.gpu`

### ไม่ต้อง Build เมื่อ:

1. **อัปเดต Python code** (`.py` files)
   - `app/` directory
   - `whisper-service/whisper_api.py`
   - `scripts/` directory

2. **อัปเดต Configuration**
   - `.env.runpod`
   - `requirements.txt` (install ใหม่ได้)

3. **อัปเดต Documentation**
   - `docs/` directory
   - `README.md`

---

## 📝 สรุป

### Direct Mode (ปัจจุบัน)

```
Code Update → Git Pull → Restart Services
     ✅              ✅              ✅
```

**ไม่ต้อง Build Docker Image** เพราะ:
- Code ถูก clone จาก Git
- รันโดยตรงด้วย Python
- ไม่ใช้ Docker containers

### Docker Compose Mode (เดิม)

```
Code Update → Git Pull → Build Image → Restart Services
     ✅              ✅          ✅              ✅
```

**ต้อง Build Docker Image** เพราะ:
- Code ถูก build เป็น Docker image
- Services รันใน Docker containers
- ต้อง rebuild image เมื่อ code เปลี่ยน

---

## 🔗 Related Documents

- **Update Code:** [UPDATE_CODE.md](./UPDATE_CODE.md)
- **Direct Mode Setup:** [DIRECT_MODE_SETUP.md](./DIRECT_MODE_SETUP.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

---

**Last Updated:** 2024-12-19

