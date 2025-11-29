# 🔧 Troubleshooting - RunPod Pod Container

คู่มือแก้ไขปัญหาที่พบบ่อยในการใช้งาน Transcription Service บน RunPod

---

## ❌ Issue: ModuleNotFoundError: No module named 'aiofiles'

### อาการ
```
ModuleNotFoundError: No module named 'aiofiles'
```

### สาเหตุ
- Python dependencies ไม่ได้ถูกติดตั้งครบถ้วน
- `requirements.txt` ไม่ได้ถูก install

### แก้ไข

**Option 1: Install dependencies ใหม่**

```bash
cd /workspace/transcription-service
pip3 install --no-cache-dir -r requirements.txt
```

**Option 2: Install แบบ manual**

```bash
pip3 install --no-cache-dir aiofiles==23.2.1
```

**Option 3: Restart services ใหม่**

```bash
cd /workspace/transcription-service
bash scripts/pod/start-services-direct.sh
```

---

## ❌ Issue: API not responding

### อาการ
- `curl http://localhost:8001/health` ไม่ตอบสนอง
- Main API ไม่ start

### สาเหตุ
- Python dependencies ไม่ครบ
- Port 8001 ถูกใช้งานแล้ว
- Main API crash

### แก้ไข

**1. ตรวจสอบ dependencies:**

```bash
python3 -c "import aiofiles, pika, redis, pythainlp"
```

**2. ตรวจสอบ processes:**

```bash
ps aux | grep python
```

**3. ตรวจสอบ logs:**

```bash
# ถ้า Main API crash, จะไม่มี logs
# ให้ start services ใหม่และดู output
cd /workspace/transcription-service
bash scripts/pod/start-services-direct.sh
```

**4. ตรวจสอบ port:**

```bash
netstat -tlnp | grep 8001
```

---

## ❌ Issue: Whisper API not responding

### อาการ
- `curl http://localhost:8002/health` ไม่ตอบสนอง

### สาเหตุ
- Whisper API crash
- Models ไม่มี

### แก้ไข

**1. ตรวจสอบ logs:**

```bash
tail -f /tmp/whisper.log
```

**2. ตรวจสอบ models:**

```bash
ls -la /workspace/transcription-service/models/
```

**3. Download models:**

```bash
cd /workspace/transcription-service/whisper-service
bash models/download-ggml-model.sh base
cp models/ggml-base.bin ../models/
```

**4. Restart Whisper API:**

```bash
# Kill existing process
pkill -f whisper_api.py

# Start ใหม่
cd /workspace/transcription-service/whisper-service
export WHISPER_MODEL_PATH=/workspace/transcription-service/models
nohup python3 whisper_api.py > /tmp/whisper.log 2>&1 &
```

---

## ❌ Issue: Redis not responding

### อาการ
- `redis-cli ping` ไม่ตอบสนอง

### สาเหตุ
- Redis ไม่ได้ start
- Port 6379 ถูกใช้งานแล้ว

### แก้ไข

**1. Start Redis:**

```bash
redis-server --daemonize yes --port 6379
```

**2. ตรวจสอบ:**

```bash
redis-cli ping
# ควรได้: PONG
```

---

## ❌ Issue: Video Worker not running

### อาการ
- Transcription jobs ไม่ถูก process

### สาเหตุ
- Video Worker crash
- RabbitMQ ไม่เชื่อมต่อได้

### แก้ไข

**1. ตรวจสอบ logs:**

```bash
tail -f /tmp/video-worker.log
```

**2. ตรวจสอบ RabbitMQ connection:**

```bash
# ตรวจสอบว่า RabbitMQ host ถูกต้อง
cat /workspace/transcription-service/.env.runpod | grep RABBITMQ
```

**3. Restart Video Worker:**

```bash
# Kill existing process
pkill -f video_worker

# Start ใหม่
cd /workspace/transcription-service
export PYTHONPATH=/workspace/transcription-service
nohup python3 -m app.workers.video_worker > /tmp/video-worker.log 2>&1 &
```

---

## ❌ Issue: GPU not being used

### อาการ
- `nvidia-smi` แสดง "No running processes found"
- Transcription ช้า

### สาเหตุ
- CUDA_VISIBLE_DEVICES ไม่ถูกตั้งค่า
- WHISPER_CUBLAS ไม่ถูกตั้งค่า
- Whisper ไม่ได้ compile ด้วย CUDA

### แก้ไข

**1. ตรวจสอบ environment variables:**

```bash
echo $CUDA_VISIBLE_DEVICES
echo $WHISPER_CUBLAS
```

**2. ตั้งค่า environment variables:**

```bash
export CUDA_VISIBLE_DEVICES=0
export WHISPER_CUBLAS=1
```

**3. Restart Whisper API:**

```bash
pkill -f whisper_api.py
cd /workspace/transcription-service/whisper-service
export WHISPER_MODEL_PATH=/workspace/transcription-service/models
export CUDA_VISIBLE_DEVICES=0
export WHISPER_CUBLAS=1
nohup python3 whisper_api.py > /tmp/whisper.log 2>&1 &
```

---

## ❌ Issue: Repository not found

### อาการ
- `ls /workspace/transcription-service` ไม่พบไฟล์

### สาเหตุ
- Repository ยังไม่ถูก clone

### แก้ไข

```bash
cd /workspace
git clone <repo-url> transcription-service
```

---

## ❌ Issue: Permission denied

### อาการ
- `bash scripts/pod/start-services-direct.sh` ได้ permission denied

### สาเหตุ
- Script ไม่มี execute permission

### แก้ไข

```bash
chmod +x scripts/pod/start-services-direct.sh
bash scripts/pod/start-services-direct.sh
```

---

## 🔍 Debug Commands

### Check all services status

```bash
# Check processes
ps aux | grep -E "(python|redis)"

# Check ports
netstat -tlnp | grep -E "(8001|8002|6379)"

# Check logs
tail -f /tmp/whisper.log
tail -f /tmp/video-worker.log

# Check GPU
nvidia-smi
```

### Test services individually

```bash
# Test Redis
redis-cli ping

# Test Whisper API
curl http://localhost:8002/health

# Test Main API
curl http://localhost:8001/health
```

### Check dependencies

```bash
# Check Python packages
pip3 list | grep -E "(aiofiles|pika|redis|pythainlp|fastapi)"

# Test imports
python3 -c "import aiofiles, pika, redis, pythainlp, fastapi; print('All OK')"
```

---

## 📋 Complete Reset

ถ้าต้องการ reset ทุกอย่าง:

```bash
# Kill all processes
pkill -f python
pkill -f redis

# Remove logs
rm -f /tmp/whisper.log /tmp/video-worker.log

# Restart services
cd /workspace/transcription-service
bash scripts/pod/start-services-direct.sh
```

---

## 🔗 Related Documents

- **Quick Start:** [QUICK_START.md](./QUICK_START.md)
- **Direct Mode Setup:** [DIRECT_MODE_SETUP.md](./DIRECT_MODE_SETUP.md)

---

**Last Updated:** 2024-12-19

