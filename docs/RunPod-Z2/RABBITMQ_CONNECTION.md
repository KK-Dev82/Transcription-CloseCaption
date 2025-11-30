# 🔌 RabbitMQ Connection Guide

คู่มือการเชื่อมต่อ RabbitMQ สำหรับ RunPod/Z2

---

## ❌ ปัญหาที่พบ

**อาการ:**
- Video Worker crash ซ้ำๆ
- Logs แสดง: `ไม่สามารถเชื่อมต่อ RabbitMQ`
- Services หยุดทำงานเมื่อกด Ctrl+C

---

## 🔍 สาเหตุ

### 1. RabbitMQ ไม่สามารถเข้าถึงได้

**จาก RunPod Pod:**
- RabbitMQ อยู่บน Docker Image Local (MacOS)
- RunPod Pod ต้องเชื่อมต่อผ่าน SSH Tunnel หรือ Network

**Configuration:**
```bash
RABBITMQ_HOST=localhost  # ❌ ไม่ถูกต้อง - RabbitMQ ไม่อยู่บน Pod
```

---

## 🛠️ วิธีแก้ไข

### Option 1: ใช้ SSH Tunnel (สำหรับ Local Testing)

**จาก MacOS:**

```bash
# สร้าง SSH Tunnel สำหรับ RabbitMQ
ssh -L 5672:localhost:5672 root@205.196.17.108 -p 13027 -N

# หรือใช้ host.docker.internal (ถ้า RabbitMQ รันใน Docker)
ssh -L 5672:host.docker.internal:5672 root@205.196.17.108 -p 13027 -N
```

**จาก RunPod Pod:**

```bash
# ตั้งค่า environment variable
export RABBITMQ_HOST=localhost
export RABBITMQ_PORT=5672
export RABBITMQ_USER=senate
export RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT
```

---

### Option 2: ใช้ Backend Server IP (สำหรับ Staging)

**จาก RunPod Pod:**

```bash
# ตั้งค่า environment variable
export RABBITMQ_HOST=10.200.22.61  # Backend Server IP
export RABBITMQ_PORT=5672
export RABBITMQ_USER=senate
export RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT
```

**หมายเหตุ:** ต้องเปิด firewall บน Backend Server

---

### Option 3: ใช้ .env.runpod File

**สร้าง `.env.runpod` บน Pod:**

```bash
# SSH เข้า Pod
ssh root@205.196.17.108 -p 13027

# สร้าง .env.runpod
cd /workspace/transcription-service
cat > .env.runpod << EOF
# RabbitMQ Configuration
RABBITMQ_HOST=localhost  # หรือ 10.200.22.61 สำหรับ staging
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Whisper Configuration
WHISPER_PROVIDER=builtin
WHISPER_API_URL=http://localhost:8002
EOF
```

---

## 🔄 Retry Logic

Video Worker มี retry logic สำหรับ RabbitMQ connection:

- **Max Retries:** 10 ครั้ง
- **Retry Delay:** 5 วินาที
- **Total Wait Time:** ~50 วินาที

**Logs:**
```
Attempting to connect to RabbitMQ at localhost:5672 (attempt 1/10)...
ไม่สามารถเชื่อมต่อ RabbitMQ (attempt 1/10): ...
Retrying in 5 seconds...
```

---

## 🧪 ทดสอบ Connection

### จาก RunPod Pod:

```bash
# ทดสอบ RabbitMQ connection
python3 -c "
import pika
try:
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host='localhost',
            port=5672,
            credentials=pika.PlainCredentials('senate', 'qP2VtHz6fAX4xDksEpMrLT')
        )
    )
    print('✅ RabbitMQ connection successful!')
    connection.close()
except Exception as e:
    print(f'❌ RabbitMQ connection failed: {e}')
"
```

---

## 📋 Checklist

- [ ] SSH Tunnel ทำงาน (ถ้าใช้ Option 1)
- [ ] RabbitMQ ทำงานบน MacOS/Docker
- [ ] Environment variables ถูกตั้งค่า
- [ ] Firewall เปิด (ถ้าใช้ Option 2)
- [ ] Video Worker logs ไม่แสดง connection errors

---

## 🔗 Related Documents

- **Start Services:** `scripts/pod/start-services-direct.sh`
- **Check Services:** `scripts/pod/check-services.sh`
- **Troubleshooting:** `docs/RunPod-Z2/TROUBLESHOOTING_CONNECTIVITY.md`

---

**Last Updated:** 2024-12-19

