# 🔧 แก้ไขปัญหา Prefetch Count และ Concurrency Control

**วันที่แก้ไข**: 2025-12-10  
**ปัญหา**: Worker รับ messages เกินความสามารถในการประมวลผล ทำให้ tasks ค้าง

---

## 📋 สรุปปัญหา

### ปัญหาที่พบ:
1. **Prefetch Count = 5**: Worker รับ 5 messages พร้อมกัน
2. **GPU_CONCURRENCY = 2**: Worker ทำได้แค่ 2 tasks พร้อมกัน
3. **ผลลัพธ์**: เมื่อมี 10 tasks ส่งมา:
   - Worker รับ 5 messages (prefetch=5)
   - Worker ทำได้แค่ 2 tasks (GPU_CONCURRENCY=2)
   - **มี 3 messages ค้างใน memory (unacked)** → RabbitMQ จะไม่ส่ง messages ใหม่มาทันที
   - Tasks อื่นๆ ค้างที่ queue

### สาเหตุ:
- **Prefetch Count สูงเกินไป**: Worker รับ messages มากกว่าความสามารถในการประมวลผล
- **ไม่มีการควบคุม concurrency ที่ถูกต้อง**: ใช้ prefetch แทน semaphore

---

## ✅ การแก้ไข

### 1. ตั้ง Prefetch Count = 1

**ไฟล์**: `env.runpod`

```bash
# เปลี่ยนจาก
TRANSCRIPTION_REQUEST_PREFETCH_COUNT=5

# เป็น
TRANSCRIPTION_REQUEST_PREFETCH_COUNT=1  # ตั้งเป็น 1 เพื่อไม่ให้ Worker รับ messages เกินความสามารถ
```

**ไฟล์**: `app/workers/async/consumers.py`

```python
# เปลี่ยนจาก
request_prefetch = int(os.getenv('TRANSCRIPTION_REQUEST_PREFETCH_COUNT', str(max_workers)))  # 5
global_prefetch = max(chunk_prefetch, request_prefetch)  # 5

# เป็น
request_prefetch = int(os.getenv('TRANSCRIPTION_REQUEST_PREFETCH_COUNT', '1'))  # Default: 1
chunk_prefetch = int(os.getenv('TRANSCRIPTION_PREFETCH_COUNT', '1'))  # Default: 1
global_prefetch = max(chunk_prefetch, request_prefetch)  # 1
```

### 2. ใช้ GPU Semaphore ควบคุม Concurrency

**การทำงาน**:
- Worker รับ **1 message** ต่อครั้ง (prefetch=1)
- เมื่อ message ถูก ack แล้ว → Worker จะรับ message ใหม่ทันที
- **GPU Semaphore** ควบคุม concurrent tasks = 2 (GPU_CONCURRENCY=2)
- ถ้ามี 2 tasks กำลังทำงานอยู่ → message ใหม่จะรอจนกว่า semaphore จะว่าง

**Flow**:
```
1. RabbitMQ ส่ง message 1 → Worker รับ (prefetch=1)
2. Worker เริ่ม process task 1 → acquire GPU semaphore (1/2)
3. Message 1 ถูก ack → RabbitMQ ส่ง message 2 → Worker รับ
4. Worker เริ่ม process task 2 → acquire GPU semaphore (2/2)
5. Message 2 ถูก ack → RabbitMQ ส่ง message 3 → Worker รับ
6. Worker พยายาม process task 3 → **รอ GPU semaphore** (2/2 full)
7. Task 1 เสร็จ → release GPU semaphore (1/2) → Task 3 เริ่มทำงาน
8. ... (ต่อเนื่อง)
```

---

## 🔍 การตรวจสอบ

### 1. ตรวจสอบ Message Acknowledgment

**ไฟล์**: `app/workers/async/handlers.py`

```python
async def handle_transcription(self, message: IncomingMessage):
    async with message.process():  # ✅ Message จะถูก ack อัตโนมัติเมื่อเสร็จแล้ว
        try:
            # ... processing ...
        except Exception as e:
            raise  # ❌ Raise → message จะถูก nack
```

**✅ Message ถูก ack เมื่อ**:
- Processing สำเร็จ → ออกจาก `async with message.process()`
- Exception ไม่เกิด → message ถูก ack

**❌ Message ถูก nack เมื่อ**:
- Exception เกิด → `raise` → message ถูก nack และส่งไป DLQ

### 2. ตรวจสอบ GPU Semaphore

**ไฟล์**: `app/services/whisper_providers/faster_whisper_provider.py`

```python
async def transcribe(...):
    if self.device == "cuda":
        thread_semaphore = self._get_gpu_thread_semaphore()  # GPU_CONCURRENCY=2
        async with _async_semaphore_wrapper(thread_semaphore):  # ✅ Acquire semaphore
            return await self._transcribe_with_retry(...)
    # ... เมื่อเสร็จแล้ว semaphore จะ release อัตโนมัติ
```

**✅ GPU Semaphore ทำงานถูกต้อง**:
- จำกัด concurrent GPU tasks = 2
- Tasks ที่เกิน limit จะรอจนกว่า semaphore จะว่าง

### 3. ตรวจสอบ Connection Management

**ไฟล์**: `app/workers/async/connection.py`

```python
# ใช้ connect_robust สำหรับ auto-reconnect
self.connection = await aio_pika.connect_robust(
    url,
    heartbeat=self.heartbeat  # 1800s = 30 minutes
)
```

**✅ Connection Management**:
- ใช้ `connect_robust` → auto-reconnect เมื่อ connection หลุด
- Heartbeat = 1800s → ตรวจสอบ connection ทุก 30 นาที
- Connection จะไม่ disconnect เมื่อทำงานเสร็จ (จะ reconnect อัตโนมัติ)

---

## 📊 ผลลัพธ์ที่คาดหวัง

### Before (prefetch=5, GPU_CONCURRENCY=2):
```
RabbitMQ Queue: [Task1, Task2, Task3, Task4, Task5, Task6, Task7, Task8, Task9, Task10]
                                      ↓
Worker รับ 5 messages: [Task1, Task2, Task3, Task4, Task5] (unacked)
                                      ↓
Worker ทำได้แค่ 2 tasks: [Task1, Task2] (GPU semaphore: 2/2)
                                      ↓
Task3, Task4, Task5 ค้างใน memory (unacked) → RabbitMQ ไม่ส่ง Task6-10
```

### After (prefetch=1, GPU_CONCURRENCY=2):
```
RabbitMQ Queue: [Task1, Task2, Task3, Task4, Task5, Task6, Task7, Task8, Task9, Task10]
                                      ↓
Worker รับ 1 message: [Task1] → เริ่ม process → acquire GPU semaphore (1/2)
                                      ↓
Message 1 acked → RabbitMQ ส่ง Task2 → Worker รับ → เริ่ม process → acquire GPU semaphore (2/2)
                                      ↓
Message 2 acked → RabbitMQ ส่ง Task3 → Worker รับ → **รอ GPU semaphore** (2/2 full)
                                      ↓
Task1 เสร็จ → release GPU semaphore (1/2) → Task3 เริ่มทำงาน
                                      ↓
Task2 เสร็จ → release GPU semaphore (0/2) → Task4 เริ่มทำงาน (ถ้ามี)
```

---

## 🧪 การทดสอบ

### 1. ทดสอบ Prefetch Count:
```bash
# ตรวจสอบ logs
grep "Set QoS" /tmp/video-worker.log
# ควรเห็น: prefetch_count=1
```

### 2. ทดสอบ GPU Semaphore:
```bash
# ตรวจสอบ logs
grep "GPU Concurrency Semaphore" /tmp/video-worker.log
# ควรเห็น: GPU semaphore acquired/released
```

### 3. ทดสอบ Message Flow:
```bash
# ตรวจสอบ logs
grep "RECEIVED MESSAGE" /tmp/video-worker.log
grep "Acknowledged message" /tmp/video-worker.log
# ควรเห็น: Messages ถูก ack เมื่อเสร็จแล้ว
```

---

## 📝 Configuration

### Current Settings:
```bash
# env.runpod
TRANSCRIPTION_REQUEST_PREFETCH_COUNT=1  # Worker รับ 1 message ต่อครั้ง
GPU_CONCURRENCY=2  # Worker ทำได้ 2 tasks พร้อมกัน
```

### Recommended Flow:
1. **Prefetch = 1**: Worker รับ 1 message ต่อครั้ง
2. **GPU Semaphore = 2**: Worker ทำได้ 2 tasks พร้อมกัน
3. **Message Ack**: Message ถูก ack เมื่อเสร็จแล้ว → Worker รับ message ใหม่ทันที

---

## ✅ Checklist

- [x] ตั้ง `TRANSCRIPTION_REQUEST_PREFETCH_COUNT=1`
- [x] อัปเดต `consumers.py` ให้ใช้ prefetch=1
- [x] ตรวจสอบว่า GPU semaphore ทำงานถูกต้อง
- [x] ตรวจสอบว่า message ถูก ack เมื่อเสร็จแล้ว
- [x] ตรวจสอบว่า connection ไม่ disconnect
- [ ] ทดสอบกับ 10 tasks เพื่อยืนยันการแก้ไข

---

## 🔗 Related Files

- `env.runpod`: Environment configuration
- `app/workers/async/consumers.py`: Consumer setup
- `app/workers/async/handlers.py`: Message handlers
- `app/services/whisper_providers/faster_whisper_provider.py`: GPU semaphore
- `app/workers/async/connection.py`: Connection management

