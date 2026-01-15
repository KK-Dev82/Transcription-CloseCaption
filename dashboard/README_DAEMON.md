# Dashboard Daemon Mode Guide

คู่มือการรัน Dashboard แบบถาวร (Background Process) เพื่อให้สามารถเข้าถึงผ่าน URL ได้ตลอดเวลา

## 🚀 วิธีที่ 1: ใช้ Script (nohup) - แนะนำสำหรับเริ่มต้น ⭐

### การใช้งาน

**เริ่ม Dashboard:**
```bash
cd dashboard
bash start-daemon.sh
```

**หยุด Dashboard:**
```bash
bash stop-daemon.sh
```

**ตรวจสอบสถานะ:**
```bash
bash status-daemon.sh
```

**ดู Logs:**
```bash
tail -f logs/dashboard.log
```

### ข้อดี
- ✅ ง่ายที่สุด ไม่ต้องติดตั้งอะไรเพิ่ม
- ✅ ทำงานได้ทันที
- ✅ มี script สำหรับ start/stop/status

### ข้อจำกัด
- ⚠️ ไม่ auto-restart ถ้า process crash
- ⚠️ ไม่ restart อัตโนมัติเมื่อ reboot

---

## 🔧 วิธีที่ 2: ใช้ systemd Service (แนะนำสำหรับ Production) ⭐⭐⭐

### การติดตั้ง

1. **คัดลอก service file:**
```bash
sudo cp dashboard/systemd/transcription-dashboard.service /etc/systemd/system/
```

2. **แก้ไข path (ถ้าจำเป็น):**
```bash
sudo nano /etc/systemd/system/transcription-dashboard.service
```

3. **Reload systemd:**
```bash
sudo systemctl daemon-reload
```

4. **Enable service (auto-start on boot):**
```bash
sudo systemctl enable transcription-dashboard
```

5. **Start service:**
```bash
sudo systemctl start transcription-dashboard
```

### การใช้งาน

**Start:**
```bash
sudo systemctl start transcription-dashboard
```

**Stop:**
```bash
sudo systemctl stop transcription-dashboard
```

**Restart:**
```bash
sudo systemctl restart transcription-dashboard
```

**Status:**
```bash
sudo systemctl status transcription-dashboard
```

**View Logs:**
```bash
sudo journalctl -u transcription-dashboard -f
```

### ข้อดี
- ✅ Auto-restart ถ้า process crash
- ✅ Auto-start เมื่อ reboot
- ✅ จัดการโดย systemd (professional)
- ✅ Logs ผ่าน journalctl

### ข้อจำกัด
- ⚠️ ต้องมี root access
- ⚠️ ต้องใช้ systemd (Linux เท่านั้น)

---

## 🎯 วิธีที่ 3: ใช้ Supervisor

### การติดตั้ง

1. **ติดตั้ง Supervisor:**
```bash
sudo apt-get update
sudo apt-get install -y supervisor
```

2. **คัดลอก config file:**
```bash
sudo cp dashboard/supervisor/dashboard.conf /etc/supervisor/conf.d/
```

3. **Reload Supervisor:**
```bash
sudo supervisorctl reread
sudo supervisorctl update
```

4. **Start service:**
```bash
sudo supervisorctl start transcription-dashboard
```

### การใช้งาน

**Start:**
```bash
sudo supervisorctl start transcription-dashboard
```

**Stop:**
```bash
sudo supervisorctl stop transcription-dashboard
```

**Restart:**
```bash
sudo supervisorctl restart transcription-dashboard
```

**Status:**
```bash
sudo supervisorctl status transcription-dashboard
```

**View Logs:**
```bash
tail -f /workspace/transcription-service/dashboard/logs/dashboard.log
```

### ข้อดี
- ✅ Auto-restart ถ้า process crash
- ✅ Web interface สำหรับจัดการ (optional)
- ✅ รองรับหลาย processes

### ข้อจำกัด
- ⚠️ ต้องติดตั้ง supervisor
- ⚠️ ต้องมี root access

---

## 🖥️ วิธีที่ 4: ใช้ screen/tmux (สำหรับ Development)

### Screen

**Start:**
```bash
cd dashboard
screen -S dashboard
bash start-local.sh
# Press Ctrl+A then D to detach
```

**Reattach:**
```bash
screen -r dashboard
```

**List sessions:**
```bash
screen -ls
```

### tmux

**Start:**
```bash
cd dashboard
tmux new -s dashboard
bash start-local.sh
# Press Ctrl+B then D to detach
```

**Reattach:**
```bash
tmux attach -t dashboard
```

**List sessions:**
```bash
tmux ls
```

### ข้อดี
- ✅ ง่าย ไม่ต้องติดตั้งอะไร
- ✅ เหมาะสำหรับ development
- ✅ สามารถดู output ได้

### ข้อจำกัด
- ⚠️ ไม่ auto-restart
- ⚠️ ต้องมี session เปิดอยู่

---

## 📊 สรุปเปรียบเทียบ

| วิธี | ความยาก | Auto-restart | Auto-start on boot | แนะนำสำหรับ |
|------|---------|--------------|-------------------|-------------|
| **nohup (Script)** | ⭐ ง่าย | ❌ | ❌ | Development, Testing |
| **systemd** | ⭐⭐ ปานกลาง | ✅ | ✅ | Production (Linux) |
| **Supervisor** | ⭐⭐ ปานกลาง | ✅ | ✅ | Production (Multiple services) |
| **screen/tmux** | ⭐ ง่าย | ❌ | ❌ | Development |

---

## 🔍 Troubleshooting

### Dashboard ไม่ start

1. **ตรวจสอบว่า port ไม่ถูกใช้งาน:**
```bash
lsof -i :8020
# หรือ
netstat -tulpn | grep 8020
```

2. **ตรวจสอบ logs:**
```bash
# nohup
tail -f dashboard/logs/dashboard.log

# systemd
sudo journalctl -u transcription-dashboard -f

# supervisor
tail -f dashboard/logs/dashboard.log
```

3. **ตรวจสอบว่า virtual environment ถูกต้อง:**
```bash
cd dashboard
source venv/bin/activate
python3 -m uvicorn main:app --host 0.0.0.0 --port 8020
```

### Dashboard หยุดทำงาน

1. **ตรวจสอบสถานะ:**
```bash
# nohup
bash dashboard/status-daemon.sh

# systemd
sudo systemctl status transcription-dashboard

# supervisor
sudo supervisorctl status transcription-dashboard
```

2. **Restart:**
```bash
# nohup
bash dashboard/stop-daemon.sh
bash dashboard/start-daemon.sh

# systemd
sudo systemctl restart transcription-dashboard

# supervisor
sudo supervisorctl restart transcription-dashboard
```

### Port ถูกใช้งานแล้ว

```bash
# หา process ที่ใช้ port
lsof -i :8020

# Kill process
kill -9 <PID>

# หรือเปลี่ยน port
export DASHBOARD_PORT=8021
bash dashboard/start-daemon.sh
```

---

## 📝 Environment Variables

Dashboard รองรับ environment variables ต่อไปนี้:

- `DASHBOARD_PORT`: Port สำหรับ Dashboard (default: 8020)
- `USE_INTERNAL_PORT`: ใช้ internal port สำหรับ API calls (default: false)
- `INTERNAL_API_PORT`: Internal API port (default: 8010)

สามารถตั้งค่าใน:
- `.env.runpod` (parent directory)
- Environment variables
- systemd service file
- supervisor config file

---

## 🎯 คำแนะนำ

### สำหรับ Development
- ใช้ **nohup script** หรือ **screen/tmux**

### สำหรับ Production (Linux)
- ใช้ **systemd service** (แนะนำ)

### สำหรับ Production (Multiple Services)
- ใช้ **Supervisor**

---

## 🔗 Related Files

- `dashboard/start-daemon.sh` - Start script (nohup)
- `dashboard/stop-daemon.sh` - Stop script
- `dashboard/status-daemon.sh` - Status script
- `dashboard/systemd/transcription-dashboard.service` - systemd service file
- `dashboard/supervisor/dashboard.conf` - Supervisor config file
