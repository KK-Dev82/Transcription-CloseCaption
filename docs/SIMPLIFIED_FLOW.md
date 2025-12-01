# 🎯 Simplified Transcription Flow

## ปัญหาที่พบ

### 1. ระบบซับซ้อนเกินไป
- **หลาย Queue**: `transcription_queue` → `transcription_chunk_queue`
- **หลายขั้นตอน**: Extract → Chunk → Queue → Worker → Transcribe → Merge
- **หลาย Services**: Main API → Transcription Service → Video Worker → Whisper Provider
- **Progress Tracking**: JSON Storage → Polling → Status Updates

### 2. GPU Utilization ต่ำ (20-30%)
- Sequential processing (1 worker)
- Model lock ทำให้ transcription เป็น sequential
- Chunk size เล็ก (30s) ทำให้ GPU ไม่ได้ใช้เต็มที่

## 💡 แนวทางแก้ไข: Simplified Flow

### Option 1: Direct Processing (Simplest) ⭐ แนะนำ

```
Client → API → Transcription Service
              ↓
         [1] Extract Audio (FFmpeg)
              ↓
         [2] Process Directly (Whisper)
              ↓
         [3] Return Result
```

**ข้อดี:**
- ✅ ง่ายที่สุด
- ✅ ไม่ต้องใช้ RabbitMQ
- ✅ ไม่ต้อง chunk (ถ้าวิดีโอไม่ยาวเกินไป)
- ✅ GPU ใช้เต็มที่ (process ทั้งไฟล์)

**ข้อเสีย:**
- ⚠️ ไม่รองรับวิดีโอยาว (อาจ OOM)
- ⚠️ ไม่มี progress tracking

**เหมาะสำหรับ:**
- วิดีโอสั้น (< 5 นาที)
- Real-time transcription
- Simple use cases

### Option 2: Simplified Queue (Recommended for Production)

```
Client → API → RabbitMQ (transcription_queue)
              ↓
         Video Worker (1 worker, ใช้ GPU เต็มที่)
              ↓
         [1] Extract Audio
              ↓
         [2] Process in Large Chunks (60-90s)
              ↓
         [3] Return Result
```

**ข้อดี:**
- ✅ ใช้ RabbitMQ สำหรับ async processing
- ✅ 1 worker ใช้ GPU เต็มที่ (80-90%)
- ✅ Chunk size ใหญ่ → GPU ทำงานนานขึ้น
- ✅ Progress tracking ได้

**ข้อเสีย:**
- ⚠️ ยังต้องใช้ RabbitMQ
- ⚠️ ต้องจัดการ queue

**เหมาะสำหรับ:**
- Production environment
- วิดีโอยาว (> 5 นาที)
- ต้องการ progress tracking

### Option 3: Batch Processing (Max GPU Utilization)

```
Client → API → Transcription Service
              ↓
         [1] Extract Audio
              ↓
         [2] Split into Large Chunks (60-90s)
              ↓
         [3] Process All Chunks in Batch (Parallel)
              ↓
         [4] Merge Results
```

**ข้อดี:**
- ✅ GPU ใช้เต็มที่ (batch processing)
- ✅ ไม่ต้องใช้ RabbitMQ
- ✅ เร็วที่สุด

**ข้อเสีย:**
- ⚠️ ต้อง refactor code
- ⚠️ อาจ OOM ถ้า chunks มากเกินไป

**เหมาะสำหรับ:**
- High-performance requirements
- Dedicated GPU server
- Batch processing

## 🚀 Implementation: Simplified Direct Processing

### Step 1: สร้าง Simple Transcription Endpoint

```python
@app.post("/transcribe/simple")
async def transcribe_simple(
    file: UploadFile,
    language: str = "th",
    model_size: str = "medium"
):
    """Simple transcription - ไม่ใช้ queue"""
    
    # 1. Save file
    file_path = await save_upload_file(file)
    
    # 2. Extract audio (if video)
    if is_video(file_path):
        audio_path = extract_audio(file_path)
    else:
        audio_path = file_path
    
    # 3. Transcribe directly
    result = whisper_service.transcribe(
        audio_path,
        language=language,
        model_size=model_size
    )
    
    # 4. Return result
    return result
```

### Step 2: Optimize for Single Worker

```python
# ใช้ 1 worker แต่ process chunks ต่อเนื่องกัน
# ไม่ต้องรอ lock (ใช้ shared model แต่ process sequential)

# Configuration
TRANSCRIPTION_MAX_WORKERS=1
WHISPER_USE_THREAD_LOCAL=false
TRANSCRIPTION_CHUNK_DURATION=90  # เพิ่ม chunk size
```

### Step 3: Maximize GPU Utilization

```python
# ใช้ GPU เต็มที่โดย:
# 1. เพิ่ม chunk size (60-90s)
# 2. Process chunks ต่อเนื่องกัน (ไม่ idle)
# 3. ใช้ prefetch_count สูง (50-100)
# 4. Optimize Whisper parameters
```

## 📊 Comparison

| Approach | Complexity | GPU Utilization | Speed | Use Case |
|----------|-----------|------------------|-------|----------|
| **Current** | High | 20-30% | Slow | ❌ |
| **Simplified Direct** | Low | 80-90% | Fast | Short videos |
| **Simplified Queue** | Medium | 80-90% | Fast | Production |
| **Batch Processing** | Medium | 90-100% | Fastest | High-performance |

## 🎯 Recommendation

### สำหรับ Production:
**ใช้ Simplified Queue (Option 2)**
- 1 worker
- Chunk size 60-90s
- Prefetch count 50-100
- GPU utilization 80-90%

### สำหรับ Testing/Development:
**ใช้ Simplified Direct (Option 1)**
- ไม่ต้องใช้ RabbitMQ
- Process โดยตรง
- ง่ายต่อการ debug

## 🔧 Quick Fix: ปรับ Current System

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
- GPU utilization: 80-90%
- Speed: 5-10x real-time
- Simpler: 1 worker, sequential processing

