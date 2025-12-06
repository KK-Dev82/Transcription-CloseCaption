# 📋 Scripts Cleanup Recommendation

**วันที่**: 2025-01-XX  
**สถานะ**: ✅ Cleanup เสร็จสมบูรณ์ - ลบ 9 scripts ที่ซ้ำซ้อนและไม่จำเป็นแล้ว

## ✅ สรุปผลการตรวจสอบ

### 1. install-dependencies.sh

✅ **สถานะ**: ติดตั้ง dependencies ไว้ที่ `/workspace/.local` ถูกต้องแล้ว

- ✅ ใช้ `pip3 install --user` ซึ่งติดตั้งใน `/workspace/.local`
- ✅ ตั้งค่า `PYTHONUSERBASE="/workspace/.local"`
- ✅ ตั้งค่า `PYTHONPATH` ให้ชี้ไปที่ `/workspace/.local/lib/pythonX.X/site-packages`
- ✅ Packages จะ persist หลัง container restart
- ✅ เพิ่มการ verify `aio-pika`, `aiofiles`, `pika` แล้ว

**หมายเหตุ**: ติดตั้งที่ `/workspace/.local` (ไม่ใช่ `/workstation`)

---

## 📊 Scripts ที่ไม่จำเป็น (สามารถลบหรือเก็บไว้ได้)

### ⚪ OPTIONAL - ซ้ำซ้อน (10 scripts)

Scripts เหล่านี้มีหน้าที่ซ้ำกับ scripts อื่น หรือใช้เฉพาะกรณี:

1. **setup-new-pod.sh** → ใช้ `setup-pod.sh` แทน
2. **quick-start.sh** → ใช้ `start-pod.sh` แทน
3. **update-dependencies.sh** → ใช้ `install-dependencies.sh` แทน
4. **start-service-for-backend.sh** → อาจซ้ำกับ `start-service-daemon.sh`
5. **start-services-direct.sh** → อาจซ้ำ
6. **download-test-videos.sh** → สำหรับ testing เท่านั้น
7. **download-tool.sh** → optional utility
8. **download-video.sh** → optional utility
9. **test-direct-transcription.py** → สำหรับ testing
10. **export-environment.sh** → ใช้เมื่อต้องการ export env เท่านั้น

**คำแนะนำ**: ✅ ลบแล้ว (9 scripts)

### 🟠 DIAGNOSIS - สำหรับ debug (6 scripts)

Scripts เหล่านี้มีประโยชน์สำหรับ troubleshooting แต่ไม่จำเป็นสำหรับ production:

1. **check-connection-issues.sh** - ตรวจสอบ connection issues
2. **check-logs-diagnosis.sh** - วินิจฉัยจาก logs
3. **diagnose-and-restart-worker.sh** - วินิจฉัยและ restart worker
4. **diagnose-task-dashboard.sh** - dashboard สำหรับวินิจฉัย tasks
5. **diagnose-transcription.sh** - วินิจฉัย transcription issues
6. **fix-multiple-consumers.sh** - แก้ปัญหา multiple consumers

**คำแนะนำ**: ✅ **เก็บไว้** สำหรับ troubleshooting (มีประโยชน์เมื่อเกิดปัญหา)

### ⚪ CONDITIONAL - ใช้เฉพาะกรณี

1. **setup-nginx-static.sh** → ถ้าไม่ใช้ nginx
2. **setup-ssh.sh** → ถ้า setup SSH แล้ว

---

## 📝 Scripts ที่จำเป็น (เก็บไว้)

### 🔴 ESSENTIAL (9 scripts)

Scripts เหล่านี้จำเป็นสำหรับการทำงานปกติ:

1. ✅ **install-dependencies.sh** - ติดตั้ง dependencies
2. ✅ **setup-pod.sh** - Setup pod ครั้งแรก
3. ✅ **start-pod.sh** - Start services ทั้งหมด
4. ✅ **stop-pod.sh** - Stop services ทั้งหมด
5. ✅ **restart-pod.sh** - Restart services
6. ✅ **check-pod.sh** - ตรวจสอบสถานะ services
7. ✅ **status.sh** - แสดงสถานะ
8. ✅ **start-service-daemon.sh** - Start service แบบ daemon
9. ✅ **stop-service.sh** - Stop service

### 🟡 USEFUL (8 scripts)

Scripts เหล่านี้มีประโยชน์เมื่อต้องการตรวจสอบหรือจัดการ:

1. **check-service-status.sh** - ตรวจสอบสถานะ service
2. **check-worker-activity.sh** - ตรวจสอบ worker activity
3. **check-worker-detailed.sh** - ตรวจสอบ worker แบบละเอียด
4. **check-task-status.sh** - ตรวจสอบสถานะ tasks
5. **check-rabbitmq-queue.sh** - ตรวจสอบ RabbitMQ queues
6. **result-view.sh** - ดู transcription results
7. **task-service.sh** - จัดการ tasks
8. **logs-pod.sh** - ดู logs

### ⚙️ SYSTEM SERVICE (3 files)

1. **setup-video-worker-service.sh** - Setup systemd service
2. **video-worker.service** - Systemd service file
3. **restart-service-daemon.sh** - Restart service daemon

### 🔵 DEPLOYMENT (3 files)

1. **build-and-push-runpod-base.sh** - Build และ push Docker image
2. **deploy-to-runpod.sh** - Deploy ไปยัง RunPod
3. **BUILD_IMAGES_README.md** - Documentation

### 📄 DOCUMENTATION (4 files)

1. **README.md** - เอกสารหลัก
2. **README-CHECK-SCRIPTS.md** - เอกสาร check scripts
3. **README-CONNECTION-ISSUES.md** - เอกสาร connection issues
4. **README-PERSISTENT-DEPENDENCIES.md** - เอกสาร persistent dependencies

---

## 💡 ข้อเสนอแนะ

### 1. install-dependencies.sh ✅

- ✅ ติดตั้งที่ `/workspace/.local` ถูกต้องแล้ว
- ✅ Packages จะ persist หลัง container restart
- ✅ เพิ่มการ verify `aio-pika`, `aiofiles`, `pika` แล้ว

### 2. Scripts ที่ไม่จำเป็น

**สามารถลบได้** (ถ้าไม่ใช้แล้ว):
- `setup-new-pod.sh`
- `quick-start.sh`
- `update-dependencies.sh` (ถ้าใช้ `install-dependencies.sh` แทน)

**เก็บไว้**:
- Diagnosis scripts ทั้งหมด (มีประโยชน์เมื่อเกิดปัญหา)
- Testing scripts (ถ้ายังต้องการใช้)

### 3. Scripts ที่ควรเก็บไว้

- ✅ Essential scripts ทั้งหมด (9 scripts)
- ✅ Useful scripts ทั้งหมด (8 scripts)
- ✅ System service files (3 files)
- ✅ Documentation files (4 files)
- ✅ Diagnosis scripts (6 scripts) - สำหรับ troubleshooting

---

## 📊 สรุป

### ก่อน Cleanup:
- **Total scripts**: 47 files
- **Essential**: 9 scripts
- **Useful**: 8 scripts
- **Diagnosis**: 6 scripts (เก็บไว้)
- **Optional (ลบได้)**: 10 scripts
- **Conditional**: 2 scripts
- **System Service**: 3 files
- **Deployment**: 3 files
- **Documentation**: 4 files

### หลัง Cleanup:
- **Total scripts**: 38 files
- **ลบไป**: 9 scripts
- **ลดลง**: ~19% ของ scripts ทั้งหมด

**สถานะ**: ✅ Cleanup เสร็จสมบูรณ์ - ลบ 9 scripts ที่ซ้ำซ้อนและไม่จำเป็นแล้ว

---

## ✅ Cleanup Status

**วันที่ทำ Cleanup**: 2025-01-XX

### Scripts ที่ลบแล้ว (9 files):

1. ✅ `setup-new-pod.sh` - ใช้ `setup-pod.sh` แทน
2. ✅ `quick-start.sh` - ใช้ `start-pod.sh` แทน
3. ✅ `update-dependencies.sh` - ใช้ `install-dependencies.sh` แทน
4. ✅ `start-service-for-backend.sh` - ใช้ `start-service-daemon.sh` แทน
5. ✅ `download-test-videos.sh` - สำหรับ testing เท่านั้น
6. ✅ `download-tool.sh` - optional utility
7. ✅ `download-video.sh` - optional utility
8. ✅ `test-direct-transcription.py` - สำหรับ testing
9. ✅ `export-environment.sh` - ใช้เมื่อต้องการ export env เท่านั้น

### Scripts ที่เก็บไว้:

- ✅ `start-services-direct.sh` - ยังใช้ใน Dockerfile (Dockerfile.z2-base, Dockerfile.runpod-base)
- ✅ Diagnosis scripts ทั้งหมด (6 scripts) - มีประโยชน์สำหรับ troubleshooting
- ✅ Essential scripts ทั้งหมด (9 scripts)
- ✅ Useful scripts ทั้งหมด (8 scripts)

