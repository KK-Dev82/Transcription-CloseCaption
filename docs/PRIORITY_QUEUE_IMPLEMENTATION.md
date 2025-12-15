# Priority Queue Implementation for Close Caption

## 📋 Overview

ระบบ Priority Queue สำหรับให้ Close Caption (realtime_chunks) ถูกประมวลผลก่อน Normal Transcription

## ✅ Implementation

### 1. Queue Configuration

```python
# app/services/rabbitmq_service.py
def _get_queue_arguments(
    self,
    queue_name: str,
    enable_priority: bool = True  # Enable priority queue
) -> Dict[str, Any]:
    arguments = {}
    
    # Priority Queue (รองรับ priority 0-10)
    if enable_priority:
        max_priority = int(os.getenv('RABBITMQ_MAX_PRIORITY', '10'))
        arguments['x-max-priority'] = max_priority
```

### 2. Priority Assignment

```python
# app/services/rabbitmq_service.py
def send_transcription_request_task(...):
    # กำหนด priority ตาม display_mode
    # CloseCaption (realtime_chunks) → priority 10 (สูงสุด)
    # Normal transcription → priority 5 (ปกติ)
    priority = 10 if display_mode == "realtime_chunks" else 5
    
    self.channel.basic_publish(
        exchange='',
        routing_key=self.transcription_request_queue,
        body=json.dumps(task_data),
        properties=pika.BasicProperties(
            delivery_mode=2,  # Persistent
            priority=priority  # Priority: 10 for CloseCaption, 5 for normal
        )
    )
```

### 3. Environment Configuration

```bash
# env.runpod
RABBITMQ_MAX_PRIORITY=10  # รองรับ priority 0-10
```

## 🎯 Priority Levels

| Display Mode | Priority | Description |
|--------------|----------|-------------|
| `realtime_chunks` | **10** | CloseCaption (สูงสุด) |
| `full_text` | **5** | Normal transcription |

## 📊 How It Works

### Message Flow

```
1. Client sends request with display_mode="realtime_chunks"
   ↓
2. API assigns priority=10
   ↓
3. Message published to queue with priority=10
   ↓
4. RabbitMQ sorts messages by priority (10 first, then 5)
   ↓
5. Worker consumes high-priority messages first
   ↓
6. Close Caption processed before Normal Transcription
```

### Example Scenario

```
Queue State:
- Message 1: Normal (priority=5)
- Message 2: Normal (priority=5)
- Message 3: CloseCaption (priority=10) ← Processed first!
- Message 4: Normal (priority=5)

Processing Order:
1. Message 3 (CloseCaption, priority=10)
2. Message 1 (Normal, priority=5)
3. Message 2 (Normal, priority=5)
4. Message 4 (Normal, priority=5)
```

## 🧪 Testing

### Test Script

```bash
# Test with v30-1.mp4
bash scripts/pod/test-v30-1-video.sh [API_URL] [VIDEO_PATH]
```

### Manual Test

```bash
# 1. Normal Transcription (priority=5)
curl -X POST http://localhost:8010/transcribe/ \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "v30-1.mp4",
    "display_mode": "full_text"
  }'

# 2. Close Caption (priority=10)
curl -X POST http://localhost:8010/transcribe/ \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "v30-1.mp4",
    "display_mode": "realtime_chunks",
    "chunk_duration": 3
  }'
```

## ✅ Benefits

1. **Close Caption Priority**: Close Caption จะถูกประมวลผลก่อน Normal Transcription
2. **Better User Experience**: Real-time close caption ได้รับการตอบสนองเร็วขึ้น
3. **Fair Resource Distribution**: Normal transcription ยังคงได้รับการประมวลผลตามลำดับ
4. **No Additional Infrastructure**: ใช้ RabbitMQ native priority feature

## 🔍 Verification

### Check Queue Priority

```bash
# Check queue arguments
rabbitmqctl list_queues name arguments

# Should show:
# transcription_request_queue  [{"x-max-priority":10}, ...]
```

### Monitor Priority Messages

```bash
# Check logs for priority assignment
grep "priority" /tmp/transcription-service.log

# Should show:
# 📤 Published with priority=10 (display_mode=realtime_chunks)
# 📤 Published with priority=5 (display_mode=full_text)
```

## 📝 Notes

1. **Quorum Queues**: Priority queue ทำงานได้ดีกับ Quorum Queues
2. **Message Ordering**: Messages with same priority จะถูกประมวลผลตามลำดับที่เข้ามา
3. **Backward Compatible**: ถ้าไม่ระบุ priority จะใช้ default (5)

## 🚀 Deployment

1. **Update Environment**:
   ```bash
   # Add to .env.runpod
   RABBITMQ_MAX_PRIORITY=10
   ```

2. **Restart Services**:
   ```bash
   bash scripts/pod/restart-service-daemon.sh 8010
   ```

3. **Verify**:
   ```bash
   # Check queue status
   curl http://localhost:8010/api/queue/status
   ```

## ✅ Summary

- ✅ Priority Queue enabled (x-max-priority=10)
- ✅ Close Caption → priority 10
- ✅ Normal Transcription → priority 5
- ✅ Test script created
- ✅ API Gateway ready (FastAPI routes)

