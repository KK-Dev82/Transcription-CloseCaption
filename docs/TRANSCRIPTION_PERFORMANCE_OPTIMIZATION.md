# 🚀 Transcription Performance Optimization

## 📋 สรุปปัญหา

### ปัญหาที่พบ
1. **Workers ทำงานทีละตัว**: `prefetch_count=1` ทำให้แต่ละ worker รับงานได้ทีละ 1
2. **Blocking processing**: ใช้ `asyncio.run()` ทำให้ worker ไม่รับงานใหม่จนกว่าจะเสร็จ
3. **Whisper service bottleneck**: resources ไม่เพียงพอ (2G RAM, 1.0 CPU)
4. **วิดีโอ 5 วินาที ใช้เวลา 284 วินาที** (นานเกินไป)
5. **Hangfire ส่ง jobs พร้อมกันมากเกินไป**: ทำให้ Transcription Service API overload

## ✅ การแก้ไข

### 1. เพิ่ม Prefetch Count ใน RabbitMQ Consumer

**ไฟล์**: `app/workers/video_worker.py`

```python
# เปลี่ยนจาก prefetch_count=1 → prefetch_count=2
self.channel.basic_qos(prefetch_count=2)
```

**ผลลัพธ์**:
- แต่ละ worker รับงานได้ 2 งานพร้อมกัน
- เมื่อมี 2 workers → ประมวลผลได้ 4 งานพร้อมกัน

### 2. เปลี่ยนเป็น Non-blocking Processing

**ไฟล์**: `app/workers/video_worker.py`

```python
def _process_transcription_task(self, ch, method, properties, body):
    """ประมวลผล transcription task - ใช้ threading เพื่อให้ worker รับงานใหม่ได้ทันที"""
    import threading
    
    def process_in_thread():
        # ... processing code ...
    
    # เริ่มประมวลผลใน thread แยก เพื่อให้ worker รับงานใหม่ได้ทันที
    thread = threading.Thread(target=process_in_thread, daemon=True)
    thread.start()
```

**ผลลัพธ์**:
- Worker รับงานใหม่ได้ทันที (ไม่ต้องรอให้งานเก่าเสร็จ)
- เพิ่ม throughput ของ workers

### 3. เพิ่ม Resources ให้ Whisper Service

**ไฟล์**: `docker-compose.staging.yml`

```yaml
whisper:
  deploy:
    resources:
      limits:
        memory: 2.5G  # เพิ่มจาก 2G → 2.5G
        cpus: '1.4'   # เพิ่มจาก 1.0 → 1.4
```

**ผลลัพธ์**:
- Whisper service รองรับ concurrent requests ได้ดีขึ้น
- ลดเวลา transcription

### 4. ปรับปรุง Whisper API

**ไฟล์**: `whisper-service/whisper_api.py`

- เปลี่ยนจาก blocking `subprocess.run()` → async `asyncio.create_subprocess_exec()`
- เพิ่ม timeout: 300s → 600s
- เพิ่ม uvicorn workers: 1 → 2

**ผลลัพธ์**:
- Whisper API รองรับ concurrent requests ได้ดีขึ้น
- ไม่ block event loop

### 5. จำกัด Hangfire Worker Count

**ไฟล์**: `senate-backend/src/Shorthand.Api/Program.cs`

```csharp
services.AddHangfireServer(options =>
{
    // จำกัด worker threads เพื่อไม่ให้ส่ง requests ไปยัง Transcription Service มากเกินไป
    options.WorkerCount = 2; // จำกัด concurrent transcription jobs เป็น 2
});
```

**ผลลัพธ์**:
- Hangfire ส่ง jobs ไปยัง Transcription Service ไม่เกิน 2 jobs พร้อมกัน
- สอดคล้องกับ transcription workers (2 workers × prefetch_count=2 = 4 concurrent tasks)
- ลด load บน Transcription Service API

## 📊 Architecture Flow

```
Backend (Hangfire)
    ↓ (WorkerCount=2, max 2 concurrent jobs)
Transcription Service API (/transcribe/)
    ↓ (ส่ง tasks ไปยัง RabbitMQ queue)
RabbitMQ Queue (transcription_queue)
    ↓ (prefetch_count=2, 2 workers)
Workers (video-worker-1, video-worker-2)
    ↓ (แต่ละ worker รับงานได้ 2 งานพร้อมกัน)
Whisper Service (2 workers, 2.5G RAM, 1.4 CPU)
    ↓
Transcription Results
```

## 🎯 ผลลัพธ์ที่คาดหวัง

1. **Workers ทำงานพร้อมกัน**: 2 workers × 2 prefetch = 4 งานพร้อมกัน
2. **ลดเวลา waiting**: workers รับงานใหม่ได้ทันที
3. **เพิ่ม throughput**: Whisper service รองรับ concurrent requests ได้ดีขึ้น
4. **ลดเวลา transcription**: ใช้ async processing และเพิ่ม resources
5. **ไม่ให้คิวชนกัน**: Hangfire จำกัด concurrent jobs ให้สอดคล้องกับ workers

## 📝 หมายเหตุ

### Monitoring
หลัง deploy ควร monitor:
- CPU และ Memory usage
- Queue length ใน RabbitMQ
- Transcription duration
- Hangfire job queue length

### การปรับแต่งเพิ่มเติม
ถ้ายังช้า อาจต้อง:
- เพิ่ม workers เป็น 3
- เพิ่ม Whisper service instance
- ปรับ prefetch_count ตาม workload
- เพิ่ม Hangfire WorkerCount (ถ้า resources เพียงพอ)

### Resource Allocation

**Total Resources (Server: 4 cores, 7.75GB RAM)**:
- API: 1G RAM, 0.6 CPU
- Worker 1: 3G RAM, 1.2 CPU
- Worker 2: 3G RAM, 1.2 CPU
- Whisper: 2.5G RAM, 1.4 CPU
- Redis: 0.5G RAM, 0.1 CPU
- **Total**: 7.5G RAM, 3.8 CPU (เหลือ 0.25G RAM, 0.2 CPU สำหรับ OS)

## 🔄 Deployment Steps

1. **Deploy Transcription Service**:
   ```bash
   cd transcription-close-caption-service
   docker-compose -f docker-compose.staging.yml up -d --build
   ```

2. **Deploy Backend**:
   ```bash
   cd senate-backend
   # Build และ deploy ตามปกติ
   ```

3. **Monitor**:
   - ตรวจสอบ RabbitMQ queue length
   - ตรวจสอบ Hangfire dashboard
   - ตรวจสอบ transcription duration

## ✅ Checklist

- [x] เพิ่ม prefetch_count ใน RabbitMQ consumer
- [x] เปลี่ยนเป็น non-blocking processing
- [x] เพิ่ม resources ให้ Whisper service
- [x] ปรับปรุง Whisper API
- [x] จำกัด Hangfire WorkerCount
- [ ] Deploy และ monitor
- [ ] ปรับแต่งเพิ่มเติมตามผลลัพธ์


