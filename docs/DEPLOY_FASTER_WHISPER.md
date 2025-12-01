# 🚀 Deploy Faster-Whisper บน Pod GPU

## 📋 สรุปการเปลี่ยนแปลง

### 1. เพิ่ม Faster-Whisper Provider
- ✅ สร้าง `FasterWhisperProvider` ที่เร็วกว่า openai-whisper 2-4x
- ✅ รองรับ batch_size สำหรับ GPU
- ✅ GPU utilization สูง (90-100%)

### 2. Simplified Flow (ไม่ chunk)
- ✅ เพิ่ม `use_chunking` option (default: `false`)
- ✅ Flow ใหม่: RabbitMQ → Extract Audio → Transcribe ทั้งไฟล์เลย
- ✅ ลด queue จาก 2 เป็น 1 (เข้า RabbitMQ ครั้งเดียว)

### 3. Requirements.txt
- ✅ เพิ่ม `faster-whisper==1.0.3`

## 🔧 ขั้นตอนการ Deploy

### Step 1: Pull Latest Code

```bash
ssh calm-pink-turtle
cd /workspace/transcription-service
git pull
```

### Step 2: อัปเดต Dependencies

```bash
cd /workspace/transcription-service
bash scripts/pod/update-dependencies.sh
```

หรือติดตั้งด้วยตนเอง:

```bash
pip3 install --no-cache-dir faster-whisper==1.0.3
pip3 install --no-cache-dir -r requirements.txt
```

### Step 3: ตรวจสอบ Configuration

```bash
cat .env.runpod | grep -E 'WHISPER_PROVIDER|WHISPER_MODEL|USE_CHUNKING'
```

ควรเห็น:
```
WHISPER_PROVIDER=faster-whisper
WHISPER_MODEL=medium
USE_CHUNKING=false
```

### Step 4: Restart Services

```bash
bash scripts/pod/restart-pod.sh
```

### Step 5: ตรวจสอบ Status

```bash
bash scripts/pod/check-pod.sh
```

## 🎯 Configuration ที่แนะนำ

### สำหรับ RTX 4080 SUPER (16GB)

```bash
# ใน .env.runpod
WHISPER_PROVIDER=faster-whisper
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
WHISPER_BATCH_SIZE=16
WHISPER_USE_THREAD_LOCAL=false
TRANSCRIPTION_MAX_WORKERS=1
TRANSCRIPTION_CHUNK_DURATION=90
TRANSCRIPTION_PREFETCH_COUNT=100
USE_CHUNKING=false  # ⚡ Simplified flow - ไม่ chunk
```

## 📊 Expected Performance

### Before (openai-whisper + chunking):
- GPU Utilization: 20-30%
- Speed: 1-2x real-time
- Flow: 2 queues, 6 steps

### After (faster-whisper + no chunking):
- GPU Utilization: 80-90%
- Speed: 5-10x real-time
- Flow: 1 queue, 3 steps

## 🧪 Testing

### Test 1: Simple Transcription (ไม่ chunk)

```bash
curl -X POST "http://localhost:8001/transcribe/" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "uploads/v05-1.mp4",
    "language": "th",
    "model_size": "medium",
    "use_chunking": false
  }'
```

### Test 2: With Chunking (ถ้าต้องการ)

```bash
curl -X POST "http://localhost:8001/transcribe/" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "uploads/v10-1.mp4",
    "language": "th",
    "model_size": "medium",
    "use_chunking": true,
    "chunk_duration": 90
  }'
```

## 🔍 Troubleshooting

### 1. faster-whisper ไม่ติดตั้ง

```bash
# ตรวจสอบ
python3 -c "import faster_whisper"

# ติดตั้งใหม่
pip3 install --no-cache-dir faster-whisper==1.0.3
```

### 2. CUDA OOM Error

```bash
# ลด batch_size
WHISPER_BATCH_SIZE=8

# หรือใช้ model เล็กกว่า
WHISPER_MODEL=small
```

### 3. Model ไม่ถูก download

```bash
# Pre-download model
python3 -c "from faster_whisper import WhisperModel; WhisperModel('medium')"
```

## 📝 Notes

- **faster-whisper** ใช้ CTranslate2 ซึ่งเร็วกว่า openai-whisper 2-4x
- **ไม่ chunk** ทำให้ flow ง่ายขึ้นและเร็วขึ้น
- **GPU utilization** จะสูงขึ้นเมื่อใช้ faster-whisper + batch_size

