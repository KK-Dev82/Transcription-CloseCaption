# Reset Database Guide

## วิธี Reset Database บน Pod

### วิธีที่ 1: ใช้ Script อัตโนมัติ (แนะนำ)

```bash
# บน Pod
cd /workspace/transcription-service

# Pull code และ reset database
./scripts/pod/update-and-reset.sh
```

### วิธีที่ 2: ทำทีละขั้นตอน

```bash
# 1. Pull code
cd /workspace/transcription-service
git pull

# 2. Reset database
./scripts/pod/reset-database.sh

# 3. Restart service
./scripts/pod/start-service-daemon.sh
```

### วิธีที่ 3: ลบ database ด้วยตนเอง

```bash
# บน Pod
cd /workspace/transcription-service

# ลบ database
rm -f storage/database.db
rm -f storage/database.db-journal
rm -f storage/database.db-wal
rm -f storage/database.db-shm

# Restart service (จะสร้าง database ใหม่อัตโนมัติ)
./scripts/pod/start-service-daemon.sh
```

## สิ่งที่ Script ทำ

1. **Pull Code**: ดึง code ล่าสุดจาก git
2. **Backup Database**: สร้าง backup ของ database เก่า (ถ้ามี)
3. **Remove Database**: ลบ database และ journal files
4. **Optional JSON Cleanup**: ลบ JSON storage เก่า (ถ้าต้องการ)
5. **Restart Service**: Service จะสร้าง database ใหม่ด้วย schema ที่ถูกต้อง

## หมายเหตุ

- Database ใหม่จะถูกสร้างอัตโนมัติเมื่อ service เริ่มทำงาน
- Schema จะถูก migrate อัตโนมัติโดย `sqlite_storage.py`
- ข้อมูลเก่าจะถูกลบทั้งหมด (ไม่มี backup ถ้าไม่ใช้ script)

## Troubleshooting

### ถ้า service ไม่ start

```bash
# ตรวจสอบ logs
tail -f logs/app.log

# ตรวจสอบว่า database ถูกสร้างหรือไม่
ls -lh storage/database.db

# ตรวจสอบ schema
sqlite3 storage/database.db ".schema transcriptions"
```

### ถ้า git pull failed

```bash
# ตรวจสอบ git status
git status

# Force pull (ระวัง: จะทับ local changes)
git fetch origin
git reset --hard origin/main
```

