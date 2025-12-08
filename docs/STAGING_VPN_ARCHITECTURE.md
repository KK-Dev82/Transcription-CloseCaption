# 🌐 Staging VPN Architecture Analysis & Setup Guide

**วันที่สร้าง**: 2024-12-05  
**Environment**: Staging (VPN)  
**Status**: Architecture Analysis Complete

---

## 📋 สารบัญ

1. [Network Topology](#network-topology)
2. [RabbitMQ Connection](#rabbitmq-connection)
3. [SignalR Architecture](#signalr-architecture)
4. [PostgreSQL Database](#postgresql-database)
5. [Configuration Changes](#configuration-changes)
6. [Implementation Checklist](#implementation-checklist)

---

## 🌐 Network Topology

### Current Setup

```
┌─────────────────────────────────────────────────────────────┐
│  VPN Network (10.200.22.xx)                                 │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │  Backend         │  │  FileService     │               │
│  │  10.200.22.61    │  │  10.200.22.60    │               │
│  │  Port: 5173      │  │  Port: 5182      │               │
│  └──────────────────┘  └──────────────────┘               │
│         │                        │                         │
│         └────────┬───────────────┘                         │
│                  │                                         │
│         ┌────────▼─────────┐                              │
│         │  PostgreSQL      │                              │
│         │  10.200.22.59    │                              │
│         │  Port: 5432      │                              │
│         └──────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Internet
                          │
┌─────────────────────────────────────────────────────────────┐
│  Public Network                                             │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │  Transcription   │  │  RabbitMQ        │               │
│  │  Service (Pod)   │  │  (Public)        │               │
│  │  80.15.7.37      │  │  178.128.105.100 │               │
│  │  Port: 8010      │  │  Port: 5672      │               │
│  └──────────────────┘  └──────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 RabbitMQ Connection

### ✅ คำตอบ: ใช่! ต้องให้ Backend และ FileService มาติดต่อกับ RabbitMQ Public

**RabbitMQ อยู่ที่ Public IP**: `178.128.105.100:5672`

### Connection Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. Backend (VPN) → RabbitMQ (Public)                       │
│                                                              │
│     ✅ Backend ต้องเชื่อมต่อ RabbitMQ Public                │
│     ✅ สำหรับ consume messages (transcription.completed)    │
│     ✅ สำหรับ consume chunks (transcription.chunk.completed)│
│                                                              │
│  2. Transcription Service (Pod) → RabbitMQ (Public)         │
│                                                              │
│     ✅ Transcription Service ต้องเชื่อมต่อ RabbitMQ Public  │
│     ✅ สำหรับ publish messages (transcription.completed)    │
│     ✅ สำหรับ publish chunks (transcription.chunk.completed)│
│                                                              │
│  3. FileService (VPN) → RabbitMQ (Public)?                  │
│                                                              │
│     ❓ FileService ต้องเชื่อมต่อ RabbitMQ หรือไม่?          │
│     ✅ ขึ้นอยู่กับว่า FileService ต้อง consume/publish หรือไม่│
└─────────────────────────────────────────────────────────────┘
```

### Backend RabbitMQ Connection

**ปัจจุบัน Backend มี RabbitMQ Consumer แล้ว:**

```csharp
// senate-backend/src/Shorthand.Api/Messaging/RabbitMqBackgroundConsumer.cs
public sealed class RabbitMqBackgroundConsumer : BackgroundService
{
    // Consume queues:
    // - transcription.completed
    // - transcription.chunk.completed (สำหรับ CloseCaption)
    // - media.audio.extract.done
    // - media.video.trim.done
}
```

**Configuration ที่ต้องตั้งค่า:**

```json
// senate-backend/appsettings.Staging.json
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

### FileService RabbitMQ Connection

**❓ คำถาม: FileService ต้องเชื่อมต่อ RabbitMQ หรือไม่?**

**คำตอบ: ขึ้นอยู่กับ Use Case**

**ถ้า FileService ต้อง:**
- ❌ Consume transcription results → **ไม่จำเป็น** (Backend จัดการแล้ว)
- ❌ Publish messages → **ไม่จำเป็น** (Backend จัดการแล้ว)
- ✅ **FileService ไม่ต้องเชื่อมต่อ RabbitMQ** (Backend จัดการทั้งหมด)

---

## 📡 SignalR Architecture

### ✅ SignalR ไม่ต้องติดต่อกับ Transcription Service โดยตรง!

**SignalR Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│  Flow: Transcription → Backend → SignalR → Frontend         │
└─────────────────────────────────────────────────────────────┘

1. Transcription Service (Pod)
   ↓ (Callback หรือ RabbitMQ)
   
2. Backend (VPN)
   ↓ (SignalR Hub)
   
3. Frontend
```

### Two Notification Paths

#### Path 1: Webhook Callback (สำหรับ Full Transcription)

```
Transcription Service (Pod)
  ↓ POST /api/transcription/webhook/completed
Backend (VPN)
  ↓ Update PostgreSQL
  ↓ SignalR.SendAsync()
Frontend (SignalR Client)
```

#### Path 2: RabbitMQ → SignalR (สำหรับ CloseCaption Chunks)

```
Transcription Worker (Pod)
  ↓ Publish to RabbitMQ (transcription.chunk.completed)
RabbitMQ (Public)
  ↓ Consume
Backend RabbitMQ Consumer (VPN)
  ↓ SignalR.SendAsync()
Frontend (SignalR Client)
```

### SignalR Configuration

**Backend SignalR Hub:**

```csharp
// senate-backend/src/Shorthand.Api/RealTime/NotificationHubV2.cs
public class NotificationHubV2 : Hub
{
    // SignalR Hub endpoint: /ws/notifications/v2
    // Clients connect via SignalR client library
}
```

**Frontend SignalR Client:**

```typescript
// senate-vite/src/services/signalrClient.ts
const connection = new HubConnectionBuilder()
  .withUrl(`${baseUrl}/ws/notifications/v2`, {
    accessTokenFactory: () => getAccessToken()
  })
  .withAutomaticReconnect()
  .build();

// Listen for transcription updates
connection.on("Notification", (message) => {
  if (message.type === "TranscriptionCompleted") {
    // Handle transcription completed
  }
  if (message.type === "TranscriptionChunk") {
    // Handle CloseCaption chunk
  }
});
```

### Summary: SignalR ไม่ต้องติดต่อ Transcription Service

- ✅ **SignalR ทำงานใน Backend** (VPN)
- ✅ **Transcription Service ส่งผลลัพธ์ไป Backend** (via Callback หรือ RabbitMQ)
- ✅ **Backend broadcast ผ่าน SignalR** → Frontend
- ❌ **SignalR ไม่ต้องติดต่อ Transcription Service โดยตรง**

---

## 🗄️ PostgreSQL Database

### ✅ Backend บันทึกข้อมูลลง PostgreSQL

**Database Location:** `10.200.22.59:5432` (VPN)

**Tables:**

#### 1. TranscriptionJobs

```sql
CREATE TABLE "TranscriptionJobs" (
    "Id" SERIAL PRIMARY KEY,
    "FileId" UUID NOT NULL,
    "FileName" VARCHAR(255) NOT NULL,
    "Language" VARCHAR(10) NOT NULL,
    "ModelSize" VARCHAR(20) NOT NULL,
    "Status" VARCHAR(20) NOT NULL,  -- pending, processing, completed, failed
    "UserId" INTEGER NOT NULL,
    "CreatedAt" TIMESTAMP NOT NULL,
    "UpdatedAt" TIMESTAMP NOT NULL
);
```

#### 2. TranscriptionResults

```sql
CREATE TABLE "TranscriptionResults" (
    "Id" SERIAL PRIMARY KEY,
    "TranscriptionJobId" INTEGER NOT NULL,
    "FullText" TEXT NOT NULL,
    "SegmentsJson" JSONB NOT NULL DEFAULT '[]',  -- สำหรับข้อมูลเล็ก (< 100KB)
    "SegmentsFileId" UUID NULL,                  -- สำหรับข้อมูลใหญ่ (> 100KB)
    "SegmentsFileName" VARCHAR(255) NULL,
    "AudioDurationSeconds" DECIMAL NULL,
    "WordCount" INTEGER NULL,
    "AverageConfidence" DECIMAL NULL,
    "CreatedBy" INTEGER NULL,
    "CreatedAt" TIMESTAMP NOT NULL
);
```

### Data Flow

```
1. Transcription Service (Pod)
   ↓ Callback: POST /api/transcription/webhook/completed
   
2. Backend (VPN)
   ↓ Receive webhook
   ↓ Update TranscriptionJob.Status = "completed"
   ↓ Insert TranscriptionResult
   ↓ Save to PostgreSQL (10.200.22.59)
   
3. PostgreSQL (VPN)
   ✅ Data persisted
```

### Connection String

```json
// senate-backend/appsettings.Staging.json
{
  "ConnectionStrings": {
    "SenateDb": "Host=10.200.22.59;Port=5432;Database=Senate;Username=postgres;Password=..."
  }
}
```

---

## ⚙️ Configuration Changes

### 1. Backend Configuration

**ไฟล์**: `senate-backend/src/Shorthand.Api/appsettings.Staging.json`

```json
{
  "ExternalServices": {
    "TranscriptionUrl": "http://80.15.7.37:41314",
    "TranscriptionCallbackBaseUrl": "http://10.200.22.61:5173"
  },
  "RabbitMQ": {
    "HostName": "178.128.105.100",
    "Port": 5672,
    "UserName": "senate",
    "Password": "qP2VtHz6fAX4xDksEpMrLT",
    "VirtualHost": "/"
  },
  "ConnectionStrings": {
    "SenateDb": "Host=10.200.22.59;Port=5432;Database=Senate;Username=postgres;Password=..."
  }
}
```

### 2. Transcription Service Configuration

**ไฟล์**: `transcription-close-caption-service/env.runpod`

```bash
# RabbitMQ (Public)
RABBITMQ_HOST=178.128.105.100
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT

# Backend API (VPN - ผ่าน Public IP หรือ VPN Tunnel)
BACKEND_API_BASE_URL=http://10.200.22.61:5173  # หรือ Public IP ถ้ามี

# FileService (VPN - ผ่าน Public IP หรือ VPN Tunnel)
FILE_SERVICE_URL=http://10.200.22.60:5182  # หรือ Public IP ถ้ามี
```

### 3. Network Connectivity

#### Backend → RabbitMQ (Public)

```
Backend (10.200.22.61) → RabbitMQ (178.128.105.100:5672)
```

**Requirements:**
- ✅ Backend ต้องสามารถเชื่อมต่อ Internet ได้
- ✅ RabbitMQ ต้อง allow connection จาก Backend IP (ถ้ามี firewall)
- ✅ Port 5672 ต้องเปิด

#### Transcription Service → RabbitMQ (Public)

```
Transcription Service (80.15.7.37) → RabbitMQ (178.128.105.100:5672)
```

**Requirements:**
- ✅ Transcription Service ต้องสามารถเชื่อมต่อ Internet ได้
- ✅ RabbitMQ ต้อง allow connection จาก Pod IP (ถ้ามี firewall)
- ✅ Port 5672 ต้องเปิด

#### Transcription Service → Backend (VPN)

**ปัญหา: Transcription Service อยู่นอก VPN → ไม่สามารถเข้าถึง Backend โดยตรง**

**Solutions:**

**Option 1: ใช้ Public IP (ถ้ามี)**

```
Transcription Service (80.15.7.37)
  → Backend Public IP (ถ้ามี)
  → Backend (10.200.22.61:5173)
```

**Option 2: ใช้ VPN Tunnel (ถ้ามี)**

```
Transcription Service (80.15.7.37)
  → VPN Tunnel
  → Backend (10.200.22.61:5173)
```

**Option 3: ใช้ Callback URL ที่เข้าถึงได้จาก Public**

```
Transcription Service (80.15.7.37)
  → Backend Public Endpoint (ถ้ามี)
  → /api/transcription/webhook/completed
```

**Option 4: ไม่ใช้ Callback → ใช้ RabbitMQ แทน**

```
Transcription Service (80.15.7.37)
  → Publish to RabbitMQ (transcription.completed)
  → Backend consume from RabbitMQ
  → Update PostgreSQL
```

**แนะนำ: Option 4 (ใช้ RabbitMQ แทน Callback)**

- ✅ ไม่ต้องเปิด Public IP สำหรับ Backend
- ✅ ใช้ RabbitMQ ที่มีอยู่แล้ว
- ✅ More reliable (RabbitMQ persistence)

---

## 📋 Implementation Checklist

### Phase 1: RabbitMQ Connection

- [ ] **Backend → RabbitMQ**
  - [ ] ตั้งค่า RabbitMQ connection ใน Backend
  - [ ] ทดสอบ connection
  - [ ] ทดสอบ consume messages

- [ ] **Transcription Service → RabbitMQ**
  - [ ] ตั้งค่า RabbitMQ connection ใน Transcription Service
  - [ ] ทดสอบ connection
  - [ ] ทดสอบ publish messages

- [ ] **Firewall Rules**
  - [ ] เปิด port 5672 สำหรับ Backend IP (ถ้ามี firewall)
  - [ ] เปิด port 5672 สำหรับ Pod IP (ถ้ามี firewall)

### Phase 2: SignalR Setup

- [ ] **Backend SignalR Hub**
  - [ ] ตรวจสอบ SignalR Hub endpoint (`/ws/notifications/v2`)
  - [ ] ทดสอบ SignalR connection

- [ ] **Frontend SignalR Client**
  - [ ] ใช้ `@microsoft/signalr` client
  - [ ] ทดสอบ connection
  - [ ] ทดสอบ receive notifications

- [ ] **Notification Flow**
  - [ ] Transcription completed → SignalR
  - [ ] Transcription chunk → SignalR

### Phase 3: PostgreSQL Integration

- [ ] **Backend Database Connection**
  - [ ] ตั้งค่า Connection String
  - [ ] ทดสอบ connection

- [ ] **Data Persistence**
  - [ ] TranscriptionJob table
  - [ ] TranscriptionResult table
  - [ ] ทดสอบบันทึกข้อมูล

- [ ] **Hybrid Storage (Segments)**
  - [ ] ข้อมูลเล็ก (< 100KB) → เก็บใน DB
  - [ ] ข้อมูลใหญ่ (> 100KB) → เก็บใน FileService

### Phase 4: Network Connectivity

- [ ] **Backend → RabbitMQ (Public)**
  - [ ] ทดสอบ connection
  - [ ] ทดสอบ publish/consume

- [ ] **Transcription Service → RabbitMQ (Public)**
  - [ ] ทดสอบ connection
  - [ ] ทดสอบ publish/consume

- [ ] **Transcription Service → Backend**
  - [ ] เลือก solution (Public IP / VPN Tunnel / RabbitMQ)
  - [ ] ทดสอบ connection

- [ ] **FileService Access**
  - [ ] Transcription Service → FileService (ผ่าน Proxy หรือ Public IP)
  - [ ] ทดสอบ file download

### Phase 5: Testing

- [ ] **Full Flow Test**
  - [ ] Frontend → Backend → Transcription Service
  - [ ] Transcription Service → RabbitMQ → Backend
  - [ ] Backend → PostgreSQL
  - [ ] Backend → SignalR → Frontend

- [ ] **CloseCaption Test**
  - [ ] Transcription chunks → RabbitMQ
  - [ ] Backend consume → SignalR
  - [ ] Frontend receive → Display

- [ ] **Error Handling**
  - [ ] Network failure
  - [ ] RabbitMQ connection loss
  - [ ] Database connection loss

---

## 🔧 Detailed Configuration

### Backend: RabbitMQ Consumer

**File**: `senate-backend/src/Shorthand.Api/Messaging/RabbitMqBackgroundConsumer.cs`

**Queues to Consume:**

1. **transcription.completed**
   - Full transcription results
   - Update TranscriptionJob status
   - Save TranscriptionResult to PostgreSQL
   - Send SignalR notification

2. **transcription.chunk.completed**
   - Real-time transcription chunks (CloseCaption)
   - Send SignalR notification immediately
   - No database update (chunks stored in final result)

### Transcription Service: RabbitMQ Publisher

**File**: `transcription-close-caption-service/app/workers/async/handlers.py`

**Queues to Publish:**

1. **transcription.completed**
   - After full transcription completed
   - Contains: task_id, job_id, full_text, chunks, status

2. **transcription.chunk.completed**
   - After each chunk transcribed (for CloseCaption)
   - Contains: task_id, chunk_index, text, start_time, end_time, user_id

### Message Format

**transcription.completed:**
```json
{
  "task_id": "abc-123-def",
  "job_id": 123,
  "status": "completed",
  "full_text": "...",
  "chunks": [
    {
      "start_time": 0.0,
      "end_time": 3.5,
      "text": "..."
    }
  ],
  "user_id": "123"
}
```

**transcription.chunk.completed:**
```json
{
  "task_id": "abc-123-def",
  "job_id": 123,
  "chunk_index": 0,
  "text": "...",
  "start_time": 0.0,
  "end_time": 3.5,
  "user_id": "123",
  "timestamp": "2024-12-05T10:00:00Z"
}
```

---

## ✅ Summary

### RabbitMQ Connection

- ✅ **Backend ต้องเชื่อมต่อ RabbitMQ Public** (178.128.105.100:5672)
- ✅ **Transcription Service ต้องเชื่อมต่อ RabbitMQ Public** (178.128.105.100:5672)
- ❌ **FileService ไม่ต้องเชื่อมต่อ RabbitMQ** (Backend จัดการแล้ว)

### SignalR Architecture

- ✅ **SignalR ทำงานใน Backend** (ไม่ต้องติดต่อ Transcription Service)
- ✅ **Transcription Service → RabbitMQ → Backend → SignalR → Frontend**
- ✅ **2 Paths:**
  - Full transcription: Callback หรือ RabbitMQ → PostgreSQL → SignalR
  - CloseCaption chunks: RabbitMQ → SignalR (real-time)

### PostgreSQL Database

- ✅ **Backend บันทึกข้อมูลลง PostgreSQL** (10.200.22.59:5432)
- ✅ **Tables:**
  - TranscriptionJobs (status, metadata)
  - TranscriptionResults (full_text, segments)
- ✅ **Hybrid Storage:**
  - Segments < 100KB → เก็บใน DB
  - Segments > 100KB → เก็บใน FileService

### Network Connectivity

- ✅ **Backend → RabbitMQ (Public)**: ผ่าน Internet
- ✅ **Transcription Service → RabbitMQ (Public)**: ผ่าน Internet
- ⚠️ **Transcription Service → Backend**: ต้องหา solution (Public IP / VPN Tunnel / RabbitMQ only)

---

**Last Updated**: 2024-12-05  
**Status**: Analysis Complete ✅

