# Admission Control Architecture

## 📋 Architecture Overview

### Current Flow
```
Client Request → Transcription Service API → RabbitMQ → Video Worker
```

### New Architecture (RabbitMQ-based Admission Control)

```
Client Request → Transcription Service API (accepts all)
                ↓
            RabbitMQ Queue (max 51: 50 transcription + 1 close caption)
                ↓ (reject-publish when full)
            Video Worker (prefetch=1, processes when available)
```

## 🔧 Configuration

### Admission Control Mode

**Environment Variable:** `ADMISSION_CONTROL_MODE`

**Options:**
1. **`rabbitmq`** (Recommended)
   - API accepts all requests
   - RabbitMQ queue handles queue limits (max-length with reject-publish)
   - When queue is full, RabbitMQ rejects publish → API returns 503
   - Benefits:
     - Simpler API logic
     - RabbitMQ handles queue management
     - Better for high concurrency

2. **`api`** (Original)
   - API checks queue size before accepting
   - Returns 503 if queue is full
   - Benefits:
     - Early rejection (before processing)
     - More predictable behavior

3. **`disabled`** (Not Recommended)
   - No admission control
   - May cause queue overflow

### Queue Configuration

```bash
# Queue Limits
MAX_QUEUE_REQUEST=51      # 50 video + 1 close caption
MAX_QUEUE_EXTRACTION=80
MAX_QUEUE_TRANSCRIBE=20

# Admission Control Mode
ADMISSION_CONTROL_MODE=rabbitmq
```

## 🔄 How It Works

### RabbitMQ-based Mode (Recommended)

1. **API Layer:**
   - Accepts all requests immediately
   - No queue size checking
   - Returns task_id immediately

2. **RabbitMQ Queue:**
   - Has `max-length=51` with `x-overflow=reject-publish`
   - When queue is full → RabbitMQ rejects publish
   - Returns error to API

3. **API Error Handling:**
   - Catches RabbitMQ publish errors
   - Returns 503 with `Retry-After` header
   - Client can retry later

4. **Video Worker:**
   - `prefetch=1` → receives 1 message at a time
   - Processes when available
   - No message accumulation

## ✅ Benefits

### RabbitMQ-based Mode

1. **Simpler API Logic:**
   - No queue size checking needed
   - Less database/queue queries
   - Faster request handling

2. **Better Concurrency:**
   - API can handle more requests
   - Queue management handled by RabbitMQ
   - Natural back-pressure

3. **Queue Management:**
   - RabbitMQ handles queue limits
   - Automatic rejection when full
   - Priority queue support (close caption = priority 10)

4. **Worker Efficiency:**
   - `prefetch=1` ensures worker only gets work when ready
   - No message accumulation in worker
   - Better resource utilization

## 📊 Queue Flow

### Request Flow

```
1. Client sends request
   ↓
2. API accepts (no checking)
   ↓
3. API tries to publish to RabbitMQ
   ↓
4a. Queue has space → Success → Return task_id
4b. Queue is full → RabbitMQ rejects → API returns 503
   ↓
5. Worker receives message (prefetch=1)
   ↓
6. Worker processes when available
```

### Queue Limits

- **transcription_request_queue**: max 51 (50 video + 1 close caption)
- **audio_extraction_queue**: max 80
- **transcription_queue**: max 20

### Priority Queue

- **Close Caption** (realtime_chunks): priority 10 (highest)
- **Normal Transcription**: priority 5 (normal)

## 🚨 Error Handling

### When Queue is Full

1. **RabbitMQ rejects publish:**
   - `ChannelClosedByBroker` exception
   - `UnroutableError` exception

2. **API catches error:**
   - Returns 503 Service Unavailable
   - Includes `Retry-After` header
   - Provides queue status information

3. **Client retry:**
   - Wait for `Retry-After` seconds
   - Check queue status at `/api/queue/status`
   - Retry request

## 📝 Implementation Details

### API Changes

- **Admission Control:** Optional (controlled by `ADMISSION_CONTROL_MODE`)
- **Error Handling:** Catches RabbitMQ publish errors
- **Response:** Returns 503 with queue status when queue is full

### RabbitMQ Changes

- **Queue Configuration:** `max-length` with `x-overflow=reject-publish`
- **Priority Support:** `x-max-priority=10` for close caption priority
- **Error Handling:** Returns exceptions when queue is full

### Worker Changes

- **Prefetch:** `prefetch=1` (already configured)
- **Processing:** Worker processes messages when available
- **No Changes Needed:** Worker already handles messages correctly

## 🔍 Monitoring

### Queue Status Endpoint

```bash
GET /api/queue/status
```

Returns:
- Queue sizes
- Available slots
- Estimated wait time
- Recommendations

### Logs

- API logs: Request acceptance/rejection
- RabbitMQ logs: Queue full events
- Worker logs: Message processing

## 📚 Related Documentation

- `docs/QUEUE_ARCHITECTURE_FINAL.md` - Queue architecture details
- `docs/PRODUCTION_CAPACITY_ANALYSIS.md` - Capacity analysis
- `docs/PRIORITY_QUEUE_IMPLEMENTATION.md` - Priority queue details

