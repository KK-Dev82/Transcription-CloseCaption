# 🏗️ Hybrid Architecture: Backend RabbitMQ → Transcription Redis

## 📋 Architecture Overview

```
Backend → RabbitMQ (Central Queue) → Transcription Service API → Redis (Local Queue) → Workers
```

### Flow
1. **Backend** ส่ง transcription request ไปยัง **RabbitMQ** (central queue)
2. **Transcription Service API** consume จาก RabbitMQ
3. **Transcription Service** ส่ง chunks ไปยัง **Redis** (local queue)
4. **Workers** consume จาก Redis และ process

---

## ✅ ข้อดี

### 1. แยก Concerns
- **Backend**: Orchestration, message guarantee, priority queue
- **Transcription**: Fast processing, local queue

### 2. Performance
- **Redis**: เร็วมาก (in-memory, low latency)
- **Local queue**: ไม่มี network latency
- **Fast processing**: Workers process ได้เร็ว

### 3. Simplicity
- **Transcription service**: ใช้ Redis (ง่าย, เร็ว)
- **ไม่ต้องแก้ RabbitMQ connection issues** ใน transcription
- **Backend**: ใช้ RabbitMQ (มี features ครบ)

### 4. Scalability
- **Redis**: Scale ได้ง่าย
- **Workers**: Scale ได้อิสระ
- **Backend**: ไม่ต้องรู้ transcription internals

---

## ⚠️ ข้อควรระวัง

### 1. Message Acknowledgment
- **Redis List**: ไม่มี acknowledgment
- **Message อาจหาย** ถ้า worker crash ก่อน process
- **Solution**: ใช้ Redis Streams (มี acknowledgment)

### 2. Message Tracking
- **ต้อง track** message status
- **ต้อง implement** retry mechanism
- **Solution**: ใช้ Redis + SQLite/JSON storage

### 3. Dead Letter Queue
- **Redis List**: ไม่มี DLQ
- **ต้อง implement** เอง
- **Solution**: ใช้ Redis List แยก (DLQ)

### 4. Message Durability
- **Redis**: AOF แต่ไม่ guarantee
- **Message อาจหาย** ถ้า Redis crash
- **Solution**: ใช้ Redis persistence + backup

---

## 💡 วิธีแก้ไข

### Option 1: Redis Streams (แนะนำ) ✅

**ข้อดี:**
- ✅ มี message acknowledgment
- ✅ มี consumer groups
- ✅ มี message tracking
- ✅ มี pending messages

**Implementation:**
```python
# Send to Redis Stream
redis_client.xadd('transcription_chunk_queue', {
    'task_id': task_id,
    'chunk_index': chunk_index,
    'data': json.dumps(chunk_data)
})

# Consume with acknowledgment
messages = redis_client.xreadgroup(
    'workers', 'worker1',
    {'transcription_chunk_queue': '>'},
    count=1,
    block=1000
)

# Process message
for stream, messages_list in messages:
    for message_id, data in messages_list:
        process_chunk(data)
        # Acknowledge
        redis_client.xack('transcription_chunk_queue', 'workers', message_id)
```

### Option 2: Redis List + Tracking

**ข้อดี:**
- ✅ ง่าย
- ✅ เร็ว

**ข้อเสีย:**
- ❌ ไม่มี acknowledgment
- ❌ ต้อง implement tracking เอง

**Implementation:**
```python
# Send to Redis List
redis_client.lpush('transcription_chunk_queue', json.dumps(chunk_data))

# Consume
message = redis_client.brpop('transcription_chunk_queue', timeout=1)
if message:
    chunk_data = json.loads(message[1])
    try:
        process_chunk(chunk_data)
        # Mark as completed in tracking
        mark_completed(chunk_data['task_id'], chunk_data['chunk_index'])
    except Exception as e:
        # Move to DLQ
        redis_client.lpush('transcription_chunk_queue.dlq', message[1])
```

### Option 3: Redis List + External Tracking

**ใช้ SQLite/JSON storage เพื่อ track:**
```python
# Track message processing
def track_message(task_id, chunk_index, status):
    storage.save_chunk_status(task_id, chunk_index, status)

# Retry mechanism
def retry_failed_chunks():
    failed_chunks = storage.get_failed_chunks()
    for chunk in failed_chunks:
        if chunk['retry_count'] < MAX_RETRIES:
            redis_client.lpush('transcription_chunk_queue', chunk['data'])
            storage.increment_retry(chunk['task_id'], chunk['chunk_index'])
```

---

## 🎯 Recommended Architecture

### Backend → RabbitMQ → Transcription API → Redis Streams → Workers

```
1. Backend → RabbitMQ (Central)
   - Message guarantee
   - Priority queue
   - Dead letter queue
   
2. Transcription API → Consume from RabbitMQ
   - Receive transcription request
   - Create chunks
   - Send to Redis Streams
   
3. Redis Streams → Workers
   - Fast local queue
   - Message acknowledgment
   - Consumer groups
   
4. Workers → Process
   - Fast processing
   - Update status in storage
```

---

## 📊 เปรียบเทียบ

| Feature | RabbitMQ (Backend) | Redis (Transcription) |
|---------|-------------------|----------------------|
| **Message Guarantee** | ✅ | ⚠️ (Streams) |
| **Priority Queue** | ✅ | ❌ |
| **Dead Letter Queue** | ✅ | ⚠️ (ต้อง implement) |
| **Performance** | ⚠️ | ✅ |
| **Simplicity** | ❌ | ✅ |
| **Network Latency** | ⚠️ | ✅ (Local) |

---

## 🔧 Implementation

### 1. Update Transcription Service

```python
# app/services/transcription_service.py
class TranscriptionService:
    def __init__(self):
        # Backend RabbitMQ (for receiving requests)
        self.backend_rabbitmq = RabbitMQService()
        
        # Local Redis (for chunk processing)
        self.local_redis = RedisQueueService()
    
    async def receive_from_backend(self):
        """Consume transcription requests from backend RabbitMQ"""
        # Consume from RabbitMQ
        message = await self.backend_rabbitmq.consume_transcription_request()
        
        # Process and create chunks
        chunks = self.create_chunks(message)
        
        # Send chunks to local Redis
        for chunk in chunks:
            self.local_redis.send_chunk_transcription_task(chunk)
```

### 2. Update Workers

```python
# app/workers/sync/redis_worker.py
class VideoWorkerRedis:
    def run(self):
        while self.running:
            # Consume from Redis Streams
            messages = self.redis_queue_service.consume_chunk_streams(
                callback=self._process_chunk_task,
                timeout=1
            )
```

### 3. Update Redis Queue Service

```python
# app/services/redis_queue_service.py
class RedisQueueService:
    def send_chunk_transcription_task(self, chunk_task: Dict[str, Any]) -> str:
        """Send to Redis Streams (with acknowledgment support)"""
        message_id = self.redis_client.xadd(
            'transcription_chunk_queue',
            chunk_task
        )
        return message_id
    
    def consume_chunk_streams(self, callback, timeout: int = 1):
        """Consume from Redis Streams with acknowledgment"""
        messages = self.redis_client.xreadgroup(
            'workers', 'worker1',
            {'transcription_chunk_queue': '>'},
            count=1,
            block=timeout * 1000
        )
        
        for stream, messages_list in messages:
            for message_id, data in messages_list:
                try:
                    callback(json.loads(data))
                    # Acknowledge
                    self.redis_client.xack(
                        'transcription_chunk_queue',
                        'workers',
                        message_id
                    )
                except Exception as e:
                    # Move to DLQ
                    self.redis_client.xadd(
                        'transcription_chunk_queue.dlq',
                        data
                    )
```

---

## ✅ สรุป

### Architecture นี้ใช้ได้ถ้า:

1. **ใช้ Redis Streams** แทน Redis List
   - มี message acknowledgment
   - มี consumer groups
   - มี message tracking

2. **Implement Retry Mechanism**
   - Track failed messages
   - Retry with exponential backoff
   - Move to DLQ after max retries

3. **Implement Dead Letter Queue**
   - ใช้ Redis Stream แยก (DLQ)
   - Track failed messages
   - Manual retry mechanism

4. **Message Tracking**
   - ใช้ SQLite/JSON storage
   - Track message status
   - Track retry count

### คำแนะนำ:

**✅ ใช้ Architecture นี้ได้** เพราะ:
- Backend ใช้ RabbitMQ (มี features ครบ)
- Transcription ใช้ Redis (เร็ว, ง่าย)
- แยก concerns ชัดเจน
- Performance ดี

**⚠️ แต่ต้อง:**
- ใช้ Redis Streams (ไม่ใช่ Redis List)
- Implement retry mechanism
- Implement DLQ
- Track message status

---

## 🚀 Migration Plan

### Phase 1: Setup Redis Streams
1. Update RedisQueueService to use Streams
2. Update workers to use consumer groups
3. Test message acknowledgment

### Phase 2: Implement Retry
1. Track message status
2. Implement retry logic
3. Test retry mechanism

### Phase 3: Implement DLQ
1. Create DLQ stream
2. Move failed messages to DLQ
3. Test DLQ mechanism

### Phase 4: Deploy
1. Deploy to production
2. Monitor message flow
3. Monitor retry rate
4. Monitor DLQ size

