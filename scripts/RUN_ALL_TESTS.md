# 🧪 คู่มือการทดสอบ 25 Concurrent Tasks

## 📋 ภาพรวม

แผนการทดสอบแบ่งเป็น 3 phases เพื่อตรวจสอบ:
1. **Connection Stability** - RabbitMQ connection เสถียร
2. **Worker Stability** - Video Worker ไม่ crash
3. **Full Concurrency** - รองรับ 25 tasks พร้อมกัน

## 🚀 วิธีใช้งาน

### Phase 1: Connection Stability Test
```bash
bash scripts/test_phase1_connection_stability.sh
```

**ทดสอบ:**
- 1 task
- 5 tasks พร้อมกัน

**ตรวจสอบ:**
- Connection ไม่หลุด
- Message flow ครบ
- Worker ไม่ crash

### Phase 2: Worker Stability Test
```bash
bash scripts/test_phase2_worker_stability.sh
```

**ทดสอบ:**
- 10 tasks พร้อมกัน
- 15 tasks พร้อมกัน

**ตรวจสอบ:**
- Worker รับได้หลาย tasks
- Worker ไม่ crash
- Memory usage ปกติ

### Phase 3: Full Concurrency Test
```bash
bash scripts/test_phase3_full_concurrency.sh
```

**ทดสอบ:**
- 25 tasks พร้อมกัน

**ตรวจสอบ:**
- Connection รับได้ 25 tasks
- Worker process 25 tasks พร้อมกัน
- Connection ไม่หลุด
- Worker ไม่ crash
- 25 tasks จบออกไป 25 tasks

## 📊 ผลลัพธ์

ผลลัพธ์จะถูกบันทึกไว้ใน:
- `test_results/phase1_*.json` - Phase 1 results
- `test_results/phase2_*.json` - Phase 2 results
- `test_results/phase3_*.json` - Phase 3 results

## 🔍 การตรวจสอบ Logs

```bash
# ดู worker logs
tail -f logs/video-worker.log

# ดู API logs
tail -f logs/api-service.log

# ดู errors
grep -i error logs/*.log | tail -20
```

## 🛠️ การแก้ไขปัญหา

### ปัญหา: Connection หลุด
1. ตรวจสอบ RabbitMQ server ทำงานอยู่
2. ตรวจสอบ network connection
3. ตรวจสอบ logs สำหรับ connection errors

### ปัญหา: Worker crash
1. ตรวจสอบ memory usage
2. ตรวจสอบ logs สำหรับ exceptions
3. ตรวจสอบ resource cleanup

### ปัญหา: Tasks ไม่ถูก process
1. ตรวจสอบ queue status: `curl http://localhost:8010/queue/status`
2. ตรวจสอบ worker กำลังทำงาน: `ps aux | grep video_worker`
3. ตรวจสอบ prefetch count ใน env.runpod

## 📈 Metrics ที่ต้องติดตาม

1. **Connection Metrics**
   - Connection uptime
   - Reconnection count
   - Connection errors

2. **Worker Metrics**
   - Tasks processed
   - Tasks failed
   - Memory usage
   - CPU usage
   - Crash count

3. **Queue Metrics**
   - Messages in queue
   - Messages processed
   - Messages failed
   - Processing time

## ✅ Checklist

### Phase 1
- [ ] 1 task สำเร็จ
- [ ] 5 tasks สำเร็จ
- [ ] Connection ไม่หลุด
- [ ] Worker ไม่ crash

### Phase 2
- [ ] 10 tasks สำเร็จ
- [ ] 15 tasks สำเร็จ
- [ ] Worker ไม่ crash
- [ ] Memory usage ปกติ

### Phase 3
- [ ] 25 tasks เข้ามา
- [ ] 25 tasks จบออกไป
- [ ] Connection ไม่หลุด
- [ ] Worker ไม่ crash
- [ ] Processing time เหมาะสม

