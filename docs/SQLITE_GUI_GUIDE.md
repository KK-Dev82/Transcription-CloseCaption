# SQLite GUI Guide

คู่มือการใช้งาน SQLite GUI สำหรับ Transcription Service โดยไม่ต้องติดตั้งบน MacOS

## วิธีที่ 1: ใช้ phpLiteAdmin (แนะนำ) ⭐

โปรเจกต์มี **phpLiteAdmin** ติดตั้งไว้แล้วใน Dashboard

### การใช้งาน

1. **เริ่ม Dashboard** (ถ้ายังไม่ได้เริ่ม):
```bash
cd dashboard
python main.py
# หรือ
uvicorn dashboard.main:app --host 0.0.0.0 --port 8020
```

2. **เปิด Browser** ไปที่:
```
http://localhost:8020/sqlite-admin/
```

3. **เลือก Database**:
   - Database path: `/app/storage/database.db` (ใน container)
   - หรือ `storage/database.db` (ใน local)

### ข้อดี
- ✅ ไม่ต้องติดตั้งอะไรบน MacOS
- ✅ ทำงานผ่าน Web Browser
- ✅ มีอยู่แล้วในโปรเจกต์
- ✅ รองรับการดู/แก้ไข/Export ข้อมูล

---

## วิธีที่ 2: ใช้ Docker Container สำหรับ SQLite Browser

### การติดตั้ง

1. **รัน SQLite Browser Container**:
```bash
docker compose -f docker-compose.sqlite-gui.yml up -d
```

2. **เปิด Browser** ไปที่:
```
http://localhost:8080
```

3. **เปิด Database**:
   - Navigate ไปที่ `/storage/database.db`
   - หรือ `/workspace/transcription-service/storage/database.db`

### ข้อดี
- ✅ ไม่ต้องติดตั้งบน MacOS
- ✅ GUI ที่ใช้งานง่าย
- ✅ รองรับการดู/แก้ไข/Export ข้อมูล

### การหยุด Container
```bash
docker compose -f docker-compose.sqlite-gui.yml down
```

---

## วิธีที่ 3: ใช้ SQLite CLI ใน Container

### การใช้งาน

1. **เข้า Container**:
```bash
# ถ้าใช้ Docker Compose
docker compose exec <service-name> bash

# หรือถ้าใช้ Pod
# เข้า Pod ผ่าน SSH/Terminal
```

2. **ใช้ SQLite CLI**:
```bash
sqlite3 /app/storage/database.db

# ตัวอย่างคำสั่ง
.tables                    # ดู tables ทั้งหมด
.schema                    # ดู schema
SELECT * FROM transcriptions LIMIT 10;
.quit                      # ออกจาก SQLite
```

### ข้อดี
- ✅ ไม่ต้องติดตั้งบน MacOS
- ✅ มีอยู่แล้วใน Container
- ✅ ใช้ได้ทันที

---

## วิธีที่ 4: Mount Volume แล้วใช้ GUI Tools ใน Docker

### การใช้งาน

1. **ตรวจสอบว่า Storage Directory ถูก Mount**:
```bash
# ตรวจสอบว่า storage directory อยู่ในเครื่อง local
ls -la storage/
```

2. **ใช้ Docker Container สำหรับ SQLite GUI**:
```bash
# รัน SQLite Browser โดย mount storage directory
docker run -d \
  --name sqlite-browser \
  -p 8080:3000 \
  -v $(pwd)/storage:/storage:ro \
  linuxserver/sqlitebrowser:latest
```

3. **เปิด Browser** ไปที่:
```
http://localhost:8080
```

### ข้อดี
- ✅ ไม่ต้องติดตั้งบน MacOS
- ✅ ใช้ไฟล์ Database จากเครื่อง local โดยตรง
- ✅ GUI ที่ใช้งานง่าย

---

## สรุป

| วิธี | ติดตั้งบน MacOS | ความยาก | แนะนำ |
|------|----------------|---------|-------|
| phpLiteAdmin | ❌ ไม่ต้อง | ⭐ ง่าย | ⭐⭐⭐⭐⭐ |
| Docker SQLite Browser | ❌ ไม่ต้อง | ⭐⭐ ปานกลาง | ⭐⭐⭐⭐ |
| SQLite CLI | ❌ ไม่ต้อง | ⭐⭐⭐ ยาก | ⭐⭐⭐ |
| Mount Volume + Docker | ❌ ไม่ต้อง | ⭐⭐ ปานกลาง | ⭐⭐⭐ |

**แนะนำ**: ใช้ **phpLiteAdmin** (วิธีที่ 1) เพราะ:
- มีอยู่แล้วในโปรเจกต์
- ไม่ต้องติดตั้งอะไรเพิ่ม
- ใช้งานง่ายผ่าน Web Browser

---

## Troubleshooting

### phpLiteAdmin ไม่ทำงาน

1. **ตรวจสอบว่า PHP ติดตั้งแล้ว**:
```bash
php --version
```

2. **ติดตั้ง PHP** (ถ้ายังไม่มี):
```bash
# ใน Container
apt-get update && apt-get install -y php php-cli php-sqlite3

# หรือใช้ script ที่มีอยู่
bash scripts/pod/install-sqlite-admin.sh
```

3. **ตรวจสอบว่า Database Path ถูกต้อง**:
```bash
# ตรวจสอบ path ใน config.php
cat dashboard/sqlite_admin/config.php
```

### Docker Container ไม่ทำงาน

1. **ตรวจสอบว่า Container รันอยู่**:
```bash
docker ps | grep sqlite
```

2. **ดู Logs**:
```bash
docker logs sqlite-browser
```

3. **ตรวจสอบ Port**:
```bash
# ตรวจสอบว่า port 8080 ไม่ถูกใช้งาน
lsof -i :8080
```

---

## Database Path

- **ใน Container**: `/app/storage/database.db`
- **ใน Local**: `storage/database.db`
- **ใน Pod**: `/workspace/transcription-service/storage/database.db`

---

## Security Notes

⚠️ **สำคัญ**: 
- ใช้ `:ro` (read-only) เมื่อ mount volume เพื่อความปลอดภัย
- ตั้ง Password ใน `config.php` ถ้าใช้ phpLiteAdmin ใน Production
- อย่า expose SQLite Admin ไปยัง Public Internet โดยไม่มีการ Authentication

