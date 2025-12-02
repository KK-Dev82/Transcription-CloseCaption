# 🚀 Start Transcription Service แบบ Daemon (nohup)

คู่มือการ Start Transcription Service แบบที่ทำงานต่อได้แม้ออกจาก Terminal

---

## ✅ ใช้ `nohup` ใช่แล้ว!

`nohup` = **no hang up** - ทำให้ process ทำงานต่อได้แม้ออกจาก terminal

---

## 🚀 วิธี Start Service (แบบ Daemon)

### วิธีที่ 1: ใช้ Script (แนะนำ)

```bash
# SSH เข้า Pod
ssh pytorch-pod

# ไปที่ project directory
cd /workspace/transcription-service

# Start service แบบ daemon
bash scripts/pod/start-service-daemon.sh
```

### วิธีที่ 2: Manual (ใช้ nohup โดยตรง)

```bash
cd /workspace/transcription-service

# Setup environment
source scripts/pod/setup-gpu-env.sh

# Start with nohup
nohup python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8001 \
    > /tmp/transcription-service.log 2>&1 &

# บันทึก PID
echo $! > /tmp/transcription-service.pid
```

---

## ✅ ข้อดีของ nohup

1. **ทำงานต่อได้** - ออกจาก terminal แล้ว service ยังทำงาน
2. **Log file** - เก็บ logs ไว้ในไฟล์ (`/tmp/transcription-service.log`)
3. **PID file** - เก็บ PID ไว้สำหรับ stop service (`/tmp/transcription-service.pid`)

---

## 🛑 วิธี Stop Service

### ใช้ Script

```bash
bash scripts/pod/stop-service.sh
```

### Manual

```bash
# ใช้ PID file
kill $(cat /tmp/transcription-service.pid)

# หรือหา PID แล้ว kill
kill $(pgrep -f "uvicorn.*app.main:app.*8001")
```

---

## 📋 ตรวจสอบ Service

### ตรวจสอบว่า Service ทำงานอยู่หรือไม่

```bash
# ตรวจสอบ process
ps aux | grep uvicorn

# ตรวจสอบ PID file
cat /tmp/transcription-service.pid

# ตรวจสอบ port
netstat -tlnp | grep 8001
# หรือ
ss -tlnp | grep 8001
```

### ดู Logs

```bash
# ดู logs แบบ real-time
tail -f /tmp/transcription-service.log

# ดู logs 20 บรรทัดล่าสุด
tail -20 /tmp/transcription-service.log
```

### ทดสอบ Health Check

```bash
curl http://localhost:8001/health
```

---

## 💡 Tips

1. **ตรวจสอบก่อน Start**: ตรวจสอบว่า service ทำงานอยู่แล้วหรือไม่
   ```bash
   ps aux | grep uvicorn
   ```

2. **ตรวจสอบ Logs**: ถ้า service ไม่ทำงาน ดู logs
   ```bash
   tail -50 /tmp/transcription-service.log
   ```

3. **Auto-restart**: สำหรับ production อาจใช้ systemd หรือ supervisor

---

## 📝 Summary

- ✅ ใช้ `nohup` เพื่อให้ทำงานต่อได้แม้ออกจาก terminal
- ✅ Log file: `/tmp/transcription-service.log`
- ✅ PID file: `/tmp/transcription-service.pid`
- ✅ ใช้ script: `start-service-daemon.sh` (สะดวกที่สุด)

---

**Last Updated**: 2025-12-02

