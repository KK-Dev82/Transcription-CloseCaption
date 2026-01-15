# SQLite GUI Architecture - คำอธิบาย

## 📋 สถานการณ์ปัจจุบัน

### Services ที่ทำงานอยู่:
1. **Transcription Service** - Port **8010**
   - Path: `app.main:app`
   - ใช้สำหรับ API endpoints หลัก
   
2. **Dashboard** - Port **8020**
   - Path: `dashboard/main.py`
   - ใช้สำหรับ Dashboard UI และ monitoring

**ทั้งสองทำงานใน Container เดียวกัน (Pod)**

---

## ❓ คำถามและคำตอบ

### 1. ต้องติดตั้ง SQLite GUI ที่ Container เลยใช่ไหม?

**คำตอบ: ✅ ใช่**

- SQLite GUI (phpLiteAdmin) ต้องติดตั้ง PHP และ SQLite extension ที่ Container
- ไม่สามารถติดตั้งเฉพาะที่ Dashboard ได้ เพราะ Dashboard เป็นแค่ Python FastAPI application
- PHP ต้องติดตั้งที่ระบบ (Container) เพื่อรัน phpLiteAdmin

```bash
# ติดตั้งที่ Container
sudo apt-get install -y php php-cli php-sqlite3
```

---

### 2. ถ้าติดตั้งผ่าน Container แล้ว ไม่จำเป็นต้องใช้ผ่าน Dashboard หรือเปล่า?

**คำตอบ: ❌ ไม่ใช่**

**phpLiteAdmin ต้องใช้ผ่าน Dashboard (Port 8020) เท่านั้น** เพราะ:

1. **phpLiteAdmin เป็น PHP application** - ต้องมี web server เพื่อ serve PHP files
2. **Dashboard มี route สำหรับ serve phpLiteAdmin** - `/sqlite-admin/` route ใน Dashboard
3. **Transcription Service (8010) ไม่มี route สำหรับ phpLiteAdmin** - ไม่มี code สำหรับ serve PHP files

**การทำงาน:**
```
Browser → http://localhost:8020/sqlite-admin/
          ↓
Dashboard (FastAPI) → Execute PHP → phpLiteAdmin
          ↓
SQLite Database
```

---

### 3. ถ้าติดตั้งผ่าน apt หมายความว่าใช้ผ่าน 8010, 8020 ได้ใช่ไหม?

**คำตอบ: ❌ ไม่ได้ - ใช้ได้เฉพาะผ่าน Port 8020 (Dashboard) เท่านั้น**

### ทำไมใช้ได้เฉพาะ Port 8020?

1. **Port 8010 (Transcription Service)**
   - ❌ **ไม่มี route สำหรับ phpLiteAdmin**
   - ❌ **ไม่มี code สำหรับ serve PHP files**
   - ✅ **มีแค่ API endpoints สำหรับ transcription**

2. **Port 8020 (Dashboard)**
   - ✅ **มี route `/sqlite-admin/`** สำหรับ phpLiteAdmin
   - ✅ **มี code สำหรับ execute PHP** (ดู `dashboard/routes/sqlite_admin_routes.py`)
   - ✅ **มี route handler** สำหรับ serve phpLiteAdmin

### สรุป:
```
✅ ใช้ได้: http://localhost:8020/sqlite-admin/
❌ ใช้ไม่ได้: http://localhost:8010/sqlite-admin/  (ไม่มี route นี้)
```

---

## 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│           Container (Pod)                        │
│                                                  │
│  ┌──────────────────────────────────────────┐  │
│  │  Transcription Service (Port 8010)       │  │
│  │  - app.main:app                          │  │
│  │  - API endpoints                         │  │
│  │  - ❌ ไม่มี phpLiteAdmin route          │  │
│  └──────────────────────────────────────────┘  │
│                                                  │
│  ┌──────────────────────────────────────────┐  │
│  │  Dashboard (Port 8020)                   │  │
│  │  - dashboard/main.py                     │  │
│  │  - ✅ มี /sqlite-admin/ route           │  │
│  │  - ✅ Execute PHP → phpLiteAdmin        │  │
│  └──────────────────────────────────────────┘  │
│                                                  │
│  ┌──────────────────────────────────────────┐  │
│  │  PHP (ติดตั้งที่ Container)              │  │
│  │  - php, php-cli, php-sqlite3            │  │
│  │  - ใช้โดย Dashboard route               │  │
│  └──────────────────────────────────────────┘  │
│                                                  │
│  ┌──────────────────────────────────────────┐  │
│  │  SQLite Database                         │  │
│  │  - /workspace/transcription-service/    │  │
│  │    storage/database.db                   │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## 🔄 Flow การทำงาน

### เมื่อเปิด SQLite GUI:

```
1. User → Browser → http://localhost:8020/sqlite-admin/
                            ↓
2. Dashboard (Port 8020) รับ request
                            ↓
3. Route: /sqlite-admin/phpliteadmin.php
                            ↓
4. Dashboard execute: php phpliteadmin.php
                            ↓
5. PHP (ติดตั้งที่ Container) process PHP file
                            ↓
6. phpLiteAdmin → อ่าน config.php
                            ↓
7. phpLiteAdmin → เข้าถึง SQLite Database
                            ↓
8. Dashboard → ส่ง HTML response กลับ
                            ↓
9. Browser → แสดง phpLiteAdmin UI
```

---

## ✅ สรุป

| คำถาม | คำตอบ |
|-------|-------|
| ต้องติดตั้งที่ Container? | ✅ ใช่ - PHP ต้องติดตั้งที่ระบบ |
| ไม่ต้องใช้ผ่าน Dashboard? | ❌ ไม่ใช่ - ต้องใช้ผ่าน Dashboard (8020) |
| ใช้ผ่าน 8010 ได้ไหม? | ❌ ไม่ได้ - ไม่มี route สำหรับ phpLiteAdmin |
| ใช้ผ่าน 8020 ได้ไหม? | ✅ ได้ - Dashboard มี route `/sqlite-admin/` |

---

## 🚀 วิธีใช้งาน

### 1. ติดตั้ง PHP (ที่ Container)
```bash
sudo apt-get update
sudo apt-get install -y php php-cli php-sqlite3
```

### 2. Download phpLiteAdmin
```bash
cd dashboard/sqlite_admin
curl -L -o phpliteadmin.php https://raw.githubusercontent.com/phpLiteAdmin/pla/master/phpliteadmin.php
```

### 3. เริ่ม Dashboard (ถ้ายังไม่ได้เริ่ม)
```bash
cd dashboard
bash start-daemon.sh
```

### 4. เปิด Browser
```
http://localhost:8020/sqlite-admin/
```

---

## 💡 ทางเลือกอื่น

### ถ้าต้องการใช้ผ่าน Port 8010

ต้องเพิ่ม route ที่ Transcription Service:

```python
# ใน app/main.py
@router.get("/sqlite-admin/")
async def sqlite_admin():
    # Similar code to dashboard/routes/sqlite_admin_routes.py
    ...
```

แต่ **ไม่แนะนำ** เพราะ:
- Transcription Service ควรทำหน้าที่ API หลัก
- Dashboard ควรทำหน้าที่ UI และ admin tools

---

## 📚 Related Files

- `dashboard/routes/sqlite_admin_routes.py` - Route handler สำหรับ phpLiteAdmin
- `dashboard/sqlite_admin/config.php` - Configuration สำหรับ phpLiteAdmin
- `scripts/install-sqlite-gui.sh` - Script สำหรับติดตั้ง SQLite GUI
