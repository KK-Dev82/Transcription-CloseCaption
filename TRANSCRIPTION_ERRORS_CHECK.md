# 📋 คู่มือตรวจสอบ Transcription Errors และ Queue Issues

## 🔍 วิธีตรวจสอบ Errors

### 1. ตรวจสอบ Errors ทั้งหมด
```bash
# นับจำนวน errors
grep -c "ERROR\|CRITICAL" logs/transcription.log

# ดู errors ล่าสุด
grep -E "ERROR|CRITICAL" logs/transcription.log | tail -20

# ดู errors ที่ไม่ใช่ model size
grep -E "ERROR|CRITICAL" logs/transcription.log | grep -v "Invalid model size" | tail -20
```

### 2. ตรวจสอบ Transcription Results
```bash
# นับ jobs ที่ได้ 0 segments
grep -c "0 segments" logs/transcription.log

# ดู transcription results ล่าสุด
grep "Transcription completed" logs/transcription.log | tail -20

# ดูสถิติ segments
grep "Transcription completed.*segments" logs/transcription.log | grep -oE "[0-9]+ segments" | sort | uniq -c
```

### 3. ตรวจสอบ Queue Status
```bash
# ตรวจสอบ Redis connection (ใช้ REDIS_URL จาก .env.runpod)
python3 << 'EOF'
import os
from pathlib import Path
from redis import Redis

# โหลด .env.runpod
try:
    from dotenv import load_dotenv
    env_file = Path(".env.runpod")
    if env_file.exists():
        load_dotenv(env_file)
except:
    pass

redis_url = os.getenv('REDIS_URL')
if redis_url:
    conn = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=10)
    print(f"✅ Redis connection: {conn.ping()}")
else:
    print("❌ REDIS_URL not set")
EOF

# ตรวจสอบ queue lengths (ใช้ REDIS_URL จาก .env.runpod)
python3 << 'EOF'
import os
from pathlib import Path
from redis import Redis
from rq import Queue

# โหลด .env.runpod
try:
    from dotenv import load_dotenv
    env_file = Path(".env.runpod")
    if env_file.exists():
        load_dotenv(env_file)
except:
    pass

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
conn = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=10)
queues = ['gpu0', 'gpu1', 'cpu0', 'cpu1', 'preprocess0', 'preprocess1', 'PRIORITY', 'failed']

for queue_name in queues:
    queue = Queue(queue_name, connection=conn)
    length = len(queue)
    if length > 0:
        print(f"{queue_name}: {length} jobs")
EOF
```

## ⚠️ ปัญหาที่พบบ่อย

### 1. "0 segments" - ไม่มีเสียงหรือเสียงไม่ชัด
**สาเหตุ:**
- Audio chunk ไม่มีเสียง
- เสียงเบาเกินไป
- Audio format ไม่ถูกต้อง

**วิธีแก้ไข:**
- ตรวจสอบ audio input
- เพิ่ม VAD threshold
- ตรวจสอบ audio format

### 2. "Invalid model size" - Model ID ไม่ถูกต้อง
**สาเหตุ:**
- ใช้ cache directory name แทน HuggingFace model ID
- Model ไม่รองรับ

**วิธีแก้ไข:**
- ✅ แก้ไขแล้ว: ใช้ `_normalize_model_id()` เพื่อแปลงอัตโนมัติ

### 3. Queue Timeout/Expiration
**การตั้งค่า:**
- `job_timeout`: 3600 seconds (1 hour)
- `result_ttl`: 43200 seconds (12 hours)

**ตรวจสอบ:**
- ไม่พบ logs เกี่ยวกับ timeout
- Jobs ควรเสร็จภายใน 1 hour

## 📊 Timeout Configuration

### RQ Job Timeouts
- **Transcription jobs**: 3600 seconds (1 hour)
- **Preprocess jobs**: 1800 seconds (30 minutes)
- **Live chunk jobs**: 300 seconds (5 minutes)

### Result TTL
- **Default**: 43200 seconds (12 hours)
- **Live chunk**: 3600 seconds (1 hour)

### Redis Chunk TTL
- **Default**: 43200 seconds (12 hours)
- **Environment**: `REDIS_CHUNK_TTL_SECONDS`

## 🔍 วิธีตรวจสอบ Jobs ที่หลุด

### 1. ตรวจสอบ Failed Jobs
```bash
# ใช้ RQ dashboard
rq-dashboard

# หรือใช้ redis-cli
redis-cli
> LLEN rq:queue:failed
> LRANGE rq:queue:failed 0 -1
```

### 2. ตรวจสอบ Jobs ที่รอนาน
```bash
# ตรวจสอบ jobs ใน queue
python3 << 'EOF'
from redis import Redis
from rq import Queue
from datetime import datetime

conn = Redis.from_url('redis://localhost:6379')
queue = Queue('gpu0', connection=conn)

for job_id in queue.job_ids:
    job = queue.job_class.fetch(job_id, connection=conn)
    if job:
        created_at = job.created_at
        if created_at:
            age = (datetime.now() - created_at).total_seconds()
            if age > 3600:  # มากกว่า 1 hour
                print(f"⚠️ Job {job_id} รอนาน: {age/60:.1f} minutes")
EOF
```

### 3. ตรวจสอบ Stuck Tasks
```bash
# ดู logs ของ stuck task detection
grep -i "stuck\|timeout\|expired" logs/*.log | tail -20
```

## 📝 Log Patterns ที่สำคัญ

### Errors
- `ERROR` - ข้อผิดพลาดทั่วไป
- `CRITICAL` - ข้อผิดพลาดร้ายแรง
- `Exception` - Exception ที่เกิดขึ้น
- `Traceback` - Stack trace

### Timeout/Expiration
- `timeout` - Job timeout
- `expired` - Result expired
- `TTL` - Time to live
- `stuck` - Task stuck

### Queue Issues
- `queue.*full` - Queue เต็ม
- `rejected` - Job ถูก reject
- `dropped` - Job ถูก drop

## 🔧 คำสั่งที่มีประโยชน์

```bash
# ดู errors ทั้งหมด
grep -E "ERROR|CRITICAL" logs/*.log | tail -50

# ดู transcription results
grep "Transcription completed" logs/transcription.log | tail -30

# ดู jobs ที่ enqueued
grep "enqueued" logs/main-api.log | tail -20

# ดู jobs ที่ failed
grep "failed\|Failed" logs/*.log | tail -20

# ดู timeout/expiration
grep -i "timeout\|expired\|TTL" logs/*.log | tail -20
```
