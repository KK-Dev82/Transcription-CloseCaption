# 🚀 Redis Queue Setup Guide

## ✅ Completed Steps

1. ✅ ติดตั้ง RQ library (`rq==1.15.1`)
2. ✅ สร้าง `RedisQueueService` สำหรับจัดการ queues
3. ✅ อัพเดต API endpoint ให้ใช้ Redis Queue
4. ✅ สร้าง worker function สำหรับ RQ

---

## 📋 สรุปการเปลี่ยนแปลง

### 1. API Endpoint (`/api/transcribe/`)
- เปลี่ยนจาก `asyncio.create_task()` → `RedisQueueService.enqueue_transcription()`
- API ตอบกลับทันที (<1s) แทนรอผล
- มี fallback ไป async mode ถ้า Redis Queue ไม่พร้อม

### 2. Redis Queue Service
- Queues: `transcription_gpu0`, `transcription_gpu1`, `transcription_default`, `transcription_priority`
- รองรับ round-robin และ specific GPU
- รองรับ priority queue สำหรับ live streaming

### 3. Worker Function
- `process_transcription_job()` - sync wrapper สำหรับ async `_process_transcription()`
- ใช้ `asyncio.run()` เพื่อรัน async function ใน sync context

---

## 🚀 การใช้งาน

### 1. เริ่ม RQ Workers

```bash
# Start workers สำหรับ 2 GPUs
bash scripts/pod/start-rq-workers.sh
```

Workers จะ:
- GPU 0: consume `transcription_gpu0` และ `transcription_default`
- GPU 1: consume `transcription_gpu1` และ `transcription_default`

### 2. ใช้ API ตามปกติ

```bash
# ส่ง transcription request
curl -X POST http://localhost:8010/api/transcribe/ \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "uploads/v30-1.mp4",
    "language": "th",
    "model_size": "base",
    "chunk_duration": 90
  }'

# Response (ทันที):
{
  "task_id": "uuid",
  "status": "queued",
  "message": "Transcription job queued successfully",
  "file_path": "uploads/v30-1.mp4",
  "queue": "redis"
}

# ตรวจสอบสถานะ
curl http://localhost:8010/api/tasks/{task_id}
```

### 3. Monitor Queues

```bash
# ดู queue stats
rq info --url redis://localhost:6379

# ดู worker logs
tail -f /tmp/rq-worker-gpu0.log
tail -f /tmp/rq-worker-gpu1.log
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Redis URL (required)
REDIS_URL=redis://localhost:6379

# หรือใช้ Redis Cloud
REDIS_URL=redis://default:password@redis-host:port
```

---

## ✅ Benefits

1. **No Timeout Issues**
   - API return `task_id` ทันที (<1s)
   - ไม่มี HTTP timeout 10s

2. **Better Concurrency**
   - Queue จัดการ jobs อัตโนมัติ
   - Workers consume ตาม capacity

3. **Multi-GPU Support**
   - แต่ละ worker fix GPU ของตัวเอง
   - Round-robin หรือ specific GPU

4. **Production Ready**
   - มี retry, monitoring, job status
   - ใช้ Redis ที่มีอยู่แล้ว

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

### API fallback to async mode
- ตรวจสอบว่า Redis connection ทำงานได้
- ตรวจสอบว่า RQ workers เริ่มแล้ว
- ดู logs: `tail -f /tmp/api.log`

---

## 📝 Next Steps

1. ✅ ติดตั้ง RQ - **Done**
2. ✅ สร้าง RedisQueueService - **Done**
3. ✅ อัพเดต API endpoint - **Done**
4. ⏳ ทดสอบระบบ Redis Queue
5. ⏳ Monitor performance
6. ⏳ เพิ่ม priority queue สำหรับ live streaming

---

## 🔗 References

- [RQ Documentation](https://python-rq.org/)
- [Redis Queue Best Practices](https://python-rq.org/docs/)

