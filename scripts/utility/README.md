# 📁 Utility Scripts

Scripts สำหรับการจัดการ Models และ Utilities อื่นๆ

**⚠️ สำคัญ:** ไฟล์นี้เป็นข้อมูลเสริมสำหรับ utility scripts เท่านั้น  
สำหรับการ setup หลัง Restart Pod Container ให้ดูที่ [README.md](../../README.md#-quick-start-หลังจาก-restart-pod-container) แทน

---

## 🚀 Quick Reference: Setup หลัง Restart Pod Container

### ⚠️ สำคัญ: ไฟล์นี้เป็นข้อมูลเสริมสำหรับ utility scripts เท่านั้น  
สำหรับการ setup หลัง Restart Pod Container ให้ดูที่ [README.md](../../README.md#-quick-start-หลังจาก-restart-pod-container) แทน

### ขั้นตอนหลัก (สรุป):

1. **ติดตั้ง System Dependencies:**
   ```bash
   apt-get update
   apt-get install -y ffmpeg
   ```

2. **ติดตั้ง Python Dependencies:**
   ```bash
   cd /workspace/transcription-service
   pip install -r requirements.txt
   ```

3. **ตั้งค่า cuDNN/CTranslate2 (persist LD_LIBRARY_PATH) — รันครั้งเดียวหลัง restart container:**
   ```bash
   ./scripts/utility/setup-cudnn-env.sh
   ```
   - สร้างไฟล์ `scripts/utility/.cudnn-ldpath.sh` ให้ `start-pod.sh` / `start-rq-workers.sh` โหลดอัตโนมัติ
   - ถ้า container มีสิทธิ root จะเขียนลง `/etc/profile.d` และ `/etc/ld.so.conf.d` ด้วย

4. **Start Services:**
   ```bash
   bash scripts/pod/start-pod.sh
   ```
   - Start Whisper API (port 8002)
   - Start Main API (port 8010)

4. **Start RQ Workers:**
   ```bash
   bash scripts/pod/restart-rq-workers.sh
   ```
   - Preprocess workers (6)
   - GPU workers (2 per GPU)
   - CPU workers (2)

### Restart Services:
```bash
# Restart Main API เฉพาะ (ไม่กระทบ services อื่น)
bash scripts/pod/restart-main-api.sh

# Restart ทุก services
bash scripts/pod/restart-pod.sh

# Restart RQ Workers
bash scripts/pod/restart-rq-workers.sh
```

### ตรวจสอบ Status:
```bash
# Health check
curl http://localhost:8010/health
curl http://localhost:8002/health

# Check workers
ps aux | grep "rq worker" | wc -l  # Should be 10+ workers

# Check queue status (ต้องมี REDIS_URL ใน environment)
python3 -c "
from redis import Redis
from rq import Queue
import os
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
conn = Redis.from_url(redis_url, decode_responses=False)
for qname in ['transcription_preprocess', 'transcription_gpu0', 'transcription_gpu1', 'transcription_cpu']:
    q = Queue(qname, connection=conn)
    print(f'{qname}: {len(q)} queued')
"
```

### Port Usage:
- **8010**: Main API (FastAPI) - Public endpoint
- **8002**: Whisper API (Faster-Whisper service) - Internal
- **Redis**: External (RedisLabs) - กำหนดใน `.env.runpod`

### หมายเหตุ:
- **cuDNN & CTranslate2**: รัน `setup-cudnn-env.sh` ครั้งเดียว → persist LD_LIBRARY_PATH + ตรวจสอบ GPU (ดูรายละเอียดด้านล่าง)
- **Models**: ต้องดาวน์โหลดก่อนใช้งาน (ดู `download-models.sh` ด้านล่าง)
- **Environment**: โหลดจาก `.env.runpod` อัตโนมัติ
- **Container**: ไม่ต้องใช้ `sudo` (รันเป็น root อยู่แล้ว)

---

## 📋 Scripts

### `download-models.sh` ⭐
**Download Whisper Models**
- ดาวน์โหลด Whisper models จาก Hugging Face
- รองรับ: tiny, base, small, medium, large, large-v2, large-v3, large-v3-turbo
- รองรับทั้ง Docker Compose และ Direct Mode
- ตรวจสอบและ validate ไฟล์อัตโนมัติ
- เก็บ models ใน `models/` directory

**Usage:**
```bash
# ดาวน์โหลด base model (default)
bash scripts/utility/download-models.sh

# ดาวน์โหลดหลาย models
bash scripts/utility/download-models.sh base small medium

# ดาวน์โหลด base, small, medium (recommended)
bash scripts/utility/download-models.sh --all

# ใช้ whisper.cpp download script (ถ้ามี)
bash scripts/utility/download-models.sh medium --docker-script

# ไม่ restart services หลัง download
bash scripts/utility/download-models.sh base --skip-restart
```

**Options:**
- `--all` - Download base, small, medium models
- `--docker-script` - Use whisper.cpp download script (if available)
- `--skip-restart` - Skip restarting containers/services

**Examples:**
```bash
# Download base model (สำหรับ CPU หรือ testing)
bash scripts/utility/download-models.sh base

# Download medium model (สำหรับ GPU 4080) ⭐ แนะนำ
bash scripts/utility/download-models.sh medium

# Download multiple models
bash scripts/utility/download-models.sh base small medium

# Download all recommended models
bash scripts/utility/download-models.sh --all
```

---

### `setup-cudnn-env.sh` ⭐ (แนะนำหลัง restart container)
**ตั้งค่า cuDNN / CTranslate2 แบบครบในไฟล์เดียว**
- **Persist:** เขียน `LD_LIBRARY_PATH` ลง `scripts/utility/.cudnn-ldpath.sh` → start-pod/start-rq-workers/restart-main-api โหลดอัตโนมัติ
- **ตรวจสอบ:** ตรวจ cuDNN libraries และทดสอบ ctranslate2 + faster-whisper (WhisperModel)
- ถ้า container รันด้วย root: เขียนลง `/etc/profile.d` และ `/etc/ld.so.conf.d` ด้วย

**Usage:**
```bash
# รันครั้งเดียวหลัง apt + pip install (หรือหลัง restart container)
./scripts/utility/setup-cudnn-env.sh
```

---

### `fix-models.sh`
**Fix Missing App Models**
- สร้างไฟล์ models ที่ขาดหายไป
- Copy models จาก whisper-service/models
- ตรวจสอบและแก้ไข permission

**Usage:**
```bash
bash scripts/utility/fix-models.sh
```

**Use Case:**
- เมื่อ models หายไปหรือ permission ผิด
- หลังจาก clone repository ใหม่

---

### `check-pending-tasks.py` ⭐
**ตรวจสอบ Task ที่ค้างอยู่ใน Redis Queue**
- แสดงจำนวน jobs ที่รอ, กำลังทำงาน, และล้มเหลว
- แสดงรายละเอียดของ jobs ที่ค้างอยู่
- ตรวจสอบ task keys ใน Redis

**Usage:**
```bash
python3 scripts/utility/check-pending-tasks.py
```

**Output:**
- สรุป queue status (queued, started, failed)
- รายละเอียด jobs ที่รออยู่ใน queue
- รายละเอียด jobs ที่กำลังทำงาน
- รายละเอียด jobs ที่ล้มเหลว (ล่าสุด 10 jobs)
- จำนวน task keys ใน Redis

**Use Case:**
- เมื่อระบบดูช้า - ตรวจสอบว่ามี task ค้างอยู่หรือไม่
- ตรวจสอบ failed jobs ที่อาจทำให้ระบบช้า
- Monitor queue status

**Example Output:**
```
📊 สรุป Queue Status:
✅ transcription_preprocess | Queued: 0 | Started: 0 | Failed: 4
✅ transcription_cpu         | Queued: 0 | Started: 0 | Failed: 14
...
```

---

## 🔗 Related Files

- `models/` - Directory สำหรับเก็บ Whisper models
- `whisper-service/models/` - Models ใน Whisper service

---

## 📝 Model Information

| Model | Size | VRAM | Speed (GPU 4080) | Accuracy | Use Case |
|-------|------|------|-----------------|----------|----------|
| tiny | ~75MB | ~500MB | ⚡⚡⚡⚡⚡ | ⭐⭐ | Fast testing |
| base | ~148MB | ~1GB | ⚡⚡⚡⚡⚡ | ⭐⭐⭐ | CPU, Fast |
| small | ~488MB | ~2GB | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | Balanced |
| medium | ~1.5GB | ~5GB | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | **GPU 4080** ⭐ |
| large | ~3.1GB | ~10GB | ⚡⚡ | ⭐⭐⭐⭐⭐ | Best accuracy |
| large-v3 | ~3.1GB | ~10GB | ⚡⚡ | ⭐⭐⭐⭐⭐ | Latest model |

**แนะนำ:**
- **CPU:** ใช้ `base` หรือ `small`
- **GPU 4080:** ใช้ `medium` (เทียบเท่า Groq API) ⭐
- **Best Accuracy:** ใช้ `large-v3`

---

### `generate_backfill_sql.py`
**สร้างไฟล์ SQL สำหรับ backfill segments จาก SQLite ไป Postgres**

ใช้เมื่อ: มีข้อมูลเก่าใน SQLite ที่ Postgres ยังมี `SegmentsJson = "[]"`

```bash
# รันบน transcription server (10.200.22.64)
python3 scripts/utility/generate_backfill_sql.py

# กำหนด output path
python3 scripts/utility/generate_backfill_sql.py -o /tmp/backfill.sql
```

Output: ไฟล์ `.sql` → copy ไปรันใน **pgAdmin** (Database: Senate, Server: 10.200.22.59)

---

### `check_storage_status.py`
**ตรวจสอบสถานะข้อมูลใน SQLite และ Transcription Service**

```bash
# ดูภาพรวม
python3 scripts/utility/check_storage_status.py

# ตรวจ task เฉพาะ
python3 scripts/utility/check_storage_status.py --task-id abc123-def456
```

