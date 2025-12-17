# 📚 คู่มือ Scripts ใน scripts/pod

**อัปเดตล่าสุด**: 2025-12-17  
**โฟลเดอร์**: `scripts/pod/`

---

## 📋 สารบัญ

1. [Service Management](#service-management)
2. [Health Check & Monitoring](#health-check--monitoring)
3. [Installation & Setup](#installation--setup)
4. [Testing](#testing)
5. [Diagnostic & Troubleshooting](#diagnostic--troubleshooting)
6. [Deployment & Build](#deployment--build)
7. [Utilities](#utilities)

---

## 🔧 Service Management

### `restart-service-daemon.sh`
**วัตถุประสงค์**: Restart API Service และ Video Worker พร้อมกัน

**วิธีใช้งาน**:
```bash
bash scripts/pod/restart-service-daemon.sh [INTERNAL_PORT]
```

**พารามิเตอร์**:
- `INTERNAL_PORT` (optional): Internal port สำหรับ API Service (default: 8010)

**การทำงาน**:
1. หยุด API Service และ Video Worker
2. Purge RabbitMQ queues (ลบ messages เก่า)
3. Start services ใหม่

**เมื่อไหร่ควรใช้**:
- หลังจากแก้ไข configuration
- หลังจากเพิ่ม consumers ใหม่
- เมื่อ service มีปัญหาและต้องการ restart ทั้งหมด

**หมายเหตุ**: Script นี้ถูกเรียกใช้จาก API endpoint `/api/control/restart`

---

### `restart-worker-only.sh`
**วัตถุประสงค์**: Restart Video Worker เท่านั้น (ไม่ restart API Service)

**วิธีใช้งาน**:
```bash
bash scripts/pod/restart-worker-only.sh
```

**การทำงาน**:
1. ตรวจสอบ worker health ก่อน kill (ป้องกันการ kill worker ที่ยัง healthy)
2. หยุด Video Worker (graceful shutdown: SIGTERM → SIGKILL)
3. Start Video Worker ใหม่
4. ตรวจสอบว่า worker connect RabbitMQ สำเร็จ

**เมื่อไหร่ควรใช้**:
- หลังจากแก้ไข worker configuration
- เมื่อ worker crash และต้องการ restart
- เมื่อต้องการ restart worker โดยไม่กระทบ API Service

**Features**:
- ✅ Health check ก่อน kill
- ✅ Graceful shutdown
- ✅ Auto-check connection status

---

### `start-service-daemon.sh`
**วัตถุประสงค์**: Start Transcription Service แบบ Daemon (ทำงานต่อได้แม้ออกจาก Terminal)

**วิธีใช้งาน**:
```bash
bash scripts/pod/start-service-daemon.sh [INTERNAL_PORT]
```

**พารามิเตอร์**:
- `INTERNAL_PORT` (optional): Internal port สำหรับ API Service (default: 8010)

**การทำงาน**:
1. ตรวจสอบและติดตั้ง dependencies (ถ้ายังไม่มี)
2. Start API Service (uvicorn) แบบ daemon
3. Start Video Worker แบบ daemon
4. ตรวจสอบว่า services ทำงานปกติ

**เมื่อไหร่ควรใช้**:
- เมื่อเริ่มต้น pod ใหม่
- เมื่อต้องการ start services หลังจาก stop
- หลังจาก restart pod

**หมายเหตุ**: Script นี้ถูกเรียกใช้จาก API endpoint `/api/control/start`

---

### `start-all-services.sh`
**วัตถุประสงค์**: Start Services ทั้งหมด (MainAPI, Video-Worker, Dashboard)

**วิธีใช้งาน**:
```bash
bash scripts/pod/start-all-services.sh
```

**การทำงาน**:
1. Start MainAPI Service
2. Start Video-Worker
3. Start Dashboard Service
4. ตรวจสอบสถานะ services ทั้งหมด

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ start services ทั้งหมดพร้อมกัน
- หลังจาก restart pod
- เมื่อ services ทั้งหมดหยุดทำงาน

---

### `start-video-worker-daemon.sh`
**วัตถุประสงค์**: Video Worker Daemon - Auto-restart on crash

**วิธีใช้งาน**:
```bash
bash scripts/pod/start-video-worker-daemon.sh
```

**การทำงาน**:
- Monitor worker health ทุก 30 วินาที
- Auto-restart worker ถ้าไม่ healthy
- จำกัดจำนวน restarts (max 10 ครั้ง)

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการให้ worker auto-restart เมื่อ crash
- สำหรับ production environment
- เมื่อ worker มีปัญหา crash บ่อย

**หมายเหตุ**: Script นี้จะรันต่อเนื่อง (infinite loop)

---

### `stop-service.sh`
**วัตถุประสงค์**: Stop Transcription Service

**วิธีใช้งาน**:
```bash
bash scripts/pod/stop-service.sh
```

**การทำงาน**:
- หยุด API Service
- หยุด Video Worker

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการหยุด services ชั่วคราว
- ก่อน restart services

---

### `stop-pod.sh`
**วัตถุประสงค์**: Stop Pod Services ทั้งหมด

**วิธีใช้งาน**:
```bash
bash scripts/pod/stop-pod.sh
```

**การทำงาน**:
- หยุด Main API
- หยุด Whisper API
- หยุด Video Worker
- หยุด Redis (ถ้ามี)

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการหยุด pod ทั้งหมด
- ก่อน restart pod

---

### `restart-pod.sh`
**วัตถุประสงค์**: Restart Pod Services ทั้งหมด

**วิธีใช้งาน**:
```bash
bash scripts/pod/restart-pod.sh
```

**การทำงาน**:
1. Stop pod services
2. Start pod services

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ restart pod ทั้งหมด
- หลังจากแก้ไข configuration ที่กระทบทุก services

---

## 🔍 Health Check & Monitoring

### `worker-health-check.sh`
**วัตถุประสงค์**: ตรวจสอบ worker health และ auto-restart ถ้าไม่ healthy

**วิธีใช้งาน**:
```bash
bash scripts/pod/worker-health-check.sh
```

**การตรวจสอบ**:
1. ✅ Worker process running
2. ✅ Worker uptime
3. ✅ Log file recent (updated in last 5 minutes)
4. ✅ Error count in logs
5. ✅ RabbitMQ consumers registered
6. ✅ Memory usage

**การทำงาน**:
- Auto-restart worker ถ้าไม่ healthy
- Log health check failures
- Prevent unnecessary restarts

**เมื่อไหร่ควรใช้**:
- สำหรับ cron job (ทุก 5 นาที)
- เมื่อต้องการตรวจสอบ worker health
- เมื่อ worker มีปัญหา

**Setup Cron Job**:
```bash
# เพิ่มใน crontab
*/5 * * * * cd /workspace/transcription-service && bash scripts/pod/worker-health-check.sh >> logs/health-check-cron.log 2>&1
```

**Log Files**:
- `logs/worker-health-check.log` - Health check failures และ restarts

---

### `monitor-worker-errors.sh`
**วัตถุประสงค์**: ติดตาม error logs และแจ้งเตือนเมื่อพบปัญหา

**วิธีใช้งาน**:
```bash
bash scripts/pod/monitor-worker-errors.sh
```

**การตรวจสอบ**:
1. ✅ Error count analysis
2. ✅ Critical error patterns (RabbitMQ, GPU, Memory)
3. ✅ Crash detection (SIGTERM, Fatal errors)
4. ✅ Worker uptime monitoring

**การทำงาน**:
- วิเคราะห์ error logs
- ตรวจจับ error patterns ที่สำคัญ
- ตรวจจับ worker crashes
- บันทึก alerts สำหรับ critical issues

**เมื่อไหร่ควรใช้**:
- สำหรับ cron job (ทุก 10 นาที)
- เมื่อต้องการติดตาม errors
- เมื่อต้องการตรวจสอบ worker stability

**Setup Cron Job**:
```bash
# เพิ่มใน crontab
*/10 * * * * cd /workspace/transcription-service && bash scripts/pod/monitor-worker-errors.sh >> logs/monitor-cron.log 2>&1
```

**Log Files**:
- `logs/worker-monitor.log` - Monitoring results
- `logs/worker-alerts.log` - Critical alerts only

---

### `monitor-api-service.sh`
**วัตถุประสงค์**: Monitor API Service และ auto-restart ถ้าไม่ healthy

**วิธีใช้งาน**:
```bash
bash scripts/pod/monitor-api-service.sh
```

**การทำงาน**:
- ตรวจสอบ API Service health
- Auto-restart ถ้าไม่ healthy
- Monitor uptime และ errors

**เมื่อไหร่ควรใช้**:
- สำหรับ cron job
- เมื่อต้องการ monitor API Service

---

### `check-all-services.sh`
**วัตถุประสงค์**: ตรวจสอบสถานะ services ทั้งหมด

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-all-services.sh
```

**การตรวจสอบ**:
- API Service status
- Video Worker status
- RabbitMQ connection
- Queue status

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการตรวจสอบสถานะ services ทั้งหมด
- หลังจาก restart services

---

### `check-service-status.sh`
**วัตถุประสงค์**: ตรวจสอบสถานะ Transcription Service

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-service-status.sh
```

**การตรวจสอบ**:
- API Service process
- Video Worker process
- Health endpoints

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการตรวจสอบ service status
- หลังจาก start/restart services

---

### `check-service-health.sh`
**วัตถุประสงค์**: ตรวจสอบ health ของ service

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-service-health.sh
```

**การทำงาน**:
- ตรวจสอบ health endpoint
- ตรวจสอบ process status

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการตรวจสอบ service health
- สำหรับ health check automation

---

### `check-worker-activity.sh`
**วัตถุประสงค์**: ตรวจสอบ worker activity

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-worker-activity.sh
```

**การตรวจสอบ**:
- Worker process status
- Consumer registration
- Message processing

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการตรวจสอบ worker activity
- เมื่อ worker ไม่ consume messages

---

### `check-worker-detailed.sh`
**วัตถุประสงค์**: ตรวจสอบ worker แบบละเอียด

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-worker-detailed.sh
```

**การตรวจสอบ**:
- Worker process details
- Memory usage
- CPU usage
- Active tasks

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการข้อมูลละเอียดเกี่ยวกับ worker
- เมื่อ troubleshoot worker issues

---

### `check-rabbitmq-queue.sh`
**วัตถุประสงค์**: ตรวจสอบ RabbitMQ queues

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-rabbitmq-queue.sh
```

**การตรวจสอบ**:
- Queue status
- Message counts
- Consumer counts
- Queue arguments

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการตรวจสอบ queue status
- เมื่อมีปัญหา queue limits
- เมื่อต้องการดู message counts

---

### `check-connection-issues.sh`
**วัตถุประสงค์**: ตรวจสอบปัญหา connection

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-connection-issues.sh
```

**การตรวจสอบ**:
- RabbitMQ connection
- Network connectivity
- Connection errors

**เมื่อไหร่ควรใช้**:
- เมื่อมีปัญหา connection
- เมื่อ RabbitMQ connection หลุด

---

### `check-logs-diagnosis.sh`
**วัตถุประสงค์**: วินิจฉัยจาก logs

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-logs-diagnosis.sh
```

**การทำงาน**:
- วิเคราะห์ logs
- หา error patterns
- แนะนำการแก้ไข

**เมื่อไหร่ควรใช้**:
- เมื่อมีปัญหาและต้องการวินิจฉัย
- เมื่อต้องการวิเคราะห์ logs

---

### `check-logs-and-webhook.sh`
**วัตถุประสงค์**: ตรวจสอบ Logs และ Webhook

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-logs-and-webhook.sh
```

**การตรวจสอบ**:
- Service logs
- Webhook configuration
- Webhook delivery status

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการตรวจสอบ logs และ webhook
- เมื่อ webhook ไม่ทำงาน

---

### `check-gpu-memory.sh`
**วัตถุประสงค์**: ตรวจสอบ GPU memory

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-gpu-memory.sh
```

**การตรวจสอบ**:
- GPU memory usage
- GPU processes
- Memory leaks

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการตรวจสอบ GPU memory
- เมื่อมีปัญหา GPU memory

---

### `check-pod.sh`
**วัตถุประสงค์**: ตรวจสอบ pod status

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-pod.sh
```

**การตรวจสอบ**:
- Pod services status
- Resource usage
- Health status

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการตรวจสอบ pod status
- หลังจาก start pod

---

### `check-server-comparison.sh`
**วัตถุประสงค์**: เปรียบเทียบ server performance

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-server-comparison.sh
```

**การทำงาน**:
- เปรียบเทียบ performance ระหว่าง servers
- วิเคราะห์ resource usage
- แนะนำ server ที่เหมาะสม

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการเปรียบเทียบ servers
- เมื่อเลือก server สำหรับ deployment

---

### `check-task-status.sh`
**วัตถุประสงค์**: ตรวจสอบสถานะ task

**วิธีใช้งาน**:
```bash
bash scripts/pod/check-task-status.sh [TASK_ID]
```

**พารามิเตอร์**:
- `TASK_ID` (optional): Task ID ที่ต้องการตรวจสอบ

**การทำงาน**:
- ตรวจสอบ task status
- แสดง task details
- ตรวจสอบ task logs

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการตรวจสอบ task status
- เมื่อ task ไม่ทำงาน

---

## 📦 Installation & Setup

### `install-dependencies.sh`
**วัตถุประสงค์**: ติดตั้ง Dependencies สำหรับ Transcription Service

**วิธีใช้งาน**:
```bash
bash scripts/pod/install-dependencies.sh
```

**การติดตั้ง**:
- Python packages (CTranslate2, PyTorch, etc.)
- System dependencies
- cuDNN libraries
- FFmpeg (ถ้ายังไม่มี)

**เมื่อไหร่ควรใช้**:
- เมื่อเริ่มต้น pod ใหม่
- เมื่อ dependencies หายไป
- หลังจาก restart pod

**หมายเหตุ**: Script นี้ถูกเรียกใช้จาก `start-service-daemon.sh` อัตโนมัติ

---

### `install-dependencies-cuda12.sh`
**วัตถุประสงค์**: ติดตั้ง Dependencies สำหรับ CUDA 12

**วิธีใช้งาน**:
```bash
bash scripts/pod/install-dependencies-cuda12.sh
```

**การติดตั้ง**:
- CUDA 12 specific dependencies
- Compatible libraries

**เมื่อไหร่ควรใช้**:
- เมื่อใช้ CUDA 12
- เมื่อต้องการ dependencies สำหรับ CUDA 12

---

### `install-ffmpeg-persistent.sh`
**วัตถุประสงค์**: ติดตั้ง FFmpeg ไปยัง persistent volume

**วิธีใช้งาน**:
```bash
bash scripts/pod/install-ffmpeg-persistent.sh
```

**การทำงาน**:
- Download และติดตั้ง FFmpeg
- เก็บไว้ใน persistent volume (`/workspace/.local/bin`)
- Setup PATH environment

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ FFmpeg ที่ persist หลัง restart
- เมื่อ system FFmpeg ไม่มีหรือไม่ทำงาน

---

### `install-timezone-persistent.sh`
**วัตถุประสงค์**: ติดตั้ง timezone data ไปยัง persistent volume

**วิธีใช้งาน**:
```bash
bash scripts/pod/install-timezone-persistent.sh
```

**การทำงาน**:
- ติดตั้ง timezone data
- เก็บไว้ใน persistent volume

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ timezone data ที่ persist
- เมื่อมีปัญหา timezone

---

### `install-sqlite-admin.sh`
**วัตถุประสงค์**: ติดตั้ง SQLite Admin

**วิธีใช้งาน**:
```bash
bash scripts/pod/install-sqlite-admin.sh
```

**การทำงาน**:
- ติดตั้ง SQLite Admin tool
- Setup web interface

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการจัดการ SQLite database
- เมื่อต้องการดู database content

---

### `setup-pod.sh`
**วัตถุประสงค์**: Setup Pod Environment

**วิธีใช้งาน**:
```bash
bash scripts/pod/setup-pod.sh
```

**การทำงาน**:
- Setup environment variables
- Install dependencies
- Configure services

**เมื่อไหร่ควรใช้**:
- เมื่อเริ่มต้น pod ใหม่
- เมื่อต้องการ setup environment ใหม่

---

### `setup-video-worker-service.sh`
**วัตถุประสงค์**: Setup Video Worker Service

**วิธีใช้งาน**:
```bash
bash scripts/pod/setup-video-worker-service.sh
```

**การทำงาน**:
- Setup systemd service สำหรับ video worker
- Configure auto-start
- Setup logging

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการให้ worker start อัตโนมัติ
- เมื่อต้องการใช้ systemd service

---

### `setup-cudnn-path.sh`
**วัตถุประสงค์**: Setup cuDNN Path

**วิธีใช้งาน**:
```bash
bash scripts/pod/setup-cudnn-path.sh
```

**การทำงาน**:
- Setup LD_LIBRARY_PATH สำหรับ cuDNN
- Configure library paths

**เมื่อไหร่ควรใช้**:
- เมื่อมีปัญหา cuDNN library
- เมื่อต้องการ configure cuDNN path

---

### `setup-nginx-static.sh`
**วัตถุประสงค์**: Setup Nginx Static Files

**วิธีใช้งาน**:
```bash
bash scripts/pod/setup-nginx-static.sh
```

**การทำงาน**:
- Setup Nginx configuration
- Configure static file serving

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ serve static files
- เมื่อต้องการ setup Nginx

---

### `setup-ssh.sh`
**วัตถุประสงค์**: Setup SSH Access

**วิธีใช้งาน**:
```bash
bash scripts/pod/setup-ssh.sh
```

**การทำงาน**:
- Setup SSH keys
- Configure SSH access

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ setup SSH access
- เมื่อต้องการ remote access

---

## 🧪 Testing

### `test-transcription-10tasks.sh`
**วัตถุประสงค์**: ทดสอบ Transcription 10 Tasks

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-transcription-10tasks.sh
```

**การทำงาน**:
- ส่ง 10 transcription tasks
- Monitor progress
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการทดสอบ transcription
- เมื่อต้องการตรวจสอบ system performance

---

### `test-transcription-5-10-15.sh`
**วัตถุประสงค์**: ทดสอบ Transcription 5, 10, 15 Tasks

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-transcription-5-10-15.sh
```

**การทำงาน**:
- ทดสอบด้วย 5, 10, 15 tasks
- เปรียบเทียบ performance
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการทดสอบ scalability
- เมื่อต้องการเปรียบเทียบ performance

---

### `test-transcription-incremental.sh`
**วัตถุประสงค์**: ทดสอบ Transcription แบบ Incremental

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-transcription-incremental.sh
```

**การทำงาน**:
- ทดสอบด้วย tasks เพิ่มขึ้นทีละน้อย
- Monitor performance
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการทดสอบ incremental load
- เมื่อต้องการดู performance degradation

---

### `test-transcription-comparison.sh`
**วัตถุประสงค์**: เปรียบเทียบ Transcription Performance

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-transcription-comparison.sh
```

**การทำงาน**:
- เปรียบเทียบ performance ระหว่าง configurations
- วิเคราะห์ results
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการเปรียบเทียบ configurations
- เมื่อต้องการ optimize performance

---

### `test-comparison-2servers.sh`
**วัตถุประสงค์**: เปรียบเทียบ 2 Servers

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-comparison-2servers.sh
```

**การทำงาน**:
- ทดสอบบน 2 servers
- เปรียบเทียบ performance
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการเปรียบเทียบ servers
- เมื่อเลือก server สำหรับ deployment

---

### `test-comparison-2servers-quick.sh`
**วัตถุประสงค์**: เปรียบเทียบ 2 Servers แบบเร็ว

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-comparison-2servers-quick.sh
```

**การทำงาน**:
- ทดสอบแบบเร็ว (น้อย tasks)
- เปรียบเทียบ performance
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการทดสอบแบบเร็ว
- เมื่อต้องการ quick comparison

---

### `test-progressive-tasks.sh`
**วัตถุประสงค์**: ทดสอบ Progressive Tasks

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-progressive-tasks.sh
```

**การทำงาน**:
- ทดสอบด้วย tasks เพิ่มขึ้นทีละน้อย
- Monitor performance
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการทดสอบ progressive load
- เมื่อต้องการดู system behavior

---

### `test-quick-dry-run.sh`
**วัตถุประสงค์**: ทดสอบ Quick Dry Run

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-quick-dry-run.sh
```

**การทำงาน**:
- ทดสอบแบบ dry run (ไม่ process จริง)
- ตรวจสอบ configuration
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการทดสอบ configuration
- เมื่อต้องการ quick check

---

### `test-10tasks-and-summarize.sh`
**วัตถุประสงค์**: ทดสอบ 10 Tasks และสรุป

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-10tasks-and-summarize.sh
```

**การทำงาน**:
- ทดสอบ 10 tasks
- สรุปผลลัพธ์
- Generate report

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการทดสอบและสรุปผล
- เมื่อต้องการ generate report

---

### `test-4000-ada-sc.sh`
**วัตถุประสงค์**: ทดสอบ 4000 ADA SC Server

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-4000-ada-sc.sh
```

**การทำงาน**:
- ทดสอบบน 4000 ADA SC server
- Monitor performance
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการทดสอบบน 4000 ADA SC
- เมื่อต้องการ benchmark 4000 ADA SC

---

### `test-benchmark-4000ada.sh`
**วัตถุประสงค์**: ทดสอบ Benchmark 4000 ADA

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-benchmark-4000ada.sh
```

**การทำงาน**:
- Run benchmark บน 4000 ADA
- Monitor performance
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ benchmark 4000 ADA
- เมื่อต้องการวัด performance

---

### `test-ffmpeg-install.sh`
**วัตถุประสงค์**: ทดสอบ FFmpeg Installation

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-ffmpeg-install.sh
```

**การทำงาน**:
- ทดสอบ FFmpeg installation
- ตรวจสอบ FFmpeg version
- ทดสอบ FFmpeg functionality

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการทดสอบ FFmpeg
- เมื่อมีปัญหา FFmpeg

---

### `test-ffmpeg-simple.sh`
**วัตถุประสงค์**: ทดสอบ FFmpeg แบบง่าย

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-ffmpeg-simple.sh
```

**การทำงาน**:
- ทดสอบ FFmpeg แบบง่าย
- ตรวจสอบ basic functionality

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ quick FFmpeg test
- เมื่อต้องการตรวจสอบ FFmpeg

---

### `test-v30-1-video.sh`
**วัตถุประสงค์**: ทดสอบ Video 30 นาที 1 ไฟล์

**วิธีใช้งาน**:
```bash
bash scripts/pod/test-v30-1-video.sh
```

**การทำงาน**:
- ทดสอบด้วย video 30 นาที
- Monitor processing
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการทดสอบ long video
- เมื่อต้องการตรวจสอบ performance

---

### `run-benchmark-batch.sh`
**วัตถุประสงค์**: รัน Benchmark แบบ Batch

**วิธีใช้งาน**:
```bash
bash scripts/pod/run-benchmark-batch.sh
```

**การทำงาน**:
- Run benchmark แบบ batch
- Process multiple tasks
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ benchmark แบบ batch
- เมื่อต้องการทดสอบ batch processing

---

### `run-benchmark-concurrent.sh`
**วัตถุประสงค์**: รัน Benchmark แบบ Concurrent

**วิธีใช้งาน**:
```bash
bash scripts/pod/run-benchmark-concurrent.sh
```

**การทำงาน**:
- Run benchmark แบบ concurrent
- Process multiple tasks พร้อมกัน
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ benchmark แบบ concurrent
- เมื่อต้องการทดสอบ concurrency

---

### `run-benchmark-4000ada-remote.sh`
**วัตถุประสงค์**: รัน Benchmark 4000 ADA แบบ Remote

**วิธีใช้งาน**:
```bash
bash scripts/pod/run-benchmark-4000ada-remote.sh
```

**การทำงาน**:
- Run benchmark บน 4000 ADA แบบ remote
- Monitor performance
- สรุปผลลัพธ์

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ benchmark 4000 ADA แบบ remote
- เมื่อต้องการ remote testing

---

### `run-full-test-and-summarize.sh`
**วัตถุประสงค์**: รันทดสอบเต็มรูปแบบและสรุป

**วิธีใช้งาน**:
```bash
bash scripts/pod/run-full-test-and-summarize.sh
```

**การทำงาน**:
- Run full test suite
- สรุปผลลัพธ์ทั้งหมด
- Generate comprehensive report

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ run full test
- เมื่อต้องการ comprehensive testing

---

## 🔧 Diagnostic & Troubleshooting

### `diagnose-and-restart-worker.sh`
**วัตถุประสงค์**: วินิจฉัยและ Restart Worker

**วิธีใช้งาน**:
```bash
bash scripts/pod/diagnose-and-restart-worker.sh
```

**การทำงาน**:
- วินิจฉัย worker issues
- Restart worker ถ้าจำเป็น
- Log diagnostic information

**เมื่อไหร่ควรใช้**:
- เมื่อ worker มีปัญหา
- เมื่อต้องการ diagnose และ fix worker

---

### `diagnose-transcription.sh`
**วัตถุประสงค์**: วินิจฉัย Transcription Issues

**วิธีใช้งาน**:
```bash
bash scripts/pod/diagnose-transcription.sh
```

**การทำงาน**:
- วินิจฉัย transcription issues
- วิเคราะห์ logs
- แนะนำการแก้ไข

**เมื่อไหร่ควรใช้**:
- เมื่อ transcription มีปัญหา
- เมื่อต้องการ diagnose transcription

---

### `diagnose-task-dashboard.sh`
**วัตถุประสงค์**: Dashboard สำหรับวินิจฉัย Tasks

**วิธีใช้งาน**:
```bash
bash scripts/pod/diagnose-task-dashboard.sh
```

**การทำงาน**:
- แสดง task dashboard
- วิเคราะห์ task status
- แนะนำการแก้ไข

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการดู task dashboard
- เมื่อต้องการ diagnose tasks

---

### `fix-transcription-issues.sh`
**วัตถุประสงค์**: แก้ปัญหา Transcription

**วิธีใช้งาน**:
```bash
bash scripts/pod/fix-transcription-issues.sh
```

**การทำงาน**:
- แก้ปัญหา transcription issues
- Restart services ถ้าจำเป็น
- Cleanup resources

**เมื่อไหร่ควรใช้**:
- เมื่อ transcription มีปัญหา
- เมื่อต้องการ fix transcription issues

---

### `fix-multiple-consumers.sh`
**วัตถุประสงค์**: แก้ปัญหา Multiple Consumers

**วิธีใช้งาน**:
```bash
bash scripts/pod/fix-multiple-consumers.sh
```

**การทำงาน**:
- แก้ปัญหา multiple consumers
- Restart worker
- Re-register consumers

**เมื่อไหร่ควรใช้**:
- เมื่อมีปัญหา multiple consumers
- เมื่อ consumers ไม่ register

---

### `fix-service-connection.sh`
**วัตถุประสงค์**: แก้ปัญหา Service Connection

**วิธีใช้งาน**:
```bash
bash scripts/pod/fix-service-connection.sh
```

**การทำงาน**:
- แก้ปัญหา service connection
- Restart services
- Test connection

**เมื่อไหร่ควรใช้**:
- เมื่อ service connection มีปัญหา
- เมื่อ connection หลุด

---

### `fix-ctranslate2-cudnn8.sh`
**วัตถุประสงค์**: แก้ปัญหา CTranslate2 cuDNN 8 Compatibility

**วิธีใช้งาน**:
```bash
bash scripts/pod/fix-ctranslate2-cudnn8.sh
```

**การทำงาน**:
- แก้ปัญหา CTranslate2 cuDNN 8 compatibility
- Setup library paths
- Test compatibility

**เมื่อไหร่ควรใช้**:
- เมื่อมีปัญหา CTranslate2 cuDNN 8
- เมื่อต้องการ fix compatibility

---

### `fix-ctranslate2-cuda.sh`
**วัตถุประสงค์**: แก้ปัญหา CTranslate2 CUDA

**วิธีใช้งาน**:
```bash
bash scripts/pod/fix-ctranslate2-cuda.sh
```

**การทำงาน**:
- แก้ปัญหา CTranslate2 CUDA
- Setup CUDA paths
- Test CUDA functionality

**เมื่อไหร่ควรใช้**:
- เมื่อมีปัญหา CTranslate2 CUDA
- เมื่อต้องการ fix CUDA issues

---

### `fix-port-8001.sh`
**วัตถุประสงค์**: แก้ปัญหา Port 8001

**วิธีใช้งาน**:
```bash
bash scripts/pod/fix-port-8001.sh
```

**การทำงาน**:
- แก้ปัญหา port 8001
- Kill processes ที่ใช้ port
- Free port

**เมื่อไหร่ควรใช้**:
- เมื่อ port 8001 ถูกใช้
- เมื่อมีปัญหา port conflict

---

### `quick-fix.sh`
**วัตถุประสงค์**: Quick Fix สำหรับ Common Issues

**วิธีใช้งาน**:
```bash
bash scripts/pod/quick-fix.sh
```

**การทำงาน**:
- Fix common issues
- Restart services
- Cleanup resources

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ quick fix
- เมื่อมี common issues

---

### `remote-fix.sh`
**วัตถุประสงค์**: Remote Fix สำหรับ Issues

**วิธีใช้งาน**:
```bash
bash scripts/pod/remote-fix.sh
```

**การทำงาน**:
- Fix issues แบบ remote
- Restart services
- Test fixes

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ fix แบบ remote
- เมื่อ remote access

---

### `ffmpeg-diagnostic.sh`
**วัตถุประสงค์**: วินิจฉัย FFmpeg Issues

**วิธีใช้งาน**:
```bash
bash scripts/pod/ffmpeg-diagnostic.sh
```

**การทำงาน**:
- วินิจฉัย FFmpeg issues
- ตรวจสอบ FFmpeg installation
- แนะนำการแก้ไข

**เมื่อไหร่ควรใช้**:
- เมื่อ FFmpeg มีปัญหา
- เมื่อต้องการ diagnose FFmpeg

---

### `quick-fix-ffmpeg.sh`
**วัตถุประสงค์**: Quick Fix สำหรับ FFmpeg

**วิธีใช้งาน**:
```bash
bash scripts/pod/quick-fix-ffmpeg.sh
```

**การทำงาน**:
- Quick fix FFmpeg issues
- Reinstall FFmpeg ถ้าจำเป็น
- Test FFmpeg

**เมื่อไหร่ควรใช้**:
- เมื่อ FFmpeg มีปัญหา
- เมื่อต้องการ quick fix FFmpeg

---

### `remote-test-ffmpeg.sh`
**วัตถุประสงค์**: Remote Test FFmpeg

**วิธีใช้งาน**:
```bash
bash scripts/pod/remote-test-ffmpeg.sh
```

**การทำงาน**:
- Test FFmpeg แบบ remote
- ตรวจสอบ FFmpeg functionality

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ test FFmpeg แบบ remote
- เมื่อ remote access

---

### `run-ffmpeg-test.sh`
**วัตถุประสงค์**: รัน FFmpeg Test

**วิธีใช้งาน**:
```bash
bash scripts/pod/run-ffmpeg-test.sh
```

**การทำงาน**:
- Run FFmpeg test
- ตรวจสอบ FFmpeg functionality

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ test FFmpeg
- เมื่อต้องการตรวจสอบ FFmpeg

---

## 🚀 Deployment & Build

### `build-and-push-runpod-base.sh`
**วัตถุประสงค์**: Build และ Push RunPod Base Image

**วิธีใช้งาน**:
```bash
bash scripts/pod/build-and-push-runpod-base.sh
```

**การทำงาน**:
- Build base image
- Push ไปยัง ACR
- Tag image

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ build base image
- เมื่อต้องการ push image

---

### `build-and-push-runpod-complete.sh`
**วัตถุประสงค์**: Build และ Push Complete Image (มี Dependencies ติดตั้งไว้แล้ว)

**วิธีใช้งาน**:
```bash
bash scripts/pod/build-and-push-runpod-complete.sh
```

**การทำงาน**:
- Build complete image
- Push ไปยัง ACR
- Tag image

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ build complete image
- เมื่อต้องการ push image with dependencies

---

### `deploy-to-runpod.sh`
**วัตถุประสงค์**: Deploy ไปยัง RunPod

**วิธีใช้งาน**:
```bash
bash scripts/pod/deploy-to-runpod.sh
```

**การทำงาน**:
- Deploy service ไปยัง RunPod
- Setup environment
- Start services

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ deploy ไปยัง RunPod
- เมื่อต้องการ setup production

---

## 🛠️ Utilities

### `status.sh`
**วัตถุประสงค์**: แสดงสถานะ Services

**วิธีใช้งาน**:
```bash
bash scripts/pod/status.sh
```

**การทำงาน**:
- แสดงสถานะ services ทั้งหมด
- แสดง resource usage
- แสดง health status

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการดูสถานะ services
- เมื่อต้องการ quick status check

---

### `logs-pod.sh`
**วัตถุประสงค์**: ดู Logs ของ Pod

**วิธีใช้งาน**:
```bash
bash scripts/pod/logs-pod.sh
```

**การทำงาน**:
- แสดง logs ของ pod services
- Filter logs
- Follow logs

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการดู logs
- เมื่อต้องการ troubleshoot

---

### `tail-all-logs.sh`
**วัตถุประสงค์**: Tail Logs ทั้งหมด

**วิธีใช้งาน**:
```bash
bash scripts/pod/tail-all-logs.sh
```

**การทำงาน**:
- Tail logs ทั้งหมด
- Follow logs
- Filter logs

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ tail logs
- เมื่อต้องการ monitor logs

---

### `download-video.sh`
**วัตถุประสงค์**: ดาวน์โหลด Video

**วิธีใช้งาน**:
```bash
bash scripts/pod/download-video.sh [URL] [OUTPUT]
```

**พารามิเตอร์**:
- `URL`: Video URL
- `OUTPUT`: Output file path

**การทำงาน**:
- Download video จาก URL
- Save ไปยัง output path

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ download video
- เมื่อต้องการ test video processing

---

### `download-multiple-videos.sh`
**วัตถุประสงค์**: ดาวน์โหลด Videos หลายไฟล์

**วิธีใช้งาน**:
```bash
bash scripts/pod/download-multiple-videos.sh [URL_FILE]
```

**พารามิเตอร์**:
- `URL_FILE`: File ที่มี URLs

**การทำงาน**:
- Download videos จาก URLs
- Save ไปยัง output directory

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ download videos หลายไฟล์
- เมื่อต้องการ batch download

---

### `cleanup-old-tasks.sh`
**วัตถุประสงค์**: ลบ Tasks เก่า

**วิธีใช้งาน**:
```bash
bash scripts/pod/cleanup-old-tasks.sh
```

**การทำงาน**:
- ลบ tasks เก่า
- Cleanup storage
- Free resources

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ cleanup old tasks
- เมื่อ storage เต็ม

---

### `cleanup-storage.sh`
**วัตถุประสงค์**: Cleanup Storage

**วิธีใช้งาน**:
```bash
bash scripts/pod/cleanup-storage.sh
```

**การทำงาน**:
- Cleanup storage
- ลบ temporary files
- Free disk space

**เมื่อไหร่ควรใช้**:
- เมื่อ storage เต็ม
- เมื่อต้องการ cleanup storage

---

### `reset-database.sh`
**วัตถุประสงค์**: Reset Database

**วิธีใช้งาน**:
```bash
bash scripts/pod/reset-database.sh
```

**การทำงาน**:
- Reset database
- ลบข้อมูลเก่า
- Initialize database ใหม่

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ reset database
- เมื่อมีปัญหา database

**⚠️ คำเตือน**: Script นี้จะลบข้อมูลทั้งหมด!

---

### `update-and-reset.sh`
**วัตถุประสงค์**: Update และ Reset

**วิธีใช้งาน**:
```bash
bash scripts/pod/update-and-reset.sh
```

**การทำงาน**:
- Update code
- Reset database
- Restart services

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ update และ reset
- เมื่อต้องการ fresh start

**⚠️ คำเตือน**: Script นี้จะลบข้อมูลทั้งหมด!

---

### `comprehensive-resource-check.sh`
**วัตถุประสงค์**: ตรวจสอบ Resources แบบครอบคลุม

**วิธีใช้งาน**:
```bash
bash scripts/pod/comprehensive-resource-check.sh
```

**การทำงาน**:
- ตรวจสอบ resources ทั้งหมด
- วิเคราะห์ resource usage
- แนะนำการ optimize

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการตรวจสอบ resources
- เมื่อต้องการ optimize resources

---

### `result-view.sh`
**วัตถุประสงค์**: ดูผลลัพธ์

**วิธีใช้งาน**:
```bash
bash scripts/pod/result-view.sh [TASK_ID]
```

**พารามิเตอร์**:
- `TASK_ID` (optional): Task ID ที่ต้องการดู

**การทำงาน**:
- แสดงผลลัพธ์ของ tasks
- วิเคราะห์ results
- Export results

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการดู results
- เมื่อต้องการ analyze results

---

### `task-service.sh`
**วัตถุประสงค์**: จัดการ Tasks

**วิธีใช้งาน**:
```bash
bash scripts/pod/task-service.sh [COMMAND] [ARGS]
```

**Commands**:
- `list`: แสดง tasks ทั้งหมด
- `status [TASK_ID]`: แสดงสถานะ task
- `cancel [TASK_ID]`: ยกเลิก task
- `retry [TASK_ID]`: Retry task

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการจัดการ tasks
- เมื่อต้องการ monitor tasks

---

### `ssh-runpod.sh`
**วัตถุประสงค์**: SSH ไปยัง RunPod

**วิธีใช้งาน**:
```bash
bash scripts/pod/ssh-runpod.sh
```

**การทำงาน**:
- SSH ไปยัง RunPod server
- Setup SSH connection

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ SSH ไปยัง RunPod
- เมื่อต้องการ remote access

---

### `ssh-4000ada.sh`
**วัตถุประสงค์**: SSH ไปยัง 4000 ADA

**วิธีใช้งาน**:
```bash
bash scripts/pod/ssh-4000ada.sh
```

**การทำงาน**:
- SSH ไปยัง 4000 ADA server
- Setup SSH connection

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ SSH ไปยัง 4000 ADA
- เมื่อต้องการ remote access

---

### `healthcheck.sh`
**วัตถุประสงค์**: Health Check

**วิธีใช้งาน**:
```bash
bash scripts/pod/healthcheck.sh
```

**การทำงาน**:
- ตรวจสอบ health ของ services
- Return exit code (0 = healthy, 1 = unhealthy)

**เมื่อไหร่ควรใช้**:
- สำหรับ health check automation
- สำหรับ monitoring systems

---

### `start-services-direct.sh`
**วัตถุประสงค์**: Start Services โดยตรง

**วิธีใช้งาน**:
```bash
bash scripts/pod/start-services-direct.sh
```

**การทำงาน**:
- Start services โดยตรง (ไม่ใช้ daemon)
- Useful สำหรับ debugging

**เมื่อไหร่ควรใช้**:
- เมื่อต้องการ debug
- เมื่อต้องการ run services แบบ foreground

---

## 📊 Quick Reference

### 🔴 Critical Scripts (เรียกใช้จาก Code)
- `restart-service-daemon.sh` - เรียกจาก API `/api/control/restart`
- `start-service-daemon.sh` - เรียกจาก API `/api/control/start`

### 🟡 Important Scripts (เรียกใช้จาก Scripts อื่น)
- `start-service-daemon.sh` - เรียกจากหลาย scripts
- `restart-service-daemon.sh` - เรียกจาก test scripts
- `install-dependencies.sh` - เรียกจาก start-service-daemon.sh

### 🟢 Most Used Scripts
- `restart-worker-only.sh` - Restart worker เท่านั้น
- `worker-health-check.sh` - Health check และ auto-restart
- `monitor-worker-errors.sh` - Monitor errors
- `check-all-services.sh` - ตรวจสอบ services ทั้งหมด

---

## 💡 Tips

1. **Health Check Scripts**: ใช้สำหรับ cron jobs เพื่อ auto-monitor และ auto-restart
2. **Restart Scripts**: ใช้เมื่อต้องการ restart services หลังจากแก้ไข configuration
3. **Test Scripts**: ใช้สำหรับทดสอบและ benchmark
4. **Diagnostic Scripts**: ใช้เมื่อมีปัญหาและต้องการวินิจฉัย

---

## 📝 Notes

- Scripts ส่วนใหญ่ต้องการ environment variables จาก `env.runpod`
- บาง scripts ต้องการ root privileges
- Scripts ที่มี "persistent" จะเก็บข้อมูลไว้ใน `/workspace/.local`
- Scripts ที่มี "daemon" จะทำงานใน background

---

## 🔗 Related Documentation

- `README.md` - คู่มือการใช้งาน scripts
- `README-CHECK-SCRIPTS.md` - คู่มือ check scripts
- `README-CONNECTION-ISSUES.md` - คู่มือแก้ปัญหา connection
- `README-PERSISTENT-DEPENDENCIES.md` - คู่มือ dependencies
- `SCRIPT_USAGE_REPORT.md` - รายงานการใช้งาน scripts

---

**อัปเดตล่าสุด**: 2025-12-17

