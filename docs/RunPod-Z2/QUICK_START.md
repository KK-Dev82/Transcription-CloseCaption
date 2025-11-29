# 🚀 Quick Start - RunPod Pod Container

คู่มือเริ่มต้นใช้งาน Transcription Service บน RunPod Pod Container

---

## ✅ สถานะปัจจุบัน

จากผลลัพธ์ `test-runpod-gpu.sh`:
- ✅ GPU ทำงานได้ (RTX 4000 Ada Generation, CUDA 12.7)
- ❌ Repository ยังไม่ถูก clone
- ❌ Services ยังไม่ start

---

## 🚀 ขั้นตอนการ Setup

### Step 1: Clone Repository

```bash
cd /workspace
git clone <repo-url> transcription-service
```

**หมายเหตุ:** แทนที่ `<repo-url>` ด้วย URL ของ repository จริง

**ตัวอย่าง:**
```bash
# ถ้าใช้ GitHub
git clone https://github.com/your-org/transcription-close-caption-service.git transcription-service

# หรือถ้าใช้ GitLab
git clone https://gitlab.com/your-org/transcription-close-caption-service.git transcription-service
```

---

### Step 2: ตรวจสอบ Repository

```bash
cd /workspace/transcription-service
ls -la
```

**ควรเห็น:**
- `app/` - Main API code
- `whisper-service/` - Whisper API code
- `scripts/` - Setup scripts
- `requirements.txt` - Python dependencies
- `docker-compose.runpod.yml` - Docker Compose config (ไม่ใช้ใน Direct Mode)

---

### Step 3: Start Services

```bash
cd /workspace/transcription-service
bash scripts/pod/start-services-direct.sh
```

**Script จะทำ:**
1. ✅ ตรวจสอบ GPU
2. ✅ สร้าง `.env.runpod` (ถ้ายังไม่มี)
3. ✅ Install Python dependencies
4. ✅ Download Whisper models (ถ้ายังไม่มี)
5. ✅ Start Redis (background)
6. ✅ Start Whisper API (background)
7. ✅ Start Video Worker (background)
8. ✅ Start Main API (foreground)

---

### Step 4: ตรวจสอบ Services

**เปิด Terminal ใหม่ (SSH เข้า Pod อีกครั้ง):**

```bash
# ตรวจสอบ processes
ps aux | grep -E "(python|redis)"

# ตรวจสอบ API health
curl http://localhost:8001/health

# ตรวจสอบ Whisper health
curl http://localhost:8002/health

# ตรวจสอบ Redis
redis-cli ping
```

**หรือรัน test script:**

```bash
bash scripts/pod/test-runpod-gpu.sh
```

---

## 📝 Environment Variables

Script จะสร้าง `.env.runpod` อัตโนมัติ แต่คุณสามารถแก้ไขได้:

```bash
cd /workspace/transcription-service
nano .env.runpod
```

**ค่าที่สำคัญ:**
- `RABBITMQ_HOST` - สำหรับ Local Testing: `localhost` (ใช้ SSH Tunnel)
- `RABBITMQ_PORT` - `5672`
- `REDIS_URL` - `redis://localhost:6379`
- `WHISPER_PROVIDER` - `builtin` (ใช้ local Whisper) หรือ `groq` (ใช้ Groq API)

---

## 🔧 Troubleshooting

### Issue: Repository ไม่มี

**อาการ:**
- `ls /workspace/transcription-service` ไม่พบไฟล์

**แก้ไข:**
```bash
cd /workspace
git clone <repo-url> transcription-service
```

---

### Issue: Services ไม่ start

**อาการ:**
- `curl http://localhost:8001/health` ไม่ตอบสนอง

**แก้ไข:**
1. ตรวจสอบ logs:
   ```bash
   tail -f /tmp/whisper.log
   tail -f /tmp/video-worker.log
   ```

2. Start services manual:
   ```bash
   cd /workspace/transcription-service
   bash scripts/pod/start-services-direct.sh
   ```

---

### Issue: Python dependencies ไม่ครบ

**อาการ:**
- Error: `ModuleNotFoundError: No module named 'fastapi'`

**แก้ไข:**
```bash
cd /workspace/transcription-service
pip3 install -r requirements.txt
```

---

### Issue: Whisper models ไม่มี

**อาการ:**
- Error: `Model not found: /workspace/transcription-service/models/ggml-base.bin`

**แก้ไข:**
```bash
cd /workspace/transcription-service/whisper-service
bash models/download-ggml-model.sh base
cp models/ggml-base.bin ../models/
```

---

## 🧪 Testing

### Test GPU

```bash
bash scripts/pod/test-runpod-gpu.sh
```

### Test Transcription

```bash
# สร้าง test audio file (ถ้ายังไม่มี)
# หรือใช้ไฟล์ที่มีอยู่

curl -X POST http://localhost:8001/api/transcription/upload \
  -F 'file=@test_audio.wav' \
  -F 'language=th' \
  -F 'model_size=small'
```

---

## 📊 Monitoring

### Check Logs

```bash
# Whisper API logs
tail -f /tmp/whisper.log

# Video Worker logs
tail -f /tmp/video-worker.log

# Main API logs (foreground process)
# Logs จะแสดงใน console ที่รัน start-services-direct.sh
```

### Check GPU Usage

```bash
# Real-time GPU monitoring
watch -n 1 nvidia-smi
```

### Check Service Status

```bash
# Check processes
ps aux | grep -E "(python|redis)"

# Check ports
netstat -tlnp | grep -E "(8001|8002|6379)"
```

---

## 🔗 Related Documents

- **Direct Mode Setup:** [DIRECT_MODE_SETUP.md](./DIRECT_MODE_SETUP.md)
- **Next Steps:** [NEXT_STEPS.md](./NEXT_STEPS.md)
- **Custom Template Configuration:** [CUSTOM_TEMPLATE_CONFIGURATION.md](./CUSTOM_TEMPLATE_CONFIGURATION.md)

---

**Last Updated:** 2024-12-19

