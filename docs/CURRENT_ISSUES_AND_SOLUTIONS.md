# 🔍 Current Issues and Solutions

## ปัญหาที่พบ

### 1. GPU Utilization ต่ำ (20-30%)
**สาเหตุ:**
- Sequential processing (1 worker)
- Model lock ทำให้ transcription เป็น sequential
- Chunk size เล็ก (30s) → GPU ไม่ได้ใช้เต็มที่

**ผลกระทบ:**
- Transcription ช้า (ไม่ถึง 5x real-time)
- GPU ไม่ได้ใช้เต็มประสิทธิภาพ

### 2. ระบบซับซ้อนเกินไป
**Flow ปัจจุบัน:**
```
Client → API → Transcription Service
              ↓
         RabbitMQ (transcription_queue)
              ↓
         Video Worker
              ↓
         [1] Extract Audio (FFmpeg)
              ↓
         [2] Chunking (30s chunks)
              ↓
         RabbitMQ (transcription_chunk_queue)
              ↓
         [3] Workers (ThreadPoolExecutor)
              ↓
         [4] Transcription (Whisper) - Sequential (เพราะ lock)
              ↓
         [5] Merge Results
              ↓
         [6] Save & Callback
```

**ปัญหาที่พบ:**
- หลาย Queue (2 queues)
- หลายขั้นตอน (6 steps)
- Progress tracking ซับซ้อน
- Model lock ทำให้ไม่ parallel

## 💡 Solutions

### Solution 1: Simplified Configuration (Quick Fix) ⭐

**ปรับ Configuration:**
```bash
# ใน .env.runpod
TRANSCRIPTION_MAX_WORKERS=1
WHISPER_USE_THREAD_LOCAL=false
TRANSCRIPTION_CHUNK_DURATION=90  # เพิ่มจาก 30 → 90
TRANSCRIPTION_PREFETCH_COUNT=100  # เพิ่มจาก 20 → 100
WHISPER_BEAM_SIZE=1
WHISPER_TEMPERATURE=0
WHISPER_CONDITION_ON_PREVIOUS_TEXT=false
```

**ผลลัพธ์:**
- ✅ GPU utilization: 80-90%
- ✅ Chunk size ใหญ่ → GPU ทำงานนานขึ้น
- ✅ Prefetch count สูง → มี chunks พร้อม process
- ✅ Sequential processing แต่เร็วขึ้น

### Solution 2: Remove Model Lock (Advanced)

**แก้ไข:** `app/services/whisper_providers/openai_whisper_provider.py`

```python
# ลบ lock ออก (ใช้ shared model โดยไม่ lock)
# ⚠️ ต้องระวัง: อาจเกิด CUDA OOM หรือ race condition

# ใน transcribe method:
# ลบ with usage_lock: ออก
result = whisper_model.transcribe(...)
```

**ผลลัพธ์:**
- ✅ True parallel processing
- ✅ GPU utilization: 90-100%
- ⚠️ อาจเกิด CUDA OOM
- ⚠️ อาจเกิด race condition

### Solution 3: Use faster-whisper (Best Performance)

**เปลี่ยนจาก openai-whisper → faster-whisper**

```python
from faster_whisper import WhisperModel

model = WhisperModel("medium", device="cuda", compute_type="float16")

# รองรับ batch_size
segments, info = model.transcribe(
    audio_path,
    language="th",
    beam_size=1,
    temperature=0,
    batch_size=16,  # ⚡ รองรับ batch processing!
)
```

**ผลลัพธ์:**
- ✅ เร็วกว่า 2-4x
- ✅ รองรับ batch_size
- ✅ GPU utilization: 90-100%
- ✅ ใช้ memory น้อยกว่า

## 🎯 Recommended Approach

### สำหรับตอนนี้ (Quick Fix):
1. ✅ **ใช้ Solution 1**: Simplified Configuration
2. ✅ **เพิ่ม chunk_duration**: 30s → 90s
3. ✅ **เพิ่ม prefetch_count**: 20 → 100
4. ✅ **ใช้ 1 worker**: Sequential แต่เร็วขึ้น

### สำหรับอนาคต (Best Performance):
1. ⭐ **เปลี่ยนไปใช้ faster-whisper**
2. ⭐ **ใช้ batch processing**
3. ⭐ **ลบ model lock** (ถ้าใช้ faster-whisper)

## 📊 Expected Results

### Current (Before):
- GPU Utilization: 20-30%
- Speed: 1-2x real-time
- Chunk size: 30s
- Workers: 1 (sequential)

### After Solution 1:
- GPU Utilization: 80-90%
- Speed: 5-10x real-time
- Chunk size: 90s
- Workers: 1 (sequential แต่เร็วขึ้น)

### After Solution 3 (faster-whisper):
- GPU Utilization: 90-100%
- Speed: 10-20x real-time
- Batch size: 16
- True parallel processing

