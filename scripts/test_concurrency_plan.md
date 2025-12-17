# 📋 แผนการทดสอบ 25 Concurrent Tasks

## 🎯 เป้าหมาย
- 25 tasks เข้ามาและจบออกไป 25 tasks โดยใช้ parallel processing
- RabbitMQ connection เสถียร
- Video Worker ไม่ crash

## 🔍 ปัญหาที่พบ
1. **RabbitMQ connection หลุดบ่อย**
   - Connection ไม่มี auto-reconnect ที่แข็งแกร่ง
   - Channel อาจจะปิดโดยไม่รู้ตัว
   - ไม่มี connection pooling

2. **Video Worker crash บ่อย**
   - Exception handling ไม่ครอบคลุม
   - Resource cleanup ไม่ดี
   - Memory leaks

3. **Queue ไม่ได้ 25 tasks**
   - Connection หลุดก่อนที่จะรับ 25 tasks
   - Prefetch count ตั้งไว้แล้วแต่ connection ไม่เสถียร

## 📊 แผนการทดสอบแบบเป็นขั้นตอน

### Phase 1: Connection Stability Test (1-5 tasks)
**เป้าหมาย**: ตรวจสอบว่า connection เสถียรหรือไม่

1. ทดสอบ 1 task
   - ตรวจสอบ connection ไม่หลุด
   - ตรวจสอบ message flow ครบ
   - ตรวจสอบ worker ไม่ crash

2. ทดสอบ 5 tasks พร้อมกัน
   - ตรวจสอบ connection รับได้ 5 tasks
   - ตรวจสอบ worker process 5 tasks พร้อมกัน
   - ตรวจสอบ connection ไม่หลุดระหว่าง process

### Phase 2: Worker Stability Test (10-15 tasks)
**เป้าหมาย**: ตรวจสอบว่า worker รับได้หลาย tasks พร้อมกัน

1. ทดสอบ 10 tasks พร้อมกัน
   - ตรวจสอบ worker รับได้ 10 tasks
   - ตรวจสอบ worker ไม่ crash
   - ตรวจสอบ memory usage

2. ทดสอบ 15 tasks พร้อมกัน
   - ตรวจสอบ worker รับได้ 15 tasks
   - ตรวจสอบ worker ไม่ crash
   - ตรวจสอบ memory usage

### Phase 3: Full Concurrency Test (25 tasks)
**เป้าหมาย**: ตรวจสอบว่า system รองรับ 25 concurrent tasks

1. ทดสอบ 25 tasks พร้อมกัน
   - ตรวจสอบ connection รับได้ 25 tasks
   - ตรวจสอบ worker process 25 tasks พร้อมกัน
   - ตรวจสอบ connection ไม่หลุด
   - ตรวจสอบ worker ไม่ crash
   - ตรวจสอบ memory usage
   - ตรวจสอบ 25 tasks จบออกไป 25 tasks

## 🛠️ การแก้ไขที่ต้องทำ

### 1. RabbitMQ Connection Stability
- เพิ่ม connection health check
- เพิ่ม auto-reconnect mechanism
- เพิ่ม channel health check
- เพิ่ม connection pooling (ถ้าจำเป็น)

### 2. Video Worker Stability
- เพิ่ม exception handling ที่ครอบคลุม
- เพิ่ม resource cleanup
- เพิ่ม memory leak detection
- เพิ่ม health check mechanism

### 3. Queue Management
- ตรวจสอบ prefetch count ถูกต้อง
- ตรวจสอบ queue limits ถูกต้อง
- ตรวจสอบ connection ไม่หลุดระหว่าง process

## 📝 สคริปต์ทดสอบ

### test_phase1_connection_stability.sh
- ทดสอบ 1 task
- ทดสอบ 5 tasks

### test_phase2_worker_stability.sh
- ทดสอบ 10 tasks
- ทดสอบ 15 tasks

### test_phase3_full_concurrency.sh
- ทดสอบ 25 tasks

## 📊 Metrics ที่ต้องติดตาม

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

