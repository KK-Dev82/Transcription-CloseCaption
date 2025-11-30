# 🔧 แก้ไข RabbitMQ Connection Issue

คู่มือแก้ไขปัญหา Video Worker ไม่สามารถเชื่อมต่อ RabbitMQ ได้

---

## ❌ อาการ

**จาก Logs:**
```
ไม่สามารถเชื่อมต่อ RabbitMQ หลังจากลอง 10 ครั้ง
RabbitMQ Host: localhost:5672
```

**สาเหตุ:**
- `.env.runpod` ยังใช้ `RABBITMQ_HOST=localhost` แทน `178.128.105.100`

---

## 🛠️ วิธีแก้ไข

### Option 1: ใช้ Script (แนะนำ)

**จาก RunPod Pod:**

```bash
# SSH เข้า Pod
ssh root@<pod-ip> -p <port>

# ไปที่ project directory
cd /workspace/transcription-service

# แก้ไข RabbitMQ configuration
bash scripts/pod/fix-rabbitmq-config.sh 178.128.105.100 5672

# Restart services
bash scripts/pod/stop-services.sh
bash scripts/pod/start-services-direct.sh
```

---

### Option 2: แก้ไขด้วยตนเอง

**จาก RunPod Pod:**

```bash
# 1. ไปที่ project directory
cd /workspace/transcription-service

# 2. แก้ไข .env.runpod
nano .env.runpod
# หรือ
vi .env.runpod

# 3. เปลี่ยน RABBITMQ_HOST จาก localhost เป็น 178.128.105.100
# RABBITMQ_HOST=178.128.105.100

# 4. Restart services
bash scripts/pod/stop-services.sh
bash scripts/pod/start-services-direct.sh
```

---

### Option 3: ใช้ setup-rabbitmq-backend.sh

**จาก RunPod Pod:**

```bash
# ไปที่ project directory
cd /workspace/transcription-service

# ตั้งค่า RabbitMQ connection
bash scripts/pod/setup-rabbitmq-backend.sh 178.128.105.100 5672

# Script จะ:
# 1. ทดสอบ connection
# 2. สร้าง/อัปเดต .env.runpod
# 3. แนะนำให้ restart services
```

---

## 🧪 ทดสอบ Connection

### จาก RunPod Pod:

```bash
# ทดสอบ RabbitMQ connection
bash scripts/pod/test-rabbitmq-connection.sh 178.128.105.100 5672 senate qP2VtHz6fAX4xDksEpMrLT
```

**ผลลัพธ์ที่คาดหวัง:**
```
✅ Port 5672 is reachable on 178.128.105.100
✅ RabbitMQ connection successful!
✅ Channel created successfully!
✅ Queue operations working!
```

---

## 🔍 ตรวจสอบ .env.runpod

**จาก RunPod Pod:**

```bash
# ตรวจสอบ RabbitMQ configuration
cat .env.runpod | grep RABBITMQ

# ควรเห็น:
# RABBITMQ_HOST=178.128.105.100
# RABBITMQ_PORT=5672
# RABBITMQ_USER=senate
# RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT
```

---

## 🔒 Firewall Configuration

**บน Backend Server Dev (178.128.105.100):**

```bash
# ตรวจสอบ firewall
sudo ufw status

# เปิด port 5672 (ถ้ายังไม่เปิด)
sudo ufw allow 5672/tcp

# ตรวจสอบ RabbitMQ container
docker ps | grep rabbitmq
# ควรเห็น: 0.0.0.0:5672->5672/tcp
```

---

## 📋 Checklist

- [ ] `.env.runpod` มี `RABBITMQ_HOST=178.128.105.100`
- [ ] `.env.runpod` มี `RABBITMQ_PORT=5672`
- [ ] `.env.runpod` มี `RABBITMQ_USER=senate`
- [ ] `.env.runpod` มี `RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT`
- [ ] Connection test ผ่าน
- [ ] Firewall เปิด port 5672 (บน Backend Server)
- [ ] Services restart แล้ว
- [ ] Video Worker logs ไม่แสดง connection errors

---

## 🔗 Related Documents

- **Setup RabbitMQ:** `scripts/pod/setup-rabbitmq-backend.sh`
- **Fix Config:** `scripts/pod/fix-rabbitmq-config.sh`
- **Test Connection:** `scripts/pod/test-rabbitmq-connection.sh`
- **Backend Setup:** `docs/RunPod-Z2/BACKEND_RABBITMQ_SETUP.md`

---

**Last Updated:** 2024-12-19

