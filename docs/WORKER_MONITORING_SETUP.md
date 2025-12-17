# 📊 Worker Monitoring Setup Guide

## 📋 สรุปการแก้ไข

แก้ไข 3 ส่วนหลักเพื่อป้องกันปัญหา worker crash:

### 1. ✅ ปรับปรุง Restart Scripts
- **ตรวจสอบ worker health ก่อน kill** - ป้องกันการ kill worker ที่ยัง healthy
- **Graceful shutdown** - ส่ง SIGTERM ก่อน force kill
- **Health check function** - ตรวจสอบ consumers ก่อน restart

**ไฟล์ที่แก้ไข**:
- `scripts/pod/restart-worker-only.sh`
- `scripts/pod/restart-service-daemon.sh`

**การเปลี่ยนแปลง**:
- เพิ่ม `check_worker_health_before_kill()` function
- ตรวจสอบ RabbitMQ consumers ก่อน kill worker
- ใช้ `kill -TERM` ก่อน `kill -9` (graceful shutdown)
- เพิ่ม logging สำหรับ health check results

### 2. ✅ ปรับปรุง Health Check Script
- **ตรวจสอบหลายมิติ** - Process, Logs, RabbitMQ, Memory
- **Auto-restart** - Restart worker อัตโนมัติเมื่อไม่ healthy
- **Detailed logging** - บันทึกผลการตรวจสอบ

**ไฟล์ที่แก้ไข**:
- `scripts/pod/worker-health-check.sh`

**การตรวจสอบ**:
1. ✅ Worker process running
2. ✅ Worker uptime
3. ✅ Log file recent (updated in last 5 minutes)
4. ✅ Error count in logs
5. ✅ RabbitMQ consumers registered
6. ✅ Memory usage

**Auto-restart**:
- Restart worker ถ้าไม่ healthy
- Log health check failures
- Prevent unnecessary restarts

### 3. ✅ เพิ่ม Error Monitoring Script
- **Error pattern detection** - ตรวจจับ error patterns ที่สำคัญ
- **Crash detection** - ตรวจจับ worker crashes
- **Alert logging** - บันทึก alerts สำหรับ critical issues

**ไฟล์ใหม่**:
- `scripts/pod/monitor-worker-errors.sh`

**การตรวจสอบ**:
1. ✅ Error count analysis
2. ✅ Critical error patterns (RabbitMQ, GPU, Memory)
3. ✅ Crash indicators (SIGTERM, Fatal errors)
4. ✅ Worker uptime monitoring

**Log files**:
- `logs/worker-monitor.log` - Monitoring results
- `logs/worker-alerts.log` - Critical alerts

## 🚀 วิธีใช้งาน

### Health Check (Manual)
```bash
# ตรวจสอบ worker health
bash scripts/pod/worker-health-check.sh

# Auto-restart ถ้าไม่ healthy
bash scripts/pod/worker-health-check.sh && echo "Worker is healthy" || echo "Worker restarted"
```

### Error Monitoring (Manual)
```bash
# ตรวจสอบ errors และ crashes
bash scripts/pod/monitor-worker-errors.sh
```

### Setup Cron Jobs (Auto-monitoring)

**Health Check (ทุก 5 นาที)**:
```bash
# เพิ่มใน crontab
*/5 * * * * cd /workspace/transcription-service && bash scripts/pod/worker-health-check.sh >> logs/health-check-cron.log 2>&1
```

**Error Monitoring (ทุก 10 นาที)**:
```bash
# เพิ่มใน crontab
*/10 * * * * cd /workspace/transcription-service && bash scripts/pod/monitor-worker-errors.sh >> logs/monitor-cron.log 2>&1
```

### Setup Crontab
```bash
# แก้ไข crontab
crontab -e

# เพิ่มบรรทัดเหล่านี้:
*/5 * * * * cd /workspace/transcription-service && bash scripts/pod/worker-health-check.sh >> logs/health-check-cron.log 2>&1
*/10 * * * * cd /workspace/transcription-service && bash scripts/pod/monitor-worker-errors.sh >> logs/monitor-cron.log 2>&1
```

## 📊 Log Files

### Health Check Logs
- `logs/worker-health-check.log` - Health check failures และ restarts
- `logs/health-check-cron.log` - Cron job output (ถ้าใช้ cron)

### Error Monitoring Logs
- `logs/worker-monitor.log` - Monitoring results (ทุกครั้งที่รัน)
- `logs/worker-alerts.log` - Critical alerts only
- `logs/monitor-cron.log` - Cron job output (ถ้าใช้ cron)

### Worker Logs
- `logs/video-worker.log` - Main worker log
- `logs/video-worker-errors.log` - Error log only

## 🔍 การตรวจสอบปัญหา

### ตรวจสอบ Worker Health
```bash
# Health check
bash scripts/pod/worker-health-check.sh

# ดู health check log
tail -20 logs/worker-health-check.log
```

### ตรวจสอบ Errors
```bash
# Error monitoring
bash scripts/pod/monitor-worker-errors.sh

# ดู alerts
tail -20 logs/worker-alerts.log

# ดู monitoring results
tail -20 logs/worker-monitor.log
```

### ตรวจสอบ Worker Status
```bash
# Process status
ps aux | grep video_worker

# Logs
tail -50 logs/video-worker.log
tail -50 logs/video-worker-errors.log
```

## 🎯 Expected Behavior

### Healthy Worker
- ✅ Process running
- ✅ Logs updated recently
- ✅ RabbitMQ consumers registered
- ✅ Low error count
- ✅ Normal memory usage

### Unhealthy Worker
- ❌ Process not running → Auto-restart
- ❌ No consumers → Auto-restart
- ❌ High error count → Alert logged
- ❌ Critical patterns → Alert logged

## 📝 Notes

1. **Health Check** - ตรวจสอบทุก 5 นาที (แนะนำ)
2. **Error Monitoring** - ตรวจสอบทุก 10 นาที (แนะนำ)
3. **Auto-restart** - Health check จะ restart worker ถ้าไม่ healthy
4. **Logs** - ทุก log ถูกเก็บใน `logs/` directory
5. **Cron Jobs** - ตั้งค่า cron jobs สำหรับ auto-monitoring

## 🔧 Troubleshooting

### Health Check ไม่ทำงาน
```bash
# ตรวจสอบ permissions
ls -la scripts/pod/worker-health-check.sh

# ตรวจสอบ environment
cd /workspace/transcription-service
bash scripts/pod/worker-health-check.sh
```

### Error Monitoring ไม่ทำงาน
```bash
# ตรวจสอบ permissions
ls -la scripts/pod/monitor-worker-errors.sh

# ตรวจสอบ log files
ls -la logs/
```

### Worker ถูก restart บ่อย
```bash
# ตรวจสอบ health check log
tail -50 logs/worker-health-check.log

# ตรวจสอบ error log
tail -50 logs/video-worker-errors.log

# ตรวจสอบ alerts
tail -50 logs/worker-alerts.log
```

