# SQLite GUI - Quick Start Guide

## 🚀 ติดตั้ง SQLite GUI (phpLiteAdmin)

### วิธีที่ 1: ใช้ Script (แนะนำ)

```bash
# ติดตั้ง SQLite GUI
sudo bash scripts/install-sqlite-gui.sh
```

### วิธีที่ 2: ติดตั้งด้วยตนเอง

```bash
# 1. ติดตั้ง PHP
sudo apt-get update
sudo apt-get install -y php php-cli php-sqlite3

# 2. Download phpLiteAdmin
cd dashboard/sqlite_admin
curl -L -o phpliteadmin.php https://raw.githubusercontent.com/phpLiteAdmin/pla/master/phpliteadmin.php

# 3. ตรวจสอบ config.php
cat config.php
```

---

## 📊 ใช้งาน SQLite GUI

### 1. เริ่ม Dashboard (ถ้ายังไม่ได้เริ่ม)

```bash
cd dashboard
bash start-daemon.sh
```

### 2. เปิด Browser

ไปที่: **http://localhost:8020/sqlite-admin/**

### 3. เลือก Database

- คลิกที่ **database.db** ในรายการ
- Database อยู่ที่: `/workspace/transcription-service/storage/database.db`

---

## ✅ ตรวจสอบการติดตั้ง

```bash
# ตรวจสอบว่า PHP ติดตั้งแล้ว
php --version

# ตรวจสอบว่า phpLiteAdmin มีอยู่
ls -la dashboard/sqlite_admin/phpliteadmin.php

# ตรวจสอบสถานะผ่าน Dashboard API
curl http://localhost:8020/sqlite-admin/status
```

---

## 🐛 Troubleshooting

### phpLiteAdmin ไม่แสดง

1. **ตรวจสอบว่า Dashboard ทำงานอยู่:**
```bash
cd dashboard
bash status-daemon.sh
```

2. **ตรวจสอบว่า PHP ติดตั้งแล้ว:**
```bash
php --version
```

3. **ตรวจสอบว่าไฟล์มีอยู่:**
```bash
ls -la dashboard/sqlite_admin/phpliteadmin.php
```

### Error: PHP is not installed

```bash
sudo apt-get update
sudo apt-get install -y php php-cli php-sqlite3
```

### Database ไม่แสดง

ตรวจสอบว่า path ใน `config.php` ถูกต้อง:
```bash
cat dashboard/sqlite_admin/config.php
```

แก้ไข path ถ้าจำเป็น:
```bash
# แก้ไข $directory ใน config.php
nano dashboard/sqlite_admin/config.php
```

---

## 🎯 วิธีอื่นๆ

### ใช้ Python Script (ไม่ต้องติดตั้ง GUI)

```bash
cd dashboard
python3 view_sqlite.py
```

### ใช้ SQLite CLI

```bash
sqlite3 storage/database.db
```

---

## 📚 ดูคู่มือเต็ม: `docs/SQLITE_GUI_GUIDE.md`
