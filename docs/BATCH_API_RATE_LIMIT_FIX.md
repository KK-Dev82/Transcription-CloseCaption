# Batch API Rate Limiting Fix

## ปัญหา

เมื่อส่ง tasks 5 ตัวผ่าน Batch API แต่ RabbitMQ รับได้แค่ 3 ตัว

### สาเหตุ

1. **Rate Limiting**: Batch API ส่ง requests ไปที่ `/transcribe/` endpoint ซึ่งมี rate limit 60 requests/minute per IP
2. **Worker Consumer**: Worker process หายไป (Consumers = 0) ทำให้ messages ค้างใน queue
3. **Queue Limits**: Queue อาจมี max-length ที่ต่ำกว่า expected

## การแก้ไข

### 1. Skip Rate Limiting สำหรับ Batch API

แก้ไข `app/main.py` เพื่อ skip rate limiting เมื่อเรียก `/transcribe/` จาก batch API:

```python
# Skip rate limiting for /transcribe/ endpoint when called from batch API
user_agent = request.headers.get("user-agent", "").lower()
referer = request.headers.get("referer", "").lower()
if request.url.path.startswith("/transcribe/") and ("batch" in user_agent or "batch" in referer):
    return await call_next(request)
```

### 2. Worker Restart

Worker ถูก kill ด้วย SIGTERM (signal 15) ต้อง restart:

```bash
bash scripts/pod/restart-worker-only.sh
```

### 3. Queue Limits

ตรวจสอบ queue limits ใน `env.runpod`:

```env
MAX_QUEUE_REQUEST=51
MAX_QUEUE_EXTRACTION=80
MAX_QUEUE_TRANSCRIBE=30
```

## หมายเหตุ

- Batch API ใช้ `/transcribe/` endpoint ซึ่งมี rate limiting
- วิธีที่ดีกว่าคือให้ batch API ใช้ internal endpoint ที่ไม่มี rate limiting
- Worker ต้อง register consumers หลังจาก restart

## ขั้นตอนถัดไป

1. ✅ Restart worker
2. ✅ Skip rate limiting สำหรับ batch API
3. ⏳ ตรวจสอบ consumer registration
4. ⏳ ทดสอบส่ง 5 tasks อีกครั้ง

