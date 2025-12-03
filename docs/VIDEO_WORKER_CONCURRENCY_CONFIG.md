# Video Worker Concurrency Configuration

## 📊 การวิเคราะห์ Video Worker Concurrency

### 1️⃣ Video Worker รับ Tasks ได้กี่ตัวพร้อมกัน?

**ปัจจุบัน:**
- `prefetch_count = 10` (สำหรับ transcription_queue)
- หมายความว่า Worker **รับได้ 10 full video tasks พร้อมกัน**

### 2️⃣ Video Worker Process Tasks อย่างไร?

- แต่ละ task ถูก process ใน **thread แยก** (non-blocking)
- แต่ละ task ใช้เวลานาน (อาจเป็นนาทีหรือชั่วโมง)
- ThreadPoolExecutor ใช้สำหรับ chunks (`TRANSCRIPTION_MAX_WORKERS=5`)

### 3️⃣ ปัญหาที่พบ

❌ **prefetch_count=10** → Worker รับ 10 tasks พร้อมกัน:
- Tasks อาจค้างใน worker memory ได้นาน
- ถ้า worker crash → tasks จะหาย
- Connection overload → crash ง่ายขึ้น
- **Tasks จะค้างใน Worker แทนที่จะค้างใน Queue**

### 4️⃣ 💡 แนวทางแก้ไข

#### สำหรับ Full Video Tasks (transcription_queue)

✅ **ตั้ง `prefetch_count = 1`** เพื่อให้ Worker:
- รับได้แค่ **1 task ต่อครั้ง**
- Process ให้เสร็จก่อนรับ task ใหม่
- ลดความเสี่ยง connection overload
- **Tasks จะค้างใน Queue แทนที่จะค้างใน Worker**

**Configuration:**
```bash
TRANSCRIPTION_QUEUE_PREFETCH_COUNT=1  # Default: 1
```

#### สำหรับ Chunks (transcription_chunk_queue)

✅ **ตั้ง `prefetch_count = max_workers`** เพื่อให้:
- Workers มีงานรออยู่เสมอ
- ไม่รับงานมากเกินไป
- ประมวลผล parallel ได้เต็มที่

**Configuration:**
```bash
TRANSCRIPTION_MAX_WORKERS=5           # จำนวน workers สำหรับ chunks
TRANSCRIPTION_PREFETCH_COUNT=5        # ควรเท่ากับ max_workers
```

## 🔧 การตั้งค่า

### Environment Variables

```bash
# สำหรับ full video tasks (transcription_queue)
TRANSCRIPTION_QUEUE_PREFETCH_COUNT=1

# สำหรับ chunks (transcription_chunk_queue)
TRANSCRIPTION_MAX_WORKERS=5
TRANSCRIPTION_PREFETCH_COUNT=5
```

### คำอธิบาย

1. **TRANSCRIPTION_QUEUE_PREFETCH_COUNT=1**
   - Worker จะรับได้แค่ 1 full video task ต่อครั้ง
   - Task จะถูก process ให้เสร็จก่อนถึงจะรับ task ใหม่
   - Tasks ที่เหลือจะค้างใน Queue (ไม่ค้างใน Worker)

2. **TRANSCRIPTION_MAX_WORKERS=5**
   - จำนวน threads ที่พร้อม process chunks พร้อมกัน
   - ขึ้นอยู่กับ GPU memory และ model size

3. **TRANSCRIPTION_PREFETCH_COUNT=5**
   - จำนวน chunks ที่ Worker รับล่วงหน้า
   - ควรเท่ากับ max_workers เพื่อให้ workers มีงานรออยู่เสมอ

## 📋 ตัวอย่างการทำงาน

### Before (prefetch_count=10)

```
Queue: [Task1, Task2, Task3, ..., Task50]
       ↓
Worker: [Task1, Task2, Task3, ..., Task10] ← รับ 10 tasks พร้อมกัน
         ↓
Process: Task1 (thread 1)
         Task2 (thread 2)
         ...
         Task10 (thread 10)

ปัญหา:
- ถ้า worker crash → 10 tasks หาย
- Connection overload
```

### After (prefetch_count=1)

```
Queue: [Task1, Task2, Task3, ..., Task50]
       ↓
Worker: [Task1] ← รับแค่ 1 task
         ↓
Process: Task1 (thread 1) → เสร็จ → acknowledge
         ↓
Worker: [Task2] ← รับ task ใหม่
         ↓
Process: Task2 (thread 1) → เสร็จ → acknowledge

ข้อดี:
- ถ้า worker crash → แค่ 1 task หาย (task อื่นยังอยู่ใน queue)
- Connection ไม่ overload
- Tasks ค้างใน Queue (ไม่ค้างใน Worker)
```

## ✅ สรุป

1. **Full Video Tasks**: `prefetch_count=1` → Worker รับได้แค่ 1 task ต่อครั้ง
2. **Chunks**: `prefetch_count=max_workers` → Workers มีงานรออยู่เสมอ
3. **Tasks จะค้างใน Queue แทนที่จะค้างใน Worker** → ปลอดภัยกว่า
4. **Connection ไม่ overload** → Worker ไม่ crash ง่าย

## 🔄 การ Restart Worker

หลังจากเปลี่ยน configuration:

```bash
ssh pytorch-pod
cd /workspace/transcription-service
bash scripts/pod/restart-pod.sh
```

