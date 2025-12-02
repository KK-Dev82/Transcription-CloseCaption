# 🔧 แก้ไข Error เมื่อ Start Service

ปัญหาที่พบและวิธีแก้ไข

---

## ❌ Errors ที่พบ

### Error 1: `No module named uvicorn`
```
/usr/bin/python3: No module named uvicorn
```

**สาเหตุ**: Dependencies ยังไม่ได้ติดตั้ง

### Error 2: `redis-server: command not found`
```
redis-server: command not found
```

**สาเหตุ**: Redis ยังไม่ได้ติดตั้ง (ไม่จำเป็นสำหรับ basic service)

---

## ✅ วิธีแก้ไข

### วิธีที่ 1: ติดตั้ง Dependencies ก่อน (แนะนำ)

```bash
ssh pytorch-pod
cd /workspace/transcription-service

# ติดตั้ง dependencies
bash scripts/pod/install-dependencies.sh
```

### วิธีที่ 2: Quick Start (ติดตั้ง + Start ในครั้งเดียว)

```bash
ssh pytorch-pod
cd /workspace/transcription-service

# ติดตั้ง dependencies และ start service
bash scripts/pod/quick-start.sh
```

---

## 📋 ขั้นตอน Manual

### Step 1: ติดตั้ง Core Dependencies

```bash
cd /workspace/transcription-service

# ติดตั้ง FastAPI และ Uvicorn
pip3 install --no-cache-dir \
    fastapi==0.104.1 \
    "uvicorn[standard]==0.24.0" \
    python-multipart==0.0.6 \
    pydantic==2.5.0
```

### Step 2: ติดตั้ง PyTorch (ถ้ายังไม่มี)

```bash
pip3 install --no-cache-dir \
    torch==2.1.0 \
    torchaudio==2.1.0 \
    --index-url https://download.pytorch.org/whl/cu118
```

### Step 3: ติดตั้ง Whisper Dependencies

```bash
pip3 install --no-cache-dir \
    numpy==1.26.4 \
    "ctranslate2==4.4.0" \
    "faster-whisper==1.0.2"
```

### Step 4: ติดตั้ง Dependencies ทั้งหมด

```bash
pip3 install --no-cache-dir -r requirements.txt
```

### Step 5: Start Service

```bash
bash scripts/pod/start-service-daemon.sh
```

---

## 🔍 ตรวจสอบการติดตั้ง

```bash
# ตรวจสอบ uvicorn
python3 -c "import uvicorn; print('✅ uvicorn:', uvicorn.__version__)"

# ตรวจสอบ fastapi
python3 -c "import fastapi; print('✅ fastapi:', fastapi.__version__)"

# ตรวจสอบ torch
python3 -c "import torch; print('✅ torch:', torch.__version__)"

# ตรวจสอบ faster-whisper
python3 -c "from faster_whisper import WhisperModel; print('✅ faster-whisper: OK')"
```

---

## ⚠️ เกี่ยวกับ Redis

Redis **ไม่จำเป็น** สำหรับ basic transcription service

ถ้าต้องการติดตั้ง Redis:

```bash
# ติดตั้ง Redis
apt-get update
apt-get install -y redis-server

# หรือใช้ Docker
docker run -d --name redis -p 6379:6379 redis:alpine
```

แต่ Transcription Service สามารถทำงานได้โดยไม่ใช้ Redis

---

## 💡 Quick Fix

ถ้าต้องการ start service เร็วๆ โดยไม่รอ dependencies ทั้งหมด:

```bash
# ติดตั้งแค่ core dependencies
pip3 install --no-cache-dir fastapi uvicorn[standard] python-multipart pydantic

# Start service (จะใช้ minimal features)
bash scripts/pod/start-service-daemon.sh
```

---

**Last Updated**: 2025-12-02

