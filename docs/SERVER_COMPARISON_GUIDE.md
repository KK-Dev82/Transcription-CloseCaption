# 📊 คู่มือการเปรียบเทียบ Transcription Performance ระหว่าง 2 Servers

**วันที่สร้าง**: 2024-12-05  
**Purpose**: เปรียบเทียบ Performance และ Stability ของ Transcription Service ระหว่าง 2 GPU Servers

---

## 📋 Servers

### Server 1: 4080s (RTX 4080 Super)
- **SSH Host**: `4080s`
- **IP**: `80.15.7.37:41433`
- **Service URL**: `http://80.15.7.37:41314`

### Server 2: 4000-ada (RTX 4000 Ada)
- **SSH Host**: `4000-ada`
- **IP**: `87.197.119.40:40111`
- **Service URL**: `http://87.197.119.40:41314`

---

## ✅ SSH Configuration

**ไฟล์**: `~/.ssh/config`

```ssh-config
Host 4080s
     HostName 80.15.7.37
     Port 41433
     User root
     IdentityFile ~/.ssh/id_ed25519
     StrictHostKeyChecking no
     UserKnownHostsFile /dev/null

Host 4000-ada
     HostName 87.197.119.40
     Port 40111
     User root
     IdentityFile ~/.ssh/id_ed25519
     StrictHostKeyChecking no
     UserKnownHostsFile /dev/null
```

**สถานะ**: ✅ ตรวจสอบแล้ว - ตั้งค่าถูกต้อง

---

## 🔍 ตรวจสอบปัญหา Transcription

### Step 1: ตรวจสอบสุขภาพทั้ง 2 Servers

```bash
# ตรวจสอบทั้ง 2 servers พร้อมกัน
bash scripts/pod/check-server-comparison.sh 4080s 4000-ada
```

**Script จะตรวจสอบ:**
- ✅ SSH Connection
- ✅ Service Status (API + Worker)
- ✅ RabbitMQ Connection
- ✅ Queue Status (messages, consumers)
- ✅ Recent Errors
- ✅ Resource Usage (CPU, Memory, GPU)

---

### Step 2: แก้ไขปัญหาที่พบ

```bash
# ตรวจสอบและแก้ไขปัญหาบน Server 1
bash scripts/pod/fix-transcription-issues.sh 4080s

# ตรวจสอบและแก้ไขปัญหาบน Server 2
bash scripts/pod/fix-transcription-issues.sh 4000-ada
```

**Script จะตรวจสอบและแนะนำ:**
- 🔧 RabbitMQ Connection Issues
- 🔧 Queue Arguments Consistency
- 🔧 Service Status Problems
- 🔧 Recent Errors

---

## 🧪 ทดสอบและเปรียบเทียบ Performance

### Step 1: ทดสอบ Transcription 10 วิดีโอ

```bash
# ทดสอบบนทั้ง 2 servers และเปรียบเทียบ
bash scripts/pod/test-comparison-2servers.sh "http://localhost:5182/api/files/video1.mp4" 10
```

**Script จะ:**
- 📤 ส่ง transcription tasks ไปยังทั้ง 2 servers
- ⏳ รอให้ทุก task เสร็จสิ้น
- 📊 เปรียบเทียบ performance metrics
- 💾 บันทึก results ใน JSON format

---

### Step 2: ตรวจสอบ Results

```bash
# ดู results
ls -lh /tmp/transcription-comparison-*/

# ดู comparison summary
cat /tmp/transcription-comparison-*/comparison.json  # ถ้ามี
```

---

## 📊 Metrics ที่เปรียบเทียบ

| Metric | Description |
|--------|-------------|
| **Success Count** | จำนวน tasks ที่สำเร็จ |
| **Fail Count** | จำนวน tasks ที่ล้มเหลว |
| **Success Rate** | อัตราความสำเร็จ (%) |
| **Avg Time** | เวลาเฉลี่ยต่อ task (วินาที) |
| **Throughput** | จำนวน tasks ต่อชั่วโมง |
| **Total Time** | เวลารวมทั้งหมด (วินาที) |

---

## 🔧 ปัญหาที่พบบ่อยและวิธีแก้ไข

### 1. RabbitMQ Connection Failed

**อาการ:**
```
❌ RabbitMQ: Failed
   Error: Connection refused / Timeout
```

**วิธีแก้:**
```bash
# ตรวจสอบ env.runpod
ssh 4080s "cat /workspace/transcription-service/env.runpod | grep RABBITMQ"

# ตรวจสอบว่า RabbitMQ Host ถูกต้อง
# ควรเป็น: RABBITMQ_HOST=178.128.105.100

# Restart service
ssh 4080s "bash /workspace/transcription-service/scripts/pod/restart-service-daemon.sh"
```

---

### 2. Queue Precondition Failed

**อาการ:**
```
⚠️ Queue transcription_request_queue exists with different arguments
```

**วิธีแก้:**
```bash
# Option 1: ลบ queue เก่าและ restart service
curl -u senate:qP2VtHz6fAX4xDksEpMrLT \
  -X DELETE http://178.128.105.100:15672/api/queues/%2F/transcription_request_queue

# Option 2: ใช้ get_queue() (code แก้ไขแล้ว)
# Service จะใช้ queue ที่มีอยู่แล้วโดยไม่เปลี่ยน arguments
```

---

### 3. No Consumers on Queues

**อาการ:**
```
transcription_request_queue: 5 messages, 0 consumers
```

**วิธีแก้:**
```bash
# ตรวจสอบ worker logs
ssh 4080s "tail -100 /workspace/transcription-service/logs/video_worker.log | grep -i consumer"

# Restart worker
ssh 4080s "bash /workspace/transcription-service/scripts/pod/restart-service-daemon.sh"
```

---

### 4. Service Not Responding

**อาการ:**
```
❌ Service is not responding
```

**วิธีแก้:**
```bash
# ตรวจสอบ service status
ssh 4080s "bash /workspace/transcription-service/scripts/pod/check-service-status.sh"

# Restart service
ssh 4080s "bash /workspace/transcription-service/scripts/pod/restart-service-daemon.sh"

# ตรวจสอบ logs
ssh 4080s "tail -100 /workspace/transcription-service/logs/video_worker.log"
```

---

## 📝 Checklist สำหรับการทดสอบ

### Pre-Test
- [ ] ตรวจสอบ SSH connection ทั้ง 2 servers
- [ ] ตรวจสอบ service status ทั้ง 2 servers
- [ ] ตรวจสอบ RabbitMQ connection ทั้ง 2 servers
- [ ] ตรวจสอบ queue status (ควรมี consumers)
- [ ] ตรวจสอบว่า video file URL เข้าถึงได้

### Test Execution
- [ ] ส่ง transcription tasks ไปยัง Server 1
- [ ] รอให้ Server 1 เสร็จสิ้น
- [ ] ส่ง transcription tasks ไปยัง Server 2
- [ ] รอให้ Server 2 เสร็จสิ้น
- [ ] เปรียบเทียบ results

### Post-Test
- [ ] ตรวจสอบ results files
- [ ] เปรียบเทียบ performance metrics
- [ ] ตรวจสอบ error logs (ถ้ามี)
- [ ] บันทึกสรุปผลการทดสอบ

---

## 📊 Example Results

```
Metric                 4080s                  4000-ada
────────────────────────────────────────────────────────────────────────────
Success Count                 10                       10
Fail Count                     0                        0
Avg Time                  45.32s                   52.18s
Throughput                79.45/hr                 69.03/hr

🏆 Winner: 4080s (Faster avg time)
```

---

## 🚀 Quick Start

```bash
# 1. ตรวจสอบสุขภาพ
bash scripts/pod/check-server-comparison.sh 4080s 4000-ada

# 2. แก้ไขปัญหา (ถ้ามี)
bash scripts/pod/fix-transcription-issues.sh 4080s
bash scripts/pod/fix-transcription-issues.sh 4000-ada

# 3. ทดสอบและเปรียบเทียบ
bash scripts/pod/test-comparison-2servers.sh "http://localhost:5182/api/files/video1.mp4" 10

# 4. ตรวจสอบ results
ls -lh /tmp/transcription-comparison-*/
```

---

**Last Updated**: 2024-12-05  
**Status**: Ready ✅

