# ⚡ Quick Setup: Backend + Pod Integration

คู่มือแบบเร็วสำหรับตั้งค่า Transcription Service บน Pod ให้ Backend เชื่อมต่อได้

---

## 📋 สรุปปัญหา

1. ✅ Pod IP: **80.15.7.37:41423** (SSH)
2. ✅ Service Port: **8001**
3. ⚠️  Transcription Service ยังไม่รัน (nginx ให้ 502)
4. ❓ ยังไม่เปิดพอร์ทรับ connection จากภายนอก

---

## 🚀 ขั้นตอนการตั้งค่า (Quick)

### Step 1: Start Transcription Service บน Pod

```bash
# SSH เข้า Pod
ssh pytorch-pod

# Run script
cd /workspace/transcription-service
bash scripts/pod/start-service-for-backend.sh
```

**หรือรันแบบ manual:**

```bash
ssh pytorch-pod << 'EOF'
cd /workspace/transcription-service
source scripts/pod/setup-gpu-env.sh
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/transcription-service.log 2>&1 &
echo "Service started. Check: tail -f /tmp/transcription-service.log"
EOF
```

### Step 2: ตรวจสอบ Service

```bash
# บน Pod
curl http://localhost:8001/health

# จากเครื่อง Backend (ถ้า network เปิด)
curl http://80.15.7.37:8001/health
```

### Step 3: ตั้งค่า Backend

**Option A: แก้ไข `appsettings.Development.json`**

```json
{
  "ExternalServices": {
    "TranscriptionUrl": "http://80.15.7.37:8001",
    "TranscriptionCallbackBaseUrl": "http://localhost:5173"
  }
}
```

**Option B: ใช้ไฟล์ใหม่ `appsettings.Development.POD.json`**

```bash
# Copy configuration
cp src/Shorthand.Api/appsettings.Development.POD.json \
   src/Shorthand.Api/appsettings.Development.json
```

---

## 🔍 ตรวจสอบ Network

### ทดสอบ Connectivity

```bash
# จากเครื่องที่รัน Backend
curl -v http://80.15.7.37:8001/health

# ถ้าไม่ได้ ตรวจสอบ:
# 1. Firewall บน Pod
# 2. Network security groups
# 3. IP accessibility
```

### เปิดพอร์ท (ถ้าจำเป็น)

```bash
# บน Pod - ตรวจสอบ firewall
sudo ufw status
sudo ufw allow 8001/tcp

# หรือใช้ iptables
sudo iptables -A INPUT -p tcp --dport 8001 -j ACCEPT
```

---

## 🧪 Testing

### Test 1: Service Health

```bash
curl http://80.15.7.37:8001/health
```

### Test 2: API Endpoint

```bash
curl -X POST http://80.15.7.37:8001/transcribe/ \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "http://example.com/test.mp4",
    "file_name": "test.mp4",
    "language": "th",
    "model_size": "tiny"
  }'
```

### Test 3: Integration

```bash
# ใช้ script ที่มีอยู่
bash scripts/test/test-backend-integration.sh \
  --transcription-url http://80.15.7.37:8001 \
  --backend-url http://localhost:5173
```

---

## ⚙️ Configuration Files

### 1. Backend Configuration

**ไฟล์**: `senate-backend/src/Shorthand.Api/appsettings.Development.json`

```json
{
  "ExternalServices": {
    "TranscriptionUrl": "http://80.15.7.37:8001",
    "TranscriptionCallbackBaseUrl": "http://localhost:5173"
  }
}
```

### 2. Transcription Service บน Pod

Service จะรันที่:
- **Host**: `0.0.0.0` (รับ connection จากทุก interface)
- **Port**: `8001`
- **URL**: `http://80.15.7.37:8001`

---

## 📝 Checklist

### บน Pod

- [ ] Transcription Service รัน (`ps aux | grep uvicorn`)
- [ ] Port 8001 เปิด (`netstat -tlnp | grep 8001`)
- [ ] Service ตอบสนอง (`curl http://localhost:8001/health`)
- [ ] GPU environment setup (`source scripts/pod/setup-gpu-env.sh`)

### บน Backend

- [ ] Configuration ตั้งค่าถูกต้อง
- [ ] Network connectivity ไป Pod ได้
- [ ] Callback URL ตั้งค่าถูกต้อง

---

## 🐛 Troubleshooting

### Service ไม่ตอบสนอง

```bash
# ตรวจสอบ log
ssh pytorch-pod "tail -f /tmp/transcription-service.log"

# ตรวจสอบ process
ssh pytorch-pod "ps aux | grep uvicorn"
```

### Network ไม่สามารถเชื่อมต่อ

1. ตรวจสอบ firewall
2. ตรวจสอบ network security groups
3. ตรวจสอบว่า Pod IP เป็น public IP หรือ internal IP

### Callback ไม่ทำงาน

1. ตรวจสอบ `TranscriptionCallbackBaseUrl` ใน config
2. ตรวจสอบว่า Backend สามารถรับ connection จาก Pod ได้
3. ใช้ ngrok/tunnel ถ้าจำเป็น

---

## 📚 Related Documents

- **POD_SETUP_FOR_BACKEND.md** - คู่มือละเอียด
- **BACKEND_INTEGRATION.md** - Flow และ API details
- **BACKEND_LOCAL_SETUP.md** - Setup guide

---

**Last Updated**: 2025-12-02

