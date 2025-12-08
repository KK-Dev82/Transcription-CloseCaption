# 🚀 Staging Improvements Plan - Phase 1-3

**วันที่สร้าง**: 2024-12-05  
**Environment**: Staging (VPN)  
**Status**: Planning Phase

---

## 📋 สารบัญ

1. [การวิเคราะห์ Transcription Result Storage](#การวิเคราะห์-transcription-result-storage)
2. [Phase 1: RabbitMQ Connection](#phase-1-rabbitmq-connection)
3. [Phase 2: SignalR Setup](#phase-2-signalr-setup)
4. [Phase 3: PostgreSQL Integration](#phase-3-postgresql-integration)
5. [Implementation Checklist](#implementation-checklist)

---

## 📊 การวิเคราะห์ Transcription Result Storage

### ✅ สถานะปัจจุบัน

#### Transcription Service (Pod)
- **Storage**: JSONStorage (เก็บในไฟล์ JSON บน Pod)
- **Location**: `/workspace/transcription-service/storage/transcriptions/{task_id}/metadata.json`
- **Data**: task_id, full_text, chunks, status, progress, etc.

#### Backend (VPN)
- **Storage**: PostgreSQL (10.200.22.59:5432)
- **Tables**: 
  - `TranscriptionJobs` (status, metadata)
  - `TranscriptionResults` (full_text, segments_json, segments_file_id)

### 🔄 Data Flow ปัจจุบัน

```
1. Transcription Service (Pod)
   ↓ Process transcription
   ↓ Save to JSONStorage (local)
   ↓ Send Callback → Backend

2. Backend (VPN)
   ↓ Receive Callback
   ↓ Save to PostgreSQL
   ↓ Send SignalR notification
```

### ❓ ต้องปรับปรุงการบันทึกข้อมูลหรือไม่?

**คำตอบ: ไม่ต้องปรับปรุงมาก!** แต่ต้องเพิ่ม **RabbitMQ Publishing**

**เหตุผล:**
- ✅ Backend บันทึกข้อมูลลง PostgreSQL อยู่แล้ว
- ✅ Callback flow ทำงานได้ดี
- ⚠️ **ต้องเพิ่ม**: Publish ไปยัง RabbitMQ เพื่อรองรับ:
  - Real-time CloseCaption chunks
  - Alternative notification path (ถ้า callback ล้มเหลว)
  - Better reliability (RabbitMQ persistence)

---

## 🔧 Phase 1: RabbitMQ Connection

### 1.1 Backend → RabbitMQ (Public)

**สถานะ**: ✅ Backend มี RabbitMQ Consumer แล้ว

**ไฟล์**: `senate-backend/src/Shorthand.Api/Messaging/RabbitMqBackgroundConsumer.cs`

**Queues ที่ Backend consume:**
- ✅ `transcription.completed` - Full transcription results
- ✅ `transcription.chunk.completed` - Real-time chunks (CloseCaption)

**Configuration ที่ต้องตั้งค่า:**

**ไฟล์**: `senate-backend/src/Shorthand.Api/appsettings.Staging.json`

```json
{
  "RabbitMQ": {
    "HostName": "178.128.105.100",
    "Port": 5672,
    "UserName": "senate",
    "Password": "qP2VtHz6fAX4xDksEpMrLT",
    "VirtualHost": "/"
  }
}
```

**หรือผ่าน Environment Variables:**
```bash
RabbitMQ__HostName=178.128.105.100
RabbitMQ__Port=5672
RabbitMQ__UserName=senate
RabbitMQ__Password=qP2VtHz6fAX4xDksEpMrLT
RabbitMQ__VirtualHost=/
```

**✅ Action Items:**
- [ ] ตรวจสอบ RabbitMQ configuration ใน Backend
- [ ] ทดสอบ RabbitMQ connection จาก Backend
- [ ] ทดสอบ consume messages

### 1.2 Transcription Service → RabbitMQ (Public)

**สถานะ**: ⚠️ ยังไม่มีการ publish `transcription.completed` และ `transcription.chunk.completed`

**ต้องเพิ่ม:**
- Publish `transcription.completed` เมื่อ transcription เสร็จสิ้น
- Publish `transcription.chunk.completed` เมื่อ chunk แต่ละ chunk เสร็จ (สำหรับ CloseCaption)

**ไฟล์ที่ต้องแก้ไข:**

1. **`app/workers/async/utils.py`** - เพิ่ม function สำหรับ publish messages
2. **`app/workers/async/processors.py`** - เพิ่ม logic publish เมื่อ transcription เสร็จ
3. **`app/services/transcription_service.py`** - เพิ่ม logic publish เมื่อ chunk เสร็จ (CloseCaption)

**✅ Action Items:**
- [ ] เพิ่ม function `publish_transcription_completed()` ใน `utils.py`
- [ ] เพิ่ม function `publish_transcription_chunk_completed()` ใน `utils.py`
- [ ] แก้ไข `execute_transcription_task()` ใน `processors.py` เพื่อ publish เมื่อเสร็จ
- [ ] แก้ไข `execute_chunk_transcription()` ใน `processors.py` เพื่อ publish chunk

---

## 📡 Phase 2: SignalR Setup

### 2.1 Backend SignalR Hub

**สถานะ**: ✅ Backend มี SignalR Hub แล้ว

**Endpoint**: `/ws/notifications/v2`

**ไฟล์**: `senate-backend/src/Shorthand.Api/RealTime/NotificationHubV2.cs`

**✅ Action Items:**
- [ ] ตรวจสอบ SignalR Hub endpoint
- [ ] ทดสอบ SignalR connection
- [ ] ตรวจสอบ notification types:
  - `TranscriptionCompleted`
  - `TranscriptionChunk` (สำหรับ CloseCaption)

### 2.2 Frontend SignalR Client

**สถานะ**: ⚠️ ต้องตรวจสอบ

**ไฟล์**: `senate-vite/src/services/signalrClient.ts`

**✅ Action Items:**
- [ ] ตรวจสอบว่า Frontend ใช้ SignalR client หรือ WebSocket ธรรมดา
- [ ] ถ้าใช้ WebSocket ธรรมดา → ต้องเปลี่ยนเป็น SignalR client
- [ ] ทดสอบ receive notifications:
  - Transcription completed
  - Transcription chunks (CloseCaption)

### 2.3 Notification Flow

**Flow ที่ต้องทำงาน:**

```
Transcription Service → RabbitMQ → Backend Consumer → SignalR → Frontend
```

**✅ Action Items:**
- [ ] ตรวจสอบ Backend RabbitMQ Consumer ส่ง SignalR notification หรือไม่
- [ ] ทดสอบ end-to-end flow

---

## 🗄️ Phase 3: PostgreSQL Integration

### 3.1 Backend Database Connection

**สถานะ**: ✅ Backend มี PostgreSQL connection แล้ว

**Connection String**: `Host=10.200.22.59;Port=5432;Database=Senate;...`

**✅ Action Items:**
- [ ] ตรวจสอบ Connection String ใน `appsettings.Staging.json`
- [ ] ทดสอบ database connection
- [ ] ตรวจสอบ tables:
  - `TranscriptionJobs`
  - `TranscriptionResults`

### 3.2 Data Persistence Flow

**Flow ปัจจุบัน:**

```
Transcription Service → Callback → Backend → PostgreSQL
```

**Flow ใหม่ (เพิ่ม RabbitMQ):**

```
Transcription Service → RabbitMQ → Backend Consumer → PostgreSQL
                     → Callback → Backend (backup path)
```

**✅ Action Items:**
- [ ] ตรวจสอบ Backend บันทึกข้อมูลลง PostgreSQL เมื่อรับ Callback
- [ ] เพิ่ม logic บันทึกข้อมูลเมื่อรับจาก RabbitMQ
- [ ] ทดสอบ data persistence

### 3.3 Hybrid Storage (Segments)

**สถานะ**: ✅ Backend รองรับ Hybrid Storage แล้ว

**Logic:**
- Segments < 100KB → เก็บใน `SegmentsJson` (JSONB)
- Segments > 100KB → เก็บใน FileService (reference via `SegmentsFileId`)

**✅ Action Items:**
- [ ] ตรวจสอบ logic Hybrid Storage
- [ ] ทดสอบกับข้อมูลเล็ก (< 100KB)
- [ ] ทดสอบกับข้อมูลใหญ่ (> 100KB)

---

## ✅ Implementation Checklist

### Phase 1: RabbitMQ Connection

#### Backend Configuration
- [ ] ตั้งค่า RabbitMQ connection string ใน `appsettings.Staging.json`
- [ ] ทดสอบ RabbitMQ connection จาก Backend
- [ ] ตรวจสอบ RabbitMQ Consumer ทำงานหรือไม่

#### Transcription Service Publishing
- [ ] เพิ่ม function `publish_transcription_completed()` ใน `app/workers/async/utils.py`
- [ ] เพิ่ม function `publish_transcription_chunk_completed()` ใน `app/workers/async/utils.py`
- [ ] แก้ไข `execute_transcription_task()` เพื่อ publish เมื่อเสร็จ
- [ ] แก้ไข `execute_chunk_transcription()` เพื่อ publish chunk (CloseCaption)
- [ ] ทดสอบ publish messages

#### Network Connectivity
- [ ] ตรวจสอบ Backend → RabbitMQ (Public) connectivity
- [ ] ตรวจสอบ Transcription Service → RabbitMQ (Public) connectivity
- [ ] ตรวจสอบ firewall rules (ถ้ามี)

### Phase 2: SignalR Setup

#### Backend SignalR
- [ ] ตรวจสอบ SignalR Hub endpoint (`/ws/notifications/v2`)
- [ ] ทดสอบ SignalR connection
- [ ] ตรวจสอบ notification types

#### Frontend SignalR Client
- [ ] ตรวจสอบ Frontend ใช้ SignalR client หรือไม่
- [ ] ถ้ายังไม่ใช้ → เปลี่ยนเป็น SignalR client
- [ ] ทดสอบ receive notifications

#### Notification Flow
- [ ] ทดสอบ: Transcription completed → SignalR → Frontend
- [ ] ทดสอบ: Transcription chunk → SignalR → Frontend (CloseCaption)

### Phase 3: PostgreSQL Integration

#### Database Connection
- [ ] ตรวจสอบ Connection String
- [ ] ทดสอบ database connection
- [ ] ตรวจสอบ tables structure

#### Data Persistence
- [ ] ตรวจสอบ Backend บันทึกข้อมูลเมื่อรับ Callback
- [ ] เพิ่ม logic บันทึกข้อมูลเมื่อรับจาก RabbitMQ
- [ ] ทดสอบ data persistence

#### Hybrid Storage
- [ ] ตรวจสอบ logic Hybrid Storage
- [ ] ทดสอบกับข้อมูลเล็ก
- [ ] ทดสอบกับข้อมูลใหญ่

---

## 📝 Code Changes Required

### 1. เพิ่ม RabbitMQ Publishing ใน Transcription Service

**File**: `app/workers/async/utils.py`

```python
async def publish_transcription_completed(
    worker,
    task_id: str,
    job_id: Optional[int],
    user_id: Optional[str],
    full_text: str,
    chunks: List[Dict],
    status: str = "completed"
):
    """Publish transcription.completed message to RabbitMQ"""
    message = {
        "task_id": task_id,
        "job_id": job_id,
        "user_id": user_id,
        "status": status,
        "full_text": full_text,
        "chunks": chunks,
        "timestamp": datetime.now().isoformat()
    }
    
    success = await worker.connection.async_safe_publish(
        exchange_name='',
        routing_key='transcription.completed',
        body=json.dumps(message),
        properties={'delivery_mode': 2}  # Persistent
    )
    
    if success:
        logger.info(f"✅ Published transcription.completed: task_id={task_id}, job_id={job_id}")
    else:
        logger.error(f"❌ Failed to publish transcription.completed: task_id={task_id}")
    
    return success

async def publish_transcription_chunk_completed(
    worker,
    task_id: str,
    job_id: Optional[int],
    user_id: Optional[str],
    chunk_index: int,
    text: str,
    start_time: float,
    end_time: float
):
    """Publish transcription.chunk.completed message to RabbitMQ"""
    message = {
        "task_id": task_id,
        "job_id": job_id,
        "user_id": user_id,
        "chunk_index": chunk_index,
        "text": text,
        "start_time": start_time,
        "end_time": end_time,
        "timestamp": datetime.now().isoformat()
    }
    
    success = await worker.connection.async_safe_publish(
        exchange_name='',
        routing_key='transcription.chunk.completed',
        body=json.dumps(message),
        properties={'delivery_mode': 2}  # Persistent
    )
    
    if success:
        logger.info(f"✅ Published transcription.chunk.completed: task_id={task_id}, chunk_index={chunk_index}")
    else:
        logger.error(f"❌ Failed to publish transcription.chunk.completed: task_id={task_id}")
    
    return success
```

### 2. แก้ไข Processors เพื่อ Publish Messages

**File**: `app/workers/async/processors.py`

```python
# ใน execute_transcription_task()
# หลังจาก transcription เสร็จ
await publish_transcription_completed(
    worker=self.worker,
    task_id=task_id,
    job_id=job_id,
    user_id=user_id,
    full_text=full_text,
    chunks=chunks,
    status="completed"
)

# ใน execute_chunk_transcription()
# หลังจาก chunk transcription เสร็จ
await publish_transcription_chunk_completed(
    worker=self.worker,
    task_id=task_id,
    job_id=job_id,
    user_id=user_id,
    chunk_index=chunk_index,
    text=text,
    start_time=start_time,
    end_time=end_time
)
```

---

## 🔍 Testing Checklist

### Phase 1: RabbitMQ Connection
- [ ] Test Backend → RabbitMQ connection
- [ ] Test Transcription Service → RabbitMQ connection
- [ ] Test publish `transcription.completed`
- [ ] Test publish `transcription.chunk.completed`
- [ ] Test Backend consume messages

### Phase 2: SignalR Setup
- [ ] Test SignalR Hub connection
- [ ] Test Frontend SignalR client connection
- [ ] Test receive transcription completed notification
- [ ] Test receive transcription chunk notification (CloseCaption)

### Phase 3: PostgreSQL Integration
- [ ] Test database connection
- [ ] Test save TranscriptionJob
- [ ] Test save TranscriptionResult
- [ ] Test Hybrid Storage (small segments)
- [ ] Test Hybrid Storage (large segments)

### End-to-End Testing
- [ ] Test full flow: Transcription → RabbitMQ → Backend → PostgreSQL → SignalR → Frontend
- [ ] Test CloseCaption flow: Chunks → RabbitMQ → Backend → SignalR → Frontend
- [ ] Test error handling (network failure, RabbitMQ down, etc.)

---

## ✅ Summary

### Transcription Result Storage

**คำตอบ: ไม่ต้องปรับปรุงมาก!**

- ✅ Backend บันทึกข้อมูลลง PostgreSQL อยู่แล้ว
- ✅ Callback flow ทำงานได้ดี
- ⚠️ **ต้องเพิ่ม**: RabbitMQ Publishing เพื่อรองรับ:
  - Real-time CloseCaption chunks
  - Alternative notification path
  - Better reliability

### Phase 1-3 Actions

**Phase 1: RabbitMQ Connection**
- ✅ Backend configuration
- ⚠️ Transcription Service publishing (ต้องเพิ่ม)

**Phase 2: SignalR Setup**
- ✅ Backend SignalR Hub
- ⚠️ Frontend SignalR Client (ต้องตรวจสอบ)

**Phase 3: PostgreSQL Integration**
- ✅ Backend database connection
- ✅ Data persistence logic
- ✅ Hybrid Storage

---

**Last Updated**: 2024-12-05  
**Status**: Planning Complete ✅

