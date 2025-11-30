# 🔄 RunPod Pod Lifecycle Management

คู่มือการจัดการ RunPod Pod เมื่อ Stop/Start ใหม่

---

## ❓ คำถามที่พบบ่อย

### 1. ถ้า Stop Pod แล้ว Start ใหม่ GPU ไม่ว่างแล้ว ต้องแก้ไขยังไง?

**คำตอบ:** 
- **ไม่ต้อง Deploy ใหม่** - Pod จะใช้ GPU เดิม (ถ้ายังว่าง)
- **ถ้า GPU ไม่ว่าง** - RunPod จะหา GPU ใหม่ให้อัตโนมัติ หรือรอจนกว่า GPU จะว่าง

---

### 2. ต้อง Deploy ใหม่ไหม?

**คำตอบ:** 
- **ไม่ต้อง Deploy ใหม่** - Pod จะใช้ Image และ Configuration เดิม
- **แต่ต้อง Start Services ใหม่** - Services จะหยุดเมื่อ Pod Stop

---

### 3. ข้อมูลจะต้องเริ่มใหม่รึเปล่า?

**คำตอบ:** 
- **ขึ้นอยู่กับ Volume Configuration**
  - **Container Disk** - ข้อมูลจะถูกลบเมื่อ Pod Terminate
  - **Volume Disk** - ข้อมูลจะคงอยู่แม้ Pod Terminate

---

## 📋 Pod States

| State | Description | Data Persistence | Services |
|-------|-------------|------------------|----------|
| **Running** | Pod ทำงานอยู่ | ✅ ข้อมูลอยู่ใน Container Disk | ✅ Services ทำงาน |
| **Stopped** | Pod หยุดทำงาน | ✅ ข้อมูลยังอยู่ใน Container Disk | ❌ Services หยุด |
| **Terminated** | Pod ถูกลบ | ❌ ข้อมูลใน Container Disk ถูกลบ | ❌ Services หยุด |
| **Restarted** | Pod เริ่มใหม่ | ✅ ข้อมูลยังอยู่ (ถ้าไม่ Terminate) | ❌ ต้อง Start Services ใหม่ |

---

## 🔄 เมื่อ Stop Pod แล้ว Start ใหม่

### Scenario 1: GPU ยังว่างอยู่

**ผลลัพธ์:**
- ✅ Pod จะใช้ GPU เดิม
- ✅ ข้อมูลใน Container Disk ยังอยู่
- ❌ Services หยุด - ต้อง Start ใหม่

**ขั้นตอน:**

```bash
# 1. SSH เข้า Pod (IP อาจเปลี่ยน)
ssh root@<new-pod-ip> -p <port>

# 2. ตรวจสอบข้อมูล
cd /workspace/transcription-service
ls -la

# 3. ตรวจสอบ .env.runpod
cat .env.runpod

# 4. Start Services
bash scripts/pod/start-services-direct.sh
```

---

### Scenario 2: GPU ไม่ว่างแล้ว

**ผลลัพธ์:**
- ⚠️ RunPod จะหา GPU ใหม่ให้ หรือรอจนกว่า GPU จะว่าง
- ✅ ข้อมูลใน Container Disk ยังอยู่ (ถ้าไม่ Terminate)
- ❌ Services หยุด - ต้อง Start ใหม่

**ขั้นตอน:**

```bash
# 1. ตรวจสอบ Pod Status ใน RunPod Console
# - ดูว่า Pod ใช้ GPU อะไร
# - ดูว่า IP เปลี่ยนหรือไม่

# 2. SSH เข้า Pod (IP อาจเปลี่ยน)
ssh root@<new-pod-ip> -p <port>

# 3. ตรวจสอบ GPU
nvidia-smi

# 4. ตรวจสอบข้อมูล
cd /workspace/transcription-service
ls -la

# 5. Start Services
bash scripts/pod/start-services-direct.sh
```

---

## 💾 Data Persistence Strategy

### Option 1: Container Disk (Default)

**ข้อมูลจะอยู่:**
- ✅ เมื่อ Pod Stop (ไม่ Terminate)
- ❌ เมื่อ Pod Terminate

**ใช้สำหรับ:**
- Source code
- Temporary files
- Logs

---

### Option 2: Volume Disk (แนะนำ)

**ข้อมูลจะอยู่:**
- ✅ เมื่อ Pod Stop
- ✅ เมื่อ Pod Terminate
- ✅ เมื่อ Pod Restart

**ใช้สำหรับ:**
- Models (ggml-*.bin)
- Storage (transcriptions, metadata)
- Persistent data

**ตั้งค่าใน RunPod Template:**
- Volume Disk: 20-50 GB
- Volume Mount Path: `/workspace`

---

## 🛠️ Best Practices

### 1. ใช้ Volume Disk สำหรับ Models

**ตั้งค่าใน RunPod Template:**
```
Volume Disk: 20 GB
Volume Mount Path: /workspace
```

**เก็บ Models ใน Volume:**
```bash
# บน Pod
cd /workspace/transcription-service
mkdir -p /workspace/models
cp models/ggml-*.bin /workspace/models/ 2>/dev/null || true

# ตั้งค่า WHISPER_MODEL_PATH
export WHISPER_MODEL_PATH=/workspace/models
```

---

### 2. Backup .env.runpod

**ก่อน Stop Pod:**

```bash
# Backup .env.runpod
cp .env.runpod /workspace/.env.runpod.backup
```

**หลัง Start Pod:**

```bash
# Restore .env.runpod
if [ -f /workspace/.env.runpod.backup ]; then
    cp /workspace/.env.runpod.backup .env.runpod
fi
```

---

### 3. ใช้ Git สำหรับ Source Code

**ก่อน Stop Pod:**

```bash
# Commit และ Push changes
git add .
git commit -m "Save before pod stop"
git push
```

**หลัง Start Pod:**

```bash
# Pull latest code
git pull
```

---

## 📋 Checklist: เมื่อ Start Pod ใหม่

- [ ] SSH เข้า Pod ได้ (ตรวจสอบ IP ใหม่)
- [ ] GPU ทำงาน (nvidia-smi)
- [ ] Source code ยังอยู่ (ls -la /workspace/transcription-service)
- [ ] .env.runpod ยังอยู่ (cat .env.runpod)
- [ ] Models ยังอยู่ (ls -la models/)
- [ ] Start Services (bash scripts/pod/start-services-direct.sh)
- [ ] ตรวจสอบ Services (bash scripts/pod/check-services.sh)
- [ ] ทดสอบ Health Check (curl http://localhost:8001/health)

---

## 🔧 Scripts ที่ช่วย

### `scripts/pod/check-services.sh`

**ตรวจสอบ Services หลัง Start Pod:**

```bash
bash scripts/pod/check-services.sh
```

---

### `scripts/pod/start-services-direct.sh`

**Start Services หลัง Start Pod:**

```bash
bash scripts/pod/start-services-direct.sh
```

---

### `scripts/pod/update-code.sh`

**อัปเดต Code หลัง Start Pod:**

```bash
bash scripts/pod/update-code.sh
```

---

## ⚠️ สิ่งที่ต้องระวัง

### 1. IP Address อาจเปลี่ยน

**เมื่อ Start Pod ใหม่:**
- IP Address อาจเปลี่ยน
- ตรวจสอบใน RunPod Console → Connect tab

---

### 2. Services หยุดเมื่อ Pod Stop

**Services จะหยุด:**
- เมื่อ Pod Stop
- เมื่อ Pod Terminate
- เมื่อ Pod Restart

**ต้อง Start ใหม่:**
```bash
bash scripts/pod/start-services-direct.sh
```

---

### 3. Container Disk ข้อมูลจะถูกลบเมื่อ Terminate

**ถ้า Terminate Pod:**
- ข้อมูลใน Container Disk จะถูกลบ
- ใช้ Volume Disk สำหรับข้อมูลสำคัญ

---

## 🎯 Recommended Workflow

### เมื่อ Stop Pod:

```bash
# 1. Backup .env.runpod
cp .env.runpod /workspace/.env.runpod.backup

# 2. Commit code changes
git add .
git commit -m "Save before pod stop"
git push

# 3. Stop Pod จาก RunPod Console
```

---

### เมื่อ Start Pod ใหม่:

```bash
# 1. SSH เข้า Pod (ตรวจสอบ IP ใหม่)
ssh root@<new-pod-ip> -p <port>

# 2. ตรวจสอบ GPU
nvidia-smi

# 3. ไปที่ project directory
cd /workspace/transcription-service

# 4. Restore .env.runpod (ถ้ามี)
if [ -f /workspace/.env.runpod.backup ]; then
    cp /workspace/.env.runpod.backup .env.runpod
fi

# 5. Pull latest code (ถ้าจำเป็น)
git pull

# 6. Start Services
bash scripts/pod/start-services-direct.sh

# 7. ตรวจสอบ Services
bash scripts/pod/check-services.sh
```

---

## 🔗 Related Documents

- **Check Services:** `scripts/pod/check-services.sh`
- **Start Services:** `scripts/pod/start-services-direct.sh`
- **Update Code:** `scripts/pod/update-code.sh`
- **FAQ:** `docs/RunPod-Z2/FAQ.md`

---

**Last Updated:** 2024-12-19

