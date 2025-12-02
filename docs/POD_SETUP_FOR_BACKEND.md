# 🚀 Pod Setup สำหรับ Backend Integration

คู่มือการตั้งค่า Transcription Service บน Pod (IP: 80.15.7.37:41423) เพื่อให้ Backend สามารถเชื่อมต่อได้

---

## 📋 สถานะปัจจุบัน

### Pod Information
- **IP**: 80.15.7.37
- **Port**: 41423 (SSH)
- **Service Port**: 8001 (Transcription API)
- **Container**: pytorch-pod
- **Project Path**: `/workspace/transcription-service`

### พบว่า:
- ✅ มี nginx listening ที่ port 8001
- ⚠️  ต้องตรวจสอบว่า Transcription Service รันอยู่หรือไม่

---

## 🔧 การตั้งค่า

### Step 1: ตรวจสอบและ Start Transcription Service บน Pod

```bash
# SSH เข้า Pod
ssh pytorch-pod

# ไปที่ project directory
cd /workspace/transcription-service

# ตรวจสอบว่า service รันอยู่หรือไม่
ps aux | grep uvicorn

# ถ้ายังไม่รัน ใช้ script ที่มีอยู่
bash scripts/pod/start-services-direct.sh

# หรือรันโดยตรง
source scripts/pod/setup-gpu-env.sh
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### Step 2: ตรวจสอบ Port และ Network

```bash
# ตรวจสอบว่าพอร์ท 8001 เปิดอยู่
netstat -tlnp | grep 8001
# หรือ
ss -tlnp | grep 8001

# ทดสอบ local
curl http://localhost:8001/health

# ทดสอบจากภายนอก (จากเครื่องที่สามารถเชื่อมต่อได้)
curl http://80.15.7.37:8001/health
```

### Step 3: เปิดพอร์ท (ถ้ายังไม่เปิด)

#### Option A: ใช้ nginx reverse proxy (แนะนำ)

สร้าง nginx config:

```nginx
# /etc/nginx/sites-available/transcription-service
server {
    listen 8001;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout สำหรับ transcription ที่อาจใช้เวลานาน
        proxy_read_timeout 1800s;
        proxy_connect_timeout 1800s;
        proxy_send_timeout 1800s;
    }
}
```

Enable และ restart:
```bash
sudo ln -s /etc/nginx/sites-available/transcription-service /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### Option B: ใช้ firewall rules (ถ้าจำเป็น)

```bash
# เปิดพอร์ท 8001 (ถ้าใช้ firewall)
sudo ufw allow 8001/tcp
# หรือ
sudo iptables -A INPUT -p tcp --dport 8001 -j ACCEPT
```

---

## ⚙️ Backend Configuration

### สำหรับ Local Development

**ไฟล์**: `senate-backend/src/Shorthand.Api/appsettings.Development.json`

```json
{
  "ExternalServices": {
    "TranscriptionUrl": "http://80.15.7.37:8001",
    "TranscriptionCallbackBaseUrl": "http://localhost:5173"
  },
  "FileService": {
    "ServerUri": "http://localhost:5000",
    "InternalServerUri": "http://file-service:5000"
  }
}
```

### สำหรับ Docker/Local Network

```json
{
  "ExternalServices": {
    "TranscriptionUrl": "http://80.15.7.37:8001",
    "TranscriptionCallbackBaseUrl": "http://host.docker.internal:5173"
  }
}
```

**หมายเหตุ**: 
- ถ้า Backend รันใน Docker และต้องการ callback จาก Pod กลับมา ต้องใช้ public IP หรือ ngrok/tunnel
- หรือใช้ `host.docker.internal` ถ้า Backend อยู่บนเครื่องเดียวกัน

---

## 🔍 Troubleshooting

### ปัญหา: ไม่สามารถเชื่อมต่อจาก Backend ไป Pod

**ตรวจสอบ**:
1. **Network connectivity**:
   ```bash
   # จากเครื่องที่รัน Backend
   curl http://80.15.7.37:8001/health
   ```

2. **Firewall rules**:
   - ตรวจสอบว่า Pod มี firewall ที่บล็อกพอร์ท 8001 หรือไม่
   - ตรวจสอบว่า network infrastructure อนุญาตการเชื่อมต่อหรือไม่

3. **Service status**:
   ```bash
   # บน Pod
   curl http://localhost:8001/health
   ps aux | grep uvicorn
   ```

### ปัญหา: Callback ไม่กลับมา

**ตรวจสอบ**:
- `TranscriptionCallbackBaseUrl` ใน Backend config
- Network connectivity จาก Pod ไป Backend
- Firewall rules สำหรับ outgoing connections จาก Pod

**ทางแก้**:
- ใช้ ngrok หรือ tunnel service สำหรับ callback
- หรือใช้ public IP ของ Backend

---

## 🧪 Testing

### Test 1: ตรวจสอบ Service บน Pod

```bash
# SSH เข้า Pod
ssh pytorch-pod

# ทดสอบ local
curl http://localhost:8001/health
curl http://localhost:8001/
```

### Test 2: ทดสอบจาก Backend Machine

```bash
# ทดสอบ connectivity
curl http://80.15.7.37:8001/health

# ทดสอบ API
curl -X POST http://80.15.7.37:8001/transcribe/ \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "http://example.com/test.mp4",
    "file_name": "test.mp4",
    "language": "th",
    "model_size": "tiny",
    "callback_url": "http://localhost:5173/api/transcription/webhook/completed"
  }'
```

### Test 3: ทดสอบ Integration Flow

```bash
# ใช้ script ที่มีอยู่
bash scripts/test/test-backend-integration.sh \
  --transcription-url http://80.15.7.37:8001 \
  --backend-url http://localhost:5173
```

---

## 📝 Checklist

### บน Pod

- [ ] Transcription Service รันอยู่ (ตรวจด้วย `ps aux | grep uvicorn`)
- [ ] Port 8001 เปิดอยู่ (ตรวจด้วย `netstat -tlnp | grep 8001`)
- [ ] Service ตอบสนอง (ทดสอบด้วย `curl http://localhost:8001/health`)
- [ ] GPU environment ตั้งค่าแล้ว (`source scripts/pod/setup-gpu-env.sh`)
- [ ] Firewall อนุญาต incoming connections (ถ้ามี)

### บน Backend

- [ ] Configuration ตั้งค่าถูกต้อง
- [ ] Network connectivity ไป Pod ได้ (ทดสอบด้วย `curl`)
- [ ] Callback URL ตั้งค่าถูกต้อง
- [ ] Firewall อนุญาต incoming connections สำหรับ callback

---

## 🚀 Quick Start Script

สร้าง script สำหรับ start service บน Pod:

```bash
#!/bin/bash
# scripts/pod/start-for-backend.sh

cd /workspace/transcription-service

# Setup GPU environment
source scripts/pod/setup-gpu-env.sh

# Start service
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/transcription-service.log 2>&1 &

echo "Transcription Service started on port 8001"
echo "Log: /tmp/transcription-service.log"
echo "Health: http://localhost:8001/health"
```

---

## 📝 Notes

1. **Public IP**: Pod ใช้ IP 80.15.7.37 ซึ่งอาจเป็น public IP หรือ internal IP ขึ้นอยู่กับ network setup
2. **Port 8001**: ต้องเปิดพอร์ทนี้ให้ Backend เข้าถึงได้
3. **Callback**: Backend ต้องมี public URL หรือใช้ tunnel สำหรับ callback
4. **Security**: ใน production ควรใช้ HTTPS และ authentication

---

**Last Updated**: 2025-12-02

