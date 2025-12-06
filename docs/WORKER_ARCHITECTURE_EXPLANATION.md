# 📊 Video Worker Architecture และการป้องกันการหยุดทำงาน

## 1. Video Worker คืออะไร?

**Video Worker** เป็น Worker หลักที่จัดการการประมวลผลทั้ง CPU และ GPU tasks:

### Architecture

```
Video Worker (Single Process)
├── Audio Extraction (CPU)
│   ├── ThreadPoolExecutor: 3 workers
│   ├── Queue: audio_extraction_queue
│   └── FFmpeg Process Semaphore: 3
│
└── Transcription (GPU)
    ├── ThreadPoolExecutor: 5 workers
    ├── Queue: transcription_queue
    └── GPU Concurrency Semaphore: 3 (ปรับเพิ่มจาก 1)
```

### สิ่งที่ Video Worker ทำ:

1. **Audio Extraction (CPU)**:
   - รับ messages จาก `audio_extraction_queue`
   - ใช้ ThreadPoolExecutor (3 workers) เพื่อ extract audio จาก video
   - ใช้ FFmpeg Process Semaphore (3) เพื่อจำกัด FFmpeg processes

2. **Transcription (GPU)**:
   - รับ messages จาก `transcription_queue`
   - ใช้ ThreadPoolExecutor (5 workers) เพื่อ transcribe audio
   - ใช้ GPU Concurrency Semaphore (3) เพื่อจำกัด concurrent GPU tasks

3. **ไม่แยกเป็น Worker แยกกัน**:
   - เป็น Worker เดียวที่จัดการทุกอย่าง
   - รับ message จาก RabbitMQ queues หลาย queue
   - แต่ละ queue มี consumer แยกกัน

## 2. GPU Concurrency Semaphore = 3

### การป้องกันงานชนกัน

✅ **GPU Semaphore ป้องกันงานชนกันอย่างสมบูรณ์**:
- ใช้ `threading.Semaphore(3)` เพื่อจำกัด concurrent GPU tasks
- แต่ละ task ต้อง `acquire()` semaphore ก่อนใช้งาน GPU
- เมื่อเสร็จแล้วต้อง `release()` semaphore
- ไม่มี race condition - semaphore จัดการให้

### ความเสี่ยง

⚠️ **CUDA OOM (Out of Memory)**:
- RTX 4080 Super 16GB VRAM
- Medium model (~2.4GB): 3 instances = 7.2GB < 16GB ✅
- Large model (~3GB): 3 instances = 9GB < 16GB (แต่ต้องเผื่อ memory อื่นๆ) ⚠️

### แนวทางที่แนะนำ

1. **ทดลองทีละขั้น**: เริ่มจาก 2 แล้วค่อยเพิ่มเป็น 3
2. **Monitor GPU memory**: ใช้ `nvidia-smi`
3. **ลด batch_size** ถ้าเกิด CUDA OOM

## 3. การป้องกันไม่ให้หยุดทำงาน

### ปัญหาที่พบ

- RabbitMQ connection error: `StreamLostError`
- Connection หลุด → Worker crash → ไม่มี consumer

### วิธีแก้ไข

#### วิธีที่ 1: Auto-restart Script (ปัจจุบัน)

```bash
# Script ที่ตรวจสอบและ restart อัตโนมัติ
bash scripts/pod/restart-service-daemon.sh
```

**ข้อเสีย**: ต้องรัน script เองหรือตั้ง cron job

#### วิธีที่ 2: Systemd Service (แนะนำสำหรับ Production)

สร้าง systemd service file:

```ini
[Unit]
Description=Transcription Video Worker
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/workspace/transcription-service
ExecStart=/usr/bin/python3 -m app.workers.video_worker
Restart=always
RestartSec=10
StandardOutput=append:/tmp/video-worker.log
StandardError=append:/tmp/video-worker.log

[Install]
WantedBy=multi-user.target
```

**ข้อดี**:
- Auto-restart เมื่อ crash
- Auto-start เมื่อ boot
- จัดการโดย systemd

#### วิธีที่ 3: Queue-based Wake-up

**แนวคิด**: Worker รันแบบ "ปลุกตื่น" เมื่อมี Task Queue

**การทำงาน**:
1. Worker เชื่อมต่อ RabbitMQ เมื่อมี message
2. Worker ปิด connection เมื่อไม่มี message นาน
3. Worker ตื่นขึ้นเมื่อมี message ใหม่

**ข้อเสีย**:
- RabbitMQ consumer ทำงานแบบ persistent connection อยู่แล้ว
- ไม่จำเป็นต้องทำแบบนี้

#### วิธีที่ 4: ปรับปรุง Connection Retry Logic (แนะนำ)

ใน `video_worker.py` มี retry logic อยู่แล้ว แต่สามารถปรับปรุงได้:

- เพิ่ม infinite retry loop
- เพิ่ม exponential backoff
- เพิ่ม connection health check

### แนวทางที่แนะนำ

1. **ปรับปรุง Connection Retry Logic**: เพิ่ม infinite retry loop
2. **ใช้ Systemd Service**: สำหรับ auto-restart
3. **Monitor Worker Health**: ตรวจสอบ worker status เป็นระยะ

## 4. Configuration

### Environment Variables

```bash
# GPU Concurrency
GPU_CONCURRENCY=3  # เพิ่มจาก 1 เป็น 3

# Audio Extraction (CPU)
AUDIO_EXTRACTION_MAX_WORKERS=3
FFMPEG_PROC_SEM=3

# Transcription (GPU)
TRANSCRIPTION_MAX_WORKERS=5
TRANSCRIPTION_PREFETCH_COUNT=5

# RabbitMQ
RABBITMQ_HEARTBEAT_TIMEOUT=1800  # 30 นาที
RABBITMQ_BLOCKED_TIMEOUT=600     # 10 นาที
```

### Queue Configuration

```
transcription_request_queue: Max 50 messages
audio_extraction_queue: Max 80 messages (CPU processing)
transcription_queue: Max 20 messages (GPU processing)
```

## 5. สรุป

1. ✅ **GPU Semaphore = 3**: ทำได้ งานไม่ชนกัน (semaphore ป้องกัน)
2. ✅ **Video Worker**: Worker หลักที่จัดการทั้ง CPU และ GPU
3. ✅ **ป้องกันการหยุดทำงาน**: ใช้ systemd service หรือปรับปรุง retry logic

