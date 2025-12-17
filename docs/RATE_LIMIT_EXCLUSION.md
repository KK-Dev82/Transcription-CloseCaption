# Rate Limiting Exclusion for Batch Endpoints

## 📋 Changes Made

### Modified File: `app/main.py`

**Change**: Exclude batch endpoints from rate limiting middleware

**Before**:
```python
async def dispatch(self, request: Request, call_next):
    # Skip rate limiting for health checks
    if request.url.path == "/health":
        return await call_next(request)
```

**After**:
```python
async def dispatch(self, request: Request, call_next):
    # Skip rate limiting for health checks
    if request.url.path == "/health":
        return await call_next(request)
    
    # Skip rate limiting for batch endpoints (internal API calls)
    if request.url.path.startswith("/api/batch/"):
        return await call_next(request)
```

## ✅ Benefits

1. **Batch API ไม่ถูก Rate Limit**
   - Dashboard Test Tab สามารถส่ง 25+ requests พร้อมกันได้
   - ไม่ถูก reject โดย rate limiting middleware

2. **Rate Limiting ยังทำงานสำหรับ Endpoints อื่น**
   - `/transcribe/` endpoint ยังถูก rate limit
   - `/api/queue/status` ยังถูก rate limit
   - ป้องกัน abuse จาก external clients

3. **Future-Proof**
   - สามารถเพิ่ม rate limiting rules อื่นๆ ได้ในอนาคต
   - Batch endpoint ไม่กระทบ

## 🔍 Excluded Endpoints

- `/api/batch/transcription` - Start batch transcription
- `/api/batch/{batch_id}` - Get batch status
- `/api/batch/*` - All batch-related endpoints

## 📊 Rate Limiting Still Active For

- `/transcribe/` - Single transcription requests
- `/api/queue/status` - Queue status checks
- `/api/server/*/tasks` - Task listings
- All other endpoints

## 🧪 Testing

### Test 1: Batch Endpoint (Should NOT be rate limited)
```bash
# Send 25 requests quickly
for i in {1..25}; do
    curl -X POST http://localhost:8010/api/batch/transcription \
        -H "Content-Type: application/json" \
        -d '{"server_name":"4000-ada-sc","video_files":["test.mp4"],"concurrency":1}' &
done
wait

# All should succeed (no 429 errors)
```

### Test 2: Regular Endpoint (Should be rate limited)
```bash
# Send 70 requests quickly (exceeds 60/minute limit)
for i in {1..70}; do
    curl -X POST http://localhost:8010/transcribe/ \
        -H "Content-Type: application/json" \
        -d '{"file_path":"test.mp4"}' &
done
wait

# Some should return 429 (Rate limit exceeded)
```

## 📝 Notes

- Rate limiting ยังทำงานสำหรับ endpoints อื่นๆ
- Batch endpoints ไม่ถูก limit เพื่อรองรับ concurrent batch processing
- Health check endpoint ยังไม่ถูก limit (as before)

