# 🧪 ผลการทดสอบ Parallel และ Sequential Processing

## สรุป

ระบบสามารถรองรับทั้ง **Parallel Processing** และ **Sequential Processing** ได้แล้ว ✅

## การทดสอบ

### 1. Sequential Processing (WHISPER_USE_THREAD_LOCAL=false)

**Configuration**:
- `WHISPER_USE_THREAD_LOCAL=false`
- ใช้ shared model instance
- ใช้ lock เพื่อป้องกัน race condition

**ผลลัพธ์**:
- ✅ Logs แสดง: `🔄 Thread-local models: False`
- ✅ ใช้ shared model (ต้องใช้ lock)
- ✅ Chunks ถูกประมวลผลแบบ sequential (1 chunk ต่อครั้ง)

**Logs**:
```
[OpenAI Whisper] 🔄 Thread-local models: False
[OpenAI Whisper] Using shared model (lock required) for sequential processing
```

### 2. Parallel Processing (WHISPER_USE_THREAD_LOCAL=true)

**Configuration**:
- `WHISPER_USE_THREAD_LOCAL=true` (default)
- ใช้ thread-local model instances
- แต่ละ thread มี model instance ของตัวเอง
- ไม่ต้องใช้ lock

**ผลลัพธ์**:
- ✅ Logs แสดง: `🔄 Thread-local models: True`
- ✅ ใช้ thread-local models (ไม่ต้องใช้ lock)
- ✅ Chunks ถูกประมวลผลแบบ parallel (หลาย chunks พร้อมกัน)

**Logs**:
```
[OpenAI Whisper] Loading thread-local model: base on cpu (for parallel processing)
[OpenAI Whisper] Thread-local model loaded in 1.50s
[OpenAI Whisper] 🔄 Thread-local models: True
[OpenAI Whisper] Using thread-local model (no lock needed) for parallel processing
```

## วิธีสลับโหมด

### วิธีที่ 1: แก้ไข .env.runpod

```bash
# สำหรับ Parallel Processing
WHISPER_USE_THREAD_LOCAL=true

# สำหรับ Sequential Processing
WHISPER_USE_THREAD_LOCAL=false
```

จากนั้น restart worker:
```bash
docker exec transcription-local-base bash -c "cd /workspace/transcription-service && pkill -f 'python.*video_worker' && sleep 2 && bash scripts/pod/start-pod.sh worker"
```

### วิธีที่ 2: ใช้ Environment Variable โดยตรง

```bash
# Parallel Processing
export WHISPER_USE_THREAD_LOCAL=true
python3 -m app.workers.video_worker

# Sequential Processing
export WHISPER_USE_THREAD_LOCAL=false
python3 -m app.workers.video_worker
```

## ข้อแตกต่าง

| Feature | Parallel Processing | Sequential Processing |
|---------|-------------------|---------------------|
| **Model Instances** | 1 instance ต่อ thread | 1 shared instance |
| **Lock** | ไม่ต้องใช้ | ต้องใช้ |
| **GPU Utilization** | สูง (หลาย chunks พร้อมกัน) | ต่ำ (1 chunk ต่อครั้ง) |
| **Memory Usage** | สูง (หลาย model instances) | ต่ำ (1 model instance) |
| **Speed** | เร็ว (parallel) | ช้า (sequential) |
| **เหมาะสำหรับ** | GPU server (memory เพียงพอ) | CPU หรือ GPU memory จำกัด |

## ข้อแนะนำ

### ใช้ Parallel Processing เมื่อ:
- ✅ มี GPU memory เพียงพอ (16GB+)
- ✅ ต้องการความเร็วสูงสุด
- ✅ มีหลาย chunks ที่ต้องประมวลผล

### ใช้ Sequential Processing เมื่อ:
- ✅ GPU memory จำกัด (< 8GB)
- ✅ ต้องการประหยัด memory
- ✅ ไม่ต้องการความเร็วสูง

## สรุป

✅ **ระบบรองรับทั้งสองโหมดแล้ว**
- Parallel Processing: ใช้ thread-local models (ไม่ต้องใช้ lock)
- Sequential Processing: ใช้ shared model (ต้องใช้ lock)

✅ **สามารถสลับโหมดได้ง่าย** โดยแก้ไข `WHISPER_USE_THREAD_LOCAL` environment variable

✅ **Default**: Parallel Processing (`WHISPER_USE_THREAD_LOCAL=true`)

