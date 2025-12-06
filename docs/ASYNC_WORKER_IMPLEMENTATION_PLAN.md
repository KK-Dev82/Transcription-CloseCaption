# 🚀 Async Worker (aio-pika) Implementation Plan

**วันที่**: 2025-12-05  
**เป้าหมาย**: สร้าง async worker ที่สมบูรณ์เพื่อแก้ปัญหา thread crash

## 🎯 วัตถุประสงค์

1. ✅ แก้ปัญหา thread safety (IndexError: pop from empty deque)
2. ✅ เพิ่มประสิทธิภาพด้วย async/await
3. ✅ Auto-reconnect built-in (ไม่ต้องใช้ maintenance thread)
4. ✅ ไม่ต้องใช้ thread locks

---

## 📋 Components ที่ต้องสร้าง

### 1. ✅ connection.py (อัพเดตให้สมบูรณ์)
- Queue declarations (quorum queues, max-length, DLX)
- Exchange declarations
- Auto-reconnect (connect_robust)
- No thread locks needed

### 2. ⏳ consumers.py
- Async consumer setup
- QoS configuration
- Consumer registration (async)

### 3. ⏳ handlers.py
- 9 async message handlers
- ใช้ async/await ทั้งหมด
- ไม่ต้องใช้ event loop management

### 4. ⏳ processors.py
- Async task processors
- ใช้ async I/O สำหรับ file operations
- ไม่ต้องใช้ ThreadPoolExecutor

### 5. ⏳ utils.py
- Helper utilities (async versions)
- Progress tracking
- File downloads (async)

### 6. ⏳ video_worker.py
- Main orchestrator (async)
- async def start() method
- Signal handling for graceful shutdown

---

## 🔄 ความแตกต่างระหว่าง Sync vs Async

### Sync Worker (pika)
- ❌ Blocking I/O
- ❌ Thread locks จำเป็น
- ❌ ThreadPoolExecutor สำหรับ parallelism
- ❌ Maintenance thread จำเป็น
- ❌ Thread safety issues

### Async Worker (aio-pika)
- ✅ Non-blocking I/O
- ✅ ไม่ต้องใช้ locks
- ✅ asyncio tasks สำหรับ concurrency
- ✅ Auto-reconnect built-in
- ✅ No thread safety issues

---

## 📝 Implementation Steps

### Step 1: Complete connection.py
- เพิ่ม queue declarations
- เพิ่ม DLX setup
- เพิ่ม exchange declarations
- เพิ่ม publish methods (async)

### Step 2: Create consumers.py
- Async consumer setup
- QoS configuration
- Register all 9 consumers

### Step 3: Create handlers.py
- Convert 9 handlers เป็น async
- Remove event loop management
- Use async/await throughout

### Step 4: Create processors.py
- Convert processors เป็น async
- Use async file operations
- Remove ThreadPoolExecutor

### Step 5: Create utils.py
- Async helper functions
- Async file downloads
- Async progress tracking

### Step 6: Create video_worker.py
- Main async orchestrator
- async def start() method
- Graceful shutdown handling

---

## 🎯 Success Criteria

1. ✅ Async worker ทำงานได้เหมือน sync worker
2. ✅ ไม่มี thread safety errors
3. ✅ Performance ดีขึ้นหรือเท่ากัน
4. ✅ Auto-reconnect ทำงาน
5. ✅ Graceful shutdown ทำงาน

---

## 📊 Expected Benefits

- **Thread Safety**: ✅ ไม่มีปัญหา IndexError
- **Performance**: ✅ ดีขึ้น (event loop efficiency)
- **Memory**: ✅ ใช้ memory น้อยกว่า (no threads)
- **Stability**: ✅ เสถียรกว่า (auto-reconnect)

---

**Last Updated**: 2025-12-05

