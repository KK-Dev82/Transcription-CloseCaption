# 🔍 ปัญหาที่พบใน Concurrency Test

## 📋 สรุปปัญหา

จากการทดสอบ 50 concurrent requests พบปัญหาหลัก 3 ข้อ:

1. **Connection หลุด** - "Server disconnected" และ "Connection reset by peer"
2. **Task Dashboard ไม่โหลดข้อมูล** - หน้า dashboard ไม่แสดง tasks
3. **Transcription ได้แค่ 1 task** - จาก 50 tasks ที่ส่งไป ประสบความสำเร็จแค่ 1 task

---

## 🔴 ปัญหาที่ 1: Connection หลุด

### อาการ
```
⚠️  Task X: Poll error - Server disconnected
⚠️  Task X: Poll error - Connection reset by peer
```

### สาเหตุที่เป็นไปได้

1. **Server Overload**
   - 50 concurrent requests อาจทำให้ server overload
   - Connection pool อาจเต็ม
   - Memory หรือ CPU resources อาจไม่พอ

2. **Connection Pooling Issues**
   - `aiohttp` connection pool อาจไม่เพียงพอ
   - Connection timeout settings อาจไม่เหมาะสม
   - TCP connection limit อาจถูกเกิน

3. **Network Issues**
   - Network instability
   - Firewall หรือ load balancer timeout
   - Keep-alive settings ไม่เหมาะสม

### แนวทางแก้ไข

#### 1. เพิ่ม Retry Logic ใน Test Script

```python
# เพิ่ม retry logic สำหรับ connection errors
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

async def poll_with_retry(session, url, max_retries=MAX_RETRIES):
    for attempt in range(max_retries):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                continue
            raise
```

#### 2. ปรับ Connection Settings

```python
# เพิ่ม connection limit และ timeout
connector = aiohttp.TCPConnector(
    limit=100,  # เพิ่มจาก 50
    limit_per_host=50,
    ttl_dns_cache=300,
    force_close=False,  # ใช้ keep-alive
    enable_cleanup_closed=True
)

timeout = aiohttp.ClientTimeout(
    total=7200,  # 2 hours
    connect=30,  # connection timeout
    sock_read=60  # socket read timeout
)
```

#### 3. ตรวจสอบ Server Settings

```bash
# ตรวจสอบ active connections
ss -an | grep ":8010" | grep ESTAB | wc -l

# ตรวจสอบ connection limits
ulimit -n

# ตรวจสอบ system resources
free -h
top
```

---

## 🔴 ปัญหาที่ 2: Task Dashboard ไม่โหลดข้อมูล

### อาการ
- หน้า dashboard ไม่แสดง tasks
- API endpoints ไม่ return ข้อมูล
- Console errors ใน browser

### สาเหตุที่เป็นไปได้

1. **ไม่มี Tasks ใน Storage**
   - Tasks อาจไม่ถูกบันทึกลง storage
   - Storage directory path อาจผิด
   - Permission issues

2. **API Endpoint Issues**
   - Date parsing errors
   - JSON format errors
   - Storage read errors

3. **Frontend Issues**
   - JavaScript errors
   - API call failures
   - CORS issues

### แนวทางแก้ไข

#### 1. ตรวจสอบ Storage

```bash
# ใช้ diagnostic script
bash scripts/pod/diagnose-task-dashboard.sh

# หรือตรวจสอบด้วยตนเอง
ls -la storage/transcriptions/
find storage/transcriptions -name "metadata.json" | wc -l
```

#### 2. ตรวจสอบ API Endpoints

```bash
# Test endpoints
curl http://localhost:8010/api/tasks/available-dates
curl http://localhost:8010/api/tasks/summary?date=$(date +%Y-%m-%d)
curl http://localhost:8010/api/tasks/by-date?date=$(date +%Y-%m-%d)
```

#### 3. ตรวจสอบ Logs

```bash
# ดู logs สำหรับ storage errors
tail -f /tmp/transcription-service.log | grep -iE "storage|json_storage|list_all"

# ดู errors
tail -f /tmp/transcription-service.log | grep -i error
```

---

## 🔴 ปัญหาที่ 3: Transcription ได้แค่ 1 Task

### อาการ
- จาก 50 tasks ที่ส่งไป ประสบความสำเร็จแค่ 1 task
- Tasks อื่นๆ ล้มเหลวหรือค้าง

### สาเหตุที่เป็นไปได้

1. **Worker Crash**
   - Video Worker อาจ crash หลังจากเริ่มงาน
   - RabbitMQ connection loss
   - Memory/GPU issues

2. **Queue Issues**
   - Queue limit reached (50 tasks)
   - Messages ไม่ถูก consume
   - Consumer crash

3. **Resource Exhaustion**
   - GPU memory full
   - CPU overload
   - Disk space full

### แนวทางแก้ไข

#### 1. ตรวจสอบ Worker Status

```bash
# ตรวจสอบ worker process
ps aux | grep video-worker

# ตรวจสอบ worker logs
tail -f /tmp/video-worker.log | grep -iE "error|exception|crash"

# ตรวจสอบ worker activity
bash scripts/pod/check-worker-activity.sh
```

#### 2. ตรวจสอบ RabbitMQ Queue

```bash
# ตรวจสอบ queue stats
curl http://localhost:8010/queue/stats

# ตรวจสอบ queue messages
# (ต้องมี RabbitMQ management tools)
```

#### 3. ตรวจสอบ System Resources

```bash
# GPU usage
nvidia-smi

# Memory
free -h

# CPU
top

# Disk
df -h
```

---

## 🛠️ Action Items

### Immediate Actions

1. **Run Diagnostic Scripts**
   ```bash
   # Task Dashboard diagnostic
   bash scripts/pod/diagnose-task-dashboard.sh
   
   # Worker activity check
   bash scripts/pod/check-worker-activity.sh
   
   # Connection issues check
   bash scripts/pod/check-connection-issues.sh
   ```

2. **Check Logs**
   ```bash
   # Service logs
   tail -100 /tmp/transcription-service.log
   
   # Worker logs
   tail -100 /tmp/video-worker.log
   ```

3. **Test API Endpoints**
   ```bash
   # Health check
   curl http://localhost:8010/health
   
   # Task endpoints
   curl http://localhost:8010/api/tasks/available-dates
   curl http://localhost:8010/api/tasks/summary?date=$(date +%Y-%m-%d)
   ```

### Medium-term Improvements

1. **เพิ่ม Retry Logic ใน Test Script**
   - Retry สำหรับ connection errors
   - Exponential backoff
   - Error classification

2. **ปรับ Connection Settings**
   - เพิ่ม connection pool size
   - ปรับ timeout values
   - ใช้ keep-alive connections

3. **เพิ่ม Monitoring**
   - Real-time queue monitoring
   - Worker health checks
   - Resource usage alerts

### Long-term Improvements

1. **Load Balancing**
   - กระจาย load ไปหลาย workers
   - Auto-scaling workers

2. **Queue Management**
   - Priority queues
   - Dead letter queues
   - Queue monitoring dashboard

3. **Error Handling**
   - Comprehensive error logging
   - Error recovery mechanisms
   - Automatic retry for failed tasks

---

## 📊 Diagnostic Checklist

### Before Running Test

- [ ] Service is running (`curl http://localhost:8010/health`)
- [ ] Worker is running (`ps aux | grep video-worker`)
- [ ] RabbitMQ is accessible
- [ ] Storage directory exists and is writable
- [ ] Test file exists and is accessible
- [ ] System resources are sufficient (memory, disk, GPU)

### During Test

- [ ] Monitor service logs
- [ ] Monitor worker logs
- [ ] Monitor queue stats
- [ ] Monitor system resources (CPU, memory, GPU)
- [ ] Monitor active connections

### After Test

- [ ] Check task completion rate
- [ ] Check error logs
- [ ] Check queue status
- [ ] Check storage for saved tasks
- [ ] Generate test report

---

## 🔗 Related Documents

- [Testing Checklist](./TESTING_CHECKLIST.md)
- [Root Cause Analysis](./ROOT_CAUSE_ANALYSIS.md)
- [Architecture Design](./ARCHITECTURE_DESIGN.md)
- [Implementation Status](./IMPLEMENTATION_STATUS.md)

---

## 📝 Notes

- การทดสอบ 50 concurrent requests เป็นการ load testing ที่หนักมาก
- อาจต้องลดจำนวน concurrent requests เพื่อให้ระบบเสถียร
- ควรทดสอบแบบค่อยๆ เพิ่มขึ้น (10 → 20 → 30 → 50) เพื่อหาจุดที่เหมาะสม

---

**Last Updated**: 2024-12-03

