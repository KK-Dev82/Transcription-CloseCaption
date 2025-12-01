# 🔧 แก้ไขปัญหาบน Pod GPU

## ปัญหาที่พบ

### 1. CUDA Out of Memory
```
torch.cuda.OutOfMemoryError: CUDA out of memory. 
GPU 0 has a total capacty of 15.58 GiB of which 2.50 MiB is free.
```

**สาเหตุ:**
- Thread-local models ทำให้แต่ละ thread load model instance ของตัวเอง
- medium model ~2.4GB × 5 threads = ~12GB (เกิน GPU memory)

### 2. Event Loop Conflict
```
RuntimeError: Cannot run the event loop while another loop is running
```

**สาเหตุ:**
- `transcribe_file` (sync) ถูกเรียกจาก async function → event loop conflict

### 3. API Endpoint Error
```
{"detail": "Not Found"}
```

**สาเหตุ:**
- API endpoint อาจไม่ถูกต้อง หรือ service ไม่ได้รัน

## วิธีแก้ไข

### Step 1: แก้ไข CUDA OOM

**Option A: ลด TRANSCRIPTION_MAX_WORKERS (แนะนำ)**

```bash
# บน Pod
cd /workspace/transcription-service

# แก้ไข .env.runpod
sed -i 's/TRANSCRIPTION_MAX_WORKERS=.*/TRANSCRIPTION_MAX_WORKERS=2/' .env.runpod

# สำหรับ medium model: 2.4GB × 2 = 4.8GB (พอดี)
# สำหรับ large-v3: 3GB × 1 = 3GB (พอดี)
```

**Option B: ใช้ Sequential Processing**

```bash
# แก้ไข .env.runpod
sed -i 's/WHISPER_USE_THREAD_LOCAL=.*/WHISPER_USE_THREAD_LOCAL=false/' .env.runpod
sed -i 's/TRANSCRIPTION_MAX_WORKERS=.*/TRANSCRIPTION_MAX_WORKERS=1/' .env.runpod
```

### Step 2: Restart Worker

```bash
# Stop worker
pkill -f 'python.*video_worker'

# Start worker (จะใช้ค่าใหม่จาก .env.runpod)
bash scripts/pod/start-pod.sh worker

# ตรวจสอบ logs
tail -f /tmp/video-worker.log | grep -E 'ThreadPoolExecutor|Thread-local|CUDA'
```

### Step 3: ตรวจสอบ GPU Memory

```bash
# ตรวจสอบ GPU memory
nvidia-smi

# ตรวจสอบว่า model ถูก load กี่ instances
watch -n 1 'nvidia-smi | grep -E "MiB|python"'
```

## Recommended Configuration

### สำหรับ medium model (RTX 4080 Super 16GB)

```bash
WHISPER_USE_THREAD_LOCAL=true
TRANSCRIPTION_MAX_WORKERS=2
TRANSCRIPTION_PREFETCH_COUNT=10
WHISPER_MODEL=medium
```

**คำนวณ:**
- Model size: 2.4GB
- Workers: 2
- Required: 2.4GB × 2 + 0.5GB overhead = **5.3GB** ✅

### สำหรับ large-v3 model (RTX 4080 Super 16GB)

```bash
WHISPER_USE_THREAD_LOCAL=false  # ใช้ sequential (ประหยัด memory)
TRANSCRIPTION_MAX_WORKERS=1
WHISPER_MODEL=large-v3
```

**คำนวณ:**
- Model size: 3GB
- Workers: 1 (sequential)
- Required: 3GB + 0.5GB overhead = **3.5GB** ✅

### สำหรับ base model (RTX 4080 Super 16GB)

```bash
WHISPER_USE_THREAD_LOCAL=true
TRANSCRIPTION_MAX_WORKERS=5
TRANSCRIPTION_PREFETCH_COUNT=20
WHISPER_MODEL=base
```

**คำนวณ:**
- Model size: 300MB
- Workers: 5
- Required: 300MB × 5 + 0.5GB overhead = **2GB** ✅

## Testing

```bash
# ทดสอบ transcription
bash scripts/pod/test-transcription.sh uploads/v10-1.mp4 medium

# ตรวจสอบ GPU utilization
watch -n 1 'nvidia-smi'

# ตรวจสอบ logs
tail -f /tmp/video-worker.log | grep -E 'Starting chunk|Completed chunk|CUDA|Thread-local'
```

## สรุป

**ปัญหาหลัก:**
1. ✅ CUDA OOM → แก้ไขโดยลด `TRANSCRIPTION_MAX_WORKERS` หรือใช้ sequential
2. ✅ Event Loop Conflict → แก้ไขโดยใช้ `await provider.transcribe()` โดยตรง
3. ⚠️ API Endpoint → ตรวจสอบว่า Main API ทำงานอยู่ (`curl http://localhost:8001/health`)

**Quick Fix:**
```bash
# ลด workers สำหรับ medium model
sed -i 's/TRANSCRIPTION_MAX_WORKERS=.*/TRANSCRIPTION_MAX_WORKERS=2/' .env.runpod

# Restart
pkill -f 'python.*video_worker' && bash scripts/pod/start-pod.sh worker
```

