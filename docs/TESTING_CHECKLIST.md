# 📋 Testing Checklist

## ✅ สิ่งที่ต้องทดสอบ

### 1. Queue Size Limiting (50 tasks)
**Objective:** ตรวจสอบว่าระบบจำกัด queue size และ return 503 เมื่อ queue เต็ม

**Steps:**
1. ส่ง transcription requests มากกว่า 50 tasks พร้อมกัน
2. ตรวจสอบว่า requests ที่ 51+ ได้รับ 503 Service Unavailable
3. ตรวจสอบ queue size จาก `/queue/stats` endpoint

**Expected Results:**
- Requests 1-50: ได้รับ 200 OK หรือ 202 Accepted
- Requests 51+: ได้รับ 503 Service Unavailable
- Queue size ไม่เกิน 50 messages

**Test Script:**
```bash
# ใช้ concurrency test script ที่มีอยู่แล้ว
bash scripts/test/run-50-concurrency-test.sh v10-1.mp4
```

**Monitoring:**
- ดู queue stats: `curl http://localhost:8010/queue/stats`
- ดู logs สำหรับ 503 responses

---

### 2. Retry Logic สำหรับ GPU Transcription
**Objective:** ตรวจสอบว่าระบบ retry GPU mode ก่อน fallback to CPU

**Steps:**
1. จำลอง GPU timeout (ถ้าเป็นไปได้)
2. ตรวจสอบ logs ว่า retry GPU mode ก่อน fallback
3. ตรวจสอบว่า GPU resources ถูก release ก่อน retry

**Expected Results:**
- ระบบ retry GPU mode มากที่สุด 3 ครั้ง (configurable)
- มี delay 5 วินาทีระหว่าง retries
- GPU cache ถูก clear ก่อน retry
- Fallback to CPU เมื่อ retries หมด

**Environment Variables:**
```bash
export GPU_TRANSCRIPTION_MAX_RETRIES=3
export GPU_TRANSCRIPTION_RETRY_DELAY=5.0
```

**Check Logs:**
```bash
# ดู logs สำหรับ retry messages
tail -f /tmp/video-worker.log | grep -i "retry\|timeout\|fallback"
```

---

### 3. RabbitMQ Heartbeat Timeout (30 นาที)
**Objective:** ตรวจสอบว่า connection ไม่หลุดเมื่อ task ใช้เวลานาน

**Steps:**
1. ส่ง transcription task ที่ใช้เวลานาน (ไฟล์ใหญ่)
2. ตรวจสอบว่า connection ยังคงอยู่ระหว่าง processing
3. ตรวจสอบ logs ว่าไม่มี connection timeout

**Expected Results:**
- Connection ไม่หลุดระหว่าง processing
- Heartbeat timeout = 1800s (30 นาที)
- Blocked connection timeout = 600s (10 นาที)

**Environment Variables:**
```bash
export RABBITMQ_HEARTBEAT_TIMEOUT=1800
export RABBITMQ_BLOCKED_TIMEOUT=600
```

**Check Connection:**
```bash
# ดู RabbitMQ connection parameters ใน logs
tail -f /tmp/video-worker.log | grep -i "heartbeat\|blocked_timeout"
```

---

### 4. Background Thread สำหรับ Maintain Connection
**Objective:** ตรวจสอบว่า background thread maintain connection และ auto-reconnect

**Steps:**
1. ตรวจสอบว่า maintenance thread เริ่มทำงาน
2. จำลอง connection loss (ถ้าเป็นไปได้)
3. ตรวจสอบว่า auto-reconnect ทำงาน

**Expected Results:**
- Maintenance thread เริ่มทำงานเมื่อ worker start
- ตรวจสอบ connection ทุก 30 วินาที (configurable)
- Auto-reconnect เมื่อ connection หลุด

**Environment Variables:**
```bash
export RABBITMQ_CONNECTION_CHECK_INTERVAL=30
```

**Check Logs:**
```bash
# ดู maintenance thread logs
tail -f /tmp/video-worker.log | grep -i "maintenance\|connection.*check\|reconnect"
```

---

### 5. Task Timeout (1 ชั่วโมง)
**Objective:** ตรวจสอบว่า tasks ถูก mark เป็น failed เมื่อ timeout

**Steps:**
1. สร้าง task ที่ใช้เวลานานเกิน 1 ชั่วโมง (หรือลด timeout สำหรับทดสอบ)
2. ตรวจสอบว่า task ถูก mark เป็น "failed" เมื่อ timeout
3. ตรวจสอบ error message

**Expected Results:**
- Task ถูก mark เป็น "failed" เมื่อ timeout
- Error message ระบุว่า timeout
- Resources ถูก release

**Environment Variables:**
```bash
# สำหรับ testing: ลด timeout เป็น 5 นาที
export TRANSCRIPTION_TASK_TIMEOUT_SECONDS=300
```

**Check Task Status:**
```bash
# ดู task status
curl http://localhost:8010/transcribe/{task_id}
```

---

## 🧪 Comprehensive Test: 50 Concurrency Test

**Script:** `scripts/test/run-50-concurrency-test.sh`

**Steps:**
1. รัน concurrency test:
   ```bash
   bash scripts/test/run-50-concurrency-test.sh v10-1.mp4
   ```

2. เปิด monitoring dashboard:
   ```bash
   # ดูที่ static/concurrency-monitor.html
   # หรือใช้ API endpoint:
   curl http://localhost:8010/queue/stats
   curl http://localhost:8010/api/active-tasks
   ```

3. ตรวจสอบ:
   - Queue size ไม่เกิน 50
   - Tasks ถูก process ทีละตัว
   - ไม่มี connection loss
   - Tasks ไม่ timeout (ถ้าใช้เวลาน้อยกว่า 1 ชั่วโมง)
   - Retry logic ทำงาน (ถ้ามี timeout)

---

## 📊 Monitoring Endpoints

### Queue Stats
```bash
curl http://localhost:8010/queue/stats
```

**Response:**
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

### Active Tasks
```bash
curl http://localhost:8010/api/active-tasks
```

**Response:**
```json
{
  "active_tasks": [
    {
      "task_id": "...",
      "status": "processing",
      "progress": 50,
      ...
    }
  ],
  "count": 10
}
```

### Task Status
```bash
curl http://localhost:8010/transcribe/{task_id}
```

---

## 🔍 Log Files

- **Video Worker:** `/tmp/video-worker.log`
- **Transcription Service:** `/tmp/transcription-service.log` (ถ้ามี)
- **Main Service:** Console output หรือ log file ที่กำหนด

**Useful grep commands:**
```bash
# Queue limiting
grep -i "queue.*full\|503" /tmp/video-worker.log

# Retry logic
grep -i "retry\|timeout\|fallback" /tmp/video-worker.log

# Connection maintenance
grep -i "maintenance\|connection.*check\|reconnect" /tmp/video-worker.log

# Task timeout
grep -i "timeout\|exceeded" /tmp/video-worker.log
```

---

## 🎯 Success Criteria

### ✅ Queue Limiting
- [ ] 50 requests ส่งได้สำเร็จ
- [ ] Request ที่ 51+ ได้รับ 503
- [ ] Queue size ไม่เกิน 50

### ✅ Retry Logic
- [ ] GPU retry เมื่อ timeout (ถ้าเป็นไปได้)
- [ ] Retry delay ทำงาน
- [ ] GPU cache ถูก clear
- [ ] Fallback to CPU ทำงาน

### ✅ Heartbeat Timeout
- [ ] Connection ไม่หลุดระหว่าง long-running tasks
- [ ] Heartbeat timeout = 30 นาที

### ✅ Background Thread
- [ ] Maintenance thread เริ่มทำงาน
- [ ] Connection check ทุก 30 วินาที
- [ ] Auto-reconnect ทำงาน

### ✅ Task Timeout
- [ ] Tasks timeout ถูกต้อง (ตาม config)
- [ ] Error message ชัดเจน
- [ ] Resources ถูก release

---

## 📝 Notes

1. **Testing Environment Variables:**
   - ตั้งค่าทั้งหมดใน `.env.runpod` หรือ export ก่อนรัน worker
   
2. **Test File:**
   - ใช้ไฟล์วิดีโอ 10 นาทีสำหรับทดสอบ (`v10-1.mp4`)
   - สำหรับ timeout testing อาจต้องใช้ไฟล์ที่ใหญ่มาก หรือลด timeout

3. **Monitoring:**
   - ใช้ `concurrency-monitor.html` สำหรับ real-time monitoring
   - ตรวจสอบ queue stats และ active tasks เป็นระยะ

4. **Performance Testing:**
   - ทดสอบ 50 concurrent requests
   - วัดเวลารวม และเวลาต่อ task
   - ตรวจสอบ queue wait time

