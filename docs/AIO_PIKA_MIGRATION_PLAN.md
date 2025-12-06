# 🔄 Migration Plan: pika → aio-pika

**วันที่**: 2025-12-05  
**เป้าหมาย**: แก้ปัญหา Thread Safety และเพิ่มประสิทธิภาพ

## 📋 Executive Summary

**ตัดสินใจ**: Migrate ไป aio-pika เพื่อ:
- ✅ แก้ปัญหา thread safety (IndexError: pop from empty deque)
- ✅ เพิ่มประสิทธิภาพ (async I/O)
- ✅ ลดความซับซ้อน (ไม่ต้องใช้ thread locks)

**ไม่ทำ**: Redis Streams (เก็บไว้พิจารณาในอนาคต)

---

## 🎯 Architecture Goals

### Current (pika - Blocking)
```
FastAPI (async) → pika (blocking) → ThreadPoolExecutor → Worker Threads
                                      ↓
                                Thread Safety Issues ❌
```

### Target (aio-pika - Async)
```
FastAPI (async) → aio-pika (async) → asyncio tasks → Async Workers
                                      ↓
                            No Thread Safety Issues ✅
```

### Real-time Updates (SignalR + WebSocket)
```
Transcription Worker → RabbitMQ (results) → Backend → SignalR → Frontend
                                                        ↓
                                              Close Caption (3-5s chunks)
```

---

## 📊 Migration Scope

### Files ที่ต้อง Refactor

1. **Video Worker** (`app/workers/video_worker.py`)
   - เปลี่ยน BlockingConnection → AsyncConnection
   - เปลี่ยน ThreadPoolExecutor → asyncio tasks
   - ลบ thread locks

2. **RabbitMQ Service** (`app/services/rabbitmq_service.py`)
   - เปลี่ยน pika → aio-pika
   - Update connection management

3. **Dependencies** (`requirements.txt`)
   - เพิ่ม `aio-pika`
   - เก็บ `pika` ไว้ชั่วคราว (backward compatibility)

---

## 🔧 Implementation Plan

### Phase 1: Preparation (Week 1)

#### 1.1 Add Dependencies
```bash
# requirements.txt
aio-pika==9.3.0
# pika==1.3.2  # Keep for now, remove after migration
```

#### 1.2 Create Async RabbitMQ Service
- สร้าง `app/services/rabbitmq_service_async.py` (ใหม่)
- ใช้ aio-pika
- Parallel run กับ service เดิม

#### 1.3 Create Async Video Worker (POC)
- สร้าง `app/workers/video_worker_async.py` (ใหม่)
- Proof of concept
- ทดสอบกับ queue แยก

### Phase 2: Migration (Week 2-3)

#### 2.1 Migrate Video Worker
```
Step 1: Convert connection management
  - BlockingConnection → AsyncConnection
  - Use connect_robust() for auto-reconnect

Step 2: Convert consumer loops
  - Thread-based → asyncio-based
  - Use queue.iterator() for async consumption

Step 3: Convert task processing
  - ThreadPoolExecutor → asyncio.create_task()
  - Convert blocking I/O → async I/O

Step 4: Remove thread locks
  - ลบ _publish_channel_lock
  - ลบ thread-safe publish methods
```

#### 2.2 Migrate RabbitMQ Service
```
Step 1: Update connection methods
Step 2: Update publish methods (async)
Step 3: Update queue declarations
```

#### 2.3 Update API Endpoints
- Update transcription endpoints to use async service
- Ensure async/await patterns

### Phase 3: Testing (Week 3)

#### 3.1 Unit Tests
- Test async connection management
- Test message consumption
- Test error handling

#### 3.2 Integration Tests
- Test full workflow (request → processing → result)
- Test concurrent requests
- Test connection recovery

#### 3.3 Performance Testing
- Benchmark throughput
- Compare memory usage
- Monitor CPU usage

### Phase 4: Deployment (Week 4)

#### 4.1 Staging Deployment
- Deploy async worker
- Monitor for 1 week
- Compare with old worker

#### 4.2 Production Rollout
- Gradual rollout (10% → 50% → 100%)
- Monitor metrics
- Rollback plan ready

---

## 📝 Code Changes

### Example 1: Connection Management

**Before (pika)**:
```python
# Blocking connection with thread lock
self.publish_connection = pika.BlockingConnection(parameters)
self.publish_channel = self.publish_connection.channel()
self._publish_channel_lock = threading.Lock()

def _get_publish_channel(self):
    with self._publish_channel_lock:  # Thread safety!
        if self.publish_channel and not self.publish_channel.is_closed:
            return self.publish_channel
        # Reconnect logic...
```

**After (aio-pika)**:
```python
# Async connection with auto-reconnect
self.connection = await aio_pika.connect_robust(
    f"amqp://{user}:{password}@{host}:{port}/"
)
self.channel = await self.connection.channel()

# No locks needed! ✅
async def get_channel(self):
    if self.channel.is_closed:
        self.channel = await self.connection.channel()
    return self.channel
```

### Example 2: Message Consumption

**Before (pika)**:
```python
# Thread-based consumption
def run(self):
    while self.running:
        try:
            method, properties, body = self.channel.basic_get(queue)
            if method:
                thread = threading.Thread(target=self.process_task, args=(body,))
                thread.start()
        except Exception as e:
            # Error handling...
```

**After (aio-pika)**:
```python
# Async consumption
async def run(self):
    queue = await self.channel.declare_queue("transcription_queue", durable=True)
    
    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                await self.process_task(message.body)  # Non-blocking!
```

### Example 3: Task Processing

**Before (pika)**:
```python
# Thread pool executor
self.executor = ThreadPoolExecutor(max_workers=5)

def process_task(self, body):
    future = self.executor.submit(self._process_sync, body)
    future.add_done_callback(self._task_done)

def _process_sync(self, body):
    # Blocking operations...
    result = transcription_service.transcribe(file_path)
```

**After (aio-pika)**:
```python
# Async tasks
async def process_task(self, body):
    task = asyncio.create_task(self._process_async(body))
    await task  # Or use asyncio.gather() for parallel

async def _process_async(self, body):
    # Async operations...
    result = await transcription_service.transcribe_async(file_path)
```

### Example 4: Publishing Messages

**Before (pika)**:
```python
# Thread-safe publish with lock
def _safe_publish(self, exchange, routing_key, body, properties):
    with self._publish_channel_lock:  # Lock needed!
        publish_ch = self._get_publish_channel()
        publish_ch.basic_publish(exchange, routing_key, body, properties)
```

**After (aio-pika)**:
```python
# Async publish - no locks needed!
async def publish(self, exchange, routing_key, body, properties):
    await self.channel.default_exchange.publish(
        aio_pika.Message(body.encode(), properties=properties),
        routing_key=routing_key
    )
```

---

## 🔍 Key Changes Summary

### 1. Connection Management
- ✅ `connect_robust()` - Auto-reconnect built-in
- ✅ No thread locks needed
- ✅ Connection pooling via channels

### 2. Message Consumption
- ✅ `queue.iterator()` - Async iterator
- ✅ `message.process()` - Auto-ACK on success
- ✅ Non-blocking I/O

### 3. Task Processing
- ✅ `asyncio.create_task()` - Lightweight tasks
- ✅ `asyncio.gather()` - Parallel execution
- ✅ No ThreadPoolExecutor overhead

### 4. Error Handling
- ✅ Built-in retry mechanisms
- ✅ Connection recovery
- ✅ Graceful degradation

---

## 📊 Performance Expectations

### Memory Usage
- **Before**: ~200MB (threads overhead)
- **After**: ~100MB (async tasks)
- **Improvement**: ~50% reduction

### Throughput
- **Before**: ~50 tasks/min (thread-limited)
- **After**: ~200 tasks/min (event loop)
- **Improvement**: ~4x increase

### CPU Usage
- **Before**: High (context switching)
- **After**: Lower (event loop efficiency)
- **Improvement**: ~30% reduction

---

## 🚨 Migration Risks & Mitigations

### Risk 1: Breaking Changes
**Mitigation**:
- Parallel run old + new workers
- Gradual migration
- Comprehensive testing

### Risk 2: Async Code Complexity
**Mitigation**:
- Code reviews
- Documentation
- Training

### Risk 3: Performance Regression
**Mitigation**:
- Benchmark before/after
- Load testing
- Monitoring

---

## ✅ Success Criteria

1. ✅ No thread safety errors (IndexError, etc.)
2. ✅ Performance improved (throughput ↑, memory ↓)
3. ✅ All existing features work
4. ✅ Production stable (no crashes)

---

## 📅 Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| **Phase 1: Preparation** | 1 week | Add dependencies, create POC |
| **Phase 2: Migration** | 2 weeks | Refactor workers, services |
| **Phase 3: Testing** | 1 week | Unit, integration, performance tests |
| **Phase 4: Deployment** | 1 week | Staging, production rollout |
| **Total** | **4-5 weeks** | |

---

## 🔗 Related Documents

- [AIO_PIKA_REDIS_STREAMS_ANALYSIS.md](./AIO_PIKA_REDIS_STREAMS_ANALYSIS.md) - Analysis
- [VIDEO_WORKER_CRASH_ANALYSIS.md](./VIDEO_WORKER_CRASH_ANALYSIS.md) - Root cause
- [PRODUCTION_IMPROVEMENTS_PLAN.md](./PRODUCTION_IMPROVEMENTS_PLAN.md) - Improvements

---

## 📝 Notes

### SignalR + WebSocket for Close Caption

**Architecture**:
```
Transcription Worker → RabbitMQ (chunk results) → Backend → SignalR → Frontend
                                                        ↓
                                              Close Caption (3-5s chunks)
```

**ไม่ต้องใช้ Redis Streams** เพราะ:
- SignalR สามารถรับข้อมูลจาก RabbitMQ → Backend ได้
- Backend เป็น single point สำหรับ SignalR broadcasting
- Architecture เรียบง่ายกว่า

**Implementation**:
1. Worker ส่ง chunk results ไป RabbitMQ (existing)
2. Backend consume จาก RabbitMQ
3. Backend broadcast ผ่าน SignalR
4. Frontend รับ real-time updates (3-5s chunks)

