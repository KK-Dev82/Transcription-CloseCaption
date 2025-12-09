# Prefetch Count Analysis และการตั้งค่าที่เหมาะสม

## 📊 สรุปปัญหา

### ปัญหาที่พบ
- RTX 4080 Super: เสร็จแค่ 5/10 tasks (3 ครั้งติดต่อกัน)
- RTX 4000 Ada: เสร็จ 10/10 tasks ✅
- Code เดียวกัน แต่ผลลัพธ์ต่างกัน

### สาเหตุ
- `prefetch_count=1` สำหรับ `transcription_request_queue` ทำให้ consumer รับได้แค่ 1 message ต่อครั้ง
- หลังจาก process 5 tasks แล้ว consumer หยุดรับ task ใหม่

---

## 🔍 Prefetch Count คืออะไร?

### คำอธิบาย
`prefetch_count` คือจำนวน messages ที่ RabbitMQ จะส่งให้ consumer **ล่วงหน้า** (pre-fetch) ก่อนที่ consumer จะ acknowledge

### กลไกการทำงาน
```
Consumer ตั้ง prefetch_count=5
  ↓
RabbitMQ ส่ง 5 messages ให้ consumer ทันที
  ↓
Consumer process messages (อาจใช้เวลานาน)
  ↓
เมื่อ acknowledge 1 message → RabbitMQ ส่ง 1 message ใหม่
```

---

## ✅ ข้อดีของ Prefetch Count สูง (10)

### 1. **Throughput สูงขึ้น**
- Consumer รับ messages ได้หลายตัวพร้อมกัน
- ไม่ต้องรอ acknowledge ก่อนรับ message ใหม่
- เหมาะสำหรับ tasks ที่ process เร็ว

### 2. **ลด Latency**
- Messages พร้อมให้ process ทันที
- ไม่ต้องรอ network round-trip

### 3. **Utilization ดีขึ้น**
- GPU/CPU ทำงานเต็มที่
- ไม่มี idle time

---

## ❌ ข้อเสียของ Prefetch Count สูง (10)

### 1. **Memory Usage สูง**
- Messages ค้างใน consumer memory
- ถ้ามี 10 messages แต่ละ message ใหญ่ → ใช้ memory มาก

### 2. **Crash Risk**
- ถ้า worker crash → messages ที่ prefetch แล้วจะหาย
- ต้องรอ timeout แล้ว requeue

### 3. **Unfair Distribution**
- Consumer ที่เร็วจะได้ messages มากกว่า
- Consumer ที่ช้าอาจไม่มีงานทำ

### 4. **ไม่เหมาะกับ Long-Running Tasks**
- Tasks ที่ใช้เวลานาน (เช่น transcription 10 นาที)
- Messages ค้างใน memory นานเกินไป

---

## 🎯 การตั้งค่าที่เหมาะสมสำหรับ Production

### สถานการณ์ Production
- **50 queues**: 1 priority สูงสุด (Close Caption) + 49 queues ปกติ
- **GPU Concurrency**: 2 (ไม่เกิน 2 jobs พร้อมกัน)
- **Max Workers**: 5 (สำหรับ chunks)

### การตั้งค่าที่แนะนำ

```bash
# .env.runpod

# GPU Concurrency (จำกัด concurrent GPU tasks)
GPU_CONCURRENCY=2

# Transcription Workers (สำหรับ chunks)
TRANSCRIPTION_MAX_WORKERS=5

# Prefetch Count สำหรับแต่ละ Queue
TRANSCRIPTION_QUEUE_PREFETCH_COUNT=1        # Full video tasks (ใช้เวลานาน)
TRANSCRIPTION_PREFETCH_COUNT=5              # Chunks (process เร็ว)
TRANSCRIPTION_REQUEST_PREFETCH_COUNT=2     # Request queue (download & route เร็ว)
```

### เหตุผล

#### 1. `TRANSCRIPTION_QUEUE_PREFETCH_COUNT=1`
- ✅ Full video tasks ใช้เวลานาน (10-30 นาที)
- ✅ ใช้ GPU_CONCURRENCY=2 จำกัดอยู่แล้ว
- ✅ Tasks ค้างใน Queue ดีกว่าค้างใน Worker memory
- ✅ ถ้า worker crash → tasks ยังอยู่ใน Queue

#### 2. `TRANSCRIPTION_PREFETCH_COUNT=5`
- ✅ Chunks process เร็ว (10-30 วินาที)
- ✅ เท่ากับ max_workers เพื่อให้มีงานรออยู่เสมอ
- ✅ ไม่รับงานมากเกินไป

#### 3. `TRANSCRIPTION_REQUEST_PREFETCH_COUNT=2`
- ✅ Download & Route ใช้เวลาไม่นาน (5-10 วินาที)
- ✅ รับได้ 2 tasks พร้อมกันเพื่อลด latency
- ✅ ไม่สูงเกินไปเพื่อป้องกัน memory issues

---

## 🔄 การแก้ไขปัญหาเฉพาะหน้า vs ระยะยาว

### การแก้ไขปัญหาเฉพาะหน้า (prefetch_count=10)
- ✅ **ข้อดี**: แก้ปัญหาได้ทันที (รับได้ 10 tasks)
- ❌ **ข้อเสีย**: 
  - ไม่เหมาะกับ production (tasks ค้างใน memory นาน)
  - ถ้า worker crash → tasks หาย
  - Memory usage สูง

### การแก้ไขระยะยาว (prefetch_count=2 + GPU_CONCURRENCY=2)
- ✅ **ข้อดี**:
  - Tasks ค้างใน Queue ดีกว่าค้างใน Worker
  - ถ้า worker crash → tasks ยังอยู่ใน Queue
  - Memory usage ต่ำ
  - ควบคุม concurrent GPU tasks ได้ดี
- ⚠️ **ข้อเสีย**: 
  - Throughput อาจต่ำกว่าเล็กน้อย
  - ต้องรอ acknowledge ก่อนรับ task ใหม่

---

## 💡 คำแนะนำสำหรับ Production

### 1. ใช้ Prefetch Count ต่ำ (1-2)
```bash
TRANSCRIPTION_QUEUE_PREFETCH_COUNT=1
TRANSCRIPTION_REQUEST_PREFETCH_COUNT=2
```

### 2. ใช้ GPU_CONCURRENCY จำกัด
```bash
GPU_CONCURRENCY=2  # ไม่เกิน 2 jobs พร้อมกัน
```

### 3. ใช้ Queue Max Length
```bash
MAX_QUEUE_REQUEST=50
MAX_QUEUE_EXTRACTION=80
MAX_QUEUE_TRANSCRIBE=20
```

### 4. ใช้ Priority Queue สำหรับ Close Caption
- Priority สูงสุด (10) สำหรับ Close Caption
- Priority ปกติ (5) สำหรับ tasks อื่นๆ

---

## 📊 เปรียบเทียบ

| Metric | Prefetch=1 | Prefetch=2 | Prefetch=10 |
|--------|------------|------------|-------------|
| **Memory Usage** | ต่ำ | ปานกลาง | สูง |
| **Crash Risk** | ต่ำ | ปานกลาง | สูง |
| **Throughput** | ต่ำ | ปานกลาง | สูง |
| **Latency** | สูง | ปานกลาง | ต่ำ |
| **Production Ready** | ✅ | ✅ | ❌ |

---

## 🎯 สรุป

### สำหรับ Benchmark (10 tasks)
- ใช้ `prefetch_count=10` เพื่อให้เสร็จครบ 10 tasks

### สำหรับ Production (50 queues)
- ใช้ `prefetch_count=1-2` + `GPU_CONCURRENCY=2`
- Tasks ค้างใน Queue ดีกว่าค้างใน Worker
- ควบคุม resource usage ได้ดี
- เสถียรและปลอดภัยกว่า

---

**Generated**: 2025-12-09

