# 📋 คู่มือการใช้ Check Scripts สำหรับ Transcription Service

## 📊 Scripts ที่มี

### 1. `check-service-status.sh` - ตรวจสอบ Transcription Service

**ใช้สำหรับ**: ตรวจสอบ Transcription Service (port 8010) โดยเฉพาะ

**ตรวจสอบ**:
- ✅ Process Status (PID, CPU, Memory, Uptime)
- ✅ Port Status (8010)
- ✅ Health Check
- ✅ API Endpoint
- ✅ Log File
- ✅ GPU Environment
- ✅ External Access (port 41462 -> 8010)

**วิธีใช้**:
```bash
bash scripts/pod/check-service-status.sh
```

---

### 2. `check-pod.sh` - ตรวจสอบ Services ทั้งหมด

**ใช้สำหรับ**: ตรวจสอบ Services ทั้งหมดใน Pod

**ตรวจสอบ**:
- ✅ Redis
- ✅ Whisper API
- ✅ Video Worker
- ✅ Main API
- ✅ RabbitMQ Connection

**หมายเหตุ**: Script นี้ไม่ตรวจสอบ Transcription Service (port 8010) โดยเฉพาะ

**วิธีใช้**:
```bash
bash scripts/pod/check-pod.sh
```

---

## 🔧 Port Configuration

### Internal (บน Pod)
- **Port**: 8010
- **URL**: `http://localhost:8010`
- **Health**: `http://localhost:8010/health`

### External (จากภายนอก)
- **Port**: 41462 (RunPod external port)
- **URL**: `http://80.15.7.37:41462`
- **Health**: `http://80.15.7.37:41462/health`
- **Forward**: 41462 → 8010 (internal)

---

## 📝 คำแนะนำการใช้งาน

### ✅ ใช้ `check-service-status.sh` เมื่อ:

1. ต้องการตรวจสอบ Transcription Service โดยเฉพาะ
2. ตรวจสอบว่า service รันอยู่หรือไม่
3. ตรวจสอบ health check
4. ตรวจสอบ external access (port 41462)
5. ดู logs และ GPU status

### ✅ ใช้ `check-pod.sh` เมื่อ:

1. ต้องการตรวจสอบ services ทั้งหมดใน Pod
2. ตรวจสอบ RabbitMQ connection
3. ตรวจสอบ Video Worker
4. ตรวจสอบ dependencies (Redis, Whisper API, etc.)

---

## 🔍 ตัวอย่างผลลัพธ์

### `check-service-status.sh`

```
📊 Transcription Service Status
===============================

1️⃣  Process Status
─────────────────
✅ Service is RUNNING
   PID: 12345
   CPU: 2.5%
   Memory: 15.3%
   Uptime: 02:30:15

2️⃣  Port Status
──────────────
✅ Port 8010 is LISTENING

3️⃣  Health Check
───────────────
✅ Health check PASSED

...

7️⃣  External Access
───────────────────
   Internal URL: http://localhost:8010/health
   External URL: http://80.15.7.37:41462/health
   
   Checking internal access...
   ✅ Internal access OK
   
   Checking external access...
   ✅ External access OK
   External port mapping: 41462 -> 8010
```

---

## 🚀 Quick Commands

```bash
# ตรวจสอบ Transcription Service
bash scripts/pod/check-service-status.sh

# ตรวจสอบ Services ทั้งหมด
bash scripts/pod/check-pod.sh

# ตรวจสอบทั้งสอง (แนะนำ)
bash scripts/pod/check-service-status.sh && echo "" && bash scripts/pod/check-pod.sh
```

---

## 💡 Troubleshooting

### ถ้า Transcription Service ไม่รัน:

```bash
# ตรวจสอบ status
bash scripts/pod/check-service-status.sh

# ดู logs
tail -f /tmp/transcription-service.log

# Start service
bash scripts/pod/start-service-daemon.sh
```

### ถ้า External Access ไม่ได้:

1. ตรวจสอบ Port Mapping ใน RunPod Dashboard:
   - Public Port: 41462
   - Private Port: 8010

2. ตรวจสอบจากภายนอก:
   ```bash
   curl http://80.15.7.37:41462/health
   ```

3. ตรวจสอบจากภายใน Pod:
   ```bash
   curl http://localhost:8010/health
   ```

---

## 📚 เอกสารเพิ่มเติม

- [Port Configuration](../../docs/POD_PORT_8010.md)
- [Service Setup](../../docs/POD_SERVICE_READY.md)
- [External Access Guide](../../docs/OPEN_PORT_8010.md)

---

**Last Updated**: 2025-12-02  
**Internal Port**: 8010  
**External Port**: 41462

