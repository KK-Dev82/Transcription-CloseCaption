# 📋 Video Worker Logs - คู่มือการติดตาม

## 📁 ตำแหน่ง Log Files

Worker ใช้ log files 2 ไฟล์:

1. **Main Log**: `logs/video-worker.log`
   - Log ทุกอย่าง (INFO, WARNING, ERROR)
   - ใช้สำหรับติดตามการทำงานปกติ

2. **Error Log**: `logs/video-worker-errors.log`
   - Log เฉพาะ ERROR level
   - ใช้สำหรับ debug ปัญหา

## 🔍 วิธีติดตาม Logs

### 1. ติดตาม Log แบบ Real-time (แนะนำ)

```bash
# วิธีที่ 1: ใช้ script ที่สร้างไว้ (แนะนำ)
bash scripts/pod/tail-worker-log.sh

# วิธีที่ 2: ใช้ tail -f โดยตรง
tail -f logs/video-worker.log

# วิธีที่ 3: ดูทั้ง main log และ error log
bash scripts/pod/watch-worker-logs.sh
```

### 2. ดู Log ล่าสุด

```bash
# ดู 50 บรรทัดล่าสุด
tail -50 logs/video-worker.log

# ดูเฉพาะ errors
tail -50 logs/video-worker-errors.log

# ดู log พร้อม timestamp
tail -50 logs/video-worker.log | grep -E "INFO|ERROR|WARNING"
```

### 3. ค้นหาใน Log

```bash
# ค้นหาการ process task
grep -i "processing\|received.*message\|transcription" logs/video-worker.log | tail -20

# ค้นหา errors
grep -i "error\|exception\|failed" logs/video-worker.log | tail -20

# ค้นหา heartbeat (ตรวจสอบว่า worker ยังทำงานอยู่)
grep -i "heartbeat" logs/video-worker.log | tail -10
```

### 4. ตรวจสอบ Worker Activity

```bash
# ใช้ script ที่มีอยู่
bash scripts/pod/check-worker-activity.sh

# ตรวจสอบรายละเอียด
bash scripts/pod/check-worker-detailed.sh
```

## ⚠️ ปัญหาที่พบบ่อย

### Log ไม่มี update

**สาเหตุที่เป็นไปได้:**
1. Worker ไม่ได้ทำงาน
2. Worker crash หรือถูก kill
3. Log file ถูก lock

**วิธีแก้:**
```bash
# ตรวจสอบว่า worker ทำงานอยู่หรือไม่
ps aux | grep video_worker

# ตรวจสอบ log file
ls -lh logs/video-worker.log

# Restart worker
bash scripts/pod/restart-service-daemon.sh
```

### Log file ไม่พบ

**สาเหตุ:**
- Worker ยังไม่ได้ start
- Log directory ไม่มี

**วิธีแก้:**
```bash
# สร้าง log directory
mkdir -p logs

# Start worker
bash scripts/pod/start-service-daemon.sh
```

## 📊 Log Patterns ที่น่าสนใจ

### Worker กำลังทำงานปกติ
```
💓 [Heartbeat] Worker alive - RabbitMQ connection healthy
✅ Video Worker พร้อมรับงาน
```

### Worker กำลัง process task
```
📥 Received message from queue: transcription_request_queue
🔄 Processing task: <task_id>
🎬 Starting transcription for: <file>
```

### Worker มีปัญหา
```
❌ Error processing task
⚠️ Channel is closed
🚨 GPU-related error detected!
```

## 🔧 Scripts ที่เกี่ยวข้อง

- `tail-worker-log.sh` - ติดตาม log แบบ real-time
- `watch-worker-logs.sh` - ดูทั้ง main log และ error log
- `check-worker-activity.sh` - ตรวจสอบ worker activity
- `check-worker-detailed.sh` - ตรวจสอบรายละเอียด worker

## 💡 Tips

1. **ใช้ `tail -f` กับ grep เพื่อ filter:**
   ```bash
   tail -f logs/video-worker.log | grep -E "ERROR|processing|task"
   ```

2. **ดู log แบบ real-time พร้อม timestamp:**
   ```bash
   tail -f logs/video-worker.log | while read line; do echo "[$(date '+%H:%M:%S')] $line"; done
   ```

3. **บันทึก log ที่ filter แล้ว:**
   ```bash
   tail -f logs/video-worker.log | grep -E "ERROR|processing" > worker-filtered.log
   ```

