# SIGTERM Tracking & Solution

## ปัญหา

Worker ได้รับ SIGTERM (signal 15) และปิดตัวลงหลังจากรอคิวประมาณ 1-2 นาที โดยไม่ได้เริ่มงานหนัก

**สาเหตุที่เป็นไปได้:**
- RunPod platform idle timeout / scale-to-zero
- Health check failure
- Spot / interruptible instance reclaim
- Resource limits

## การแก้ไข

### 1. Heartbeat Logging (Video Worker)

**ไฟล์:** `app/workers/async/video_worker.py`

- Log heartbeat ทุก 25 วินาที พร้อม ping RabbitMQ
- ป้องกัน platform มองว่า idle
- Log format: `💓 [Heartbeat] Worker alive - RabbitMQ connection healthy`

### 2. Graceful Shutdown (Video Worker)

**ไฟล์:** `app/workers/async/video_worker.py`

- Nack messages ที่ค้างอยู่ (requeue=True) เมื่อ shutdown
- Wait 1 วินาที ก่อน close connection เพื่อให้ messages ถูก nack
- ป้องกันงานหายเมื่อ worker ถูก terminate

### 3. Health Check Endpoint (Main API)

**ไฟล์:** `app/main.py`

- Ping RabbitMQ จริงๆ ทุกครั้งที่เรียก `/health`
- แสดง activity จริงๆ ให้ platform เห็น
- Return ping time และ queue count

### 4. Monitoring Scripts

#### `scripts/pod/check-container-exit-codes.sh`
- ตรวจสอบ container exit codes
- ตรวจสอบ OOM killed
- แสดงสาเหตุที่เป็นไปได้

#### `scripts/pod/monitor-sigterm.sh`
- Monitor SIGTERM events จาก logs
- Track Main API และ Video Worker
- วิเคราะห์ uptime patterns

## การใช้งาน

### ตรวจสอบ Container Exit Codes
```bash
bash scripts/pod/check-container-exit-codes.sh
```

### Monitor SIGTERM Events
```bash
bash scripts/pod/monitor-sigterm.sh
```

### Monitor Heartbeat Logs
```bash
tail -f logs/video-worker-errors.log | grep Heartbeat
```

### Health Check (ส่ง activity จริงๆ)
```bash
curl http://localhost:8010/health
```

## คำแนะนำสำหรับ RunPod

### 1. ตรวจสอบ RunPod Settings

- **Idle Timeout**: ปิดหรือเพิ่มให้มากกว่า 2 นาที
- **Health Check Policy**: ตั้งให้ตรวจสอบ `/health` endpoint
- **Max Execution Time**: เพิ่มให้มากพอ
- **Spot / Interruptible**: หลีกเลี่ยงถ้าต้องการเสถียร

### 2. ใช้ On-Demand Pod

สำหรับ worker ที่ต้องคอยคิวตลอด ควรใช้:
- **On-Demand Pod** (ไม่ใช่ serverless/scale-to-zero)
- **Persistent Pod** (ไม่ใช่ spot/interruptible)

### 3. Alternative Architecture

ถ้าจำเป็นต้องใช้ serverless:
- เปลี่ยนเป็น "per-job worker" (start → process 1 job → exit)
- ควบคุม concurrency ด้วยจำนวน instances
- ใช้ API เรียก worker แบบ on-demand

## ผลลัพธ์ที่คาดหวัง

1. **Heartbeat logs** จะปรากฏทุก 25 วินาที
2. **Health check** จะ ping RabbitMQ จริงๆ
3. **Graceful shutdown** จะ nack messages ที่ค้างอยู่
4. **Monitoring scripts** จะช่วยหาต้นเหตุ SIGTERM

## การตรวจสอบ

### ตรวจสอบว่า Heartbeat ทำงาน
```bash
tail -f logs/video-worker-errors.log | grep -E "Heartbeat|SIGTERM"
```

### ตรวจสอบ Health Check Activity
```bash
watch -n 5 'curl -s http://localhost:8010/health | jq .rabbitmq'
```

### ตรวจสอบ Container Status
```bash
bash scripts/pod/check-container-exit-codes.sh
```

