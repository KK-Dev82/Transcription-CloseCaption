# 🔧 แผนปรับปรุงให้รองรับ Production

**วันที่**: 2025-12-05

## 📋 สรุปการปรับปรุงที่ต้องทำ

### 1. GPU Semaphore = 2 ✅ (เสร็จแล้ว)
- **เปลี่ยนจาก**: GPU_CONCURRENCY=3
- **เป็น**: GPU_CONCURRENCY=2
- **เหตุผล**: เพื่อความเสถียรมากขึ้น ลดความเสี่ยง CUDA OOM
- **ผลลัพธ์**: 
  - Medium model: 2 instances = 4.8GB < 16GB ✅
  - Large model: 2 instances = 6GB < 16GB ✅

### 2. ปรับปรุง Pika Thread Safety

#### ปัญหาที่พบ:
- `IndexError: pop from an empty deque` ใน Pika library (version 1.3.2)
- เกิดจากหลาย threads ใช้ connection พร้อมกัน
- Thread safety issue ใน Pika BlockingConnection

#### การแก้ไขที่ต้องทำ:

**2.1 เพิ่ม Thread Lock สำหรับ Publish Channel**
- เพิ่ม `self._publish_channel_lock = threading.Lock()`
- ใช้ lock ใน `_get_publish_channel()` และ `_connect_publish_channel()`
- ป้องกัน concurrent access ที่ทำให้เกิด IndexError

**2.2 สร้าง Safe Publish Method**
- สร้าง `_safe_publish()` method ที่มี retry logic
- ใช้ thread lock เพื่อความปลอดภัย
- Handle errors gracefully

**2.3 ปรับปรุง Connection Management**
- เพิ่ม connection validation
- ปรับปรุง reconnect logic
- เพิ่ม connection health checks

### 3. Infinite Retry Loop ✅ (เสร็จแล้ว)
- Worker จะไม่ exit เมื่อเกิด error
- จะ restart อัตโนมัติเมื่อ crash
- Infinite retry สำหรับ RabbitMQ connection

### 4. Systemd Service ✅ (เสร็จแล้ว)
- Auto-restart เมื่อ crash
- Auto-start เมื่อ boot
- Logging ผ่าน journalctl

## 🎯 Priority

### Phase 1: Thread Safety (ทำทันที - Critical)
1. ✅ เพิ่ม thread lock สำหรับ publish channel operations
2. ✅ สร้าง safe publish method
3. ✅ ปรับปรุง connection management

### Phase 2: Monitoring (1-2 สัปดาห์ - High)
1. Worker health check endpoint
2. Connection status monitoring
3. Queue status monitoring

### Phase 3: Error Handling (1-2 สัปดาห์ - High)
1. Circuit breaker pattern
2. Graceful degradation
3. Better retry mechanisms

### Phase 4: Alternative Solutions (1 เดือน - Medium)
1. พิจารณาใช้ aio-pika (async RabbitMQ client)
2. หรือใช้ kombu (high-level messaging library)
3. หรือ migrate ไป Celery

## 📊 Configuration สำหรับ Production

```bash
# GPU Concurrency (ปรับเป็น 2 เพื่อความเสถียร)
GPU_CONCURRENCY=2

# RabbitMQ Connection
RABBITMQ_HEARTBEAT_TIMEOUT=1800  # 30 นาที
RABBITMQ_BLOCKED_TIMEOUT=600     # 10 นาที
RABBITMQ_CONNECTION_CHECK_INTERVAL=30

# Queue Configuration
MAX_QUEUE_REQUEST=50
MAX_QUEUE_EXTRACTION=80
MAX_QUEUE_TRANSCRIBE=20

# Workers
TRANSCRIPTION_MAX_WORKERS=5
AUDIO_EXTRACTION_MAX_WORKERS=3
FFMPEG_PROC_SEM=3
```

## 🔍 สาเหตุปัญหาหลัก

1. **Pika Thread Safety Issue**: 
   - หลาย threads ใช้ connection พร้อมกัน
   - Buffer conflict → IndexError → StreamLostError

2. **Worker Exit เมื่อ Error**:
   - ไม่มี infinite retry loop
   - Worker หยุดทำงานถาวร

## ✅ วิธีแก้ไขที่ทำแล้ว

1. ✅ Infinite retry loop ใน `main()` และ `run()`
2. ✅ Systemd service สำหรับ auto-restart
3. ✅ GPU_CONCURRENCY=2

## 📋 สิ่งที่ต้องทำต่อ

1. เพิ่ม thread lock สำหรับ publish operations
2. สร้าง safe publish method
3. ปรับปรุง connection management
4. เพิ่ม health checks
5. Monitor และ alerting

## 💡 คำแนะนำ

- ใช้ GPU_CONCURRENCY=2 เพื่อความเสถียร
- ใช้ systemd service สำหรับ auto-restart
- Monitor worker logs และ queue status
- ทดสอบกับ workload จริงก่อน deploy
