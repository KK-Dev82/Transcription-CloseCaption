# 🔧 Troubleshooting Guide

## ปัญหา: Connection Refused Error

### อาการ
```
aiohttp.client_exceptions.ClientConnectorError: Cannot connect to host 213.173.108.6:14237 ssl:default [Connection refused]
```

### สาเหตุ
- Dashboard พยายามเชื่อมต่อกับ remote server `4000-ada-sc` แต่ server ไม่ได้รันอยู่
- Port mapping ผิด
- Network issue

### วิธีแก้

#### 1. ตรวจสอบว่า Server รันอยู่หรือไม่

```bash
# SSH เข้าไปที่ server
ssh 4000-ada-sc

# ตรวจสอบว่า service รันอยู่หรือไม่
ps aux | grep uvicorn

# ตรวจสอบ port
netstat -tlnp | grep 8010
```

#### 2. Start Service บน Pod

```bash
# SSH เข้าไปที่ pod
ssh 4000-ada-sc

# Start service
cd /workspace/transcription-service
bash scripts/pod/start-service-daemon.sh
```

#### 3. ตรวจสอบ Port Mapping

```bash
# ตรวจสอบว่า port mapping ถูกต้องหรือไม่
# ควรเป็น: External Port 14237 -> Internal Port 8010
```

#### 4. ตรวจสอบ Firewall/Network

```bash
# ทดสอบ connection จาก local
curl http://213.173.108.6:14237/health

# ถ้าไม่ได้ → อาจเป็น firewall หรือ network issue
```

## ปัญหา: Import Errors

### อาการ
```
ModuleNotFoundError: No module named 'aiofiles'
```

### สาเหตุ
- Dependencies ไม่ได้ติดตั้ง
- Virtual environment ไม่ได้ activate

### วิธีแก้

```bash
# ติดตั้ง dependencies
cd /workspace/transcription-service
bash scripts/pod/install-dependencies.sh

# หรือ
pip3 install -r requirements.txt
```

## ปัญหา: Storage Type Error

### อาการ
- Service ไม่สามารถ start ได้
- Error เกี่ยวกับ SQLite หรือ JSON storage

### วิธีแก้

#### 1. ตรวจสอบ Environment Variables

```bash
# ตรวจสอบ STORAGE_TYPE
echo $STORAGE_TYPE

# ควรเป็น: sqlite หรือ json
```

#### 2. ตรวจสอบ Database Path

```bash
# สำหรับ SQLite
ls -lh /workspace/transcription-service/storage/database.db

# ถ้าไม่มี → จะสร้างอัตโนมัติเมื่อ service start
```

#### 3. Migration จาก JSON → SQLite

```bash
# ถ้ามีข้อมูลเก่าใน JSON storage
python3 scripts/migrate_json_to_sqlite.py \
    --json-dir /workspace/transcription-service/storage \
    --sqlite-db /workspace/transcription-service/storage/database.db
```

## ปัญหา: Cleanup Script ไม่ทำงาน

### อาการ
- Script ไม่ลบไฟล์
- Error เมื่อรัน script

### วิธีแก้

#### 1. ตรวจสอบ Permissions

```bash
# ให้ execute permission
chmod +x scripts/cleanup_old_data.py
```

#### 2. Dry Run ก่อน

```bash
# ทดสอบก่อน (ไม่ลบจริง)
python3 scripts/cleanup_old_data.py --dry-run
```

#### 3. ตรวจสอบ Paths

```bash
# ตรวจสอบว่า paths ถูกต้อง
python3 scripts/cleanup_old_data.py \
    --storage-dir /workspace/transcription-service/storage \
    --uploads-dir /workspace/transcription-service/uploads \
    --temp-dir /workspace/transcription-service/temp \
    --dry-run
```

## ปัญหา: Service ไม่ Start

### อาการ
- Service ไม่สามารถ start ได้
- Error เมื่อรัน start-service-daemon.sh

### วิธีแก้

#### 1. ตรวจสอบ Dependencies

```bash
# ตรวจสอบว่า dependencies ติดตั้งแล้วหรือไม่
python3 -c "import uvicorn; print('OK')"
python3 -c "import fastapi; print('OK')"
```

#### 2. ตรวจสอบ Logs

```bash
# ดู logs
tail -f /tmp/transcription-service.log

# หรือ
journalctl -u transcription-service -f
```

#### 3. ตรวจสอบ Port

```bash
# ตรวจสอบว่า port ถูกใช้หรือไม่
lsof -i :8010

# ถ้ามี → kill process เดิม
kill <PID>
```

#### 4. ตรวจสอบ Environment Variables

```bash
# ตรวจสอบ env.runpod
cat env.runpod | grep STORAGE_TYPE
cat env.runpod | grep SAVE_TEMP_FILES

# ควรเป็น:
# STORAGE_TYPE=sqlite
# SAVE_TEMP_FILES=not_save
```

## Checklist สำหรับการ Start Service

1. ✅ Dependencies ติดตั้งแล้ว
2. ✅ Environment variables ถูกต้อง (STORAGE_TYPE, SAVE_TEMP_FILES)
3. ✅ Port ไม่ถูกใช้ (8010)
4. ✅ Directories สร้างแล้ว (storage, uploads, temp)
5. ✅ Redis รันอยู่ (ถ้าใช้)
6. ✅ Timezone data ติดตั้งแล้ว (tzdata)

## Quick Fix Commands

```bash
# 1. Install dependencies
bash scripts/pod/install-dependencies.sh

# 2. Cleanup old data (optional)
python3 scripts/cleanup_old_data.py

# 3. Start service
bash scripts/pod/start-service-daemon.sh

# 4. Check service status
ps aux | grep uvicorn
curl http://localhost:8010/health
```

