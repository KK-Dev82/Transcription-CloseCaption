# SSH Commands สำหรับ Pod

## 🔧 Quick Fix (Pull + Reset Database + Restart)

```bash
# SSH เข้า Pod
ssh <pod-ssh-connection>

# รัน quick-fix script
cd /workspace/transcription-service
./scripts/pod/quick-fix.sh
```

Script นี้จะ:
1. Pull code จาก git
2. ลบ database เก่า (เริ่มใหม่)
3. Stop service เก่า
4. Start service ใหม่

---

## 📋 คำสั่งแยกทีละขั้นตอน

### 1. Pull Code
```bash
cd /workspace/transcription-service
git pull
```

### 2. Reset Database
```bash
# ลบ database เก่า
rm -f storage/database.db
rm -f storage/database.db-journal
rm -f storage/database.db-wal
rm -f storage/database.db-shm
```

### 3. Restart Service
```bash
# Stop service เก่า
./scripts/pod/stop-service.sh

# Start service ใหม่
./scripts/pod/start-service-daemon.sh
```

---

## ✅ ตรวจสอบผลลัพธ์

```bash
# ตรวจสอบ service status
curl http://localhost:8010/health

# ตรวจสอบ logs
tail -f logs/app.log

# ตรวจสอบ database
ls -lh storage/database.db
```

---

## 🆘 ถ้ามีปัญหา

```bash
# ดู logs
tail -50 logs/app.log

# ตรวจสอบ process
ps aux | grep uvicorn

# ตรวจสอบ port
lsof -i :8010
```

