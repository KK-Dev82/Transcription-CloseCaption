# 🛠️ Phase 1: Queue Setup - Implementation Plan

## 📋 Overview

Implementation plan สำหรับ Phase 1: Queue Setup ตาม `QUEUE_ARCHITECTURE_FINAL.md`

---

## 🎯 Goals

1. ✅ สร้าง 3-Queue Architecture (request → extraction → transcription)
2. ✅ เปลี่ยนเป็น Quorum Queues
3. ✅ เพิ่ม Queue Max-Length และ Overflow (reject-publish)
4. ✅ Setup DLX (Dead Letter Exchange)

---

## 📝 Implementation Steps

### Step 1: Update RabbitMQ Service - Queue Declarations

**File**: `app/services/rabbitmq_service.py`

**Changes**:
1. เพิ่ม queue names ใหม่:
   - `transcription_request_queue`
   - `audio_extraction_queue`
   - (keep `transcription_queue`)

2. เพิ่ม helper method สำหรับสร้าง queue arguments:
   ```python
   def _get_queue_arguments(self, queue_name: str, max_length: int, enable_dlx: bool = True):
       """สร้าง queue arguments สำหรับ quorum queue"""
   ```

3. Update `_connect()` method เพื่อสร้าง queues ใหม่ด้วย quorum type

### Step 2: Update Video Worker - Queue Declarations

**File**: `app/workers/video_worker.py`

**Changes**:
1. เพิ่ม queue names ใหม่
2. Update queue declarations ใน `connect_rabbitmq()`
3. Update consumers สำหรับ queues ใหม่

### Step 3: Update Routing Logic

**File**: `app/services/transcription_service.py`

**Changes**:
1. เปลี่ยนจากส่งไป `transcription_queue` → ส่งไป `transcription_request_queue`
2. สร้าง Download & Route Worker (ใหม่)

### Step 4: Create Download & Route Worker

**File**: `app/workers/request_router_worker.py` (ใหม่)

**Changes**:
1. Consume จาก `transcription_request_queue`
2. Download file
3. Check file type
4. Route ไปยัง `audio_extraction_queue` หรือ `transcription_queue`

---

## 🔧 Implementation Details

### Queue Arguments Structure

```python
def _get_queue_arguments(
    self,
    queue_name: str,
    max_length: int,
    enable_dlx: bool = True,
    enable_quorum: bool = True
) -> Dict[str, Any]:
    """
    สร้าง queue arguments สำหรับ quorum queue
    
    Args:
        queue_name: ชื่อ queue
        max_length: จำนวน messages สูงสุด
        enable_dlx: เปิดใช้งาน DLX
        enable_quorum: ใช้ quorum queue
    
    Returns:
        Dictionary ของ queue arguments
    """
    arguments = {}
    
    if enable_quorum:
        arguments['x-queue-type'] = 'quorum'
    
    if max_length > 0:
        arguments['x-max-length'] = max_length
        arguments['x-overflow'] = 'reject-publish'
    
    if enable_dlx:
        dlx_exchange = f'{queue_name}.dlx'
        dlx_queue = f'{queue_name}.dlq'
        arguments['x-dead-letter-exchange'] = dlx_exchange
        arguments['x-dead-letter-routing-key'] = dlx_queue
    
    return arguments
```

### Queue Declarations

```python
# Transcription Request Queue (max 50)
self.channel.queue_declare(
    queue='transcription_request_queue',
    durable=True,
    arguments=self._get_queue_arguments(
        'transcription_request_queue',
        max_length=50,
        enable_dlx=True,
        enable_quorum=True
    )
)

# Audio Extraction Queue (max 80)
self.channel.queue_declare(
    queue='audio_extraction_queue',
    durable=True,
    arguments=self._get_queue_arguments(
        'audio_extraction_queue',
        max_length=80,
        enable_dlx=True,
        enable_quorum=True
    )
)

# Transcription Queue (max 20)
self.channel.queue_declare(
    queue='transcription_queue',
    durable=True,
    arguments=self._get_queue_arguments(
        'transcription_queue',
        max_length=20,
        enable_dlx=True,
        enable_quorum=True
    )
)
```

### DLX Setup

```python
# สร้าง DLX exchanges และ queues
for queue_name in ['transcription_request_queue', 'audio_extraction_queue', 'transcription_queue']:
    dlx_exchange = f'{queue_name}.dlx'
    dlx_queue = f'{queue_name}.dlq'
    
    # DLX Exchange
    self.channel.exchange_declare(
        exchange=dlx_exchange,
        exchange_type='direct',
        durable=True
    )
    
    # DLQ Queue
    self.channel.queue_declare(
        queue=dlx_queue,
        durable=True,
        arguments={'x-queue-type': 'quorum'} if enable_quorum else {}
    )
    
    # Bind DLQ to DLX
    self.channel.queue_bind(
        exchange=dlx_exchange,
        queue=dlx_queue,
        routing_key=dlx_queue
    )
```

---

## 📊 Migration Strategy

### Phase 1A: Add New Queues (Backward Compatible)

1. สร้าง queues ใหม่โดยไม่ลบ queue เก่า
2. ยังใช้ `transcription_queue` อยู่ (backward compatible)
3. Test queues ใหม่

### Phase 1B: Update Routing Logic

1. เปลี่ยน `send_transcription_task()` ให้ส่งไป `transcription_request_queue`
2. สร้าง Request Router Worker
3. Test routing

### Phase 1C: Full Migration

1. ย้าย consumers ทั้งหมดไปใช้ queues ใหม่
2. ลบ queue เก่า (ถ้าต้องการ)
3. Final testing

---

## ⚠️ Breaking Changes

**None** - Implementation จะเป็น backward compatible โดย:
1. เก็บ queue เก่าไว้ชั่วคราว
2. สร้าง queues ใหม่คู่ขนาน
3. Migrate ทีละขั้นตอน

---

## 🧪 Testing Checklist

- [ ] สร้าง queues ใหม่สำเร็จ
- [ ] Quorum queues ทำงาน
- [ ] Queue max-length ทำงาน (reject เมื่อเต็ม)
- [ ] DLX queues ทำงาน
- [ ] Routing logic ถูกต้อง
- [ ] Backward compatible (queue เก่ายังทำงาน)

---

**Last Updated**: 2024-12-04

