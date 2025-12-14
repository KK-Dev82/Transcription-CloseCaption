# 🔧 Scripts Index

**อัพเดทล่าสุด**: 2024-12-19

Scripts ทั้งหมดถูกจัดหมวดหมู่ตามการใช้งานจริง

---

## 🔴 ESSENTIAL - จำเป็นสำหรับ Production (9 scripts)

Scripts ที่จำเป็นสำหรับการทำงานปกติ:

### Pod Management (`scripts/pod/`)
1. **install-dependencies.sh** - ติดตั้ง dependencies บน Pod
2. **start-service-daemon.sh** - Start service แบบ daemon
3. **stop-service.sh** - Stop service
4. **restart-service-daemon.sh** - Restart service
5. **reset-database.sh** - Reset database (ลบเก่า เริ่มใหม่)
6. **update-and-reset.sh** - Pull code + reset database

### Database Management (`scripts/`)
7. **migrate_json_to_sqlite.py** - Migrate จาก JSON ไป SQLite
8. **cleanup_old_data.py** - ลบข้อมูลเก่าและไฟล์ชั่วคราว
9. **fix_sqlite_schema.py** - แก้ไข SQLite schema

---

## 🟡 USEFUL - มีประโยชน์เมื่อต้องการ (8 scripts)

Scripts ที่มีประโยชน์เมื่อต้องการตรวจสอบหรือจัดการ:

### Pod Scripts (`scripts/pod/`)
1. **check-pod.sh** - ตรวจสอบสถานะ services
2. **check-service-status.sh** - ตรวจสอบสถานะ service
3. **check-worker-activity.sh** - ตรวจสอบ worker activity
4. **check-rabbitmq-queue.sh** - ตรวจสอบ RabbitMQ queues
5. **logs-pod.sh** - ดู logs
6. **status.sh** - แสดงสถานะ

### Utility Scripts (`scripts/`)
7. **test-local-to-pod.sh** - Test connection local ไป Pod
8. **check-transcription-status.sh** - ตรวจสอบสถานะ transcription

---

## 🟢 DIAGNOSIS - สำหรับ Troubleshooting (6 scripts)

Scripts สำหรับวินิจฉัยปัญหา:

### Pod Scripts (`scripts/pod/`)
1. **diagnose-and-restart-worker.sh** - วินิจฉัยและ restart worker
2. **diagnose-transcription.sh** - วินิจฉัย transcription issues
3. **check-connection-issues.sh** - ตรวจสอบ connection issues
4. **check-logs-diagnosis.sh** - วินิจฉัยจาก logs
5. **fix-multiple-consumers.sh** - แก้ปัญหา multiple consumers
6. **diagnose-task-dashboard.sh** - dashboard สำหรับวินิจฉัย tasks

---

## 🔵 DEPLOYMENT - สำหรับ Deployment (3 scripts)

Scripts สำหรับ deployment:

### Pod Scripts (`scripts/pod/`)
1. **build-and-push-runpod-base.sh** - Build และ push Docker image
2. **deploy-to-runpod.sh** - Deploy ไปยัง RunPod
3. **setup-pod.sh** - Setup Pod ครั้งแรก

---

## ⚪ CONDITIONAL - ใช้เฉพาะกรณี (2 scripts)

Scripts ที่ใช้เฉพาะเมื่อต้องการ:

1. **setup-nginx-static.sh** - Setup nginx (ถ้าไม่ใช้ nginx)
2. **setup-ssh.sh** - Setup SSH (ถ้า setup SSH แล้ว)

---

## 🗑️ Scripts ที่สามารถลบได้ (ถ้าต้องการ)

Scripts เหล่านี้เป็น historical records ที่อาจไม่จำเป็น:

### Old/Unused Scripts
- `scripts/pod/start-pod.sh` - ใช้ `start-service-daemon.sh` แทน
- `scripts/pod/stop-pod.sh` - ใช้ `stop-service.sh` แทน
- `scripts/pod/restart-pod.sh` - ใช้ `restart-service-daemon.sh` แทน
- `scripts/pod/setup-new-pod.sh` - ใช้ `setup-pod.sh` แทน
- `scripts/pod/quick-start.sh` - ไม่จำเป็น

### Analysis/Diagnosis Scripts (เก็บไว้สำหรับอ้างอิง)
- `scripts/*.exp` - Expect scripts สำหรับ automation
- `scripts/*.md` - Analysis documents (ย้ายไป docs/)

---

## 💡 คำแนะนำการใช้งาน

### สำหรับ Developer ใหม่
1. ใช้ `install-dependencies.sh` ติดตั้ง dependencies
2. ใช้ `start-service-daemon.sh` start service
3. ใช้ `check-pod.sh` ตรวจสอบสถานะ

### สำหรับ Troubleshooting
1. ใช้ `check-pod.sh` ตรวจสอบปัญหา
2. ใช้ `diagnose-*.sh` scripts สำหรับวินิจฉัย
3. ใช้ `logs-pod.sh` ดู logs

### สำหรับ Database Issues
1. ใช้ `reset-database.sh` reset database
2. ใช้ `fix_sqlite_schema.py` แก้ไข schema
3. ใช้ `migrate_json_to_sqlite.py` migrate ข้อมูล

---

## 📝 การอัพเดท INDEX นี้

เมื่อเพิ่ม script ใหม่:
1. จัดหมวดหมู่ตามการใช้งาน
2. อัพเดทวันที่ "อัพเดทล่าสุด"
3. เพิ่มคำอธิบายสั้นๆ

