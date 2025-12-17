# 🔍 Batch API Issue Analysis: ทำไมส่ง 25 tasks ได้แค่ 1 task

## 📋 ปัญหา

เมื่อส่ง 25 tasks จาก Dashboard Test Tab:
- **Expected**: 25 tasks เข้า queue
- **Actual**: ได้แค่ 1 task เข้า queue

## 🔍 สาเหตุที่เป็นไปได้

### 1. Rate Limiting Middleware

**Location**: `app/main.py`

```python
# Rate limiting: 60 requests/minute per IP
rate_limit_per_minute = int(os.getenv('API_RATE_LIMIT_PER_MINUTE', '60'))
app.add_middleware(RateLimitMiddleware, requests_per_minute=rate_limit_per_minute)
```

**Impact**:
- Dashboard ส่ง 25 requests พร้อมกัน (concurrency=25)
- Rate limit = 60 requests/minute per IP
- **ถ้าส่ง 25 requests ใน < 1 second → อาจถูก reject บางส่วน**

**Solution**:
- เพิ่ม rate limit สำหรับ batch requests
- หรือ disable rate limiting สำหรับ batch endpoint
- หรือใช้ internal API call แทน HTTP requests

### 2. Admission Control

**Location**: `app/services/transcription_service.py`

**Mode**: `ADMISSION_CONTROL_MODE=rabbitmq`

**How it works**:
- API accepts all requests
- RabbitMQ rejects when queue is full (max-length with reject-publish)
- Returns 503 when queue is full

**Impact**:
- ถ้า queue เต็ม (51 tasks) → RabbitMQ reject publish
- API returns 503 → Batch API อาจไม่ retry

### 3. Queue Limits

**Current Settings**:
```bash
MAX_QUEUE_REQUEST=51      # 50 video + 1 close caption
MAX_QUEUE_EXTRACTION=80
MAX_QUEUE_TRANSCRIBE=30
```

**Impact**:
- ถ้ามี tasks เก่าค้างอยู่ → queue เต็ม
- Requests ใหม่ถูก reject

### 4. Batch API Implementation

**Location**: `dashboard/routes/batch_routes.py`

**Current Implementation**:
```python
# Send all tasks concurrently
effective_concurrency = min(concurrency, 50)  # Cap at 50
semaphore = asyncio.Semaphore(effective_concurrency)

async def send_with_semaphore(video_file: str, index: int):
    async with semaphore:
        # Add small delay between requests
        if index > 0 and index % 10 == 0:
            await asyncio.sleep(1)  # Small delay every 10 requests
        return await send_transcription_task(...)
```

**Issues**:
- ส่ง requests ไปที่ `/transcribe/` endpoint แบบ HTTP
- ผ่าน rate limiting middleware
- ผ่าน admission control
- **ถ้า rate limit หรือ queue เต็ม → requests ถูก reject**

## ✅ Solutions

### Solution 1: เพิ่ม Rate Limit สำหรับ Batch

**Option A**: เพิ่ม rate limit
```bash
API_RATE_LIMIT_PER_MINUTE=300  # เพิ่มจาก 60 เป็น 300
```

**Option B**: Exclude batch endpoint จาก rate limiting
```python
# In app/main.py
if request.url.path.startswith("/api/batch/"):
    return await call_next(request)  # Skip rate limiting
```

### Solution 2: ใช้ Internal API Call

**Modify**: `dashboard/routes/batch_routes.py`

แทนที่จะส่ง HTTP requests ไปที่ `/transcribe/`:
```python
# Instead of HTTP request
async with session.post(f"{api_url}/transcribe/", ...)

# Use internal service call
from app.services.transcription_service import TranscriptionService
transcription_service = TranscriptionService()
task_id = await transcription_service.start_transcription(...)
```

**Benefits**:
- ไม่ผ่าน rate limiting
- ไม่ผ่าน HTTP overhead
- เร็วกว่า
- ไม่ถูก limit โดย middleware

### Solution 3: เพิ่ม Retry Logic

**Modify**: `dashboard/routes/batch_routes.py`

เพิ่ม retry logic สำหรับ 503 errors:
```python
for attempt in range(max_retries):
    try:
        result = await send_transcription_task(...)
        if result:
            return result
    except HTTPException as e:
        if e.status_code == 503:
            # Queue full - retry after delay
            retry_after = int(e.headers.get("Retry-After", "30"))
            await asyncio.sleep(retry_after)
            continue
        raise
```

### Solution 4: Check Queue Status Before Sending

**Modify**: `dashboard/routes/batch_routes.py`

ตรวจสอบ queue status ก่อนส่ง batch:
```python
# Check queue status
queue_status = await check_queue_status(api_url)
if queue_status['available_slots'] < len(video_files):
    raise HTTPException(
        status_code=503,
        detail=f"Not enough queue slots. Available: {queue_status['available_slots']}, Required: {len(video_files)}"
    )
```

## 🎯 Recommended Solution

**ใช้ Solution 2: Internal API Call**

**Reasons**:
1. ไม่ถูก rate limit
2. เร็วกว่า (no HTTP overhead)
3. ไม่ต้องแก้ rate limiting settings
4. ทำงานได้แม้ queue เต็ม (จะ reject ที่ RabbitMQ level)

**Implementation**:
1. Import `TranscriptionService` ใน batch routes
2. เรียก `start_transcription()` โดยตรง แทน HTTP request
3. Handle exceptions จาก admission control

## 📊 Testing

### Test 1: Check Rate Limiting
```bash
# Send 25 requests quickly
for i in {1..25}; do
    curl -X POST http://localhost:8010/transcribe/ ... &
done
wait

# Check how many succeeded
```

### Test 2: Check Queue Status
```bash
# Check queue before sending
curl http://localhost:8010/api/queue/status

# Send batch
# Check queue after
curl http://localhost:8010/api/queue/status
```

### Test 3: Check Logs
```bash
# Check API logs for rate limit errors
tail -f /tmp/transcription-service.log | grep -i "rate limit\|429"

# Check batch API logs
tail -f /tmp/dashboard.log | grep -i "batch\|transcription"
```

## 🔧 Quick Fix

**Temporary**: เพิ่ม rate limit
```bash
# In env.runpod
API_RATE_LIMIT_PER_MINUTE=300  # เพิ่มจาก 60
```

**Restart API**:
```bash
bash scripts/pod/restart-service-daemon.sh
```

## 📝 Next Steps

1. ✅ ตรวจสอบ rate limiting settings
2. ✅ ตรวจสอบ queue status
3. ✅ Implement internal API call (Solution 2)
4. ✅ Test with 25 concurrent tasks
5. ✅ Monitor logs for errors


