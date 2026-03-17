# 📡 เปรียบเทียบ WebHook vs WebSocket สำหรับ Transcription Service

## 📋 สรุป

### WebHook
- **Client ต้องส่ง URL มาให้** Server เพื่อ Push ข้อมูลกลับไป
- **URL ห้ามเปลี่ยน** (Server เก็บ URL ไว้ใน task data)
- **Latency**: ~100-500ms (HTTP request/response)
- **Retry**: มี retry mechanism (3 attempts, 5 seconds delay)

### WebSocket
- **Client ต้องเชื่อมต่อ WebSocket ก่อน**
- **Register userId และ task_id** (subscribe)
- **Server จะ Push ข้อมูลกลับมาแบบ real-time**
- **Latency**: ~10-50ms (persistent connection)
- **Real-time**: ส่ง progress updates ทุก 5% หรือเมื่อ stage เปลี่ยน

---

## 🔌 WebHook

### วิธีใช้งาน

**1. ส่ง Transcription Request พร้อม callback_url:**

```json
POST /api/transcribe/ หรือ POST /api/transcribe-enhanced/start
Content-Type: application/json

{
  "file_url": "https://example.com/video.mp4",
  "language": "th",
  "model_size": "Vinxscribe/biodatlab-whisper-th-medium-faster",
  "callback_url": "https://your-server.com/webhook/transcription",
  "source": "upload"
}
```

**source** (optional): `"upload"` | `"video_record"` | `"fe_cc"` — จะถูกส่งกลับใน callback payload ให้ผู้รับรู้ประเภทไฟล์

**2. Server จะ POST ข้อมูลกลับไปที่ callback_url เมื่อ:**

- ✅ Transcription เสร็จ (`transcription.completed`)
- ❌ Transcription ล้มเหลว (`transcription.failed`)
- 📊 Progress update (`transcription.progress`) - ถ้า subscribe

**3. Webhook Payload (เมื่อเสร็จ):**

```json
{
  "task_id": "uuid-here",
  "status": "completed",
  "progress": 100,
  "file_path": "/path/to/file.wav",
  "file_name": "video.wav",
  "language": "th",
  "model_size": "base",
  "source": "upload",
  "full_text": "...",
  "chunks_count": 10,
  "total_duration": 120.5,
  "created_at": "...",
  "updated_at": "...",
  "completed_at": "..."
}
```

**source**: `"upload"` | `"video_record"` | `"fe_cc"` — ประเภทไฟล์ที่ส่งมา (ให้ผู้รับ callback รู้ว่าเป็น Upload, Record หรือ FE CC)

**4. Webhook Payload (Progress Update):**

```json
{
  "event": "transcription.progress",
  "timestamp": "2026-01-12T20:00:00Z",
  "task_id": "uuid-here",
  "data": {
    "task_id": "uuid-here",
    "progress": 50,
    "status": "processing",
    "stage": "transcribing"
  }
}
```

### ⚠️ ข้อกำหนด

1. **URL ห้ามเปลี่ยน** - Server เก็บ `callback_url` ไว้ใน task data เมื่อส่ง request
2. **Client ต้องมี HTTP endpoint** - รับ POST request จาก Server
3. **HTTPS แนะนำ** - เพื่อความปลอดภัย
4. **Timeout**: 10 seconds (Server จะ retry 3 ครั้ง)
5. **Signature Verification** (Optional) - ใช้ `X-Webhook-Signature` header

### 📊 Latency

| Event | Latency | Notes |
|-------|---------|-------|
| HTTP Request | ~100-500ms | ขึ้นอยู่กับ network |
| Retry Delay | 5 seconds | ถ้า request ล้มเหลว |
| Total (Success) | ~100-500ms | ถ้า request สำเร็จ |
| Total (Failed + Retry) | ~15+ seconds | ถ้า retry 3 ครั้ง |

### ✅ ข้อดี

- ✅ **Stateless** - ไม่ต้อง maintain connection
- ✅ **Firewall-friendly** - ใช้ HTTP/HTTPS
- ✅ **Retry mechanism** - มี retry อัตโนมัติ
- ✅ **Signature verification** - รองรับ security

### ❌ ข้อเสีย

- ❌ **Latency สูงกว่า** - HTTP request/response overhead
- ❌ **URL ห้ามเปลี่ยน** - ต้องระบุ URL ตอนส่ง request
- ❌ **Client ต้องมี HTTP endpoint** - ต้องมี server รับ webhook
- ❌ **ไม่ real-time** - ขึ้นอยู่กับ HTTP request time

---

## 🔌 WebSocket

### วิธีใช้งาน

**1. เชื่อมต่อ WebSocket:**

```javascript
const ws = new WebSocket('ws://localhost:8010/api/ws/transcription/user123');
```

**2. Subscribe task_id:**

```javascript
// Option 1: Subscribe ตอนเชื่อมต่อ
const ws = new WebSocket('ws://localhost:8010/api/ws/transcription/user123?task_id=uuid-here');

// Option 2: Subscribe หลังเชื่อมต่อ
ws.send(JSON.stringify({
  type: 'subscribe',
  task_id: 'uuid-here'
}));
```

**3. รับข้อมูล real-time:**

```javascript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'transcription.progress':
      console.log('Progress:', data.progress, '%');
      console.log('Stage:', data.stage);
      break;
      
    case 'transcription.completed':
      console.log('Completed!', data.text);
      break;
      
    case 'transcription.failed':
      console.log('Failed:', data.error);
      break;
  }
};
```

**4. WebSocket Messages:**

**Progress Update:**
```json
{
  "type": "transcription.progress",
  "task_id": "uuid-here",
  "progress": 50,
  "status": "processing",
  "stage": "transcribing",
  "timestamp": "2026-01-12T20:00:00Z"
}
```

**Completed:**
```json
{
  "type": "transcription.completed",
  "task_id": "uuid-here",
  "text": "ข้อความที่แปลงแล้ว...",
  "chunks": [...],
  "timestamp": "2026-01-12T20:00:00Z"
}
```

### ⚠️ ข้อกำหนด

1. **Client ต้องเชื่อมต่อ WebSocket ก่อน** - ก่อนส่ง transcription request
2. **Register userId และ task_id** - ใช้ `subscribe` message
3. **Persistent Connection** - ต้อง maintain connection
4. **Heartbeat** - Server ส่ง ping ทุก 30 วินาที

### 📊 Latency

| Event | Latency | Notes |
|-------|---------|-------|
| WebSocket Message | ~10-50ms | Persistent connection |
| Progress Update | ~10-50ms | ส่งทุก 5% หรือ stage เปลี่ยน |
| Completed | ~10-50ms | ส่งทันทีเมื่อเสร็จ |

### ✅ ข้อดี

- ✅ **Latency ต่ำ** - Persistent connection, ไม่มี HTTP overhead
- ✅ **Real-time** - ส่ง progress updates ทุก 5% หรือ stage เปลี่ยน
- ✅ **ไม่ต้องมี HTTP endpoint** - Client แค่เชื่อมต่อ WebSocket
- ✅ **Bidirectional** - Client สามารถส่ง message กลับได้

### ❌ ข้อเสีย

- ❌ **ต้อง maintain connection** - ถ้า connection หลุดต้อง reconnect
- ❌ **Firewall issues** - บาง firewall อาจ block WebSocket
- ❌ **Stateful** - Server ต้องเก็บ connection state
- ❌ **ไม่รองรับ retry** - ถ้า connection หลุดต้อง reconnect เอง

---

## 📊 เปรียบเทียบ

| Feature | WebHook | WebSocket |
|---------|---------|-----------|
| **Setup** | ส่ง `callback_url` ใน request | เชื่อมต่อ WebSocket ก่อน |
| **URL** | ห้ามเปลี่ยน (เก็บใน task) | ไม่ต้องระบุ URL |
| **Connection** | Stateless (HTTP request) | Persistent connection |
| **Latency** | ~100-500ms | ~10-50ms |
| **Real-time** | ❌ (ขึ้นอยู่กับ HTTP) | ✅ (real-time updates) |
| **Progress Updates** | ⚠️ (ถ้า subscribe) | ✅ (ทุก 5% หรือ stage เปลี่ยน) |
| **Retry** | ✅ (3 attempts, 5s delay) | ❌ (ต้อง reconnect เอง) |
| **Firewall** | ✅ (HTTP/HTTPS) | ⚠️ (อาจ block) |
| **Client Requirements** | ต้องมี HTTP endpoint | แค่เชื่อมต่อ WebSocket |
| **Security** | ✅ (Signature verification) | ⚠️ (ต้องใช้ WSS) |

---

## 🎯 Use Cases

### WebHook เหมาะสำหรับ:

- ✅ **Server-to-Server** - เมื่อ client เป็น backend service
- ✅ **Firewall restrictions** - เมื่อ WebSocket ถูก block
- ✅ **Stateless architecture** - เมื่อไม่ต้องการ maintain connection
- ✅ **Batch processing** - เมื่อไม่ต้องการ real-time updates
- ✅ **Third-party integration** - เมื่อ integrate กับ external services

**Example:**
```javascript
// Backend service
const response = await fetch('http://transcription-service/api/transcribe/', {
  method: 'POST',
  body: JSON.stringify({
    file_url: 'https://example.com/video.mp4',
    callback_url: 'https://my-backend.com/webhook/transcription'
  })
});

// Webhook endpoint (my-backend.com/webhook/transcription)
app.post('/webhook/transcription', (req, res) => {
  const { event, data } = req.body;
  if (event === 'transcription.completed') {
    // Process completed transcription
    processTranscription(data);
  }
});
```

### WebSocket เหมาะสำหรับ:

- ✅ **Real-time UI** - เมื่อต้องการแสดง progress แบบ real-time
- ✅ **Low latency** - เมื่อต้องการ latency ต่ำ
- ✅ **Client-side application** - เมื่อ client เป็น web/mobile app
- ✅ **Progress tracking** - เมื่อต้องการ track progress แบบ real-time

**Example:**
```javascript
// Frontend application
const ws = new WebSocket('ws://transcription-service/api/ws/transcription/user123');

// Send transcription request
const response = await fetch('http://transcription-service/api/transcribe/', {
  method: 'POST',
  body: JSON.stringify({
    file_url: 'https://example.com/video.mp4'
  })
});

const { task_id } = await response.json();

// Subscribe to task
ws.send(JSON.stringify({
  type: 'subscribe',
  task_id: task_id
}));

// Receive real-time updates
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'transcription.progress') {
    updateProgressBar(data.progress);
  }
  if (data.type === 'transcription.completed') {
    displayTranscription(data.text);
  }
};
```

---

## 💡 คำแนะนำ

### สำหรับการใช้งานจริง (อัปโหลดแบบ URL):

**ถ้า Client เป็น Backend Service:**
- ✅ ใช้ **WebHook** - ส่ง `callback_url` ใน request
- ✅ URL ห้ามเปลี่ยน - ระบุ URL ที่ stable
- ✅ ใช้ HTTPS - เพื่อความปลอดภัย
- ✅ ใช้ Signature verification - เพื่อ verify request

**ถ้า Client เป็น Frontend Application:**
- ✅ ใช้ **WebSocket** - เชื่อมต่อ WebSocket ก่อน
- ✅ Register userId และ task_id - ใช้ `subscribe` message
- ✅ รับ real-time updates - progress updates ทุก 5%

**ถ้าต้องการทั้งสอง:**
- ✅ ใช้ **WebSocket สำหรับ real-time UI**
- ✅ ใช้ **WebHook สำหรับ backend processing**
- ✅ ส่งทั้ง `callback_url` และเชื่อมต่อ WebSocket

---

## 📚 เอกสารเพิ่มเติม

- [Transcription Endpoints Comparison](./TRANSCRIPTION_ENDPOINTS_COMPARISON.md)
- [WebSocket Usage Guide](../WEBSOCKET_USAGE.md)
- [Webhook Service](../app/services/webhook_service.py)
- [WebSocket Service](../app/services/websocket_service.py)
