# 🔍 Debug RabbitMQ Messages ที่กลับมา

## 🐛 ปัญหา

- Purge RabbitMQ queue แล้ว
- Restart workers แล้ว
- แต่ `transcription_queue` กลับมาเป็น 2 messages อีก

## 🔍 สาเหตุที่เป็นไปได้

### 1. **Hangfire Recurring Jobs ส่ง Tasks ซ้ำ**

**ตรวจสอบ:**
```bash
# บน Staging server
# เข้า Hangfire Dashboard
# URL: http://10.200.22.61:5173/hangfire

# ตรวจสอบ:
# 1. Recurring Jobs → ดูว่ามี jobs ที่ส่ง transcription tasks ซ้ำหรือไม่
# 2. Processing Jobs → ดูว่ามี jobs ที่ค้างอยู่หรือไม่
# 3. Succeeded/Failed Jobs → ดูว่ามี jobs ที่ fail แล้วถูก retry หรือไม่
```

### 2. **Backend ส่ง Transcription Requests ซ้ำ**

**ตรวจสอบ:**
```bash
# ตรวจสอบ RabbitMQ message content
docker exec -it rabbitmq rabbitmqctl list_queues name messages consumers

# ดู message content (ต้องใช้ management plugin)
# หรือใช้ rabbitmqadmin
docker exec -it rabbitmq rabbitmqadmin get queue=transcription_queue count=2
```

### 3. **Tasks ที่ Fail แล้วถูก Requeue**

**ตรวจสอบ:**
```bash
# ตรวจสอบ logs ว่ามี tasks ที่ fail แล้วถูก requeue หรือไม่
docker logs video-worker-1 --tail 200 | grep -E "nack|requeue|failed"

# ตรวจสอบ tasks ที่ status = "failed"
docker exec -it video-worker-1 grep -r '"status":"failed"' /app/storage/transcriptions/ 2>/dev/null
```

### 4. **Duplicate Messages จาก Source**

**ตรวจสอบ:**
```bash
# ดู message content เพื่อดูว่าเป็น duplicate หรือไม่
docker exec -it rabbitmq rabbitmqadmin get queue=transcription_queue count=2 ackmode=ack_requeue_false
```

## 🔧 วิธีแก้ไข

### Step 1: ตรวจสอบ Message Content

```bash
# บน Staging server
# ติดตั้ง rabbitmqadmin (ถ้ายังไม่มี)
docker exec -it rabbitmq apt-get update && apt-get install -y rabbitmq-server-tools

# ดู message content
docker exec -it rabbitmq rabbitmqadmin get queue=transcription_queue count=2 ackmode=ack_requeue_false
```

### Step 2: ตรวจสอบ Hangfire Jobs

```bash
# ตรวจสอบ backend logs
docker logs transcription-api --tail 200 | grep -E "transcription|Hangfire|Enqueue"

# ตรวจสอบว่ามี recurring jobs ที่ส่ง transcription tasks หรือไม่
# เข้า Hangfire Dashboard: http://10.200.22.61:5173/hangfire
```

### Step 3: ตรวจสอบ Backend Code

```bash
# ตรวจสอบว่ามี code ที่ส่ง transcription requests ซ้ำหรือไม่
# ดูที่:
# - TranscriptionController.cs
# - RabbitMqBackgroundConsumer.cs
# - HangfireJobsHostedService.cs
```

### Step 4: ป้องกัน Duplicate Messages

**เพิ่ม Idempotency Check:**

```python
# ใน video_worker.py
def _process_transcription_task(self, ch, method, properties, body):
    """ประมวลผล transcription task"""
    try:
        task_data = json.loads(body.decode('utf-8'))
        task_id = task_data.get('task_id')
        
        # ตรวจสอบว่า task นี้ถูกประมวลผลไปแล้วหรือไม่
        existing_task = self.json_storage.get_transcription(task_id)
        if existing_task:
            existing_status = existing_task.get('status', '')
            if existing_status in ['completed', 'processing']:
                logger.warning(f"⚠️ Task {task_id} มีสถานะ '{existing_status}' แล้ว, ข้ามการประมวลผลซ้ำ")
                # Acknowledge message เพื่อไม่ให้ requeue
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
        
        # ... rest of the code ...
```

## 🚨 Quick Fix (ด่วน)

### 1. Purge Queue และ Stop Workers ชั่วคราว

```bash
# Purge queue
docker exec -it rabbitmq rabbitmqctl purge_queue transcription_queue

# Stop workers ชั่วคราว
docker-compose -f docker-compose.staging.yml stop video-worker-1 video-worker-2

# ตรวจสอบว่า queue ยังมี messages หรือไม่ (รอ 1-2 นาที)
watch -n 5 'docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription'
```

**ถ้า queue ยังมี messages หลังจาก stop workers → มี source ที่ส่ง messages ใหม่เข้ามา**

### 2. ตรวจสอบ Source ของ Messages

```bash
# ตรวจสอบ backend logs
docker logs transcription-api --tail 500 | grep -E "transcription|Enqueue|Publish"

# ตรวจสอบ Hangfire
# เข้า Hangfire Dashboard และดู Recurring Jobs
```

### 3. ปิด Hangfire Recurring Jobs ชั่วคราว (ถ้าจำเป็น)

```bash
# ตรวจสอบ Hangfire jobs
# เข้า Hangfire Dashboard และ disable recurring jobs ที่เกี่ยวข้อง
```

## 📋 Checklist

- [ ] ตรวจสอบ message content
- [ ] ตรวจสอบ Hangfire jobs
- [ ] ตรวจสอบ backend logs
- [ ] ตรวจสอบว่า messages มาจากไหน
- [ ] เพิ่ม idempotency check
- [ ] Purge queue และ stop workers ชั่วคราวเพื่อดูว่า messages มาจากไหน





