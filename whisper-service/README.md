# Whisper Service

Whisper.cpp API Service สำหรับแปลงเสียงเป็นข้อความ

## การใช้งาน

### Build Image
```bash
docker build -t whisper-service .
```

### รัน Service
```bash
docker run -p 8002:8002 whisper-service
```

### API Endpoints

- `GET /health` - ตรวจสอบสถานะ service
- `POST /transcribe` - แปลงเสียงเป็นข้อความ
- `GET /models` - แสดงรายการ models ที่มี

### ตัวอย่างการใช้งาน

```bash
# ตรวจสอบสถานะ
curl http://localhost:8002/health

# แปลงเสียง
curl -X POST http://localhost:8002/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "audio_path": "/app/audio/sample.wav",
    "language": "th",
    "model_size": "base",
    "output_format": "json"
  }'
```

## Volume Mounts

- `/app/audio` - โฟลเดอร์สำหรับไฟล์เสียง (จาก API container)
- `/app/temp` - โฟลเดอร์สำหรับไฟล์ชั่วคราว (audio chunks จาก API)
- `/app/models` - โฟลเดอร์สำหรับ models
- `/app/output` - โฟลเดอร์สำหรับผลลัพธ์

## หมายเหตุ

Whisper Container นี้ทำหน้าที่เฉพาะ transcription เท่านั้น:
- รับไฟล์ audio (.wav, .mp3) จาก API container
- ไม่ทำ video processing
- ไม่มี ffmpeg
- เน้นแค่การแปลงเสียงเป็นข้อความ 