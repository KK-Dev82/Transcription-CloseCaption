# 🚀 Redis Queue (RQ) Implementation Guide

## 📋 สรุป

ใช้ **Redis + RQ (Redis Queue)** แทน HTTP request แบบ sync เพื่อ:
- ✅ แก้ปัญหา timeout (10s)
- ✅ รองรับ 25 concurrent requests
- ✅ ใช้ Redis ที่มีอยู่แล้ว
- ✅ ง่ายกว่า RabbitMQ สำหรับงานนี้

---

## 🎯 Architecture

```
API (FastAPI)
  ↓
Redis Queue Service (enqueue job)
  ↓
Redis Queue (transcription_gpu0, transcription_gpu1, transcription_default, transcription_priority)
  ↓
RQ Workers (แต่ละ worker fix GPU ด้วย CUDA_VISIBLE_DEVICES)
  ↓
TranscriptionService._process_with_chunking()
```

---

## 📦 Installation

```bash
# ติดตั้ง RQ
pip install rq==1.15.1

# หรือใช้ requirements.txt
pip install -r requirements.txt
```

---

## 🚀 Usage

### 1. Start RQ Workers

```bash
# Start workers สำหรับ 2 GPUs
bash scripts/pod/start-rq-workers.sh
```

Workers จะ:
- GPU 0: consume `transcription_gpu0` และ `transcription_default`
- GPU 1: consume `transcription_gpu1` และ `transcription_default`
- Priority (ถ้ามี GPU 2): consume `transcription_priority`

### 2. API Integration

```python
from app.services.redis_queue_service import get_redis_queue_service

# ใน API endpoint
queue_service = get_redis_queue_service()

# Enqueue job
job_id = queue_service.enqueue_transcription(
    task_id=task_id,
    file_path=file_path,
    language="th",
    model_size="base",
    chunk_duration=90,
    priority=False,  # True สำหรับ live streaming
    worker_gpu=None  # None = round-robin, 'gpu0' หรือ 'gpu1' = specific GPU
)

# Get job status
status = queue_service.get_job_status(job_id)
```

### 3. Monitor Queues

```bash
# ดู queue stats
rq info --url redis://localhost:6379

# ดู worker status
rq worker --url redis://localhost:6379 --help
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Redis URL
REDIS_URL=redis://localhost:6379

# หรือใช้ Redis Cloud
REDIS_URL=redis://default:password@redis-host:port
```

---

## 📊 Queue Strategy

### Round-Robin (Default)
- Jobs ไปที่ `transcription_default` queue
- Workers (GPU 0 และ GPU 1) consume จาก queue นี้
- RQ จะ distribute jobs ให้ workers อัตโนมัติ

### Specific GPU
- Jobs ไปที่ `transcription_gpu0` หรือ `transcription_gpu1`
- Worker ที่ fix GPU นั้นจะ consume

### Priority (Live Streaming)
- Jobs ไปที่ `transcription_priority` queue
- Priority worker (GPU 2) consume
- หรือใช้ GPU 0/1 แต่ consume priority queue ก่อน

---

## ✅ Benefits

1. **No Timeout Issues**
   - API return `task_id` ทันที (<1s)
   - Client poll `/status/{task_id}` แทนรอผล

2. **Better Concurrency**
   - Queue จัดการ jobs อัตโนมัติ
   - Workers consume ตาม capacity

3. **Simple Architecture**
   - ใช้ Redis ที่มีอยู่แล้ว
   - ไม่ต้อง setup RabbitMQ server

4. **Multi-GPU Support**
   - แต่ละ worker fix GPU ของตัวเอง
   - Round-robin หรือ specific GPU

---

## 🆚 Comparison: RQ vs RabbitMQ

| Feature | RQ | RabbitMQ |
|---------|----|----------|
| Setup | ✅ Simple (Redis only) | ⚠️ Need server |
| Learning Curve | ✅ Easy | ⚠️ Moderate |
| Features | ✅ Basic queue | ✅ Advanced features |
| Performance | ✅ Good for this use case | ✅ Better for complex workflows |
| **Recommendation** | ✅ **Use for this project** | ⚠️ Overkill |

---

## 🔄 Migration Plan

### Phase 1: Add RQ (Current)
- ✅ Add `rq` to requirements.txt
- ✅ Create `RedisQueueService`
- ✅ Create worker script
- ✅ Test with 1 request

### Phase 2: API Integration
- ⏳ Update API endpoint to use RQ
- ⏳ Add `/status/{task_id}` endpoint
- ⏳ Test with 5 concurrent requests

### Phase 3: Production
- ⏳ Monitor queue stats
- ⏳ Add retry logic
- ⏳ Add priority queue for live streaming

---

## 📝 Next Steps

1. **Install RQ**: `pip install rq==1.15.1`
2. **Start Workers**: `bash scripts/pod/start-rq-workers.sh`
3. **Update API**: ใช้ `RedisQueueService` แทน HTTP request
4. **Test**: ทดสอบ 1 request → 5 requests → 25 requests

---

## 🐛 Troubleshooting

### Workers not starting
```bash
# Check Redis connection
python3 -c "import redis; r=redis.from_url('redis://localhost:6379'); r.ping()"

# Check logs
tail -f /tmp/rq-worker-gpu0.log
```

### Jobs stuck
```bash
# Check queue stats
rq info --url redis://localhost:6379

# Check failed jobs
rq failed --url redis://localhost:6379
```

---

## 📚 References

- [RQ Documentation](https://python-rq.org/)
- [Redis Queue Best Practices](https://python-rq.org/docs/)

