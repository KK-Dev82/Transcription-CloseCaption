# 🤔 ทำไมต้องติดตั้ง FFmpeg และ Media Processor ช่วยอะไรได้บ้าง?

## 📋 สรุป

### ทำไม Transcription Service ต้องใช้ FFmpeg?

Transcription Service ใช้ FFmpeg เพื่อ:

1. **Extract Audio จาก Video Files**
   - วิดีโอที่อัปโหลดมา (MP4, AVI, MOV, etc.) ต้องแปลงเป็น audio ก่อน
   - Whisper model ต้องการ audio input (WAV, MP3, etc.)

2. **สร้าง Audio Chunks**
   - แบ่งวิดีโอเป็น chunks (30 วินาทีต่อ chunk)
   - แต่ละ chunk ถูกประมวลผลแบบ parallel เพื่อเพิ่มความเร็ว

3. **ตรวจสอบ Video Metadata**
   - Duration, bitrate, codec, etc.
   - ใช้ในการคำนวณจำนวน chunks และจัดการ resources

### ปัญหาของการติดตั้ง FFmpeg ใน Container

1. **ขนาด Container ใหญ่ขึ้น**
   - FFmpeg + dependencies ≈ 100-200MB
   - ทำให้ build/deploy ช้าลง

2. **Resource Usage**
   - FFmpeg ใช้ CPU และ Memory มาก
   - แย่ง resources กับ Whisper transcription

3. **Maintenance Overhead**
   - ต้องติดตั้งและอัปเดต FFmpeg ในทุก container
   - Version conflicts

## 🚀 วิธีแก้: ใช้ Media Processor Service

### Media Processor Service คืออะไร?

Media Processor Service เป็น dedicated service สำหรับ video/audio processing:

- **AudioExtractor.cs**: Extract audio จาก video files
- **VideoTrimmer.cs**: ตัดวิดีโอตามช่วงเวลา
- **VideoMerger.cs**: รวมวิดีโอหลายไฟล์
- **RabbitMQ Integration**: รับงานผ่าน message queue

### ข้อดีของการใช้ Media Processor

#### 1. **ลด Network Overhead** ⚡

**Flow เดิม (ใช้ FFmpeg ใน Transcription Service):**
```
Video File → Transcription Service → FFmpeg Extract → Audio Chunks → Whisper
```
- ไฟล์ต้องอยู่ใน Transcription Service container

**Flow ใหม่ (ใช้ Media Processor):**
```
Video File → Media Processor → Extract Audio → Transcription Service → Whisper
```
- ใช้ RabbitMQ ส่งงาน (ไม่ต้องส่งไฟล์)
- Direct file access (ถ้าใช้ shared storage)

#### 2. **แยก Responsibility** 🎯

- **Transcription Service**: Focus on transcription เท่านั้น
- **Media Processor**: Focus on video/audio processing
- **Scalability**: Scale แต่ละ service แยกกัน

#### 3. **Performance** 🚀

**Direct File Access:**
```
Media Processor → อ่านไฟล์โดยตรงจาก Storage → Process → เขียนผลลัพธ์
```
- ไม่ต้อง download/upload ผ่าน network
- เร็วกว่า 10-100 เท่า

**Network Transfer Comparison:**
- **เดิม**: 4 ครั้ง (download → process → upload → download → process)
- **ใหม่**: 0 ครั้ง (direct file access)

#### 4. **Resource Optimization** 💪

- **Transcription Service**: ใช้ GPU สำหรับ Whisper
- **Media Processor**: ใช้ CPU สำหรับ FFmpeg
- ไม่แย่ง resources กัน

## 📊 Architecture Comparison

### Architecture เดิม

```
┌─────────────────────────────────┐
│   Transcription Service          │
│  ┌───────────────────────────┐  │
│  │ FFmpeg (Extract Audio)    │  │
│  │ Whisper (Transcription)   │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
         ▲
         │ Video File
         │
┌─────────┴─────────┐
│   File Service    │
└───────────────────┘
```

**ปัญหา:**
- Container ใหญ่ (FFmpeg + Whisper)
- Resource contention
- Network overhead

### Architecture ใหม่ (แนะนำ)

```
┌─────────────────────────────────┐
│   Transcription Service          │
│  ┌───────────────────────────┐  │
│  │ Whisper (Transcription)    │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
         ▲
         │ Audio Chunks (via RabbitMQ)
         │
┌─────────────────────────────────┐
│      RabbitMQ                    │
│  ┌───────────────────────────┐  │
│  │ media.audio.extract       │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
         ▲
         │ Request
         │
┌─────────────────────────────────┐
│   Media Processor Service        │
│  ┌───────────────────────────┐  │
│  │ AudioExtractor (FFmpeg)    │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
         ▲
         │ Direct File Access
         │
┌─────────┴─────────┐
│   File Service    │
└───────────────────┘
```

**ข้อดี:**
- แยก responsibility
- Direct file access (เร็วกว่า)
- Scale แยกกัน
- ไม่แย่ง resources

## 🔄 Migration Plan

### Step 1: ใช้ Media Processor สำหรับ Audio Extraction

**ปัจจุบัน:**
```python
# transcription_service.py
chunks = self.video_service.extract_audio_chunks(video_path, chunk_duration)
```

**ใหม่:**
```python
# ส่ง request ไปยัง Media Processor ผ่าน RabbitMQ
audio_chunks = await self.media_processor_client.extract_audio_chunks(
    video_path, 
    chunk_duration
)
```

### Step 2: Remove FFmpeg จาก Transcription Service

**Dockerfile:**
```dockerfile
# ลบ
# RUN apt-get install -y ffmpeg

# ลบ
# RUN pip install ffmpeg-python
```

**Requirements:**
```txt
# ลบ
# ffmpeg-python
```

### Step 3: Update File Service

**ปัจจุบัน:**
```python
import ffmpeg
probe = ffmpeg.probe(file_path)
```

**ใหม่:**
```python
# ใช้ Media Processor API หรือ RabbitMQ
metadata = await self.media_processor_client.get_video_metadata(file_path)
```

## 📝 Implementation Example

### 1. Media Processor Client

```python
# app/services/media_processor_client.py
import pika
import json

class MediaProcessorClient:
    def __init__(self, rabbitmq_host, rabbitmq_port):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=rabbitmq_host, port=rabbitmq_port)
        )
        self.channel = self.connection.channel()
    
    async def extract_audio_chunks(self, video_path: str, chunk_duration: int = 30):
        """ส่ง request ไปยัง Media Processor เพื่อ extract audio chunks"""
        message = {
            "video_path": video_path,
            "chunk_duration": chunk_duration,
            "output_format": "wav",
            "sample_rate": 16000
        }
        
        # ส่งไปยัง queue
        self.channel.basic_publish(
            exchange='media.exchange',
            routing_key='media.audio.extract.request',
            body=json.dumps(message)
        )
        
        # รอผลลัพธ์ (polling หรือ WebSocket)
        # ...
```

### 2. Update Transcription Service

```python
# app/services/transcription_service.py
class TranscriptionService:
    def __init__(self):
        # ลบ video_service.extract_audio_chunks()
        # เพิ่ม
        self.media_processor = MediaProcessorClient(...)
    
    async def _process_transcription(self, ...):
        # ใช้ Media Processor แทน
        chunks = await self.media_processor.extract_audio_chunks(
            video_path, 
            chunk_duration
        )
```

## ✅ สรุป

### ทำไมต้องติดตั้ง FFmpeg ใน Container?

**คำตอบ: ไม่จำเป็น!** ควรใช้ Media Processor Service แทน

### Media Processor ช่วยอะไรได้บ้าง?

1. **ลด Network Overhead**: Direct file access (เร็วกว่า 10-100 เท่า)
2. **แยก Responsibility**: Transcription Service focus on transcription
3. **Resource Optimization**: ไม่แย่ง resources กัน
4. **Scalability**: Scale แต่ละ service แยกกัน
5. **Maintenance**: FFmpeg อยู่ในที่เดียว (Media Processor)

### ขั้นตอนถัดไป

1. ✅ ใช้ Media Processor สำหรับ audio extraction
2. ✅ Remove FFmpeg จาก Transcription Service
3. ✅ Update Dockerfile และ requirements.txt
4. ✅ Test และ verify

## 📚 References

- [Media Processor Migration Guide](../../media-processor/MIGRATION_TO_MEDIAPROCESSOR.md)
- [Video Processing Architecture](../../media-processor/VIDEO_PROCESSING_ARCHITECTURE.md)
- [Audio Extractor Implementation](../../media-processor/MediaProcessor.Worker/AudioExtractor.cs)

