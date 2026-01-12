# 📡 คู่มือการ Subscribe WebSocket และ Message Format

## 🔌 1. การเชื่อมต่อ WebSocket

### Endpoint
```
ws://localhost:8010/ws/transcription/{user_id}
```

**Parameters:**
- `user_id`: User ID ของผู้ใช้ (ใช้สำหรับการ subscribe และ routing messages)

**Example:**
```javascript
const userId = 'user-123';
const ws = new WebSocket(`ws://localhost:8010/ws/transcription/${userId}`);
```

---

## 📨 2. การ Subscribe Task

### 2.1 ส่ง Subscribe Message

หลังจากเชื่อมต่อ WebSocket สำเร็จ Frontend ต้องส่ง message เพื่อ subscribe task:

```json
{
  "type": "subscribe",
  "task_id": "abc-123-def-456"
}
```

**Example Code:**
```javascript
ws.onopen = () => {
  console.log('✅ WebSocket connected');
  
  // Subscribe task
  ws.send(JSON.stringify({
    type: 'subscribe',
    task_id: 'abc-123-def-456'
  }));
};
```

### 2.2 Backend Response

เมื่อ subscribe สำเร็จ Backend จะส่ง confirmation:

```json
{
  "type": "subscription",
  "task_id": "abc-123-def-456",
  "status": "subscribed",
  "timestamp": "2026-01-11T09:00:00Z"
}
```

---

## 📊 3. Message Format ที่ส่งกลับมา

### 3.1 transcription.progress

ส่งเมื่อ progress อัปเดต (rate-limited: ทุก 5% หรือเมื่อ stage เปลี่ยน)

```json
{
  "type": "transcription.progress",
  "task_id": "abc-123-def-456",
  "progress": 45,
  "status": "processing",
  "stage": "transcribing",
  "timestamp": "2026-01-11T09:45:30.123Z"
}
```

**Fields:**
- `type`: `"transcription.progress"` (required)
- `task_id`: Task ID (required)
- `progress`: 0-100 (percentage, required)
- `status`: `"processing"`, `"queued"`, `"pending"`, `"completed"`, `"failed"` (required)
- `stage`: ชื่อ stage ปัจจุบัน เช่น `"transcribing"`, `"merging"`, `"extracting_audio"` (optional)
- `timestamp`: ISO 8601 timestamp (required)

**Example Handler:**
```javascript
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'transcription.progress') {
    console.log(`Task ${message.task_id}: ${message.progress}% - ${message.stage}`);
    // Update UI
    updateProgress(message.task_id, message.progress, message.status, message.stage);
  }
};
```

---

### 3.2 transcription.completed

ส่งเมื่อ transcription เสร็จสมบูรณ์

```json
{
  "type": "transcription.completed",
  "task_id": "abc-123-def-456",
  "status": "completed",
  "progress": 100,
  "text_length": 1234,
  "chunks_count": 20,
  "results_summary": {
    "duration": 360.5,
    "language": "th",
    "processing_time": 45.2
  },
  "timestamp": "2026-01-11T09:50:00.456Z"
}
```

**Fields:**
- `type`: `"transcription.completed"` (required)
- `task_id`: Task ID (required)
- `status`: `"completed"` (required)
- `progress`: `100` (required)
- `text_length`: จำนวนตัวอักษรในข้อความ (optional)
- `chunks_count`: จำนวน chunks (optional)
- `results_summary`: สรุปผลลัพธ์ (optional)
  - `duration`: ระยะเวลาวิดีโอ (วินาที)
  - `language`: ภาษาที่ตรวจพบ
  - `processing_time`: เวลาที่ใช้ในการประมวลผล (วินาที)
- `timestamp`: ISO 8601 timestamp (required)

---

### 3.3 transcription.failed

ส่งเมื่อ transcription ล้มเหลว

```json
{
  "type": "transcription.failed",
  "task_id": "abc-123-def-456",
  "status": "failed",
  "error": "Error message here",
  "timestamp": "2026-01-11T09:48:00.789Z"
}
```

**Fields:**
- `type`: `"transcription.failed"` (required)
- `task_id`: Task ID (required)
- `status`: `"failed"` (required)
- `error`: ข้อความ error (optional)
- `timestamp`: ISO 8601 timestamp (required)

---

### 3.4 transcription.started

ส่งเมื่อ transcription เริ่มต้น

```json
{
  "type": "transcription.started",
  "task_id": "abc-123-def-456",
  "file_path": "/path/to/file.mp4",
  "language": "th",
  "status": "started",
  "timestamp": "2026-01-11T09:00:00.000Z"
}
```

---

### 3.5 ping (Heartbeat)

Backend ส่ง ping ทุก 30 วินาที เพื่อ keep connection alive

```json
{
  "type": "ping",
  "timestamp": "2026-01-11T09:00:00Z"
}
```

**Frontend ควรตอบกลับ:**
```json
{
  "type": "pong",
  "timestamp": "2026-01-11T09:00:00Z"
}
```

---

## 💻 4. Complete Example

### JavaScript/TypeScript

```javascript
class TranscriptionWebSocketClient {
  constructor(userId, baseUrl = 'ws://localhost:8010') {
    this.userId = userId;
    this.baseUrl = baseUrl;
    this.ws = null;
    this.subscribedTasks = new Set();
  }

  connect() {
    const url = `${this.baseUrl}/ws/transcription/${this.userId}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('✅ WebSocket connected');
      
      // Re-subscribe all tasks
      this.subscribedTasks.forEach(taskId => {
        this.subscribe(taskId);
      });
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('Error parsing message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      // Reconnect after 5 seconds
      setTimeout(() => this.connect(), 5000);
    };
  }

  subscribe(taskId) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'subscribe',
        task_id: taskId
      }));
      this.subscribedTasks.add(taskId);
      console.log(`✅ Subscribed to task: ${taskId}`);
    } else {
      // Queue subscription for when connection is ready
      this.subscribedTasks.add(taskId);
      console.warn('WebSocket not connected, queued subscription');
    }
  }

  unsubscribe(taskId) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'unsubscribe',
        task_id: taskId
      }));
      this.subscribedTasks.delete(taskId);
      console.log(`✅ Unsubscribed from task: ${taskId}`);
    }
  }

  handleMessage(message) {
    switch (message.type) {
      case 'ping':
        // Respond to ping
        this.ws.send(JSON.stringify({
          type: 'pong',
          timestamp: message.timestamp
        }));
        break;

      case 'subscription':
        console.log(`✅ Subscription confirmed: ${message.task_id}`);
        break;

      case 'transcription.progress':
        console.log(`📊 Task ${message.task_id}: ${message.progress}% - ${message.stage}`);
        this.onProgress?.(message);
        break;

      case 'transcription.completed':
        console.log(`✅ Task ${message.task_id} completed`);
        this.onCompleted?.(message);
        break;

      case 'transcription.failed':
        console.error(`❌ Task ${message.task_id} failed: ${message.error}`);
        this.onFailed?.(message);
        break;

      case 'transcription.started':
        console.log(`🚀 Task ${message.task_id} started`);
        this.onStarted?.(message);
        break;

      default:
        console.log('Unknown message type:', message.type);
    }
  }

  // Callbacks (set these from outside)
  onProgress = null;
  onCompleted = null;
  onFailed = null;
  onStarted = null;
}

// Usage
const client = new TranscriptionWebSocketClient('user-123');
client.onProgress = (message) => {
  // Update UI with progress
  updateProgressBar(message.task_id, message.progress);
  updateStatus(message.task_id, message.status, message.stage);
};
client.onCompleted = (message) => {
  // Show completion message
  showSuccess(`Task ${message.task_id} completed!`);
};
client.onFailed = (message) => {
  // Show error message
  showError(`Task ${message.task_id} failed: ${message.error}`);
};

client.connect();
client.subscribe('abc-123-def-456');
```

---

## 🔄 5. Flow Diagram

```
Frontend                          Backend                          Worker
   |                                |                                |
   |-- Connect WebSocket ---------->|                                |
   |                                |                                |
   |<-- Connection Established -----|                                |
   |                                |                                |
   |-- Subscribe {task_id} -------->|                                |
   |                                |                                |
   |<-- Subscription Confirmed -----|                                |
   |                                |                                |
   |                                |<-- Progress Update ------------|
   |                                |                                |
   |<-- transcription.progress -----|                                |
   |                                |                                |
   |                                |<-- Progress Update ------------|
   |                                |                                |
   |<-- transcription.progress -----|                                |
   |                                |                                |
   |                                |<-- Completed -------------------|
   |                                |                                |
   |<-- transcription.completed ----|                                |
```

---

## 📋 6. สรุป

### Frontend ต้องทำ:
1. ✅ เชื่อมต่อ WebSocket: `ws://localhost:8010/ws/transcription/{user_id}`
2. ✅ ส่ง subscribe message: `{"type": "subscribe", "task_id": "..."}`
3. ✅ Handle messages:
   - `transcription.progress` - อัปเดต progress
   - `transcription.completed` - แสดงผลลัพธ์
   - `transcription.failed` - แสดง error
   - `ping` - ตอบกลับด้วย `pong`

### Message Format ที่สำคัญ:
- **Progress**: `{"type": "transcription.progress", "task_id": "...", "progress": 45, "status": "processing", "stage": "transcribing", "timestamp": "..."}`
- **Completed**: `{"type": "transcription.completed", "task_id": "...", "status": "completed", "progress": 100, ...}`
- **Failed**: `{"type": "transcription.failed", "task_id": "...", "status": "failed", "error": "..."}`

---

## 🔍 7. Debugging

### ตรวจสอบว่า Frontend Subscribe สำเร็จหรือไม่:

```javascript
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('📨 Received:', message);
  
  if (message.type === 'subscription') {
    console.log('✅ Subscription confirmed for:', message.task_id);
  }
};
```

### ตรวจสอบว่า Backend ส่ง Progress Updates หรือไม่:

ดู logs:
```bash
tail -f /tmp/main-api.log | grep -E "transcription.progress|Published task update"
```

### ตรวจสอบ WebSocket Connections:

```bash
curl http://localhost:8010/ws/stats
```

---

## 📚 เอกสารเพิ่มเติม

- [WEBSOCKET_USAGE.md](../WEBSOCKET_USAGE.md) - คู่มือการใช้งาน WebSocket แบบละเอียด
- [REALTIME_API_GUIDE.md](./REALTIME_API_GUIDE.md) - คู่มือ API แบบ real-time
