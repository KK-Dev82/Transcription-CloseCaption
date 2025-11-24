# 🔄 แก้ไขปัญหา Infinite Chunk Creation

## 🐛 ปัญหา

จาก logs บน Staging:
- Transcription สร้างไฟล์ chunks ไม่หยุด (chunk 236, 237, 238, ... ไปเรื่อยๆ)
- Restart แล้วก็กลับมา
- สร้าง chunks ทุก 30 วินาที (5875s-5905s, 5900s-5930s, etc.)

## 🔍 สาเหตุที่เป็นไปได้

### 1. **Loop ใน `extract_audio_chunks` ไม่หยุด**

**ปัญหา:**
```python
# app/services/video_service.py:662-695
while start_time < duration:
    end_time = min(start_time + chunk_duration, duration)
    # ... สร้าง chunk ...
    start_time = end_time - overlap  # ⚠️ ถ้า overlap >= chunk_duration จะไม่เพิ่มขึ้น
    i += 1
    if start_time + chunk_duration >= duration:
        break
```

**สาเหตุ:**
- ถ้า `overlap >= chunk_duration` → `start_time` จะไม่เพิ่มขึ้น → infinite loop
- ถ้า `duration` ผิดพลาด (เช่น NaN หรือ infinity) → loop ไม่หยุด
- ถ้า `end_time - overlap` <= `start_time` → loop ไม่หยุด

### 2. **RabbitMQ Messages ค้างอยู่**

**ปัญหา:**
- Messages ไม่ถูก acknowledge → requeue ซ้ำๆ
- Duplicate messages จาก RabbitMQ
- Messages ถูกส่งซ้ำจาก Hangfire

### 3. **Hangfire Recurring Jobs**

**ปัญหา:**
- `TranscriptionCleanupJob` รันทุกชั่วโมง → อาจส่ง tasks ซ้ำ
- Tasks ไม่ถูก mark เป็น completed → ส่งใหม่

## ✅ วิธีแก้ไข

### Fix 1: เพิ่ม Safety Check ใน `extract_audio_chunks`

```python
# app/services/video_service.py
def extract_audio_chunks(self, video_path: str, chunk_duration: int = 30, 
                       overlap: int = 5, audio_format: str = "wav", 
                       sample_rate: int = 16000) -> List[str]:
    # ... existing code ...
    
    # สร้าง chunks พร้อม overlap
    start_time = 0
    i = 0
    max_chunks = int(duration / (chunk_duration - overlap)) + 10  # Safety limit
    previous_start_time = -1  # Track previous start_time
    
    while start_time < duration and i < max_chunks:
        # Safety check: ถ้า start_time ไม่เพิ่มขึ้น → break
        if start_time <= previous_start_time:
            logger.warning(f"start_time ไม่เพิ่มขึ้น ({start_time} <= {previous_start_time}), หยุด loop")
            break
        
        previous_start_time = start_time
        end_time = min(start_time + chunk_duration, duration)
        
        # ... สร้าง chunk ...
        
        # เลื่อนไปยัง chunk ถัดไป (ลบ overlap)
        new_start_time = end_time - overlap
        
        # Safety check: ถ้า new_start_time <= start_time → break
        if new_start_time <= start_time:
            logger.warning(f"new_start_time ({new_start_time}) <= start_time ({start_time}), หยุด loop")
            break
        
        start_time = new_start_time
        i += 1
        
        # หยุดถ้าเหลือน้อยกว่า chunk_duration
        if start_time + chunk_duration >= duration:
            break
    
    logger.info(f"สร้าง audio chunks สำเร็จ: {len(chunk_paths)} chunks")
    return chunk_paths
```

### Fix 2: ตรวจสอบ RabbitMQ Queue

```bash
# บน Staging server
# ตรวจสอบ messages ใน queue
docker exec -it rabbitmq rabbitmqctl list_queues name messages

# ตรวจสอบ transcription_queue
docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription

# Purge queue (ถ้าจำเป็น)
docker exec -it rabbitmq rabbitmqctl purge_queue transcription_queue
```

### Fix 3: ตรวจสอบ Hangfire Jobs

```bash
# เข้า Hangfire Dashboard
# URL: http://10.200.22.61:5173/hangfire

# ตรวจสอบ:
# 1. Recurring Jobs → transcription-cleanup
# 2. Processing Jobs → ดูว่ามี jobs ที่ค้างอยู่หรือไม่
# 3. Succeeded/Failed Jobs → ดูว่ามี jobs ที่ส่งซ้ำหรือไม่
```

## 🔧 Quick Fix (ด่วน)

### 1. Purge RabbitMQ Queue

```bash
# บน Staging server
docker exec -it rabbitmq rabbitmqctl purge_queue transcription_queue
```

### 2. Restart Workers

```bash
docker-compose -f docker-compose.staging.yml restart video-worker-1 video-worker-2
```

### 3. ตรวจสอบ Tasks ที่ค้างอยู่

```bash
# ตรวจสอบ tasks ใน JSON storage
docker exec -it video-worker-1 ls -la /app/storage/transcriptions/

# ตรวจสอบ tasks ที่ status = "processing"
docker exec -it video-worker-1 grep -r "processing" /app/storage/transcriptions/

# ตรวจสอบ tasks ที่ status = "completed"
docker exec -it video-worker-1 grep -r "completed" /app/storage/transcriptions/ | wc -l
```

### 4. ตรวจสอบสถานะหลัง Restart

```bash
# ตรวจสอบ RabbitMQ Queue (ดูว่ายังมี messages ค้างอยู่หรือไม่)
docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep -E 'transcription|audio'

# ตรวจสอบ Logs ล่าสุด (ดูว่ายังสร้าง chunks ไม่หยุดหรือไม่)
docker logs video-worker-1 --tail 100 | grep -E 'chunk|transcription' | tail -20

# ตรวจสอบว่ามี tasks ใหม่ถูกสร้างหลัง restart หรือไม่
docker exec -it video-worker-1 ls -lt /app/storage/transcriptions/ | head -10
```

### 5. ตรวจสอบ Infinite Loop

```bash
# ตรวจสอบ logs ว่ามี chunk numbers ที่เพิ่มขึ้นเรื่อยๆ หรือไม่
docker logs video-worker-1 --tail 200 | grep "สร้าง audio chunk" | tail -30

# ถ้าเห็น chunk numbers เพิ่มขึ้นเรื่อยๆ (236, 237, 238, ...) → ยังมีปัญหา
# ถ้าเห็น chunk numbers หยุดที่จำนวนที่เหมาะสม → ปกติ
```

## 📋 Checklist

- [ ] เพิ่ม safety check ใน `extract_audio_chunks`
- [ ] Purge RabbitMQ queue
- [ ] ตรวจสอบ Hangfire jobs
- [ ] Restart workers
- [ ] ตรวจสอบ logs ว่าไม่มี infinite loop

