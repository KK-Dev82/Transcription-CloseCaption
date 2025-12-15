# การติดตั้ง PHP บน PodContainer - ข้อควรระวัง

## ⚠️ ปัญหาที่อาจเกิดขึ้น

### 1. **ไม่มี sudo**
- **ปัญหา**: PodContainer อาจไม่มี `sudo` command
- **สาเหตุ**: Container มักรันเป็น root user อยู่แล้ว ไม่ต้องใช้ sudo
- **แก้ไข**: Script จะตรวจสอบว่าเป็น root หรือไม่ และใช้ sudo เฉพาะเมื่อจำเป็น

### 2. **ไม่มี Package Manager**
- **ปัญหา**: Base image อาจเป็น minimal image ที่ไม่มี `apt-get` หรือ `yum`
- **สาเหตุ**: 
  - Minimal images เพื่อลดขนาด
  - หรือใช้ base image ที่ไม่ใช่ Ubuntu/Debian/CentOS
- **แก้ไข**: 
  - ใช้ base image ที่มี package manager
  - หรือติดตั้ง PHP แบบ manual (compile from source)

### 3. **Container ใหญ่ขึ้น**
- **ปัญหา**: การติดตั้ง PHP และ dependencies จะทำให้ container ใหญ่ขึ้น
- **ผลกระทบ**: 
  - ใช้ disk space มากขึ้น (~50-100MB)
  - Pull/push image ช้าลง
- **แนะนำ**: 
  - ใช้ multi-stage build
  - หรือติดตั้ง PHP เฉพาะเมื่อจำเป็น

### 4. **Permission Issues**
- **ปัญหา**: ไม่สามารถติดตั้ง package ได้เพราะไม่มี permission
- **สาเหตุ**: 
  - ไม่ใช่ root user
  - ไม่มี sudo
  - Container มี security restrictions
- **แก้ไข**: 
  - ตรวจสอบว่าเป็น root: `whoami` หรือ `id`
  - หรือใช้ base image ที่มี sudo

## ✅ วิธีแก้ไข

### วิธีที่ 1: ใช้ Script ที่แก้ไขแล้ว (แนะนำ)

Script จะตรวจสอบและจัดการอัตโนมัติ:

```bash
cd /workspace/transcription-service
git pull  # ดึง script ที่แก้ไขแล้ว
bash scripts/pod/install-sqlite-admin.sh
```

### วิธีที่ 2: ติดตั้ง PHP แบบ Manual (ถ้า script ไม่ได้)

```bash
# ตรวจสอบว่าเป็น root หรือไม่
whoami

# ถ้าเป็น root (ไม่ต้องใช้ sudo)
apt-get update
apt-get install -y php php-cli php-sqlite3

# ถ้าไม่ใช่ root และมี sudo
sudo apt-get update
sudo apt-get install -y php php-cli php-sqlite3
```

### วิธีที่ 3: ใช้ Base Image ที่มี PHP อยู่แล้ว

แก้ไข Dockerfile หรือ RunPod Template:

```dockerfile
# ใช้ base image ที่มี PHP
FROM php:8.2-cli

# หรือติดตั้ง PHP ใน Dockerfile
RUN apt-get update && apt-get install -y \
    php \
    php-cli \
    php-sqlite3 \
    && rm -rf /var/lib/apt/lists/*
```

### วิธีที่ 4: ใช้ Alternative (ไม่ต้องติดตั้ง PHP)

#### Option A: ใช้ Command Line (sqlite3)
```bash
sqlite3 /workspace/transcription-service/storage/database.db
```

#### Option B: ใช้ VS Code Remote
1. Install VS Code Remote extension
2. Connect to PodContainer via SSH
3. Install "SQLite Viewer" extension
4. เปิดไฟล์ `storage/database.db`

#### Option C: ใช้ Adminer (ยังต้องมี PHP)
- Adminer เป็น single PHP file
- แต่ยังต้องมี PHP runtime

## 📋 ตรวจสอบ Base Image

### ตรวจสอบว่าใช้ base image อะไร

```bash
# ดู base image
cat Dockerfile | grep FROM

# หรือดูใน RunPod Template
# ไปที่ Pod Template → Container Image
```

### Base Images ที่แนะนำ

1. **RunPod Template Images** (มี apt-get):
   - `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`
   - `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`

2. **Ubuntu-based Images** (มี apt-get):
   - `ubuntu:22.04`
   - `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime`

3. **Minimal Images** (อาจไม่มี package manager):
   - `alpine:latest` (ใช้ `apk` แทน `apt-get`)
   - `scratch` (ไม่มีอะไรเลย)

## 🔍 Troubleshooting

### ปัญหา: "sudo: command not found"

**แก้ไข:**
```bash
# ตรวจสอบว่าเป็น root หรือไม่
whoami

# ถ้าเป็น root (แสดง "root") ไม่ต้องใช้ sudo
apt-get update
apt-get install -y php php-cli php-sqlite3

# ถ้าไม่ใช่ root และไม่มี sudo
# ต้องใช้ base image ที่มี sudo หรือรัน container เป็น root
```

### ปัญหา: "apt-get: command not found"

**สาเหตุ:**
- Base image ไม่ใช่ Ubuntu/Debian
- หรือเป็น minimal image

**แก้ไข:**
```bash
# ตรวจสอบ OS
cat /etc/os-release

# ถ้าเป็น Alpine (ใช้ apk)
apk add --no-cache php php-cli php-sqlite3

# ถ้าเป็น CentOS/RHEL (ใช้ yum)
yum install -y php php-cli php-pdo php-sqlite3
```

### ปัญหา: "Permission denied"

**แก้ไข:**
```bash
# ตรวจสอบ permission
id

# ถ้าไม่ใช่ root และไม่มี sudo
# ต้องแก้ไข Dockerfile หรือ RunPod Template
# หรือรัน container เป็น root user
```

## 💡 คำแนะนำ

### สำหรับ PodContainer (RunPod)

1. **ใช้ RunPod Template Images** (แนะนำ):
   - มี apt-get พร้อมแล้ว
   - ไม่ต้องติดตั้งอะไรเพิ่ม
   - Optimized สำหรับ RunPod

2. **ถ้าต้องติดตั้ง PHP**:
   - ใช้ script ที่แก้ไขแล้ว (รองรับกรณีไม่มี sudo)
   - หรือติดตั้งใน Dockerfile/Base Image

3. **Alternative (ไม่ต้องติดตั้ง PHP)**:
   - ใช้ command line (sqlite3) - เร็วและง่าย
   - ใช้ VS Code Remote + SQLite Viewer

### สำหรับ Production

1. **ติดตั้ง PHP ใน Base Image**:
   - แก้ไข Dockerfile
   - Build custom image
   - Push ไปยัง registry

2. **ใช้ Multi-stage Build**:
   - Build stage: ติดตั้ง PHP
   - Runtime stage: Copy PHP binaries

3. **Security**:
   - ตั้ง password สำหรับ phpLiteAdmin
   - ใช้ HTTPS
   - จำกัด access เฉพาะ IP ที่ต้องการ

## 📚 อ้างอิง

- [phpLiteAdmin Documentation](https://www.phpliteadmin.org/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [RunPod Documentation](https://docs.runpod.io/)

