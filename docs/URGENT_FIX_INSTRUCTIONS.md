# 🚨 คำสั่งแก้ไขปัญหา Infinite Chunk Creation (ด่วน)

## ⚠️ สถานะปัจจุบัน

- ✅ Code แก้ไขแล้ว (มี safety checks)
- ❌ Docker image ยังไม่ได้ build/push ใหม่
- ❌ RabbitMQ queue ยังมี messages ค้างอยู่ (2 messages)
- ❌ Workers ยังใช้ image เก่าที่ไม่มี safety checks

## 🔧 ขั้นตอนแก้ไข (ต้องทำทันที)

### Step 1: Purge RabbitMQ Queue (บน Staging)

```bash
# บน Staging server (dvstmediaprocph263)
cd ~/deploy

# Purge transcription_queue
docker exec -it rabbitmq rabbitmqctl purge_queue transcription_queue

# ตรวจสอบว่า queue ว่างแล้ว
docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription
# ผลลัพธ์ที่คาดหวัง: transcription_queue     0
```

### Step 2: Build และ Push Docker Image ใหม่ (บน Local)

```bash
# บน Local machine
cd /Users/athip-ch/Work/Korrakang/KK_Client_Work/KSC/บันทึกการประชุม-สว/Code/transcription-close-caption-service

# Build และ push ไปยัง ACR
./scripts/build-and-push-acr.sh
```

### Step 3: Deploy Image ใหม่ (บน Staging)

```bash
# บน Staging server
cd ~/deploy

# Pull image ใหม่
docker-compose -f docker-compose.staging.yml pull transcription-api

# Restart workers เพื่อใช้ image ใหม่
docker-compose -f docker-compose.staging.yml up -d --force-recreate video-worker-1 video-worker-2

# ตรวจสอบ logs
docker logs video-worker-1 --tail 50 -f
```

### Step 4: ตรวจสอบว่าแก้ไขแล้ว

```bash
# ตรวจสอบ logs ว่ายังสร้าง chunks ไม่หยุดหรือไม่
docker logs video-worker-1 --tail 100 | grep "สร้าง audio chunk" | tail -20

# ตรวจสอบ RabbitMQ queue
docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription

# ตรวจสอบ tasks ที่ค้างอยู่
docker exec -it video-worker-1 grep -r '"status":"processing"' /app/storage/transcriptions/ 2>/dev/null | wc -l
```

## ✅ ผลลัพธ์ที่คาดหวังหลังแก้ไข

1. **Chunk numbers หยุดที่จำนวนที่เหมาะสม:**
   ```
   สร้าง audio chunk 1: 0s - 30s
   สร้าง audio chunk 2: 25s - 55s
   ...
   สร้าง audio chunks สำเร็จ: 50 chunks  ← หยุดที่จำนวนที่เหมาะสม
   ```

2. **RabbitMQ queue ว่าง:**
   ```
   transcription_queue     0
   ```

3. **ไม่มี tasks ค้างอยู่:**
   ```
   0  (ไม่มี tasks ที่ status = "processing")
   ```

## 🚨 ถ้ายังมีปัญหา

### ถ้ายังสร้าง chunks ไม่หยุด:

1. **ตรวจสอบว่าใช้ image ใหม่แล้ว:**
   ```bash
   docker images | grep kk-transcription
   # ตรวจสอบว่า IMAGE ID ตรงกับ image ที่เพิ่ง push หรือไม่
   ```

2. **ตรวจสอบ logs ว่ามี safety check warnings:**
   ```bash
   docker logs video-worker-1 --tail 200 | grep -E "⚠️|warning|max_chunks"
   ```

3. **Force restart workers:**
   ```bash
   docker-compose -f docker-compose.staging.yml stop video-worker-1 video-worker-2
   docker-compose -f docker-compose.staging.yml rm -f video-worker-1 video-worker-2
   docker-compose -f docker-compose.staging.yml up -d video-worker-1 video-worker-2
   ```

### ถ้า RabbitMQ queue ยังมี messages:

1. **Purge queue อีกครั้ง:**
   ```bash
   docker exec -it rabbitmq rabbitmqctl purge_queue transcription_queue
   ```

2. **ตรวจสอบว่าไม่มี messages ใหม่เข้ามา:**
   ```bash
   # ตรวจสอบทุก 10 วินาที
   watch -n 10 'docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription'
   ```





