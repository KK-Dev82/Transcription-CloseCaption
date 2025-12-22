# 🔧 Environment Variables Persistence Guide

## 📋 คำถาม: เมื่อ restart Pod ค่าจะหายไหม?

### ✅ คำตอบ: ขึ้นอยู่กับวิธีที่ตั้งค่า

---

## 🔍 วิธีตั้งค่า Environment Variables

### 1. **Export ใน Shell (ชั่วคราว)**
```bash
export REDIS_URL="redis://..."
```

**ผลลัพธ์:**
- ✅ ใช้ได้ใน shell session นี้
- ❌ **หายเมื่อ restart Pod**
- ❌ **หายเมื่อเปิด shell ใหม่**

---

### 2. **ใช้ .env.runpod File (ถาวร)**
```bash
# สร้างหรือแก้ไข .env.runpod
cat >> .env.runpod << EOF
REDIS_URL=redis://...
EOF

# Load environment variables
source .env.runpod
```

**ผลลัพธ์:**
- ✅ ใช้ได้ใน shell session นี้
- ✅ **ไม่หายเมื่อ restart Pod** (ถ้าไฟล์ยังอยู่)
- ✅ **ไม่หายเมื่อเปิด shell ใหม่** (ถ้า load ไฟล์)

---

### 3. **ใช้ Script setup-redis-env.sh (แนะนำ)**
```bash
# ตั้งค่าและ export อัตโนมัติ
bash scripts/pod/setup-redis-env.sh
```

**ผลลัพธ์:**
- ✅ สร้าง/อัพเดต .env.runpod อัตโนมัติ
- ✅ Load และ export environment variables
- ✅ ทดสอบ Redis connection
- ✅ **ไม่หายเมื่อ restart Pod** (เพราะเก็บใน .env.runpod)

---

## 🎯 แนะนำ: ใช้ .env.runpod File

### ข้อดี:
1. ✅ **Persistent** - ไม่หายเมื่อ restart Pod
2. ✅ **Version Control** - เก็บใน git ได้ (ถ้าต้องการ)
3. ✅ **Easy to Load** - `source .env.runpod` ทุกครั้งที่ต้องการ
4. ✅ **Centralized** - จัดการ config ที่เดียว

### วิธีใช้:

#### 1. สร้าง/อัพเดต .env.runpod
```bash
cat > .env.runpod << EOF
ENVIRONMENT=runpod
REDIS_URL=redis://default:password@redis-host:port
RABBITMQ_HOST=178.128.105.100
RABBITMQ_PORT=5672
# ... other variables
EOF
```

#### 2. Load ใน Scripts
```bash
# ใน start script
if [ -f ".env.runpod" ]; then
    set -a
    source .env.runpod
    set +a
fi
```

#### 3. Load ใน Shell
```bash
source .env.runpod
# หรือ
bash scripts/pod/setup-redis-env.sh
```

---

## 📝 Best Practices

### 1. **เก็บ .env.runpod ใน Project Root**
```
/workspace/transcription-service/
  ├── .env.runpod          # ✅ เก็บ config ไว้ที่นี่
  ├── scripts/
  └── app/
```

### 2. **ใช้ setup-redis-env.sh สำหรับ Setup**
```bash
# ครั้งแรก
bash scripts/pod/setup-redis-env.sh

# ครั้งถัดไป (ถ้า restart Pod)
source .env.runpod
# หรือ
bash scripts/pod/setup-redis-env.sh
```

### 3. **ตรวจสอบ Environment Variables**
```bash
# ดูค่าปัจจุบัน
echo $REDIS_URL

# ทดสอบ connection
python3 -c "import redis; r=redis.from_url('$REDIS_URL'); r.ping()"
```

---

## 🔄 Workflow สำหรับ Pod Restart

### Scenario: Restart Pod

1. **ก่อน Restart:**
   ```bash
   # ตรวจสอบว่า .env.runpod มีอยู่
   ls -la .env.runpod
   ```

2. **หลัง Restart:**
   ```bash
   # Load environment variables
   source .env.runpod
   # หรือ
   bash scripts/pod/setup-redis-env.sh
   
   # ตรวจสอบ
   echo $REDIS_URL
   ```

3. **เริ่ม Services:**
   ```bash
   # Start RQ workers
   bash scripts/pod/start-rq-workers.sh
   
   # Start API
   python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8010
   ```

---

## ⚠️ ข้อควรระวัง

### 1. **.env.runpod อาจหายถ้า:**
- Pod ถูก recreate (ไม่ใช่ restart)
- Volume ไม่ persistent
- ไฟล์ถูกลบ

### 2. **แก้ไข:**
- เก็บ backup ของ .env.runpod
- หรือใช้ environment variables จาก Pod/Container config
- หรือใช้ secrets management (Kubernetes Secrets, etc.)

---

## 📚 References

- [setup-redis-env.sh](../scripts/pod/setup-redis-env.sh)
- [start-pod.sh](../scripts/pod/start-pod.sh)
- [.env.runpod example](../scripts/pod/start-pod.sh#L73-L88)

