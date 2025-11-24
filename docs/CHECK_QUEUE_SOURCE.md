# 🔍 ตรวจสอบ Source ของ Messages

## ✅ สรุปสถานะ

1. **Loop หยุดแล้ว** ✅
   - "สร้าง audio chunks สำเร็จ: 366 chunks" 
   - 366 chunks สำหรับวิดีโอ ~2.5 ชั่วโมง = ปกติ

2. **มี Hangfire Jobs สำหรับ Real-time Close Caption** ✅
   - `ChunkedAudioExtractor` - Extract audio chunks ทุก 3-5 วินาที
   - Publish RabbitMQ: `media.audio.chunk.extracted`
   - Video worker consume messages จาก `media.audio.chunk.extracted` queue

3. **Timeout Issues** ⚠️
   - Whisper service timeout (read timeout=300 = 5 นาที)
   - แก้ไขแล้ว (เพิ่มเป็น 600 วินาที) แต่ยังไม่ได้ deploy

## 🔍 ตรวจสอบว่า Messages มาจาก Queue ไหน

### Step 1: ตรวจสอบ RabbitMQ Queues

```bash
# บน Staging server
# ตรวจสอบ queues ทั้งหมด
docker exec -it rabbitmq rabbitmqctl list_queues name messages consumers

# ตรวจสอบเฉพาะ transcription และ audio queues
docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep -E 'transcription|audio'
```

**Queues ที่เกี่ยวข้อง:**
- `transcription_queue` - Normal transcription tasks
- `media.audio.chunk.extracted` - Real-time close caption audio chunks

### Step 2: ดู Message Content

```bash
# ดู message content จาก transcription_queue
docker exec -it rabbitmq rabbitmqadmin get queue=transcription_queue count=2 ackmode=ack_requeue_false

# ดู message content จาก media.audio.chunk.extracted
docker exec -it rabbitmq rabbitmqadmin get queue=media.audio.chunk.extracted count=2 ackmode=ack_requeue_false
```

**สิ่งที่ต้องดู:**
- `task_id` / `chunkId` - ว่าเป็น task/chunk เดียวกันหรือไม่
- `job_id` / `meetingId` - ว่าเป็น job/meeting เดียวกันหรือไม่
- `file_url` / `audioFileUrl` - ว่าเป็นไฟล์เดียวกันหรือไม่
- `created_at` / `createdAt` - ว่า messages ถูกสร้างเมื่อไหร่

### Step 3: ตรวจสอบ Hangfire Jobs

```bash
# เข้า Hangfire Dashboard
# URL: http://10.200.22.61:5173/hangfire

# ตรวจสอบ:
# 1. Recurring Jobs → ดูว่ามี jobs ที่ส่ง audio chunk extraction หรือไม่
# 2. Processing Jobs → ดูว่ามี jobs ที่ค้างอยู่หรือไม่
# 3. Succeeded/Failed Jobs → ดูว่ามี jobs ที่ fail แล้วถูก retry หรือไม่
```

### Step 4: ตรวจสอบ Backend Logs

```bash
# ตรวจสอบ backend logs ว่ามีการส่ง audio chunk extraction หรือไม่
docker logs transcription-api --tail 500 | grep -E "ChunkedAudioExtractor|audio.chunk.extracted|StartChunkedAudioExtraction"

# ตรวจสอบว่ามีการเรียก transcription API หรือไม่
docker logs transcription-api --tail 500 | grep -E "transcription|ProcessTranscriptionAsync"
```

### Step 5: ตรวจสอบว่ามีคนใช้งานจริงๆ หรือไม่

```bash
# ตรวจสอบ database ว่ามี meetings ที่กำลัง record อยู่หรือไม่
# ตรวจสอบ TranscriptionJobs table ว่ามี jobs ใหม่ถูกสร้างหรือไม่
# ตรวจสอบ CloseCaptionSegments table ว่ามี segments ใหม่ถูกสร้างหรือไม่
```

## 🔧 วิธีแก้ไขตามสาเหตุ

### สาเหตุ 1: Real-time Close Caption (ปกติ)

**ถ้า messages มาจาก `media.audio.chunk.extracted`:**
- นี่คือปกติ! มีคนใช้งาน real-time close caption
- `ChunkedAudioExtractor` extract audio chunks ทุก 3-5 วินาที
- Video worker consume และ transcribe chunks

**ไม่ต้องแก้ไข** - นี่คือการใช้งานปกติ

### สาเหตุ 2: Normal Transcription (ปกติ)

**ถ้า messages มาจาก `transcription_queue`:**
- มีคนใช้งาน normal transcription
- Backend ส่ง transcription requests

**ไม่ต้องแก้ไข** - นี่คือการใช้งานปกติ

### สาเหตุ 3: Timeout Issues (ต้องแก้ไข)

**Whisper service timeout:**
- แก้ไขแล้ว (เพิ่ม timeout เป็น 600 วินาที)
- ต้อง build และ deploy image ใหม่

**แก้ไข:**
```bash
# Build และ push Docker image ใหม่
cd /Users/athip-ch/Work/Korrakang/KK_Client_Work/KSC/บันทึกการประชุม-สว/Code/transcription-close-caption-service
./scripts/build-and-push-acr.sh

# Deploy image ใหม่
cd ~/deploy
docker-compose -f docker-compose.staging.yml pull transcription-api
docker-compose -f docker-compose.staging.yml up -d --force-recreate video-worker-1 video-worker-2
```

## 📋 Checklist

- [ ] ตรวจสอบ RabbitMQ queues
- [ ] ดู message content
- [ ] ตรวจสอบ Hangfire jobs
- [ ] ตรวจสอบ backend logs
- [ ] ตรวจสอบว่ามีคนใช้งานจริงๆ หรือไม่
- [ ] Build และ deploy image ใหม่ (แก้ไข timeout)





