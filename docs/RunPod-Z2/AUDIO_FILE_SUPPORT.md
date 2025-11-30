# Audio File Support (Media Processor Integration)

## ภาพรวม

Transcription Service รองรับทั้ง **video files** และ **audio files** ที่ extract แล้วจาก Media Processor

## Flow การทำงาน

### Production Flow (Media Processor Extract Audio)

```
Backend C# → Media Processor (RabbitMQ)
  ↓
Media Processor:
  1. Download video จาก FileService
  2. Extract audio ด้วย FFmpeg (WAV 16kHz mono)
  3. Upload audio กลับไปยัง FileService
  4. Publish AudioExtractDoneMessage
  ↓
Backend C# → Transcription Service
  ↓
Transcription Service:
  - ตรวจสอบประเภทไฟล์ (audio/video)
  - ถ้าเป็น audio → ใช้ create_chunks() โดยตรง
  - ถ้าเป็น video → ใช้ extract_audio_chunks() (extract audio ก่อน)
```

### Direct Mode (RunPod/HP Z2)

```
Backend C# → Transcription Service (file_url)
  ↓
Transcription Service:
  - Download file จาก FileService
  - ตรวจสอบประเภทไฟล์ (audio/video)
  - ถ้าเป็น audio → ใช้ create_chunks() โดยตรง
  - ถ้าเป็น video → ใช้ extract_audio_chunks() (extract audio ก่อน)
  - Transcribe chunks ด้วย Whisper
```

## การตรวจสอบประเภทไฟล์

### Audio File Extensions
- `.wav` (WAV - Media Processor extract เป็น format นี้)
- `.mp3` (MP3)
- `.flac` (FLAC)
- `.aac` (AAC)
- `.ogg` (OGG)
- `.m4a` (M4A)

### Video File Extensions
- `.mp4` (MP4)
- `.avi` (AVI)
- `.mov` (MOV)
- `.mkv` (MKV)
- `.wmv` (WMV)
- `.flv` (FLV)
- `.webm` (WebM)

## การทำงานของ Transcription Service

### 1. Audio Files (ที่ extract แล้ว)

```python
# ตรวจสอบว่าเป็น audio file
if self.file_service.is_audio_file(local_file_path):
    # ใช้ create_chunks() โดยตรง (ไม่ต้อง extract audio)
    chunks = self.file_service.create_chunks(local_file_path, chunk_duration)
```

**ข้อดี:**
- ✅ ไม่ต้อง extract audio (ประหยัดเวลา)
- ✅ Audio file พร้อมใช้กับ Whisper (16kHz mono WAV)
- ✅ เร็วกว่า video files

### 2. Video Files

```python
# ตรวจสอบว่าเป็น video file
elif self.file_service.is_video_file(local_file_path):
    # ใช้ extract_audio_chunks() เพื่อ extract audio ก่อน
    chunks = self.video_service.extract_audio_chunks(local_file_path, chunk_duration)
```

**ข้อดี:**
- ✅ รองรับ video files ที่ยังไม่ได้ extract audio
- ✅ Extract audio chunks โดยอัตโนมัติ
- ✅ รองรับทั้ง video และ audio files

## Scripts ใน Pod Directory

### ไม่ต้องปรับ Scripts

**Scripts ที่ไม่ต้องปรับ:**
- ✅ `start-pod.sh` - ยังใช้ Direct Mode เหมือนเดิม
- ✅ `setup-pod.sh` - ยังใช้ Direct Mode เหมือนเดิม
- ✅ `stop-pod.sh` - ไม่ต้องปรับ
- ✅ `restart-pod.sh` - ไม่ต้องปรับ
- ✅ `check-pod.sh` - ไม่ต้องปรับ
- ✅ `logs-pod.sh` - ไม่ต้องปรับ
- ✅ `test-transcription.sh` - ไม่ต้องปรับ
- ✅ `result-view.sh` - ไม่ต้องปรับ
- ✅ `task-service.sh` - ไม่ต้องปรับ
- ✅ `download-tool.sh` - ไม่ต้องปรับ

**เหตุผล:**
- Direct Mode ยังใช้เหมือนเดิม
- Transcription Service code ถูกปรับให้รองรับทั้ง audio และ video files อัตโนมัติ
- Scripts ไม่ต้องรู้ว่าไฟล์เป็น audio หรือ video

## FFmpeg ใน Transcription Service

### ยังจำเป็นสำหรับ Video Files

**FFmpeg ใช้สำหรับ:**
- ✅ Extract audio chunks จาก video files
- ✅ Create audio chunks (ถ้าเป็น video file)
- ✅ Audio format conversion (ถ้าจำเป็น)

**ไม่จำเป็นสำหรับ Audio Files:**
- ❌ Audio files ที่ extract แล้วจาก Media Processor พร้อมใช้แล้ว
- ❌ ไม่ต้อง extract audio อีกครั้ง

## Performance Comparison

### Audio Files (Extract แล้ว)
- **Processing Time**: ~0.1-0.2x real-time (เร็วกว่า video)
- **Network Transfer**: น้อยกว่า (ไฟล์เล็กกว่า)
- **CPU Usage**: น้อยกว่า (ไม่ต้อง extract audio)

### Video Files
- **Processing Time**: ~0.3-0.5x real-time (ช้ากว่า audio)
- **Network Transfer**: มากกว่า (ไฟล์ใหญ่กว่า)
- **CPU Usage**: มากกว่า (ต้อง extract audio)

## ตัวอย่างการใช้งาน

### Production (Media Processor Extract Audio)

```bash
# Backend ส่ง audio file URL
POST /transcribe/
{
  "file_url": "http://file-service/api/files/{audio_file_id}",
  "file_name": "audio.wav",
  "language": "th",
  "model_size": "large-v3"
}

# Transcription Service:
# 1. Download audio file
# 2. ตรวจสอบว่าเป็น audio file (.wav)
# 3. ใช้ create_chunks() โดยตรง
# 4. Transcribe chunks
```

### Direct Mode (Video File)

```bash
# Backend ส่ง video file URL
POST /transcribe/
{
  "file_url": "http://file-service/api/files/{video_file_id}",
  "file_name": "video.mp4",
  "language": "th",
  "model_size": "large-v3"
}

# Transcription Service:
# 1. Download video file
# 2. ตรวจสอบว่าเป็น video file (.mp4)
# 3. ใช้ extract_audio_chunks() เพื่อ extract audio
# 4. Transcribe chunks
```

## สรุป

### ✅ สิ่งที่ปรับปรุง
1. **Transcription Service** - รองรับทั้ง audio และ video files
2. **File Detection** - ตรวจสอบประเภทไฟล์อัตโนมัติ
3. **Optimization** - ใช้วิธีที่เหมาะสมตามประเภทไฟล์

### ✅ สิ่งที่ไม่ต้องปรับ
1. **Scripts ใน Pod Directory** - ยังใช้ Direct Mode เหมือนเดิม
2. **FFmpeg** - ยังจำเป็นสำหรับ video files
3. **Direct Mode** - ยังใช้เหมือนเดิม

### 📝 หมายเหตุ
- Production ควรใช้ Media Processor extract audio ก่อนส่งไปยัง Transcription Service
- Direct Mode ยังรองรับ video files (สำหรับ testing)
- Transcription Service รองรับทั้ง audio และ video files อัตโนมัติ

