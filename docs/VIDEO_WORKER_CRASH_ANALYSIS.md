# 🔍 Video Worker Crash Analysis และวิธีแก้ไขถาวร

## 1. สาเหตุที่ Video Worker หยุดทำงาน

### Error ที่พบ

```
IndexError: pop from an empty deque
pika.exceptions.StreamLostError: Stream connection lost: IndexError('pop from an empty deque')
```

### Root Cause

**ปัญหาเกิดจาก Pika Library (RabbitMQ client) เมื่อ:**

1. **Thread Safety Issue**:
   - มีหลาย threads พยายามใช้ connection/channel พร้อมกัน
   - `process_data_events()` ถูกเรียกจาก main thread
   - `publish()` ถูกเรียกจาก worker threads
   - ไม่มีการ synchronize ที่ถูกต้อง

2. **Internal Buffer Issue**:
   - Pika ใช้ `deque` เป็น buffer สำหรับส่งข้อมูล
   - เมื่อหลาย threads เขียน/อ่าน buffer พร้อมกัน → buffer ว่าง → `pop()` จาก empty deque → crash

3. **Connection State Conflict**:
   - Connection ถูกใช้ในหลาย threads
   - Maintenance thread พยายาม reconnect
   - Worker threads พยายาม publish
   - → State conflict → connection lost

### Error Pattern

```
1. Worker เริ่มทำงาน → เชื่อมต่อ RabbitMQ สำเร็จ
2. มี threads หลายตัวใช้ connection พร้อมกัน:
   - Main thread: process_data_events()
   - Worker threads: publish messages
   - Maintenance thread: check/reconnect
3. Buffer conflict → IndexError('pop from an empty deque')
4. Connection lost → StreamLostError
5. Worker crash → ไม่มี consumer
```

## 2. วิธีแก้ไขถาวร

### วิธีที่ 1: ใช้ Connection Pooling (แนะนำ)

แยก connection สำหรับแต่ละ purpose:
- Main connection: สำหรับ consume messages
- Publish connection pool: สำหรับ publish messages จาก threads

**ข้อดี**: แยก connection ชัดเจน ไม่ชนกัน

### วิธีที่ 2: ใช้ Thread-Safe Channel Pooling

สร้าง channel pool ที่ thread-safe:
- แต่ละ thread ใช้ channel ของตัวเอง
- ไม่แชร์ channel ระหว่าง threads

### วิธีที่ 3: ใช้ Auto-Restart Mechanism

สร้าง watchdog/service manager ที่:
- ตรวจสอบ worker status
- Restart worker อัตโนมัติเมื่อ crash
- ใช้ systemd หรือ supervisor

**ข้อดี**: แม้ crash ก็จะ restart อัตโนมัติ

### วิธีที่ 4: Upgrade/Downgrade Pika Version

ลอง version อื่นของ pika ที่มี bug fix:
- ลอง pika 1.3.3 หรือใหม่กว่า
- หรือ downgrade เป็น 1.3.1

### วิธีที่ 5: ปรับปรุง Connection Management

- ปิด publish connection pool (ใช้ main connection แทน)
- หรือใช้ callback-based publishing แทน thread-based

## 3. แนวทางที่แนะนำ (Production-Ready)

### Solution 1: Connection Pooling + Auto-Restart (แนะนำ)

1. **ปรับปรุง Connection Management**:
   - แยก publish connection ให้ชัดเจน
   - ใช้ connection pool สำหรับ publish

2. **เพิ่ม Auto-Restart**:
   - ใช้ systemd service
   - หรือ supervisor
   - หรือ watchdog script

3. **เพิ่ม Health Check**:
   - ตรวจสอบ worker status
   - ตรวจสอบ connection status
   - Auto-recovery

### Solution 2: ใช้ Celery หรือ RQ (Alternative)

แทนที่จะใช้ Pika โดยตรง:
- ใช้ Celery สำหรับ task queue
- ใช้ RQ (Redis Queue)
- มี worker management ที่ดีกว่า

### Solution 3: ใช้ RabbitMQ Client อื่น

แทน pika:
- **aio-pika**: Async RabbitMQ client (ดีกว่า)
- **kombu**: High-level messaging library

## 4. Implementation Plan

### Phase 1: Short-term Fix (ทำทันที)

1. ✅ เพิ่ม infinite retry loop
2. ✅ ปรับปรุง error handling
3. ✅ เพิ่ม auto-restart script

### Phase 2: Medium-term Fix (1-2 สัปดาห์)

1. ✅ แยก publish connection ให้ชัดเจน
2. ✅ เพิ่ม connection pool
3. ✅ ใช้ systemd service

### Phase 3: Long-term Fix (1 เดือน)

1. ✅ พิจารณาใช้ aio-pika หรือ kombu
2. ✅ หรือ migrate ไป Celery

## 5. Code Changes Required

### 5.1 เพิ่ม Infinite Retry Loop

```python
def run(self):
    """เริ่มต้น worker พร้อม infinite retry"""
    while True:  # Infinite loop
        try:
            # Connect and run
            self._run_worker()
        except Exception as e:
            logger.error(f"Worker crashed: {e}")
            logger.info("Restarting worker in 10 seconds...")
            time.sleep(10)
            # Continue loop to retry
```

### 5.2 ใช้ Systemd Service

สร้าง `/etc/systemd/system/video-worker.service`:

```ini
[Unit]
Description=Transcription Video Worker
After=network.target rabbitmq-server.service

[Service]
Type=simple
User=root
WorkingDirectory=/workspace/transcription-service
ExecStart=/usr/bin/python3 -m app.workers.video_worker
Restart=always
RestartSec=10
StandardOutput=append:/tmp/video-worker.log
StandardError=append:/tmp/video-worker.log
Environment="PYTHONPATH=/workspace/transcription-service"
EnvironmentFile=/workspace/transcription-service/.env.runpod

[Install]
WantedBy=multi-user.target
```

### 5.3 ใช้ Connection Pool

```python
class ConnectionPool:
    """Thread-safe connection pool"""
    def __init__(self, max_connections=5):
        self.pool = queue.Queue(maxsize=max_connections)
        # Initialize connections...
    
    def get_connection(self):
        """Get connection from pool"""
        return self.pool.get()
    
    def return_connection(self, conn):
        """Return connection to pool"""
        self.pool.put(conn)
```

## 6. Monitoring และ Alerting

### Health Check Endpoint

```python
@app.get("/health/worker")
async def worker_health():
    """Check worker status"""
    worker_running = check_worker_process()
    rabbitmq_connected = check_rabbitmq_connection()
    
    if worker_running and rabbitmq_connected:
        return {"status": "healthy"}
    else:
        return {"status": "unhealthy", "details": {...}}
```

### Alerting

- ส่ง alert เมื่อ worker crash
- Monitor queue length (ถ้ายาวเกินไป = worker ไม่ทำงาน)
- Monitor worker process status

## 7. สรุป

### ปัญหา

- **Root Cause**: Pika thread safety issue → IndexError → StreamLostError → Worker crash
- **Impact**: Worker หยุดทำงาน → ไม่มี consumer → Queue ค้าง

### วิธีแก้ไข

1. **Short-term**: Auto-restart script + infinite retry
2. **Medium-term**: Connection pooling + systemd service
3. **Long-term**: ใช้ aio-pika หรือ migrate ไป Celery

### Priority

1. ⚠️ **Critical**: Auto-restart mechanism (ทำทันที)
2. 🔧 **High**: Connection pooling (1-2 สัปดาห์)
3. 📊 **Medium**: Monitoring และ alerting (1 เดือน)

