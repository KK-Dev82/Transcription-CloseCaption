# Dashboard Daemon - Quick Start

## 🚀 วิธีที่ง่ายที่สุด (nohup)

### เริ่ม Dashboard แบบถาวร:
```bash
cd dashboard
bash start-daemon.sh
```

### หยุด Dashboard:
```bash
bash stop-daemon.sh
```

### ตรวจสอบสถานะ:
```bash
bash status-daemon.sh
```

### ดู Logs:
```bash
tail -f logs/dashboard.log
```

---

## ✅ ตรวจสอบว่า Dashboard ทำงาน

```bash
# ตรวจสอบ process
ps aux | grep uvicorn

# ตรวจสอบ port
curl http://localhost:8020

# หรือเปิด browser
open http://localhost:8020
```

---

## 🔧 สำหรับ Production (systemd)

```bash
# 1. คัดลอก service file
sudo cp dashboard/systemd/transcription-dashboard.service /etc/systemd/system/

# 2. Enable และ Start
sudo systemctl daemon-reload
sudo systemctl enable transcription-dashboard
sudo systemctl start transcription-dashboard

# 3. ตรวจสอบสถานะ
sudo systemctl status transcription-dashboard
```

---

## 📚 ดูคู่มือเต็ม: `README_DAEMON.md`
