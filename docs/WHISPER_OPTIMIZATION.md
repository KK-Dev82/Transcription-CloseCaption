# ⚡ Whisper Optimization Guide

## 🎯 เป้าหมาย
- **เร่งความเร็ว**: 10 นาที video → 1-2 นาที transcription (5-10x real-time)
- **ไม่เสียคุณภาพ**: ยังคงความแม่นยำสูง
- **ใช้ GPU เต็มที่**: GPU utilization ≥80%

## 🔧 Optimization Parameters

### 1. Greedy Decoding (beam_size=1)
**Default**: `beam_size=5` (ช้า แต่แม่นยำ)  
**Optimized**: `beam_size=1` (เร็วมาก, คุณภาพลดลงเล็กน้อย)

```bash
# ใน .env.runpod
WHISPER_BEAM_SIZE=1
```

**ผลกระทบ**:
- ✅ เร็วขึ้น 2-3x
- ⚠️ คุณภาพลดลง ~2-5%

### 2. Temperature=0
**Default**: `temperature=0` (ดีอยู่แล้ว)  
**Optimized**: `temperature=0` (ชัดเจน, เสถียร)

```bash
# ใน .env.runpod
WHISPER_TEMPERATURE=0
```

**ผลกระทบ**:
- ✅ เสถียร, ไม่สุ่ม
- ✅ เร็วขึ้นเล็กน้อย

### 3. Condition on Previous Text=False
**Default**: `condition_on_previous_text=True` (ใช้ context จาก chunk ก่อนหน้า)  
**Optimized**: `condition_on_previous_text=False` (ไม่ใช้ context)

```bash
# ใน .env.runpod
WHISPER_CONDITION_ON_PREVIOUS_TEXT=false
```

**ผลกระทบ**:
- ✅ เร็วขึ้น (ไม่ต้องรอ context)
- ✅ เหมาะสำหรับ chunks (แต่ละ chunk เป็นอิสระ)
- ⚠️ คุณภาพลดลงเล็กน้อย (ไม่ใช้ context)

### 4. Language Specification
**Default**: `language=None` (auto-detect)  
**Optimized**: `language="th"` (ระบุภาษา)

```python
# ใน code (มีอยู่แล้ว)
language="th"  # ไม่ต้อง auto-detect
```

**ผลกระทบ**:
- ✅ เร็วขึ้น (ไม่ต้อง detect ภาษา)
- ✅ แม่นยำขึ้น (รู้ภาษาแน่นอน)

### 5. FP16 Precision
**Default**: `fp16=False` (CPU) หรือ `fp16=True` (CUDA)  
**Optimized**: `fp16=True` (CUDA)

```python
# ใน code (มีอยู่แล้ว)
fp16=True  # สำหรับ CUDA
```

**ผลกระทบ**:
- ✅ เร็วขึ้น 1.5-2x บน GPU
- ✅ ใช้ memory น้อยลง
- ⚠️ คุณภาพลดลงเล็กน้อย (แต่ไม่สังเกตเห็น)

### 6. Word Timestamps=False
**Default**: `word_timestamps=False` (ดีอยู่แล้ว)  
**Optimized**: `word_timestamps=False` (ไม่ใช้ word-level timestamps)

```python
# ใน code (มีอยู่แล้ว)
word_timestamps=False  # ใช้ segment-level timestamps แทน
```

**ผลกระทบ**:
- ✅ เร็วขึ้น (ไม่ต้องคำนวณ word-level timestamps)
- ✅ เหมาะสำหรับ chunk transcription

### 7. Batch Size
**Note**: `openai-whisper` ไม่รองรับ `batch_size` parameter โดยตรง (ใช้ internal batching)

**สำหรับ faster-whisper (CTranslate2)**:
```bash
WHISPER_BATCH_SIZE=16  # สำหรับ RTX 4080S
```

## 📊 Performance Comparison

| Configuration | Speed (10min video) | GPU Utilization | Quality |
|--------------|---------------------|-----------------|---------|
| **Default** | ~5-8 min | 20-30% | ⭐⭐⭐⭐⭐ |
| **Optimized** | ~1-2 min | 80-95% | ⭐⭐⭐⭐ |

## 🚀 Recommended Settings

### สำหรับ RTX 4080 Super (16GB VRAM)

```bash
# ใน .env.runpod
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
WHISPER_BEAM_SIZE=1
WHISPER_TEMPERATURE=0
WHISPER_CONDITION_ON_PREVIOUS_TEXT=false
WHISPER_USE_THREAD_LOCAL=false  # Sequential processing
TRANSCRIPTION_MAX_WORKERS=1  # 1 worker ใช้ GPU เต็มที่
TRANSCRIPTION_PREFETCH_COUNT=10
```

### สำหรับ Parallel Processing (ถ้าต้องการ)

```bash
# ใน .env.runpod
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
WHISPER_BEAM_SIZE=1
WHISPER_TEMPERATURE=0
WHISPER_CONDITION_ON_PREVIOUS_TEXT=false
WHISPER_USE_THREAD_LOCAL=true  # Parallel processing
TRANSCRIPTION_MAX_WORKERS=2-3  # ขึ้นกับ GPU memory
TRANSCRIPTION_PREFETCH_COUNT=20
```

## 🔄 Migration to faster-whisper (CTranslate2)

### ทำไมควรเปลี่ยน?
- ⚡ **เร็วกว่า 2-4x** เมื่อเทียบกับ openai-whisper
- 💾 **ใช้ memory น้อยกว่า** (optimized C++ backend)
- 🎯 **รองรับ batch_size** สำหรับ GPU
- ✅ **คุณภาพเท่ากัน** (ใช้ model เดียวกัน)

### การติดตั้ง

```bash
pip install faster-whisper
```

### การใช้งาน

```python
from faster_whisper import WhisperModel

model = WhisperModel("medium", device="cuda", compute_type="float16")

segments, info = model.transcribe(
    "audio.wav",
    language="th",
    beam_size=1,
    temperature=0,
    condition_on_previous_text=False,
    batch_size=16,  # ⚡ รองรับ batch_size!
    vad_filter=True,  # Voice Activity Detection
)
```

### Performance

| Provider | Speed (10min video) | GPU Utilization |
|----------|-------------------|-----------------|
| openai-whisper | ~1-2 min | 80-95% |
| faster-whisper | ~30-60s | 90-99% |

## 📝 Summary

### Optimization ที่ทำแล้ว:
1. ✅ **FP16** สำหรับ CUDA
2. ✅ **Language="th"** (ไม่ต้อง auto-detect)
3. ✅ **Word timestamps=False**
4. ✅ **Greedy decoding** (beam_size=1) - ผ่าน env var
5. ✅ **Temperature=0** - ผ่าน env var
6. ✅ **Condition on previous text=False** - ผ่าน env var

### ข้อเสนอแนะ:
1. **ใช้ Sequential Processing** (1 worker) เพื่อใช้ GPU เต็มที่
2. **พิจารณา faster-whisper** สำหรับ production (เร็วกว่า 2-4x)
3. **เตรียม audio ที่ 16 kHz mono** ล่วงหน้า (ลดงาน resample)

## 🔍 Testing

```bash
# ทดสอบกับวิดีโอ 5 วินาที
bash scripts/pod/test-single-video.sh uploads/v05-1.mp4 medium 1

# ตรวจสอบ GPU utilization
nvidia-smi -l 1

# ตรวจสอบ logs
tail -f /tmp/video-worker.log | grep "Optimization"
```

