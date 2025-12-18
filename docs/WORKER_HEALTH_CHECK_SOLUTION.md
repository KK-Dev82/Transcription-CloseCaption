# Worker Health Check Solution - แก้ปัญหา SIGTERM

## ปัญหา

Video Worker ถูก SIGTERM/SIGKILL ตลอดเวลาเพราะ:
- RunPod วัด activity จาก inbound traffic/service activity
- Worker "นั่งรอคิว" = idle → ถูก SIGTERM
- Heartbeat ใน log ไม่ช่วย (RunPod ไม่ดู log)

## วิธีแก้ไข: Worker เปิด HTTP port + Health Check

### หลักการ

ทำให้ Video Worker "เป็น service ที่มี inbound activity เหมือน API" ไม่ใช่ daemon ที่นั่งรอคิว

### Implementation

#### 1. HTTP Health Check Server ใน Worker

**ไฟล์:** `app/workers/async/health_server.py`

- เปิด HTTP port 8030 สำหรับ health check endpoint
- Endpoint: `/health`
- Track worker status: running, rabbitmq_connected, consumers_registered, active_tasks, uptime

#### 2. Main API ยิง Health Check ไปหา Worker

**ไฟล์:** `app/main.py`

- เพิ่ม `periodic_worker_health_check()` function
- ยิง health check ไปหา worker ทุก 30-60 วินาที
- Random interval เพื่อให้ดูเป็น natural traffic

#### 3. Worker Status Tracking

- Track: running, rabbitmq_connected, consumers_registered, active_tasks, uptime
- Update status ทุก 5 วินาที

### Configuration

**Environment Variables:**
- `WORKER_HEALTH_PORT`: Port สำหรับ health check server (default: 8030)
- `ENABLE_WORKER_HEALTH_CHECK`: เปิด/ปิด health check (default: true)

### การทำงาน

1. **Worker Start:**
   - Start health check server (port 8030)
   - Update worker status: running=True

2. **Worker Running:**
   - Main API ยิง health check ไปหา worker ทุก 30-60 วินาที
   - Update worker status ทุก 5 วินาที (active_tasks, uptime)

3. **Worker Shutdown:**
   - Update worker status: running=False
   - Stop health check server

### ข้อดี

- ✅ ง่ายที่สุด - เพิ่ม HTTP endpoint ใน worker
- ✅ ไม่ต้องแก้ architecture มาก
- ✅ Worker ยังเป็น process แยก (ง่ายต่อการ debug)
- ✅ ใช้ได้กับ Secure Pod (internal health check)

### ข้อควรระวัง

- ⚠️ Internal health check อาจไม่ถูกนับ (ต้องทดสอบ)
- ⚠️ ถ้าไม่ work → ใช้ external health check (UptimeRobot/Cloudflare cron)
- ⚠️ ถ้ายังไม่ work → ใช้วิธี 1B (Worker ผูกอยู่กับ API process)

## การทดสอบ

### 1. ทดสอบ Health Check Server

```bash
# ตรวจสอบว่า health check server ทำงาน
curl http://localhost:8030/health

# ควรได้ response:
{
  "status": "healthy",
  "service": "video-worker",
  "rabbitmq_connected": true,
  "consumers_registered": true,
  "active_tasks": 0,
  "uptime_seconds": 123
}
```

### 2. ทดสอบ Main API Health Check

```bash
# ตรวจสอบ log ของ Main API
tail -f logs/api-service.log | grep "Worker Health Check"

# ควรเห็น:
# 💓 [Worker Health Check] Worker is healthy: healthy
```

### 3. ตรวจสอบว่า RunPod เห็น Inbound Activity

- ตรวจสอบว่า worker ไม่ถูก SIGTERM
- ตรวจสอบว่า worker อยู่ได้นานขึ้น

## ถ้า Internal Health Check ไม่ Work

### ทางเลือก 1: External Health Check

ใช้ UptimeRobot หรือ Cloudflare cron:
- ยิง `http://<pod-ip>:8030/health` ทุก 30-60 วินาที
- RunPod จะเห็น inbound traffic จากภายนอก

### ทางเลือก 2: Worker ผูกอยู่กับ API Process (วิธี 1B)

- รัน consumer เป็น background task ภายใน uvicorn app
- งานหนัก (ffmpeg + whisper) รันใน process pool
- ไม่ต้องเปิดพอร์ตเพิ่ม
- Process เดียว / lifecycle เดียว

## สรุป

**วิธี 1A (Worker เปิด HTTP port + Health Check)** เป็นวิธีที่แนะนำเพราะ:
- ✅ ง่ายที่สุด
- ✅ ไม่ต้องแก้ architecture มาก
- ✅ Worker ยังเป็น process แยก (ง่ายต่อการ debug)

**ถ้าไม่ work:**
- → ใช้ external health check (UptimeRobot/Cloudflare cron)
- → หรือใช้วิธี 1B (Worker ผูกอยู่กับ API process)


