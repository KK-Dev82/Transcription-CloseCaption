# 🔧 Persistent Dependencies - Dependencies ไม่หายหลัง Restart

## 🔍 ปัญหา

เมื่อ restart container แล้วใช้คำสั่ง:
```bash
bash scripts/pod/start-service-daemon.sh
```

พบว่า:
```
❌ Error: uvicorn is not installed
💡 Installing dependencies...
```

**สาเหตุ**: Dependencies ถูกติดตั้งใน system location ที่ไม่ persist หลัง restart container

---

## ✅ วิธีแก้ไข

### 1. ติดตั้ง Dependencies ใน Persistent Storage

แก้ไขแล้วโดย:
- ใช้ `pip3 install --user` เพื่อติดตั้งใน `/workspace/.local`
- สร้าง persistent directories อัตโนมัติ
- Detect Python version dynamically

### 2. Persistent Storage Location

```
/workspace/.local/
  ├── lib/python3.10/site-packages/  (Python packages)
  └── bin/                           (Executables)
```

**หมายเหตุ**: Path จะปรับตาม Python version อัตโนมัติ (เช่น 3.10, 3.11)

---

## 📋 การเปลี่ยนแปลง

### `install-dependencies.sh`

**ก่อน**:
```bash
pip3 install --no-cache-dir fastapi uvicorn ...
```

**หลัง**:
```bash
export PYTHONUSERBASE="/workspace/.local"
export PATH="/workspace/.local/bin:$PATH"
export PYTHONPATH="/workspace/.local/lib/python3.10/site-packages:$PYTHONPATH"

pip3 install --user --no-cache-dir fastapi uvicorn ...
```

### `start-service-daemon.sh`

**ก่อน**:
```bash
# Check dependencies (ไม่มี PYTHONPATH)
if ! python3 -c "import uvicorn" 2>/dev/null; then
```

**หลัง**:
```bash
# Setup persistent location ก่อน
export PYTHONUSERBASE="/workspace/.local"
export PYTHONPATH="/workspace/.local/lib/python3.10/site-packages:$PYTHONPATH"

# Check dependencies (ใช้ PYTHONPATH)
if ! env PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
        python3 -c "import uvicorn" 2>/dev/null; then
```

---

## 🚀 วิธีใช้งาน

### ครั้งแรก: ติดตั้ง Dependencies

```bash
# SSH เข้า Pod
ssh pytorch-pod

# ติดตั้ง dependencies (จะติดตั้งใน /workspace/.local)
cd /workspace/transcription-service
bash scripts/pod/install-dependencies.sh
```

### หลังจาก Restart: Start Service

```bash
# Dependencies จะถูกตรวจพบอัตโนมัติ (ไม่ต้อง install ใหม่)
bash scripts/pod/start-service-daemon.sh
```

---

## ✅ ตรวจสอบว่า Dependencies Persist

```bash
# ตรวจสอบ packages ใน persistent location
ls -la /workspace/.local/lib/python3.10/site-packages/ | grep uvicorn

# หรือใช้ pip list
PYTHONUSERBASE="/workspace/.local" \
PYTHONPATH="/workspace/.local/lib/python3.10/site-packages:$PYTHONPATH" \
python3 -m pip list --user
```

---

## 💡 สรุป

✅ **แก้ไขแล้ว**:
- Dependencies ติดตั้งใน persistent location (`/workspace/.local`)
- ไม่ต้อง install ใหม่หลัง restart
- Python version detect อัตโนมัติ

✅ **หลังจากนี้**:
- Install dependencies ครั้งเดียว
- Dependencies จะ persist หลัง restart
- ไม่ต้อง install ทุกครั้งที่ start service

---

**Last Updated**: 2025-12-02  
**Persistent Location**: `/workspace/.local`

