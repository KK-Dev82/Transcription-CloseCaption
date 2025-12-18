# 🔌 Port Configuration Guide

## ⚠️ สิ่งสำคัญ

**Port 8001 ถูกใช้โดย RunPod Nginx/Proxy แล้ว!**

- ❌ **อย่าใช้ Port 8001** สำหรับ API Server
- ✅ **ใช้ Port 8000** แทน (หรือ port อื่นที่ว่าง)

---

## 📋 Port Mapping

### Internal Ports (ใน Pod) = RunPod HTTP Expose Ports
```
API Server:     Port 8010
Webhook Server: Port 8020 (optional)
Monitoring:     Port 8030 (optional)
```

### RunPod HTTP Expose (Proxy)
```
8010 → Port 8010 (API Server) - Auto-mapped
8020 → Port 8020 (Webhook Server) - Auto-mapped
8030 → Port 8030 (Monitoring) - Auto-mapped
```

**⚠️ หมายเหตุ:**
- RunPod HTTP Expose จะ map port เดียวกัน (8010 → 8010)
- ไม่ต้องตั้งค่า port mapping เพิ่มเติม

---

## ⚙️ ตั้งค่า RunPod Proxy

### 1. ไปที่ RunPod Dashboard
- เลือก Pod ของคุณ
- ไปที่ "Connect" tab → "HTTP services"

### 2. Ports ที่มีให้ใช้
```
✅ Port 8001: Ready (HTTP Service) - ถูกใช้โดย Nginx/Proxy (ห้ามใช้)
⚠️  Port 8002: Not ready - ใช้ได้ (Webhook Server - optional)
⚠️  Port 8010: Not ready - ใช้ได้ (API Server - แนะนำ)
⚠️  Port 8020: Not ready - ใช้ได้ (Webhook Server - optional)
⚠️  Port 8030: Not ready - ใช้ได้ (Monitoring - optional)
❌ Port 8888: Ready (Jupyter Lab) - ห้ามใช้
```

### 3. RunPod HTTP Expose จะ Auto-map
- Port 8010 → Port 8010 (API Server)
- Port 8020 → Port 8020 (Webhook Server)
- Port 8030 → Port 8030 (Monitoring)
- **ไม่ต้องตั้งค่า port mapping เพิ่มเติม**

---

## 🚀 Start API Server

```bash
# API Server จะรันที่ port 8010
bash scripts/start-api-nohup.sh

# ตรวจสอบ
curl http://127.0.0.1:8010/health
```

---

## 🧪 ทดสอบ

### Localhost (Internal)
```bash
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:8010/api/upload/list
```

### Through Proxy (External)
```bash
curl https://n2l8ke53h14aaw-8010.proxy.runpod.net/health
curl https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/upload/list
```

---

## 📝 Environment Variables

### `.env.runpod`
```env
API_PORT=8010
API_HOST=0.0.0.0
```

### หรือใช้ Default
- `API_PORT` default = 8010 (แก้ไขใน script แล้ว)

---

## 🔍 ตรวจสอบ Port

```bash
# ตรวจสอบ port ที่ใช้
netstat -tuln | grep -E "8010|8020|8030"

# ตรวจสอบ process
ps aux | grep uvicorn
```

---

## ⚠️ Troubleshooting

### ปัญหา: 502 Bad Gateway
- **สาเหตุ**: API server ยังไม่รัน หรือรันที่ port ผิด
- **แก้ไข**: 
  ```bash
  # ตรวจสอบว่า API server รันอยู่
  ps aux | grep uvicorn
  # Restart API server
  bash scripts/stop-all.sh
  bash scripts/start-api-nohup.sh
  ```

### ปัญหา: Port already in use
- **สาเหตุ**: Port ถูกใช้อยู่แล้ว
- **แก้ไข**: 
  ```bash
  lsof -i :8010
  kill $(lsof -t -i:8010)
  ```

---

## 📚 Related Documentation

- [POSTMAN_GUIDE.md](./POSTMAN_GUIDE.md) - คู่มือ Postman
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - คู่มือแก้ปัญหา

