# 📋 สรุปการแก้ไขและ Restart Pod Container

## ✅ การแก้ไขที่ทำไป (ทั้งหมดอยู่ถาวรแล้ว)

### 1. Resource Monitor Script
- **File:** `scripts/monitor_resources.py`
- **หน้าที่:** Monitor CPU, RAM, GPU usage และบันทึกไปที่ `/workspace/resource_usage.log`
- **สถานะ:** ✅ สร้างเสร็จแล้ว (อยู่ถาวร)
- **ต้องทำซ้ำ:** ❌ ไม่ต้อง

### 2. Enhanced Test Script
- **File:** `scripts/test_5_jobs_with_monitoring.py`
- **หน้าที่:** ทดสอบ 5 jobs พร้อมติดตาม GPU, SQLite, Redis
- **สถานะ:** ✅ สร้างเสร็จแล้ว (อยู่ถาวร)
- **ต้องทำซ้ำ:** ❌ ไม่ต้อง

### 3. Clear Stale Workers Script
- **File:** `scripts/pod/clear-stale-workers.py`
- **หน้าที่:** ลบ stale worker registrations จาก Redis
- **สถานะ:** ✅ สร้างเสร็จแล้ว (อยู่ถาวร)
- **ต้องทำซ้ำ:** ❌ ไม่ต้อง

### 4. แก้ไข start-rq-workers.sh
- **การเปลี่ยนแปลง:** เพิ่มการ clear stale worker registrations ก่อน start workers
- **สถานะ:** ✅ แก้ไขเสร็จแล้ว (อยู่ใน script)
- **ต้องทำซ้ำ:** ❌ ไม่ต้อง

---

## 🔄 เมื่อ Restart Pod Container

### ✅ ระบบจะทำงานอัตโนมัติ

เมื่อ restart Pod Container และเรียก `scripts/pod/start-rq-workers.sh` ระบบจะ:

1. **Kill workers เดิม** - อัตโนมัติ
   ```bash
   pkill -f "rq worker.*transcription_gpu"
   pkill -f "rq worker.*transcription_preprocess"
   # ... และอื่นๆ
   ```

2. **Clear stale registrations** - อัตโนมัติ
   ```bash
   python3 scripts/pod/clear-stale-workers.py
   ```

3. **Start workers ใหม่** - อัตโนมัติ
   - GPU workers (5 workers per GPU)
   - Preprocess workers (2 workers)
   - CPU workers (2 workers)

### ⚠️ ไม่ต้องทำอะไรเพิ่มเติม

- ✅ ไม่ต้อง clear stale registrations เอง
- ✅ ไม่ต้อง kill workers เอง
- ✅ ไม่ต้องแก้ไข script อีก

**ระบบจะทำงานอัตโนมัติทุกครั้งที่ restart**

---

## 📝 การใช้งาน Scripts

### Resource Monitor
```bash
# Start monitor ใน background
nohup python3 scripts/monitor_resources.py > /workspace/monitor_resources.log 2>&1 &

# ดู logs
tail -f /workspace/resource_usage.log
```

### Test Script
```bash
# Run test
python3 scripts/test_5_jobs_with_monitoring.py
```

### Clear Stale Workers (ถ้าต้องการใช้แยก)
```bash
# Clear stale workers manually
python3 scripts/pod/clear-stale-workers.py
```

---

## 🔍 ตรวจสอบสถานะ

### ตรวจสอบ Workers
```bash
ps aux | grep "rq worker" | grep -v grep
```

### ตรวจสอบ Queue
```bash
python3 << 'EOF'
import redis
import os
from dotenv import load_dotenv

load_dotenv('.env.runpod')
r = redis.from_url(os.getenv('REDIS_URL'), decode_responses=True)

queues = ['transcription_priority', 'transcription_preprocess', 'transcription_gpu0', 'transcription_cpu']
for queue in queues:
    length = r.llen(f'rq:queue:{queue}')
    print(f"{queue}: {length} jobs")
EOF
```

### ตรวจสอบ Worker Logs
```bash
# GPU workers
tail -f /tmp/rq-worker-gpu0-w0.log

# Preprocess workers
tail -f /tmp/rq-worker-preprocess-0.log

# CPU workers
tail -f /tmp/rq-worker-cpu-0.log
```

---

## 🎯 สรุป

**✅ การแก้ไขทั้งหมดอยู่ถาวรแล้ว - ไม่ต้องทำซ้ำทุกครั้งที่ restart**

**✅ ระบบจะทำงานอัตโนมัติเมื่อ restart Pod Container**

**✅ เพียงเรียก `scripts/pod/start-rq-workers.sh` - ทุกอย่างจะทำงานอัตโนมัติ**
