# 🚀 Quick Test Guide

## การทดสอบอย่างรวดเร็ว

### 1. ตรวจสอบ Environment Variables

ตรวจสอบว่าได้ตั้งค่า environment variables แล้วหรือยัง:

```bash
# บน Pod
cd /workspace/transcription-service

# ตรวจสอบ .env.runpod หรือ export variables
cat .env.runpod | grep -E "TRANSCRIPTION_MAX_QUEUE_SIZE|GPU_TRANSCRIPTION|RABBITMQ|TASK_TIMEOUT"
```

**Environment Variables ที่ต้องมี:**

```bash
# Queue Limiting
TRANSCRIPTION_MAX_QUEUE_SIZE=50

# Retry Logic
GPU_TRANSCRIPTION_MAX_RETRIES=3
GPU_TRANSCRIPTION_RETRY_DELAY=5.0

# RabbitMQ Timeouts
RABBITMQ_HEARTBEAT_TIMEOUT=1800  # 30 นาที
RABBITMQ_BLOCKED_TIMEOUT=600     # 10 นาที
RABBITMQ_CONNECTION_CHECK_INTERVAL=30

# Task Timeout
TRANSCRIPTION_TASK_TIMEOUT_SECONDS=3600  # 1 ชั่วโมง
```

### 2. ตรวจสอบ Services

**ตรวจสอบว่า services รันอยู่:**

```bash
# ตรวจสอบ Video Worker
ps aux | grep video_worker | grep -v grep

# ตรวจสอบ Transcription Service (FastAPI)
ps aux | grep uvicorn | grep -v grep

# ตรวจสอบ RabbitMQ
ps aux | grep rabbitmq | grep -v grep
```

**ตรวจสอบ Logs:**

```bash
# Video Worker logs
tail -f /tmp/video-worker.log

# หรือถ้าใช้ journalctl
journalctl -u video-worker -f
```

### 3. รัน 50 Concurrency Test

```bash
cd /workspace/transcription-service

# ตรวจสอบว่าไฟล์วิดีโอมีอยู่
ls -lh uploads/v10-1.mp4

# รัน test
bash scripts/test/run-50-concurrency-test.sh v10-1.mp4
```

**สิ่งที่ควรเห็น:**
- ✅ ส่ง 50 requests สำเร็จ
- ⚠️ Requests ที่ 51+ ได้รับ 503 (ถ้าส่งมากกว่า 50)
- 📊 Tasks ถูก process ทีละตัว

### 4. เปิด Monitoring Dashboard

**Option 1: จาก Pod เอง**
```bash
# ตรวจสอบ port
netstat -tlnp | grep 8010

# เปิด browser ไปที่
# http://localhost:8010/static/concurrency-monitor.html
```

**Option 2: จากภายนอก**
```bash
# เปิด browser ไปที่
# http://80.15.7.37:41462/static/concurrency-monitor.html
```

### 5. ตรวจสอบ Queue Stats

**ตรวจสอบ Queue Stats:**

```bash
curl http://localhost:8010/queue/stats | python3 -m json.tool
```

**ตรวจสอบ Active Tasks:**

```bash
curl http://localhost:8010/api/active-tasks | python3 -m json.tool
```

**ตรวจสอบ Task Status:**

```bash
# แทน {task_id} ด้วย task ID จริง
curl http://localhost:8010/transcribe/{task_id} | python3 -m json.tool
```

### 6. ตรวจสอบ Logs สำหรับ Features ใหม่

**Queue Limiting:**
```bash
tail -f /tmp/video-worker.log | grep -i "queue.*full\|503"
```

**Retry Logic:**
```bash
tail -f /tmp/video-worker.log | grep -i "retry\|timeout.*gpu\|fallback"
```

**Connection Maintenance:**
```bash
tail -f /tmp/video-worker.log | grep -i "maintenance\|connection.*check\|reconnect"
```

**Task Timeout:**
```bash
tail -f /tmp/video-worker.log | grep -i "timeout\|exceeded"
```

---

## 🎯 Success Criteria

### ✅ Queue Limiting
- [ ] 50 requests ส่งได้สำเร็จ
- [ ] Request ที่ 51+ ได้รับ 503
- [ ] Queue size ไม่เกิน 50 (ตรวจสอบจาก `/queue/stats`)

### ✅ Retry Logic
- [ ] เมื่อ GPU timeout (ถ้าเป็นไปได้) ระบบ retry ก่อน fallback
- [ ] Logs แสดง retry attempts
- [ ] Fallback to CPU เมื่อ retries หมด

### ✅ Heartbeat Timeout
- [ ] Connection ไม่หลุดระหว่าง long-running tasks
- [ ] Logs แสดง heartbeat timeout = 1800s

### ✅ Background Thread
- [ ] Maintenance thread เริ่มทำงาน (ดูใน logs)
- [ ] Connection check ทุก 30 วินาที
- [ ] Auto-reconnect ทำงาน (ถ้า connection หลุด)

### ✅ Task Timeout
- [ ] Tasks timeout ถูกต้อง (ตาม config)
- [ ] Error message ชัดเจน
- [ ] Task status = "failed" เมื่อ timeout

---

## 📊 Expected Results

### Queue Stats Response
```json
{
  "message": "ดึงสถิติ queue สำเร็จ",
  "stats": {
    "total_queues": 1,
    "total_messages": 25,
    "total_consumers": 1,
    "queue_details": {
      "transcription_queue": {
        "name": "transcription_queue",
        "message_count": 25,
        "consumer_count": 1
      }
    }
  }
}
```

### Task Status Response (เมื่อ queue เต็ม)
```json
{
  "detail": "Queue is full (50/50). Please try again later."
}
```
**HTTP Status:** 503 Service Unavailable

---

## 🔍 Troubleshooting

### ถ้าไม่เห็น 503 เมื่อ queue เต็ม
1. ตรวจสอบว่า `TRANSCRIPTION_MAX_QUEUE_SIZE` ตั้งค่าแล้ว
2. ตรวจสอบว่า queue size checking ทำงาน (ดู logs)
3. ลองส่ง requests มากกว่า 50 ตัว

### ถ้า Connection หลุดบ่อย
1. ตรวจสอบว่า `RABBITMQ_HEARTBEAT_TIMEOUT` ตั้งค่าเป็น 1800
2. ตรวจสอบว่า maintenance thread ทำงาน
3. ดู logs สำหรับ connection errors

### ถ้า Tasks Timeout เร็วเกินไป
1. ตรวจสอบว่า `TRANSCRIPTION_TASK_TIMEOUT_SECONDS` ตั้งค่าเป็น 3600 (1 ชั่วโมง)
2. หรือเพิ่มค่าถ้าต้องการ timeout นานกว่า

---

## 📝 Notes

1. **Testing File:** ใช้ไฟล์วิดีโอ 10 นาที (`v10-1.mp4`) สำหรับทดสอบ
2. **Performance:** แต่ละ task อาจใช้เวลา 2-5 นาที ขึ้นอยู่กับ GPU และ model size
3. **Monitoring:** ใช้ HTML dashboard สำหรับ real-time monitoring
4. **Logs:** ตรวจสอบ logs เป็นระยะเพื่อดูการทำงานของ features ใหม่

