# 🛠️ Development Strategy: FFmpeg vs Media Processor

## 📋 สรุป

### สำหรับการ Development

**✅ ใช้ FFmpeg ติดตั้งใน Transcription Service Container**

**เหตุผล:**
1. **ง่ายต่อการพัฒนา**: ไม่ต้อง setup Media Processor Service
2. **เร็วในการทดสอบ**: ทดสอบ transcription ได้ทันที
3. **ตรวจสอบเป้าหมาย**: ตรวจสอบว่า transcription ทำงานได้ตามเป้าหมาย
4. **ลดความซับซ้อน**: Focus on transcription logic ก่อน

### สำหรับการ Production

**✅ ใช้ Media Processor Service**

**เหตุผล:**
1. **Performance**: Direct file access (เร็วกว่า 10-100 เท่า)
2. **Scalability**: Scale แยกกันได้
3. **Resource Optimization**: ไม่แย่ง resources
4. **Maintainability**: แยก responsibility

## 🔄 Development Workflow

### Phase 1: Development (ปัจจุบัน)

```
┌─────────────────────────────────┐
│   Transcription Service          │
│  ┌───────────────────────────┐  │
│  │ FFmpeg (Extract Audio)    │  │ ← ติดตั้งไว้ก่อน
│  │ Whisper (Transcription)   │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

**สิ่งที่ต้องทำ:**
1. ✅ ติดตั้ง `ffmpeg` และ `ffmpeg-python` ใน container
2. ✅ ทดสอบ transcription กับวิดีโอทั้ง 3 ตัว
3. ✅ ตรวจสอบว่า transcription ทำงานได้ตามเป้าหมาย:
   - v05-1.mp4: ~1 วินาที
   - v10-1.mp4: 60-120 วินาที
   - v60-1.mp4: 600-700 วินาที
4. ✅ Optimize GPU performance
5. ✅ Verify parallel processing

### Phase 2: Migration (ภายหลัง)

```
┌─────────────────────────────────┐
│   Transcription Service          │
│  ┌───────────────────────────┐  │
│  │ Whisper (Transcription)    │  │ ← ลบ FFmpeg
│  └───────────────────────────┘  │
└─────────────────────────────────┘
         ▲
         │ Audio Chunks (via RabbitMQ)
         │
┌─────────────────────────────────┐
│   Media Processor Service        │
│  ┌───────────────────────────┐  │
│  │ AudioExtractor (FFmpeg)   │  │ ← ย้าย FFmpeg มาที่นี่
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

**สิ่งที่ต้องทำ:**
1. ✅ Integrate Media Processor Service
2. ✅ Update Transcription Service เพื่อใช้ Media Processor
3. ✅ Remove FFmpeg จาก Transcription Service
4. ✅ Test และ verify

## 📝 Current Setup (Development)

### Dockerfile

```dockerfile
# ติดตั้ง FFmpeg สำหรับ Development
RUN apt-get update && apt-get install -y ffmpeg

# ติดตั้ง Python dependencies
RUN pip install ffmpeg-python
```

### Requirements.txt

```txt
# สำหรับ Development
ffmpeg-python
```

### Setup Script

```bash
# scripts/pod/setup-pod.sh
# ติดตั้ง FFmpeg
apt-get install -y ffmpeg

# ติดตั้ง Python dependencies
pip3 install ffmpeg-python
```

## ✅ Checklist

### Development Phase

- [x] ติดตั้ง FFmpeg ใน container
- [x] ติดตั้ง `ffmpeg-python`
- [ ] ทดสอบ transcription กับ v05-1.mp4 (~1s)
- [ ] ทดสอบ transcription กับ v10-1.mp4 (60-120s)
- [ ] ทดสอบ transcription กับ v60-1.mp4 (600-700s)
- [ ] Optimize GPU performance
- [ ] Verify parallel processing
- [ ] ตรวจสอบว่า transcription ทำงานได้ตามเป้าหมาย

### Production Migration (ภายหลัง)

- [ ] Setup Media Processor Service
- [ ] Integrate Media Processor Client
- [ ] Update Transcription Service
- [ ] Remove FFmpeg จาก Transcription Service
- [ ] Test และ verify
- [ ] Deploy

## 🎯 เป้าหมาย

### Development Phase

**เป้าหมายหลัก:**
1. ✅ Transcription ทำงานได้
2. ✅ ตรวจสอบ performance ตามเป้าหมาย
3. ✅ Optimize GPU utilization
4. ✅ Verify parallel processing

**ไม่ต้องกังวล:**
- Network overhead (ยังไม่ใช่ production)
- Container size (ยังไม่ใช่ production)
- Resource optimization (ยังไม่ใช่ production)

### Production Phase

**เป้าหมายหลัก:**
1. ✅ Performance optimization
2. ✅ Scalability
3. ✅ Resource optimization
4. ✅ Maintainability

## 📚 References

- [Why FFmpeg and Media Processor](./WHY_FFMPEG_AND_MEDIA_PROCESSOR.md)
- [Media Processor Migration](../../media-processor/MIGRATION_TO_MEDIAPROCESSOR.md)

