# 🔧 แก้ไข CUDA Out of Memory และ Event Loop Issues

## ปัญหาที่พบ

### 1. CUDA Out of Memory
- **สาเหตุ**: Thread-local models ทำให้แต่ละ thread load model instance ของตัวเอง
- **medium model** ~2.4GB × 5 threads = ~12GB (เกิน GPU memory 15.58GB)
- **ผลลัพธ์**: GPU memory เต็ม → ไม่สามารถ load model ได้

### 2. Event Loop Conflict
- **สาเหตุ**: `transcribe_file` (sync) ถูกเรียกจาก async function → event loop conflict
- **ผลลัพธ์**: `RuntimeError: Cannot run the event loop while another loop is running`

## วิธีแก้ไข

### Option 1: ลด TRANSCRIPTION_MAX_WORKERS (แนะนำ)

**สำหรับ medium model:**
```bash
TRANSCRIPTION_MAX_WORKERS=2  # medium model ~2.4GB × 2 = ~4.8GB (พอดี)
```

**สำหรับ large-v3 model:**
```bash
TRANSCRIPTION_MAX_WORKERS=1  # large-v3 model ~3GB × 1 = ~3GB (พอดี)
```

### Option 2: ใช้ Sequential Processing

**ตั้งค่า `.env.runpod`:**
```bash
WHISPER_USE_THREAD_LOCAL=false  # ใช้ shared model (sequential)
TRANSCRIPTION_MAX_WORKERS=1     # ไม่จำเป็นเมื่อใช้ sequential
```

### Option 3: ใช้ Model ที่เล็กกว่า

**สำหรับ GPU memory จำกัด:**
```bash
WHISPER_MODEL=base   # ~300MB
# หรือ
WHISPER_MODEL=small  # ~1GB
```

## การคำนวณ GPU Memory

**Model Sizes:**
- `base`: ~300MB
- `small`: ~1GB
- `medium`: ~2.4GB
- `large-v3`: ~3GB

**Formula:**
```
Required Memory = Model Size × TRANSCRIPTION_MAX_WORKERS + Overhead (~500MB)
```

**ตัวอย่าง:**
- medium model + 5 workers = 2.4GB × 5 + 0.5GB = **12.5GB** ❌ (เกิน)
- medium model + 2 workers = 2.4GB × 2 + 0.5GB = **5.3GB** ✅ (พอดี)
- large-v3 + 1 worker = 3GB × 1 + 0.5GB = **3.5GB** ✅ (พอดี)

## แนะนำ Configuration

### สำหรับ RTX 4080 Super (16GB)

**Parallel Processing (medium model):**
```bash
WHISPER_USE_THREAD_LOCAL=true
TRANSCRIPTION_MAX_WORKERS=2
TRANSCRIPTION_PREFETCH_COUNT=10
WHISPER_MODEL=medium
```

**Sequential Processing (large-v3 model):**
```bash
WHISPER_USE_THREAD_LOCAL=false
TRANSCRIPTION_MAX_WORKERS=1
WHISPER_MODEL=large-v3
```

**Parallel Processing (base model):**
```bash
WHISPER_USE_THREAD_LOCAL=true
TRANSCRIPTION_MAX_WORKERS=5
TRANSCRIPTION_PREFETCH_COUNT=20
WHISPER_MODEL=base
```

## Quick Fix

**บน Pod:**
```bash
# แก้ไข .env.runpod
sed -i 's/TRANSCRIPTION_MAX_WORKERS=.*/TRANSCRIPTION_MAX_WORKERS=2/' .env.runpod

# หรือใช้ sequential processing
sed -i 's/WHISPER_USE_THREAD_LOCAL=.*/WHISPER_USE_THREAD_LOCAL=false/' .env.runpod

# Restart worker
pkill -f 'python.*video_worker'
bash scripts/pod/start-pod.sh worker
```

