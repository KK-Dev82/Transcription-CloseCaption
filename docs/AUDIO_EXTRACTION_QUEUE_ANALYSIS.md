# Audio Extraction Queue Analysis

## 🔍 ปัญหาที่พบ

### จาก Logs ที่วิเคราะห์

1. **FFmpeg ไม่ได้ติดตั้ง**
   - Error: `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'`
   - ทำให้ audio extraction ล้มเหลวทุก task

2. **Prefetch Count ไม่ได้ผล**
   - แม้ตั้ง `prefetch_count=1` แล้ว แต่ยังรับ messages หลายตัวพร้อมกัน
   - เหตุผล: Worker process ใน thread แยก (non-blocking)
   - เมื่อ reconnect → messages ที่รออยู่ถูกส่งมาพร้อมกัน

3. **Connection Errors**
   - `IndexError: pop from an empty deque`
   - `StreamLostError: Stream connection lost`

4. **Tasks Completed แต่ Empty**
   - `full_text length=0, chunks count=0`
   - เพราะ audio extraction ล้มเหลว

## 💡 คำถาม: Audio Extraction ควรมี Queue ไหม?

### ปัญหาปัจจุบัน

**Current Flow:**
```
Transcription Task → Audio Extraction (FFmpeg) → Transcription
```

**ปัญหาที่พบ:**
- ถ้ามี 50 concurrent requests → ต้อง extract audio 50 ตัวพร้อมกัน
- FFmpeg อาจใช้ CPU/Memory มาก
- ไม่มีการควบคุม concurrent extractions
- ถ้า FFmpeg ใช้ทรัพยากรมาก → อาจทำให้ระบบล่ม

### 💡 แนวทางแก้ไข: Audio Extraction Queue

**Recommended Flow:**
```
Transcription Task → Audio Extraction Queue → [Limited FFmpeg Workers] → Transcription
```

**ข้อดี:**
1. ✅ **ควบคุม Concurrent Extractions**
   - จำกัดจำนวน FFmpeg processes ที่ทำงานพร้อมกัน
   - ป้องกัน CPU/Memory overload

2. ✅ **Scalable**
   - เพิ่ม/ลด workers ได้ตามต้องการ
   - แยก resource management ออกจาก transcription

3. ✅ **Fault Tolerance**
   - ถ้า FFmpeg process crash → task ไม่หาย
   - Messages ค้างใน queue (ไม่ค้างใน memory)

4. ✅ **Resource Management**
   - ควบคุม CPU/Memory usage
   - แยก audio extraction จาก transcription processing

### การ Implement

#### Option 1: Separate Queue for Audio Extraction

```python
# Flow:
transcription_queue → audio_extraction_queue → transcription_processing_queue

# Workers:
- Audio Extraction Workers (2-3 workers, prefetch_count=1)
- Transcription Workers (5 workers, prefetch_count=5)
```

#### Option 2: In-Process Queue with Semaphore

```python
# ใช้ Semaphore เพื่อจำกัด concurrent extractions
import asyncio

class VideoService:
    def __init__(self):
        self.extraction_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent
    
    async def extract_audio(self, video_path: str):
        async with self.extraction_semaphore:
            # Extract audio with FFmpeg
            ...
```

#### Option 3: Thread Pool for Audio Extraction

```python
# ใช้ ThreadPoolExecutor เพื่อจำกัด concurrent extractions
from concurrent.futures import ThreadPoolExecutor

class VideoService:
    def __init__(self):
        self.extraction_executor = ThreadPoolExecutor(max_workers=3)
    
    def extract_audio(self, video_path: str):
        # Submit to thread pool
        future = self.extraction_executor.submit(self._extract_audio_sync, video_path)
        return future.result()
```

### 🎯 แนะนำ: Option 3 (Thread Pool)

**เหตุผล:**
- ✅ ง่ายต่อการ implement (ไม่ต้องเปลี่ยน architecture มาก)
- ✅ ควบคุม concurrent extractions ได้
- ✅ ไม่ต้องมี queue ใหม่ (ใช้ใน-process queue)
- ✅ Resource management ดี

**Configuration:**
```bash
# Environment variables
AUDIO_EXTRACTION_MAX_WORKERS=3  # Max concurrent extractions
```

## 📋 Implementation Plan

### Step 1: Fix FFmpeg Installation (ด่วน)

```bash
ssh pytorch-pod
apt-get update
apt-get install -y ffmpeg
```

### Step 2: Add Thread Pool for Audio Extraction

```python
# app/services/video_service.py
class VideoService:
    def __init__(self):
        max_workers = int(os.getenv('AUDIO_EXTRACTION_MAX_WORKERS', '3'))
        self.extraction_executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def extract_audio(self, video_path: str, output_path: str = None) -> str:
        # Submit to thread pool
        future = self.extraction_executor.submit(
            self._extract_audio_sync, video_path, output_path
        )
        return future.result()
    
    def _extract_audio_sync(self, video_path: str, output_path: str = None) -> str:
        # Synchronous audio extraction (blocking)
        ...
```

### Step 3: Monitor Resource Usage

```bash
# Monitor FFmpeg processes
ps aux | grep ffmpeg

# Monitor CPU/Memory
htop
```

## ✅ สรุป

**คำตอบ: Audio Extraction ควรมี Queue/Control Mechanism**

1. ✅ **ต้องติดตั้ง FFmpeg ก่อน** (ปัญหาหลัก) - **เสร็จแล้ว**
2. ✅ **ใช้ Thread Pool** เพื่อจำกัด concurrent extractions - **Implemented**
3. ✅ **ตั้งค่า**: `AUDIO_EXTRACTION_MAX_WORKERS=3` (ปรับตาม resources)
4. ✅ **ผลลัพธ์**: ควบคุม CPU/Memory usage, ป้องกันระบบ overload

## 📊 Configuration

```bash
# .env.runpod
AUDIO_EXTRACTION_MAX_WORKERS=3  # Max concurrent audio extractions
TRANSCRIPTION_QUEUE_PREFETCH_COUNT=1  # 1 task at a time
TRANSCRIPTION_MAX_WORKERS=5  # 5 chunks in parallel
TRANSCRIPTION_PREFETCH_COUNT=5  # 5 chunks prefetch
```

## 🎯 Implementation Status: ✅ Completed

### 1. Thread Pool สำหรับ Audio Extraction

**File**: `app/services/video_service.py`

- ✅ เพิ่ม `ThreadPoolExecutor` ใน `__init__()`
- ✅ แก้ไข `extract_audio()` ให้ใช้ thread pool
- ✅ แยกเป็น `extract_audio()` และ `_extract_audio_sync()`
- ✅ จำกัด concurrent extractions (default: 3 workers)

### 2. แยกการวิเคราะห์ผล

**Audio Extraction Metrics**: `storage/metrics/audio_extraction_{task_id}.json`
```json
{
  "task_id": "...",
  "type": "audio_extraction",
  "video_path": "...",
  "video_size_bytes": 123456,
  "audio_path": "...",
  "audio_size_bytes": 78901,
  "extraction_time_seconds": 5.23,
  "success": true,
  "timestamp": "..."
}
```

**Transcription Metrics**: `storage/metrics/transcription_{task_id}.json`
```json
{
  "task_id": "...",
  "type": "transcription",
  "audio_path": "...",
  "audio_size_bytes": 78901,
  "transcription_time_seconds": 45.67,
  "text_length": 1234,
  "chunks_count": 5,
  "success": true,
  "timestamp": "..."
}
```

### 3. Logging แยกกัน

- `[Audio Extraction]` - สำหรับ audio extraction logs
- `[Transcription]` - สำหรับ transcription logs
- Metrics ถูกบันทึกแยกไฟล์กันตาม task_id

## 🚀 การใช้งาน

### สำหรับการทดลอง 50 Concurrency

```bash
# ตั้งค่า environment variable
export AUDIO_EXTRACTION_MAX_WORKERS=3

# รันทดสอบ
bash scripts/test/run-50-concurrency-test.sh v10-1.mp4

# ตรวจสอบ metrics
ls -la storage/metrics/
# - audio_extraction_*.json (สำหรับ audio extraction)
# - transcription_*.json (สำหรับ transcription)
```

### วิเคราะห์ผล

```bash
# ดู Audio Extraction metrics
cat storage/metrics/audio_extraction_*.json | jq '.extraction_time_seconds'

# ดู Transcription metrics
cat storage/metrics/transcription_*.json | jq '.transcription_time_seconds'

# เปรียบเทียบเวลา
python3 -c "
import json, glob
extraction_times = [json.load(open(f))['extraction_time_seconds'] 
                   for f in glob.glob('storage/metrics/audio_extraction_*.json')]
transcription_times = [json.load(open(f))['transcription_time_seconds'] 
                      for f in glob.glob('storage/metrics/transcription_*.json')]
print(f'Audio Extraction: avg={sum(extraction_times)/len(extraction_times):.2f}s')
print(f'Transcription: avg={sum(transcription_times)/len(transcription_times):.2f}s')
"
```

