# 🛑 คำสั่งหยุดการสร้าง Chunks (ด่วน)

## 📋 สถานะปัจจุบัน

- ✅ Hangfire ไม่มี Job แล้ว
- ❌ ยังมีการสร้าง chunks อยู่ (chunk 165-185)
- ❌ RabbitMQ queue อาจมี messages ค้างอยู่
- ❌ Workers ยังคง process messages

## 🔧 ขั้นตอนหยุดการสร้าง Chunks

### Step 1: ตรวจสอบ RabbitMQ Queue Status

```bash
# ตรวจสอบ queues ทั้งหมด
docker exec -it rabbitmq rabbitmqctl list_queues name messages consumers

# ตรวจสอบเฉพาะ transcription queue
docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription
```

**ผลลัพธ์ที่คาดหวัง:**
```
transcription_queue     2  (มี messages ค้างอยู่)
```

### Step 2: Purge RabbitMQ Queue

```bash
# Purge transcription_queue เพื่อลบ messages ทั้งหมด
docker exec -it rabbitmq rabbitmqctl purge_queue transcription_queue

# ตรวจสอบว่า queue ว่างแล้ว
docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription
# ผลลัพธ์ที่คาดหวัง: transcription_queue     0
```

### Step 3: Stop Workers ชั่วคราว (ถ้าจำเป็น)

```bash
# Stop workers เพื่อหยุดการ process messages
docker-compose stop video-worker-1 video-worker-2

# หรือ restart workers
docker-compose restart video-worker-1 video-worker-2
```

### Step 4: ตรวจสอบว่า Queue ว่างแล้ว

```bash
# ตรวจสอบทุก 10 วินาที
watch -n 10 'docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription'

# หรือตรวจสอบครั้งเดียว
docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription
```

**ผลลัพธ์ที่คาดหวัง:**
```
transcription_queue     0  (queue ว่างแล้ว)
```

### Step 5: ตรวจสอบ Logs ว่าไม่มีการสร้าง Chunks แล้ว

```bash
# ตรวจสอบ logs ล่าสุด
docker logs video-worker-1 --tail 50 | grep "สร้าง audio chunk"

# ถ้าไม่มี output = ไม่มีการสร้าง chunks แล้ว ✅
```

## 🚨 ถ้ายังมีการสร้าง Chunks อยู่

### Option 1: Purge Queue อีกครั้ง

```bash
# Purge queue อีกครั้ง
docker exec -it rabbitmq rabbitmqctl purge_queue transcription_queue

# ตรวจสอบว่า queue ว่างแล้ว
docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription
```

### Option 2: Stop Workers และ Purge Queue

```bash
# Stop workers
docker-compose stop video-worker-1 video-worker-2

# Purge queue
docker exec -it rabbitmq rabbitmqctl purge_queue transcription_queue

# ตรวจสอบ queue
docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription

# Start workers ใหม่ (ถ้าต้องการ)
docker-compose start video-worker-1 video-worker-2
```

### Option 3: ตรวจสอบว่า Messages มาจากไหน

```bash
# ดู message content (2 messages)
docker exec -it rabbitmq rabbitmqadmin get queue=transcription_queue count=2 ackmode=ack_requeue_false

# ตรวจสอบ backend logs
docker logs transcription-api --tail 500 | grep -E "transcription|Enqueue|Publish"

# ตรวจสอบ Hangfire (ถ้ามี)
# เข้า Hangfire Dashboard และดู Processing Jobs
```

## 📝 หมายเหตุ

1. **Purge Queue**: จะลบ messages ทั้งหมดใน queue (ไม่สามารถกู้คืนได้)
2. **Stop Workers**: จะหยุดการ process messages แต่ messages ยังอยู่ใน queue
3. **Restart Workers**: จะเริ่ม process messages ใหม่จาก queue

## ✅ Checklist

- [ ] ตรวจสอบ RabbitMQ queue status
- [ ] Purge transcription_queue
- [ ] ตรวจสอบว่า queue ว่างแล้ว
- [ ] Stop workers (ถ้าจำเป็น)
- [ ] ตรวจสอบ logs ว่าไม่มีการสร้าง chunks แล้ว
- [ ] ตรวจสอบว่า messages ไม่กลับมาใหม่

## 🎯 สรุป

**คำสั่งหลัก:**
```bash
# 1. Purge queue
docker exec -it rabbitmq rabbitmqctl purge_queue transcription_queue

# 2. ตรวจสอบ queue
docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription

# 3. ตรวจสอบ logs
docker logs video-worker-1 --tail 50 | grep "สร้าง audio chunk"
```

**ถ้ายังมีปัญหา:**
- Stop workers → Purge queue → ตรวจสอบ queue → Start workers

