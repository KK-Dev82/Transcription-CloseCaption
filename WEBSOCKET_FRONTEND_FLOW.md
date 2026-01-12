# 📡 WebSocket Flow สำหรับ Frontend UI

## ✅ แนวทางนี้รองรับ Frontend UI 100%

**Flow ที่สมบูรณ์:**
1. **Frontend**: Connect WebSocket → `ws://localhost:8010/ws/transcription/{user_id}`
2. **Frontend**: Subscribe task → `{type: 'subscribe', task_id: 'abc-123'}`
3. **Backend (Worker)**: Process transcription → ส่ง HTTP callback
4. **Backend (Main API)**: รับ callback → broadcast via WebSocket
5. **Frontend**: รับ progress/completion notifications

---

## 🔄 Complete Flow

### Step 1: Frontend Connect WebSocket

```javascript
// Frontend JavaScript
const userId = 'user-123';
const ws = new WebSocket(`ws://localhost:8010/ws/transcription/${userId}`);

ws.onopen = () => {
  console.log('✅ WebSocket connected');
  
  // Step 2: Subscribe to task
  ws.send(JSON.stringify({
    type: 'subscribe',
    task_id: 'abc-123'
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('📥 Received:', message);
  
  switch (message.type) {
    case 'connection':
      console.log('✅ Connection confirmed');
      break;
      
    case 'subscription':
      console.log(`✅ Subscribed to task: ${message.task_id}`);
      break;
      
    case 'transcription.progress':
      console.log(`📊 Progress: ${message.progress}% - ${message.stage}`);
      updateProgressBar(message.progress);
      break;
      
    case 'transcription.completed':
      console.log('✅ Transcription completed!');
      showResults(message);
      break;
      
    case 'transcription.failed':
      console.error('❌ Transcription failed:', message.error);
      showError(message.error);
      break;
  }
};

ws.onerror = (error) => {
  console.error('❌ WebSocket error:', error);
};

ws.onclose = () => {
  console.log('🔌 WebSocket closed');
};
```

---

### Step 2: Frontend Subscribe to Task

**Message จาก Frontend → Backend:**
```json
{
  "type": "subscribe",
  "task_id": "abc-123"
}
```

**Response จาก Backend → Frontend:**
```json
{
  "type": "subscription",
  "task_id": "abc-123",
  "status": "subscribed",
  "timestamp": "2026-01-12T12:00:00Z"
}
```

---

### Step 3: Worker Process Transcription

**Worker (RQ Worker Process):**
```python
# ใน app/workers/rq_worker.py
async def _update_task_stage_and_webhook(...):
    # Worker ส่ง HTTP callback
    await send_ws_event_via_http(
        task_id=task_id,
        message={
            "type": "transcription.progress",
            "progress": 45,
            "status": "processing",
            "stage": "transcribing",
            "timestamp": datetime.now().isoformat()
        }
    )
```

**HTTP Callback (Worker → Main API):**
```http
POST /api/internal/ws-event
Content-Type: application/json

{
  "task_id": "abc-123",
  "message": {
    "type": "transcription.progress",
    "progress": 45,
    "status": "processing",
    "stage": "transcribing",
    "timestamp": "2026-01-12T12:00:00Z"
  }
}
```

---

### Step 4: Main API Broadcast via WebSocket

**Main API (`/api/internal/ws-event`):**
```python
@router.post("/ws-event")
async def ws_event(payload: Dict[str, Any]):
    task_id = payload.get("task_id")
    message = payload.get("message", payload)
    
    # Broadcast ไปยัง WebSocket clients ที่ subscribe task นี้
    await websocket_manager.broadcast_task_update(task_id, message)
    
    return {"ok": True, "type": "task_update", "task_id": task_id}
```

**WebSocketManager:**
```python
async def broadcast_task_update(self, task_id: str, message: dict):
    """In-process broadcast to all users who subscribed task_id"""
    user_ids = list(self.task_users.get(task_id, set()))
    for user_id in user_ids:
        await self.send_to_user(user_id, message)  # ส่งไปยัง Frontend
```

---

### Step 5: Frontend Receive Notifications

**Progress Update:**
```json
{
  "type": "transcription.progress",
  "task_id": "abc-123",
  "progress": 45,
  "status": "processing",
  "stage": "transcribing",
  "timestamp": "2026-01-12T12:00:00Z"
}
```

**Completion Notification:**
```json
{
  "type": "transcription.completed",
  "task_id": "abc-123",
  "status": "completed",
  "text_length": 1234,
  "chunks_count": 10,
  "results_summary": {
    "duration": 120.5,
    "language": "th",
    "processing_time": 45.2
  },
  "timestamp": "2026-01-12T12:00:00Z"
}
```

**Failed Notification:**
```json
{
  "type": "transcription.failed",
  "task_id": "abc-123",
  "status": "failed",
  "error": "Transcription failed",
  "timestamp": "2026-01-12T12:00:00Z"
}
```

---

## 📋 Complete Example

### Frontend Code

```javascript
class TranscriptionClient {
  constructor(userId, apiUrl = 'ws://localhost:8010') {
    this.userId = userId;
    this.apiUrl = apiUrl;
    this.ws = null;
    this.subscriptions = new Set();
  }
  
  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(`${this.apiUrl}/ws/transcription/${this.userId}`);
      
      this.ws.onopen = () => {
        console.log('✅ WebSocket connected');
        resolve();
      };
      
      this.ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        this.handleMessage(message);
      };
      
      this.ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        reject(error);
      };
      
      this.ws.onclose = () => {
        console.log('🔌 WebSocket closed');
        // Auto-reconnect logic here
      };
    });
  }
  
  subscribe(taskId) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'subscribe',
        task_id: taskId
      }));
      this.subscriptions.add(taskId);
      console.log(`📡 Subscribed to task: ${taskId}`);
    }
  }
  
  unsubscribe(taskId) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'unsubscribe',
        task_id: taskId
      }));
      this.subscriptions.delete(taskId);
      console.log(`📡 Unsubscribed from task: ${taskId}`);
    }
  }
  
  handleMessage(message) {
    switch (message.type) {
      case 'connection':
        console.log('✅ Connection confirmed');
        break;
        
      case 'subscription':
        console.log(`✅ Subscribed to task: ${message.task_id}`);
        break;
        
      case 'transcription.progress':
        console.log(`📊 Progress: ${message.progress}% - ${message.stage}`);
        this.onProgress?.(message);
        break;
        
      case 'transcription.completed':
        console.log('✅ Transcription completed!');
        this.onCompleted?.(message);
        break;
        
      case 'transcription.failed':
        console.error('❌ Transcription failed:', message.error);
        this.onFailed?.(message);
        break;
        
      default:
        console.log('📥 Unknown message type:', message.type);
    }
  }
  
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.subscriptions.clear();
    }
  }
}

// Usage
const client = new TranscriptionClient('user-123');

client.onProgress = (message) => {
  // Update UI progress bar
  updateProgressBar(message.progress);
  updateStatus(message.status, message.stage);
};

client.onCompleted = (message) => {
  // Show results
  showResults(message);
};

client.onFailed = (message) => {
  // Show error
  showError(message.error);
};

// Connect and subscribe
await client.connect();
client.subscribe('abc-123');
```

---

## 🎯 สรุป

### ✅ แนวทางนี้รองรับ Frontend UI 100%

**Flow:**
1. ✅ Frontend Connect WebSocket → `ws://localhost:8010/ws/transcription/{user_id}`
2. ✅ Frontend Subscribe Task → `{type: 'subscribe', task_id: '...'}`
3. ✅ Worker Process → HTTP Callback → Main API
4. ✅ Main API Broadcast → WebSocket → Frontend
5. ✅ Frontend Receive → Progress/Completion Notifications

**Features:**
- ✅ Real-time progress updates
- ✅ Completion notifications
- ✅ Error notifications
- ✅ Multiple task subscriptions
- ✅ User-specific connections

**ข้อดี:**
- ✅ ไม่ต้อง polling (real-time)
- ✅ Low latency
- ✅ Efficient (push-based)
- ✅ Works with single instance

**ข้อจำกัด:**
- ⚠️ Works only with 1 Main API instance (ถ้ามีหลาย instance ต้องใช้ load balancer sticky session หรือ polling)

---

## 📋 Message Types

### From Frontend → Backend

1. **Subscribe:**
```json
{
  "type": "subscribe",
  "task_id": "abc-123"
}
```

2. **Unsubscribe:**
```json
{
  "type": "unsubscribe",
  "task_id": "abc-123"
}
```

3. **Ping:**
```json
{
  "type": "ping",
  "timestamp": "2026-01-12T12:00:00Z"
}
```

### From Backend → Frontend

1. **Connection:**
```json
{
  "type": "connection",
  "status": "connected",
  "user_id": "user-123",
  "timestamp": "2026-01-12T12:00:00Z"
}
```

2. **Subscription:**
```json
{
  "type": "subscription",
  "task_id": "abc-123",
  "status": "subscribed",
  "timestamp": "2026-01-12T12:00:00Z"
}
```

3. **Progress:**
```json
{
  "type": "transcription.progress",
  "task_id": "abc-123",
  "progress": 45,
  "status": "processing",
  "stage": "transcribing",
  "timestamp": "2026-01-12T12:00:00Z"
}
```

4. **Completed:**
```json
{
  "type": "transcription.completed",
  "task_id": "abc-123",
  "status": "completed",
  "text_length": 1234,
  "chunks_count": 10,
  "results_summary": {
    "duration": 120.5,
    "language": "th",
    "processing_time": 45.2
  },
  "timestamp": "2026-01-12T12:00:00Z"
}
```

5. **Failed:**
```json
{
  "type": "transcription.failed",
  "task_id": "abc-123",
  "status": "failed",
  "error": "Transcription failed",
  "timestamp": "2026-01-12T12:00:00Z"
}
```

---

## ✅ สรุป

**แนวทางนี้รองรับ Frontend UI 100%**

- ✅ Frontend สามารถ Connect WebSocket และ Subscribe tasks ได้
- ✅ Frontend รับ progress updates แบบ real-time
- ✅ Frontend รับ completion/error notifications
- ✅ ไม่ได้ใช้แค่ภายใน Transcription Service
- ✅ ใช้งานได้กับ Frontend UI จริง

**Flow:**
```
Frontend UI
    ↓ (Connect WebSocket)
Main API (WebSocket Server)
    ↑ (HTTP Callback)
Worker Process
    ↓ (Broadcast via WebSocket)
Frontend UI (Receive Notifications)
```
