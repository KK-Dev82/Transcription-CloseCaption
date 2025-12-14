# 📊 รายงานการเรียกใช้งาน Scripts ใน scripts/pod

**วันที่สร้าง**: 2024-12-19  
**โฟลเดอร์**: `scripts/pod/`

---

## 📋 สรุป

- **Total Scripts**: 68 ไฟล์
- **ถูกเรียกใช้จาก Python Code**: 2 scripts
- **ถูกเรียกใช้จาก Scripts อื่น**: 15+ scripts
- **ถูกอ้างอิงในเอกสารเท่านั้น**: 30+ scripts
- **ไม่มีการเรียกใช้**: 20+ scripts

---

## 🔴 Scripts ที่ถูกเรียกใช้จาก Python Code

### 1. `restart-service-daemon.sh`
- **เรียกใช้จาก**: `app/api/control.py` (line 120)
- **Endpoint**: `POST /api/control/restart`
- **การใช้งาน**: Restart service ผ่าน API endpoint

```120:120:app/api/control.py
        script_path = Path(__file__).parent.parent.parent / "scripts" / "pod" / "restart-service-daemon.sh"
```

### 2. `start-service-daemon.sh`
- **เรียกใช้จาก**: `app/api/control.py` (line 155)
- **Endpoint**: `POST /api/control/start`
- **การใช้งาน**: Start service ผ่าน API endpoint

```155:155:app/api/control.py
        script_path = Path(__file__).parent.parent.parent / "scripts" / "pod" / "start-service-daemon.sh"
```

---

## 🟡 Scripts ที่ถูกเรียกใช้จาก Scripts อื่น

### 1. `start-service-daemon.sh`
**ถูกเรียกใช้จาก**:
- `quick-fix.sh` (line 61)
- `remote-fix.sh` (line 103)
- `restart-service-daemon.sh` (line 114)
- `install-dependencies.sh` (อ้างอิงในข้อความ)
- `update-and-reset.sh` (อ้างอิงในข้อความ)

### 2. `restart-service-daemon.sh`
**ถูกเรียกใช้จาก**:
- `test-transcription-comparison.sh` (line 214)
- `fix-transcription-issues.sh` (อ้างอิงในข้อความ)
- `docs/SERVER_COMPARISON_GUIDE.md` (อ้างอิง)

### 3. `stop-service.sh`
**ถูกเรียกใช้จาก**:
- `restart-service-daemon.sh` (อ้างอิง)
- `SSH_COMMANDS.md` (อ้างอิง)

### 4. `stop-pod.sh`
**ถูกเรียกใช้จาก**:
- `restart-pod.sh` (line 27)

### 5. `start-pod.sh`
**ถูกเรียกใช้จาก**:
- `restart-pod.sh` (line 33)
- `test-benchmark-4000ada.sh` (line 91)
- `run-benchmark-concurrent.sh` (อ้างอิงในข้อความ)

### 6. `reset-database.sh`
**ถูกเรียกใช้จาก**:
- `update-and-reset.sh` (line 28)

### 7. `check-service-status.sh`
**ถูกเรียกใช้จาก**:
- `test-comparison-2servers.sh` (line 132)
- `docs/SERVER_COMPARISON_GUIDE.md` (อ้างอิง)

### 8. `check-pod.sh`
**ถูกเรียกใช้จาก**:
- `start-pod.sh` (อ้างอิงในข้อความ line 268)
- `run-benchmark-4000ada-remote.sh` (line 58)
- `docs/RTX_4000_ADA_BENCHMARK_GUIDE.md` (อ้างอิง)

### 9. `download-video.sh`
**ถูกเรียกใช้จาก**:
- `test-benchmark-4000ada.sh` (line 119)
- `run-benchmark-4000ada-remote.sh` (line 71)

### 10. `test-benchmark-4000ada.sh`
**ถูกเรียกใช้จาก**:
- `run-benchmark-4000ada-remote.sh` (line 80)

### 11. `run-benchmark-concurrent.sh`
**ถูกเรียกใช้จาก**:
- `test-benchmark-4000ada.sh` (line 201)

### 12. `test-10tasks-and-summarize.sh`
**ถูกเรียกใช้จาก**:
- `test-10tasks-and-summarize.sh` (self-reference, line 333)

### 13. `test-comparison-2servers-quick.sh`
**ถูกเรียกใช้จาก**:
- `test-quick-dry-run.sh` (ตรวจสอบการมีอยู่ของ functions)

### 14. `install-dependencies.sh`
**ถูกเรียกใช้จาก**:
- `start-service-daemon.sh` (line 144)

### 15. `logs-pod.sh`
**ถูกเรียกใช้จาก**:
- `start-pod.sh` (อ้างอิงในข้อความ line 269)

---

## 🟢 Scripts ที่ถูกอ้างอิงในเอกสารเท่านั้น

### Documentation Files ที่อ้างอิง Scripts:

1. **`scripts/INDEX.md`** - รายการ script ทั้งหมด
2. **`scripts/pod/README.md`** - คู่มือการใช้งาน scripts
3. **`docs/RESET_DATABASE.md`** - คู่มือ reset database
4. **`docs/TROUBLESHOOTING.md`** - คู่มือแก้ปัญหา
5. **`docs/SERVER_COMPARISON_GUIDE.md`** - คู่มือเปรียบเทียบ server
6. **`docs/RTX_4000_ADA_BENCHMARK_GUIDE.md`** - คู่มือ benchmark
7. **`SSH_COMMANDS.md`** - คำสั่ง SSH
8. **`scripts/pod/README-CHECK-SCRIPTS.md`** - คู่มือ check scripts
9. **`scripts/pod/README-CONNECTION-ISSUES.md`** - คู่มือแก้ปัญหา connection
10. **`scripts/pod/README-PERSISTENT-DEPENDENCIES.md`** - คู่มือ dependencies

### Scripts ที่ถูกอ้างอิงในเอกสาร:

- `setup-pod.sh`
- `check-pod.sh`
- `check-service-status.sh`
- `check-worker-activity.sh`
- `check-rabbitmq-queue.sh`
- `logs-pod.sh`
- `status.sh`
- `diagnose-and-restart-worker.sh`
- `diagnose-transcription.sh`
- `check-connection-issues.sh`
- `check-logs-diagnosis.sh`
- `fix-multiple-consumers.sh`
- `diagnose-task-dashboard.sh`
- `build-and-push-runpod-base.sh`
- `deploy-to-runpod.sh`
- `setup-nginx-static.sh`
- `setup-ssh.sh`
- `result-view.sh`
- `task-service.sh`
- `download-tool.sh`
- `test-transcription.sh`
- `fix-transcription-issues.sh`
- `check-server-comparison.sh`
- `test-comparison-2servers.sh`
- `test-transcription-comparison.sh`
- `test-transcription-5-10-15.sh`
- `test-transcription-incremental.sh`
- `test-transcription-10tasks.sh`
- `run-benchmark-batch.sh`
- `fix-port-8001.sh`
- `ssh-4000ada.sh`
- `run-benchmark-4000ada-remote.sh`
- `test-benchmark-4000ada.sh`
- `run-benchmark-concurrent.sh`
- `test-4000-ada-sc.sh`
- `test-progressive-tasks.sh`
- `test-quick-dry-run.sh`
- `test-comparison-2servers-quick.sh`
- `test-10tasks-and-summarize.sh`
- `run-full-test-and-summarize.sh`
- `quick-fix.sh`
- `remote-fix.sh`
- `update-and-reset.sh`
- `reset-database.sh`
- `install-dependencies.sh`
- `install-dependencies-cuda12.sh`
- `start-service-daemon.sh`
- `stop-service.sh`
- `restart-service-daemon.sh`
- `start-pod.sh`
- `stop-pod.sh`
- `restart-pod.sh`
- `check-pod.sh`
- `check-task-status.sh`
- `check-worker-detailed.sh`
- `check-worker-activity.sh`
- `check-connection-issues.sh`
- `check-logs-diagnosis.sh`
- `check-server-comparison.sh`
- `check-service-status.sh`
- `check-rabbitmq-queue.sh`
- `diagnose-and-restart-worker.sh`
- `diagnose-transcription.sh`
- `diagnose-task-dashboard.sh`
- `fix-transcription-issues.sh`
- `fix-multiple-consumers.sh`
- `fix-port-8001.sh`
- `fix-ctranslate2-cuda.sh`
- `setup-pod.sh`
- `setup-cudnn-path.sh`
- `setup-nginx-static.sh`
- `setup-ssh.sh`
- `setup-video-worker-service.sh`
- `download-video.sh`
- `download-multiple-videos.sh`
- `tail-all-logs.sh`
- `logs-pod.sh`
- `status.sh`
- `healthcheck.sh`
- `ssh-runpod.sh`
- `ssh-4000ada.sh`
- `deploy-to-runpod.sh`
- `build-and-push-runpod-base.sh`
- `result-view.sh`
- `task-service.sh`
- `cleanup-old-tasks.sh`

---

## ⚪ Scripts ที่ไม่มีการเรียกใช้ (Standalone Scripts)

Scripts เหล่านี้เป็น utility scripts ที่รันโดยตรงจาก command line:

- `check-task-status.sh` - ตรวจสอบสถานะ task
- `check-worker-detailed.sh` - ตรวจสอบ worker แบบละเอียด
- `cleanup-old-tasks.sh` - ลบ tasks เก่า
- `fix-ctranslate2-cuda.sh` - แก้ปัญหา CTranslate2 CUDA
- `fix-port-8001.sh` - แก้ปัญหา port 8001
- `healthcheck.sh` - health check
- `result-view.sh` - ดูผลลัพธ์
- `status.sh` - แสดงสถานะ
- `task-service.sh` - จัดการ tasks
- `test-4000-ada-sc.sh` - ทดสอบ 4000 ADA SC
- `test-progressive-tasks.sh` - ทดสอบ progressive tasks
- `test-quick-dry-run.sh` - ทดสอบ quick dry run
- `test-transcription-5-10-15.sh` - ทดสอบ transcription 5-10-15
- `test-transcription-incremental.sh` - ทดสอบ transcription incremental
- `test-transcription-10tasks.sh` - ทดสอบ transcription 10 tasks
- `test-transcription-comparison.sh` - เปรียบเทียบ transcription
- `test-comparison-2servers.sh` - เปรียบเทียบ 2 servers
- `test-comparison-2servers-quick.sh` - เปรียบเทียบ 2 servers แบบเร็ว
- `test-10tasks-and-summarize.sh` - ทดสอบ 10 tasks และสรุป
- `run-full-test-and-summarize.sh` - รันทดสอบเต็มรูปแบบและสรุป
- `run-benchmark-batch.sh` - รัน benchmark แบบ batch
- `run-benchmark-concurrent.sh` - รัน benchmark แบบ concurrent
- `run-benchmark-4000ada-remote.sh` - รัน benchmark 4000 ADA แบบ remote
- `test-benchmark-4000ada.sh` - ทดสอบ benchmark 4000 ADA
- `download-multiple-videos.sh` - ดาวน์โหลดวิดีโอหลายไฟล์
- `tail-all-logs.sh` - ดู logs ทั้งหมด
- `check-rabbitmq-queue.sh` - ตรวจสอบ RabbitMQ queue
- `check-worker-activity.sh` - ตรวจสอบ worker activity
- `check-connection-issues.sh` - ตรวจสอบปัญหา connection
- `check-logs-diagnosis.sh` - วินิจฉัยจาก logs
- `check-server-comparison.sh` - เปรียบเทียบ server
- `diagnose-and-restart-worker.sh` - วินิจฉัยและ restart worker
- `diagnose-transcription.sh` - วินิจฉัย transcription
- `diagnose-task-dashboard.sh` - dashboard สำหรับวินิจฉัย tasks
- `fix-transcription-issues.sh` - แก้ปัญหา transcription
- `fix-multiple-consumers.sh` - แก้ปัญหา multiple consumers
- `setup-cudnn-path.sh` - setup cuDNN path
- `setup-nginx-static.sh` - setup nginx static
- `setup-ssh.sh` - setup SSH
- `setup-video-worker-service.sh` - setup video worker service
- `deploy-to-runpod.sh` - deploy ไปยัง RunPod
- `build-and-push-runpod-base.sh` - build และ push RunPod base image
- `ssh-runpod.sh` - SSH ไปยัง RunPod
- `ssh-4000ada.sh` - SSH ไปยัง 4000 ADA
- `start-services-direct.sh` - start services โดยตรง
- `check-pod.sh` - ตรวจสอบ pod
- `logs-pod.sh` - ดู logs ของ pod
- `restart-pod.sh` - restart pod
- `stop-pod.sh` - stop pod
- `quick-fix.sh` - quick fix
- `remote-fix.sh` - remote fix
- `update-and-reset.sh` - update และ reset
- `reset-database.sh` - reset database
- `install-dependencies.sh` - ติดตั้ง dependencies
- `install-dependencies-cuda12.sh` - ติดตั้ง dependencies CUDA 12
- `start-service-daemon.sh` - start service daemon
- `stop-service.sh` - stop service
- `restart-service-daemon.sh` - restart service daemon
- `setup-pod.sh` - setup pod
- `start-pod.sh` - start pod

---

## 📊 สรุปตามประเภทการใช้งาน

### 🔴 Critical Scripts (ถูกเรียกใช้จาก Code)
1. `restart-service-daemon.sh` - เรียกจาก API
2. `start-service-daemon.sh` - เรียกจาก API

### 🟡 Important Scripts (ถูกเรียกใช้จาก Scripts อื่น)
1. `start-service-daemon.sh` - เรียกจากหลาย scripts
2. `restart-service-daemon.sh` - เรียกจาก test scripts
3. `stop-service.sh` - เรียกจาก restart script
4. `stop-pod.sh` - เรียกจาก restart-pod.sh
5. `start-pod.sh` - เรียกจาก restart-pod.sh
6. `reset-database.sh` - เรียกจาก update-and-reset.sh
7. `install-dependencies.sh` - เรียกจาก start-service-daemon.sh

### 🟢 Utility Scripts (Standalone)
- Scripts ที่รันโดยตรงจาก command line
- ไม่มีการเรียกใช้จาก code หรือ scripts อื่น
- ส่วนใหญ่เป็น test scripts, diagnostic scripts, และ setup scripts

---

## 💡 คำแนะนำ

1. **Scripts ที่ Critical**: `restart-service-daemon.sh` และ `start-service-daemon.sh` ควรได้รับการดูแลเป็นพิเศษ เพราะถูกเรียกใช้จาก API

2. **Scripts ที่ Important**: Scripts ที่ถูกเรียกใช้จาก scripts อื่นควรมีการทดสอบและตรวจสอบว่า path ถูกต้อง

3. **Standalone Scripts**: Scripts ที่ไม่มีการเรียกใช้สามารถลบได้ถ้าไม่ใช้งานแล้ว แต่ควรตรวจสอบก่อนว่ามีการใช้งานจริงหรือไม่

4. **Documentation**: Scripts ที่ถูกอ้างอิงในเอกสารควรมีการอัพเดทเมื่อมีการเปลี่ยนแปลง

---

## 📝 หมายเหตุ

- รายงานนี้สร้างจากการค้นหาในโค้ดเบสทั้งหมด
- บาง scripts อาจมีการเรียกใช้แบบ dynamic หรือผ่าน environment variables ที่ไม่สามารถตรวจจับได้
- Scripts ที่ถูกอ้างอิงในเอกสารอาจมีการใช้งานจริงแต่ไม่มีการเรียกใช้จาก code

