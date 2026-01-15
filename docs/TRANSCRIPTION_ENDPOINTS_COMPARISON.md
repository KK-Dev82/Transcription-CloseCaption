# 📋 เปรียบเทียบ Transcription Endpoints

## 🔌 Endpoints Overview

### 1️⃣ File Transcription (สำหรับไฟล์ 10-30 นาที)

**Endpoint:** `POST /api/transcribe/`

สำหรับ transcription ไฟล์ audio/video แบบเต็มไฟล์ (10-30 นาที หรือมากกว่า)

---

### 2️⃣ Live-Chunk Transcription (สำหรับ Real-time Streaming)

**Endpoint:** `POST /api/transcription/realtime/live-chunk`

สำหรับ transcription audio chunks แบบ real-time (streaming)

---

## 📊 เปรียบเทียบรายละเอียด

| Feature | File Transcription | Live-Chunk |
|---------|-------------------|------------|
| **Endpoint** | `POST /api/transcribe/` | `POST /api/transcription/realtime/live-chunk` |
| **Content-Type** | `application/json` | `application/octet-stream` |
| **Input Format** | JSON (file_path หรือ file_url) | Raw PCM16 binary data |
| **Use Case** | ไฟล์ 10-30 นาที หรือมากกว่า | Real-time streaming chunks |
| **Response** | `task_id` (async job) | `session_id` (immediate) |
| **Result Location** | GET `/api/v2/tasks/{task_id}` | WebSocket events |
| **Queue Type** | Redis (preprocess → GPU → CPU) | Priority Queue |
| **Processing** | Background job (อาจใช้เวลานาน) | Near real-time (~1-2 seconds) |
| **Chunking** | Optional (use_chunking parameter) | Always chunked (3-5 seconds) |
| **WebSocket** | ✅ Supported (via `/api/ws/transcription/{user_id}` or `/api/history/ws/realtime`) | Required (real-time events via `/api/ws/captions`) |

---

## 📥 Request Format

### File Transcription

#### Required Parameters

**ต้องระบุอย่างใดอย่างหนึ่ง:**
- `file_path`: ไฟล์ที่อัปโหลดแล้วในระบบ (เช่น `"uploads/video.mp4"`)
- `file_url`: URL ของไฟล์ที่ต้องการดาวน์โหลดและ transcribe (เช่น `"https://example.com/video.mp4"`)

**⚠️ ระวัง:** ห้ามระบุทั้ง `file_path` และ `file_url` พร้อมกัน

#### Optional Parameters (มี Default Values)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `language` | string | `"th"` | ภาษา (th, en, auto) |
| `model_size` | string | `"Vinxscribe/biodatlab-whisper-th-medium-faster"` | ขนาด model (ดูรายละเอียดด้านล่าง) |
| `chunk_duration` | integer | `150` | ความยาว chunk (วินาที) - ใช้เมื่อ `use_chunking=true` |
| `use_chunking` | boolean | `false` | ใช้ chunking หรือไม่ |
| `callback_url` | string | `null` | Webhook URL สำหรับรับผลลัพธ์ |

#### Model Size Values

**1. Standard Models:**
- `tiny` - เร็วที่สุด แต่ความแม่นยำต่ำ
- `base` - สมดุลระหว่างความเร็วและความแม่นยำ
- `small` - แม่นยำกว่า base แต่ช้ากว่า
- `medium` - แม่นยำสูง แต่ช้ากว่า small
- `large` - แม่นยำสูงสุด แต่ช้ามาก
- `large-v3-turbo` - Optimized version ของ large

**2. HuggingFace Models:**
- `Vinxscribe/biodatlab-whisper-th-medium-faster` - **Default** - Thai-optimized model
- `Systran/faster-whisper-small` - Faster Whisper small
- หรือ model อื่นๆ จาก HuggingFace Hub

**Note:** สำหรับ HuggingFace models ระบบจะดาวน์โหลด model อัตโนมัติเมื่อใช้ครั้งแรก

#### Example 1: ใช้ file_url (Minimal - ใช้ Default Values)

```json
POST /api/transcribe/
Content-Type: application/json

{
  "file_url": "https://example.com/video.mp4"
}
```

**ผลลัพธ์:**
- `language`: "th" (default)
- `model_size`: "base" (default)
- `chunk_duration`: 150 (default)
- `use_chunking`: false (default)

#### Example 2: ใช้ file_url พร้อม Custom Model

```json
POST /api/transcribe/
Content-Type: application/json

{
  "file_url": "https://example.com/video.mp4",
  "model_size": "Vinxscribe/biodatlab-whisper-th-medium-faster",
  "language": "th"
}
```

#### Example 3: ใช้ file_url พร้อม Webhook

```json
POST /api/transcribe/
Content-Type: application/json

{
  "file_url": "https://example.com/video.mp4",
  "model_size": "base",
  "language": "th",
  "callback_url": "https://your-server.com/webhook/transcription"
}
```

#### Example 4: ใช้ file_path (ไฟล์ที่อัปโหลดแล้ว)

```json
POST /api/transcribe/
Content-Type: application/json

{
  "file_path": "uploads/video.mp4",
  "model_size": "small",
  "language": "en"
}
```

#### Example 5: ใช้ file_url พร้อม Chunking

```json
POST /api/transcribe/
Content-Type: application/json

{
  "file_url": "https://example.com/long-video.mp4",
  "model_size": "base",
  "chunk_duration": 120,
  "use_chunking": true
}
```

**Notes:**
- รองรับทั้ง audio และ video files (mp4, wav, mp3, mkv, avi, etc.)
- เมื่อใช้ `file_url` ระบบจะดาวน์โหลดไฟล์อัตโนมัติก่อน transcription
- `file_url` ต้องเป็น publicly accessible URL (HTTPS แนะนำ)

### Live-Chunk Transcription

```
POST /api/transcription/realtime/live-chunk
Content-Type: application/octet-stream
X-Meeting-Id: meeting-123
X-Chunk-Index: 0
X-Start-Time: 0.0
X-Duration: 3.0
X-Audio-Format: s16le
X-Sample-Rate: 16000
X-Channels: 1

[Raw PCM16 audio data (binary)]
```

**Notes:**
- Body เป็น raw binary data (PCM16 format)
- Format: 16kHz, Mono, PCM16 (s16le)
- Headers จำเป็นสำหรับ metadata

---

## 📤 Response Format

### File Transcription

**Success (200 OK):**
```json
{
  "task_id": "uuid-here",
  "status": "queued",
  "message": "Transcription job queued successfully (preprocessing in background)",
  "file_path": "uploads/video.mp4",
  "queue": "redis",
  "chunks": 0
}
```

**ตรวจสอบสถานะ:**
```bash
GET /api/v2/tasks/{task_id}
```

**หรือใช้ WebSocket สำหรับ real-time updates:**
```javascript
// Option 1: WebSocket สำหรับ task เฉพาะ
const ws = new WebSocket(`ws://localhost:8010/api/ws/transcription/user123?task_id=${task_id}`);
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};

// Option 2: WebSocket สำหรับ real-time updates ของรายการทั้งหมด
const ws = new WebSocket('ws://localhost:8010/api/history/ws/realtime');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'task.updated' && data.task_id === task_id) {
    console.log('Task updated:', data);
  }
};
```

**Response:**
```json
{
  "task_id": "uuid-here",
  "status": "completed",
  "progress": 100,
  "full_text": "ข้อความที่แปลงแล้ว...",
  "chunks": [...],
  "created_at": "2026-01-12T20:00:00Z",
  "completed_at": "2026-01-12T20:05:30Z"
}
```

### Live-Chunk Transcription

**Success (200 OK):**
```json
{
  "status": "accepted",
  "session_id": "live-meeting-123-0",
  "meeting_id": "meeting-123",
  "chunk_index": 0,
  "start_time": 0.0,
  "duration": 3.0,
  "job_id": "live-chunk-meeting-123-0",
  "queue": "priority",
  "message": "Audio chunk received. Processing in priority queue. Caption events will be sent via WebSocket."
}
```

**รับผลลัพธ์ผ่าน WebSocket:**
```
ws://localhost:8010/api/ws/captions?meeting_id={meeting_id}
```

**Event Type: `final`**
```json
{
  "type": "final",
  "meeting_id": "meeting-123",
  "session_id": "live-meeting-123-0",
  "chunk_index": 0,
  "text": "ข้อความที่แปลงแล้ว...",
  "segments": [...]
}
```

---

## 🎯 Use Cases

### File Transcription (`/api/transcribe/`)

เหมาะสำหรับ:
- ✅ ไฟล์ video/audio ที่มีอยู่แล้ว (10-30 นาที หรือมากกว่า)
- ✅ Batch processing
- ✅ ไม่ต้องการ real-time results
- ✅ ต้องการผลลัพธ์แบบเต็มไฟล์

**Example 1: ใช้ file_url (Minimal - ใช้ Default Values)**

```javascript
// ส่ง request พร้อม file_url เท่านั้น (ใช้ default values)
const response = await fetch('http://localhost:8010/api/transcribe/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    file_url: 'https://example.com/video.mp4'
    // language: 'th' (default)
    // model_size: 'base' (default)
  })
});

const { task_id } = await response.json();
console.log('Task ID:', task_id);
```

**Example 2: ใช้ file_url พร้อม Custom Model**

```javascript
// ใช้ HuggingFace model สำหรับภาษาไทย
const response = await fetch('http://localhost:8010/api/transcribe/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    file_url: 'https://example.com/video.mp4',
    model_size: 'Vinxscribe/biodatlab-whisper-th-medium-faster',
    language: 'th'
  })
});

const { task_id } = await response.json();
```

**Example 3: ใช้ file_url พร้อม WebSocket (Real-time Updates)**

```javascript
// Step 1: ส่ง transcription request
const response = await fetch('http://localhost:8010/api/transcribe/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    file_url: 'https://example.com/video.mp4',
    model_size: 'base',
    language: 'th'
  })
});

const { task_id } = await response.json();
console.log('Task ID:', task_id);

// Step 2: เชื่อมต่อ WebSocket สำหรับ real-time updates
const userId = 'user123';  // ใช้ user ID ของคุณ
const ws = new WebSocket(`ws://localhost:8010/api/ws/transcription/${userId}?task_id=${task_id}`);

ws.onopen = () => {
  console.log('WebSocket connected');
  // Subscribe to task (ถ้ายังไม่ได้ subscribe ตอนเชื่อมต่อ)
  ws.send(JSON.stringify({
    type: 'subscribe',
    task_id: task_id
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'transcription.progress':
      console.log(`Progress: ${data.progress}% - ${data.stage}`);
      // อัปเดต progress bar
      updateProgressBar(data.progress);
      break;
      
    case 'transcription.completed':
      console.log('✅ Transcription completed!');
      console.log('Full text:', data.text);
      console.log('Chunks:', data.chunks);
      // แสดงผลลัพธ์
      displayTranscription(data.text, data.chunks);
      ws.close();
      break;
      
    case 'transcription.failed':
      console.error('❌ Transcription failed:', data.error);
      // แสดง error
      displayError(data.error);
      ws.close();
      break;
      
    case 'task.updated':
      // อัปเดต task information
      console.log('Task updated:', data);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket closed');
};
```

**Example 4: ใช้ file_url พร้อม WebSocket (Real-time History)**

```javascript
// Step 1: ส่ง transcription request
const response = await fetch('http://localhost:8010/api/transcribe/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    file_url: 'https://example.com/video.mp4'
  })
});

const { task_id } = await response.json();

// Step 2: เชื่อมต่อ WebSocket สำหรับ real-time updates ของรายการทั้งหมด
const ws = new WebSocket('ws://localhost:8010/api/history/ws/realtime');

ws.onopen = () => {
  console.log('WebSocket connected');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  // ตรวจสอบว่าเป็น task ที่เราสนใจ
  if (data.task_id === task_id) {
    switch (data.type) {
      case 'task.updated':
        console.log(`Task ${task_id} updated: ${data.progress}%`);
        break;
        
      case 'task.completed':
        console.log(`Task ${task_id} completed!`);
        console.log('Full text:', data.full_text);
        break;
        
      case 'task.failed':
        console.error(`Task ${task_id} failed:`, data.error_message);
        break;
    }
  }
};
```

**Example 5: ใช้ file_path (ไฟล์ที่อัปโหลดแล้ว)**

```javascript
// Step 1: อัปโหลดไฟล์ก่อน
const formData = new FormData();
formData.append('file', videoFile);
const uploadResponse = await fetch('http://localhost:8010/api/upload/', {
  method: 'POST',
  body: formData
});
const { file_path } = await uploadResponse.json();

// Step 2: ส่ง transcription request
const response = await fetch('http://localhost:8010/api/transcribe/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    file_path: file_path,
    model_size: 'base',
    language: 'th'
  })
});

const { task_id } = await response.json();

// Step 3: ตรวจสอบสถานะผ่าน REST API (Polling)
async function checkStatus() {
  const statusResponse = await fetch(`http://localhost:8010/api/v2/tasks/${task_id}`);
  const result = await statusResponse.json();
  
  if (result.status === 'completed') {
    console.log('Completed!', result.full_text);
  } else if (result.status === 'failed') {
    console.error('Failed:', result.error_message);
  } else {
    console.log(`Progress: ${result.progress}%`);
    // Poll again after 2 seconds
    setTimeout(checkStatus, 2000);
  }
}

checkStatus();
```

### Live-Chunk Transcription (`/api/transcription/realtime/live-chunk`)

เหมาะสำหรับ:
- ✅ Real-time streaming (live audio)
- ✅ Close captioning
- ✅ Low latency requirements (~1-2 seconds)
- ✅ Chunk-based processing (3-5 seconds per chunk)

**Example:**
```javascript
// Connect to WebSocket first
const ws = new WebSocket(`ws://localhost:8010/api/ws/captions?meeting_id=meeting-123`);
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'final') {
    console.log('Transcription:', data.text);
  }
};

// Send audio chunks
const audioChunk = new ArrayBuffer(96000); // 3 seconds of PCM16
await fetch('http://localhost:8010/api/transcription/realtime/live-chunk', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/octet-stream',
    'X-Meeting-Id': 'meeting-123',
    'X-Chunk-Index': '0',
    'X-Start-Time': '0.0',
    'X-Duration': '3.0',
    'X-Audio-Format': 's16le',
    'X-Sample-Rate': '16000',
    'X-Channels': '1'
  },
  body: audioChunk
});
```

---

## 🎯 Model Specification

### File Transcription (`/api/transcribe/`)

**`model_size` ไม่จำเป็นต้องส่ง** - มี default value = `"Vinxscribe/biodatlab-whisper-th-medium-faster"`

#### Standard Models

| Model | Speed | Accuracy | VRAM Usage | Use Case |
|-------|-------|----------|------------|----------|
| `tiny` | ⚡⚡⚡ เร็วที่สุด | ⭐ ต่ำ | ~1GB | Real-time, low accuracy |
| `base` | ⚡⚡ เร็ว | ⭐⭐ ปานกลาง | ~1GB | **Default** - สมดุล |
| `small` | ⚡ เร็วปานกลาง | ⭐⭐⭐ ดี | ~2GB | ความแม่นยำดี |
| `medium` | 🐌 ช้า | ⭐⭐⭐⭐ ดีมาก | ~5GB | ความแม่นยำสูง |
| `large` | 🐌🐌 ช้ามาก | ⭐⭐⭐⭐⭐ สูงสุด | ~10GB | ความแม่นยำสูงสุด |
| `large-v3-turbo` | 🐌 ช้า | ⭐⭐⭐⭐⭐ สูงสุด | ~10GB | Optimized large |

#### HuggingFace Models

| Model | Description | Language |
|-------|-------------|----------|
| `Vinxscribe/biodatlab-whisper-th-medium-faster` | Thai-optimized, faster | Thai |
| `Systran/faster-whisper-small` | Faster Whisper small | Multi |
| หรือ model อื่นๆ จาก HuggingFace Hub | - | - |

**Note:** 
- สำหรับ HuggingFace models ระบบจะดาวน์โหลด model อัตโนมัติเมื่อใช้ครั้งแรก
- Model จะถูก cache ไว้ที่ `/workspace/transcription-service/models/`
- Format: `models--{org}--{model-name}` (เช่น `models--Vinxscribe--biodatlab-whisper-th-medium-faster`)

#### Example Usage

```json
// ใช้ default model (Vinxscribe/biodatlab-whisper-th-medium-faster)
{
  "file_url": "https://example.com/video.mp4"
}

// ใช้ standard model
{
  "file_url": "https://example.com/video.mp4",
  "model_size": "base"
}

// ใช้ HuggingFace model อื่น
{
  "file_url": "https://example.com/video.mp4",
  "model_size": "Systran/faster-whisper-small"
}
```

---

## ⚠️ Swagger Documentation Status

### File Transcription (`/api/transcribe/`)

✅ **Documentation ครบถ้วน:**
- ✅ Request body documented
- ✅ Response schema documented
- ✅ Parameters documented
- ✅ Examples available

### Live-Chunk (`/api/transcription/realtime/live-chunk`)

⚠️ **Documentation ไม่ครบถ้วน:**
- ❌ Request body (binary) ไม่ได้ document
- ⚠️ Header parameters ไม่มี type/description ชัดเจน
- ⚠️ Response schema ไม่ได้ระบุชัดเจน
- ⚠️ ต้องดู documentation file แทน

---

## 📚 เอกสารเพิ่มเติม

- [WebHook vs WebSocket Comparison](./WEBHOOK_VS_WEBSOCKET.md) - เปรียบเทียบ WebHook และ WebSocket
- [Live Chunk Frontend Integration](./LIVE_CHUNK_FRONTEND_INTEGRATION.md)
- [WebSocket API Guide](../WORKERS_WS_EVENT_GUIDE.md)
- [API Documentation (Swagger UI)](http://localhost:8010/docs)
