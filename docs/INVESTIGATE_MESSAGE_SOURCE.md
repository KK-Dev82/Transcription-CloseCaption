# 🔍 ตรวจสอบ Source ของ Messages ที่กลับมา

## 🐛 ปัญหา

- Purge RabbitMQ queue แล้ว
- Restart workers แล้ว
- แต่ `transcription_queue` กลับมาเป็น 2 messages อีก

## 🔍 ขั้นตอนตรวจสอบ

### Step 1: ดู Message Content

```bash
# บน Staging server
# ติดตั้ง rabbitmqadmin (ถ้ายังไม่มี)
docker exec -it rabbitmq apt-get update && apt-get install -y rabbitmq-server-tools

# ดู message content (ไม่ consume)
docker exec -it rabbitmq rabbitmqadmin get queue=transcription_queue count=2 ackmode=ack_requeue_true

# หรือ consume messages เพื่อดู content
docker exec -it rabbitmq rabbitmqadmin get queue=transcription_queue count=2 ackmode=ack_requeue_false
```

**สิ่งที่ต้องดู:**
- `task_id` - ว่าเป็น task เดียวกันหรือไม่
- `job_id` - ว่าเป็น job เดียวกันหรือไม่
- `file_url` - ว่าเป็นไฟล์เดียวกันหรือไม่
- `created_at` - ว่า messages ถูกสร้างเมื่อไหร่

### Step 2: ตรวจสอบ Backend Logs

```bash
# ตรวจสอบ backend logs ว่ามีการเรียก transcription API ซ้ำหรือไม่
docker logs transcription-api --tail 500 | grep -E "transcription|ProcessTranscriptionAsync|Enqueue"

# ตรวจสอบว่ามี Hangfire jobs ที่ส่ง transcription tasks ซ้ำหรือไม่
# เข้า Hangfire Dashboard: http://10.200.22.61:5173/hangfire
# ดูที่:
# - Recurring Jobs
# - Processing Jobs
# - Succeeded/Failed Jobs
```

### Step 3: ตรวจสอบ Transcription Service Logs

```bash
# ตรวจสอบ transcription service logs ว่ามีการรับ requests ซ้ำหรือไม่
docker logs transcription-api --tail 500 | grep -E "/transcribe|POST.*transcribe"

# ตรวจสอบว่ามีการส่ง messages ไปยัง RabbitMQ ซ้ำหรือไม่
docker logs transcription-api --tail 500 | grep -E "send_transcription_task|transcription_queue"
```

### Step 4: Stop Workers และ Watch Queue

```bash
# Stop workers ชั่วคราว
docker-compose -f docker-compose.staging.yml stop video-worker-1 video-worker-2

# Purge queue
docker exec -it rabbitmq rabbitmqctl purge_queue transcription_queue

# Watch queue ทุก 10 วินาที (รอ 2-3 นาที)
watch -n 10 'docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription'
```

**ถ้า queue ยังมี messages หลังจาก stop workers → มี source ที่ส่ง messages ใหม่เข้ามา**

### Step 5: ตรวจสอบ Hangfire Jobs

```bash
# เข้า Hangfire Dashboard
# URL: http://10.200.22.61:5173/hangfire

# ตรวจสอบ:
# 1. Recurring Jobs → ดูว่ามี jobs ที่ส่ง transcription tasks หรือไม่
# 2. Processing Jobs → ดูว่ามี jobs ที่ค้างอยู่หรือไม่
# 3. Succeeded/Failed Jobs → ดูว่ามี jobs ที่ fail แล้วถูก retry หรือไม่
```

### Step 6: ตรวจสอบ Database

```bash
# ตรวจสอบ TranscriptionJobs table
# ดูว่ามี jobs ที่ status = "pending" หรือ "processing" ที่ค้างอยู่หรือไม่
# ดูว่ามี jobs ที่ถูกสร้างซ้ำหรือไม่
```

## 🔧 วิธีแก้ไขตามสาเหตุ

### สาเหตุ 1: Hangfire Jobs ส่ง Tasks ซ้ำ

**แก้ไข:**
```bash
# เข้า Hangfire Dashboard และ disable/delete recurring jobs ที่เกี่ยวข้อง
# หรือแก้ไข code ที่ส่ง transcription tasks ซ้ำ
```

### สาเหตุ 2: Backend ส่ง Requests ซ้ำ

**แก้ไข:**
```bash
# ตรวจสอบ backend code ที่ส่ง transcription requests
# เพิ่ม idempotency check หรือ rate limiting
```

### สาเหตุ 3: Transcription Service ส่ง Messages ซ้ำ

**แก้ไข:**
```bash
# ตรวจสอบ transcription service code
# เพิ่ม idempotency check ก่อนส่ง messages ไปยัง RabbitMQ
```

### สาเหตุ 4: Tasks ที่ Fail แล้วถูก Requeue

**แก้ไข:**
```bash
# ตรวจสอบ video worker code
# ตรวจสอบว่า tasks ที่ fail ไม่ถูก requeue
```

## 🚨 Quick Fix (ชั่วคราว)

### 1. Purge Queue และ Stop Workers

```bash
# Purge queue
docker exec -it rabbitmq rabbitmqctl purge_queue transcription_queue

# Stop workers
docker-compose -f docker-compose.staging.yml stop video-worker-1 video-worker-2

# Watch queue (รอ 2-3 นาที)
watch -n 10 'docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription'
```

### 2. ถ้า Queue ยังมี Messages → มี Source ที่ส่งเข้ามา

```bash
# ตรวจสอบ backend logs
docker logs transcription-api --tail 500 | grep -E "transcription|Enqueue"

# ตรวจสอบ Hangfire
# เข้า Hangfire Dashboard
```

### 3. Disable Source ชั่วคราว (ถ้าจำเป็น)

```bash
# Disable Hangfire recurring jobs (ถ้าจำเป็น)
# หรือ stop backend service ชั่วคราว
```

## 📋 Checklist

- [ ] ดู message content
- [ ] ตรวจสอบ backend logs
- [ ] ตรวจสอบ transcription service logs
- [ ] Stop workers และ watch queue
- [ ] ตรวจสอบ Hangfire jobs
- [ ] ตรวจสอบ database
- [ ] แก้ไข source ที่ส่ง messages ซ้ำ





