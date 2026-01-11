# 📡 คู่มือการใช้งาน WebSocket Notifications

## 📋 ภาพรวม

ระบบ WebSocket notifications ช่วยให้ frontend ได้รับ real-time updates เกี่ยวกับ transcription tasks โดยไม่ต้อง polling

---

## 🔌 1. เชื่อมต่อ WebSocket

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

## 📨 2. Message Types

### 2.1 Messages จาก Frontend → Backend

#### Subscribe to Task
```json
{
  "type": "subscribe",
  "task_id": "abc-123-def-456"
}
```

#### Unsubscribe from Task
```json
{
  "type": "unsubscribe",
  "task_id": "abc-123-def-456"
}
```

#### Ping (Health Check)
```json
{
  "type": "ping",
  "timestamp": "2026-01-11T09:00:00Z"
}
```

---

### 2.2 Messages จาก Backend → Frontend

#### transcription.progress
ส่งเมื่อ progress อัปเดต (rate-limited: ทุก 5% หรือทุก 2-3 วินาที)

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
- `progress`: 0-100 (percentage)
- `status`: "processing", "queued", "pending"
- `stage`: ชื่อ stage ปัจจุบัน (เช่น "transcribing", "merging", "extracting_audio")

---

#### transcription.completed
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

---

#### transcription.failed
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

---

#### task.list
ส่งเมื่อ request task list

```json
{
  "type": "task.list",
  "tasks": [
    {
      "task_id": "abc-123",
      "status": "completed",
      "progress": 100,
      "file_name": "video.mp4",
      "created_at": "2026-01-11T09:00:00Z",
      "completed_at": "2026-01-11T09:05:00Z"
    }
  ],
  "timestamp": "2026-01-11T09:50:00Z"
}
```

---

#### task.updated / task.created / task.completed / task.failed
ส่งเมื่อ task ถูกสร้าง/อัปเดต/เสร็จ/ล้มเหลว (สำหรับ task list updates)

```json
{
  "type": "task.updated",
  "task_id": "abc-123-def-456",
  "task": {
    "task_id": "abc-123-def-456",
    "status": "processing",
    "progress": 50,
    "current_stage": "transcribing",
    "current_stage_description": "กำลังแปลงเสียงเป็นข้อความ (10/20 ส่วนเสร็จ)",
    "file_name": "video.mp4",
    "created_at": "2026-01-11T09:00:00Z",
    "updated_at": "2026-01-11T09:45:00Z"
  },
  "timestamp": "2026-01-11T09:45:00Z"
}
```

---

## 💻 3. Example Code (JavaScript/TypeScript)

### 3.1 Basic WebSocket Client

```javascript
class TranscriptionWebSocketClient {
  constructor(userId, baseUrl = 'ws://localhost:8010') {
    this.userId = userId;
    this.baseUrl = baseUrl;
    this.ws = null;
    this.reconnectInterval = 5000;
    this.shouldReconnect = true;
  }

  connect() {
    const url = `${this.baseUrl}/ws/transcription/${this.userId}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('✅ WebSocket connected');
      this.onConnect();
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
      if (this.shouldReconnect) {
        setTimeout(() => this.connect(), this.reconnectInterval);
      }
    };
  }

  subscribe(taskId) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'subscribe',
        task_id: taskId
      }));
      console.log(`✅ Subscribed to task: ${taskId}`);
    } else {
      console.error('WebSocket not connected');
    }
  }

  unsubscribe(taskId) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'unsubscribe',
        task_id: taskId
      }));
      console.log(`✅ Unsubscribed from task: ${taskId}`);
    }
  }

  handleMessage(message) {
    switch (message.type) {
      case 'transcription.progress':
        this.onProgress(message);
        break;
      case 'transcription.completed':
        this.onCompleted(message);
        break;
      case 'transcription.failed':
        this.onFailed(message);
        break;
      case 'task.list':
        this.onTaskList(message.tasks);
        break;
      case 'task.updated':
      case 'task.created':
      case 'task.completed':
      case 'task.failed':
        this.onTaskUpdate(message);
        break;
      default:
        console.log('Unknown message type:', message.type);
    }
  }

  // Override these methods in your implementation
  onConnect() {}
  onProgress(message) {
    console.log('Progress:', message);
  }
  onCompleted(message) {
    console.log('Completed:', message);
  }
  onFailed(message) {
    console.log('Failed:', message);
  }
  onTaskList(tasks) {
    console.log('Task list:', tasks);
  }
  onTaskUpdate(message) {
    console.log('Task update:', message);
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.ws) {
      this.ws.close();
    }
  }
}
```

---

### 3.2 React Hook Example

```typescript
import { useEffect, useRef, useState } from 'react';

interface TranscriptionProgress {
  task_id: string;
  progress: number;
  status: string;
  stage: string;
}

export function useTranscriptionWebSocket(userId: string) {
  const [progress, setProgress] = useState<Map<string, TranscriptionProgress>>(new Map());
  const [tasks, setTasks] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8010/ws/transcription/${userId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      // Request task list on connect
      ws.send(JSON.stringify({ action: 'get_task_list' }));
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      switch (message.type) {
        case 'transcription.progress':
          setProgress(prev => {
            const newMap = new Map(prev);
            newMap.set(message.task_id, {
              task_id: message.task_id,
              progress: message.progress,
              status: message.status,
              stage: message.stage,
            });
            return newMap;
          });
          break;
          
        case 'transcription.completed':
          setProgress(prev => {
            const newMap = new Map(prev);
            newMap.set(message.task_id, {
              task_id: message.task_id,
              progress: 100,
              status: 'completed',
              stage: 'completed',
            });
            return newMap;
          });
          break;
          
        case 'transcription.failed':
          setProgress(prev => {
            const newMap = new Map(prev);
            newMap.set(message.task_id, {
              task_id: message.task_id,
              progress: 0,
              status: 'failed',
              stage: 'failed',
            });
            return newMap;
          });
          break;
          
        case 'task.list':
          setTasks(message.tasks || []);
          break;
          
        case 'task.updated':
        case 'task.created':
        case 'task.completed':
        case 'task.failed':
          // Update task in list
          setTasks(prev => {
            const index = prev.findIndex(t => t.task_id === message.task_id);
            if (index >= 0) {
              const newTasks = [...prev];
              newTasks[index] = message.task;
              return newTasks;
            } else {
              return [...prev, message.task];
            }
          });
          break;
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      // Reconnect after 5 seconds
      setTimeout(() => {
        if (wsRef.current?.readyState === WebSocket.CLOSED) {
          // Reconnect logic here if needed
        }
      }, 5000);
    };

    return () => {
      ws.close();
    };
  }, [userId]);

  const subscribe = (taskId: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'subscribe',
        task_id: taskId
      }));
    }
  };

  const unsubscribe = (taskId: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'unsubscribe',
        task_id: taskId
      }));
    }
  };

  return {
    progress,
    tasks,
    subscribe,
    unsubscribe,
  };
}
```

---

## 🧪 4. วิธีทดสอบ

### 4.1 ทดสอบด้วย Browser Console

```javascript
// 1. เชื่อมต่อ WebSocket
const ws = new WebSocket('ws://localhost:8010/ws/transcription/test-user');

// 2. รับ messages
ws.onmessage = (event) => {
  console.log('Received:', JSON.parse(event.data));
};

// 3. Subscribe task (หลังจากส่ง transcription job)
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    task_id: 'your-task-id-here'
  }));
};

// 4. ส่ง transcription job ผ่าน API
fetch('http://localhost:8010/api/transcribe/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    file_url: 'https://example.com/video.mp4',
    language: 'th',
    model_size: 'medium'
  })
})
.then(res => res.json())
.then(data => {
  console.log('Task ID:', data.task_id);
  // Subscribe to this task
  ws.send(JSON.stringify({
    type: 'subscribe',
    task_id: data.task_id
  }));
});
```

### 4.2 ทดสอบด้วย curl + websocat

```bash
# 1. ติดตั้ง websocat (if not installed)
# curl -L https://github.com/vi/websocat/releases/download/v1.11.0/websocat.x86_64-unknown-linux-musl -o /usr/local/bin/websocat
# chmod +x /usr/local/bin/websocat

# 2. เชื่อมต่อ WebSocket
websocat ws://localhost:8010/ws/transcription/test-user

# 3. Subscribe task (หลังจากส่ง transcription job)
{"type": "subscribe", "task_id": "your-task-id-here"}
```

---

## 📊 5. Rate Limiting

WebSocket notifications มี rate limiting เพื่อลด network traffic:

- **Progress updates**: ส่งเมื่อ progress เปลี่ยน **>= 5%** หรือเมื่อ stage เปลี่ยน
- **Status changes**: ส่งทันทีเมื่อ status เป็น "completed", "failed", "queued", "processing" (progress = 0)

---

## ⚠️ 6. Error Handling

### Connection Errors
- WebSocket connection อาจหลุดได้ (network issues, server restart)
- **แนะนำ**: Implement auto-reconnect logic
- ตรวจสอบ `readyState` ก่อนส่ง messages

### Message Errors
- Messages อาจมาผิดรูปแบบ (ควร validate ก่อนใช้งาน)
- ใช้ `try-catch` เมื่อ parse JSON

---

## 🔍 7. Debugging

### ตรวจสอบ WebSocket Connections

```bash
# ดู logs จาก Main API
tail -f /tmp/main-api.log | grep -E "WebSocket|User.*เชื่อมต่อ|ส่ง task update"

# ดู logs จาก RQ Workers
tail -f /tmp/rq-worker-cpu-0.log | grep -E "บันทึก transcription|notify_transcription"
```

### ตรวจสอบว่า Task ถูก Subscribe หรือไม่

```python
# ใน Python console
from app.services.websocket_service import websocket_manager
stats = websocket_manager.get_stats()
print(stats)
# จะแสดง:
# - connection_count
# - user_connections
# - task_users (mapping task_id -> set of user_ids)
```

---

## 📝 8. Best Practices

1. **Subscribe ก่อนส่ง Job**: Subscribe task ทันทีหลังจากส่ง transcription job
2. **Unsubscribe เมื่อไม่ใช้**: Unsubscribe เมื่อไม่ต้องการรับ updates แล้ว (เพื่อลด memory usage)
3. **Handle Reconnection**: Implement auto-reconnect และ re-subscribe tasks หลัง reconnect
4. **Error Handling**: Handle connection errors และ message errors gracefully
5. **Rate Limiting**: ไม่ต้องส่ง requests บ่อยเกินไป (ระบบมี rate limiting อยู่แล้ว)

---

## 🎯 9. Workflow Example

```javascript
// 1. เชื่อมต่อ WebSocket
const ws = new WebSocket('ws://localhost:8010/ws/transcription/user-123');

ws.onopen = async () => {
  // 2. ส่ง transcription job
  const response = await fetch('http://localhost:8010/api/transcribe/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_url: 'https://example.com/video.mp4',
      language: 'th',
      model_size: 'medium'
    })
  });
  
  const data = await response.json();
  const taskId = data.task_id;
  
  // 3. Subscribe to task
  ws.send(JSON.stringify({
    type: 'subscribe',
    task_id: taskId
  }));
};

// 4. รับ progress updates
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'transcription.progress') {
    console.log(`Progress: ${message.progress}% - ${message.stage}`);
    // Update UI
    updateProgressBar(message.progress);
    updateStage(message.stage);
  } else if (message.type === 'transcription.completed') {
    console.log('Transcription completed!');
    // Show success message
    showSuccessMessage();
    // Fetch full results
    fetch(`http://localhost:8010/api/transcribe/${message.task_id}`)
      .then(res => res.json())
      .then(results => {
        displayResults(results);
      });
  } else if (message.type === 'transcription.failed') {
    console.error('Transcription failed:', message.error);
    showErrorMessage(message.error);
  }
};
```

---

## 📚 10. API Reference

### WebSocket Endpoint
- **URL**: `ws://localhost:8010/ws/transcription/{user_id}`
- **Protocol**: WebSocket (ws://) or Secure WebSocket (wss://)

### Actions (Frontend → Backend)
- `subscribe`: Subscribe to task updates (ต้องส่ง `task_id` ด้วย)
- `unsubscribe`: Unsubscribe from task updates (ต้องส่ง `task_id` ด้วย)
- `ping`: Health check (server จะตอบกลับด้วย `pong`)

### Message Types (Backend → Frontend)
- `transcription.progress`: Progress update
- `transcription.completed`: Task completed
- `transcription.failed`: Task failed
- `task.list`: Task list response
- `task.created`: New task created
- `task.updated`: Task updated
- `task.completed`: Task completed (for list)
- `task.failed`: Task failed (for list)

---

## 🆘 Troubleshooting

### ไม่ได้รับ Notifications
1. ตรวจสอบว่า WebSocket connection เปิดอยู่ (`ws.readyState === WebSocket.OPEN`)
2. ตรวจสอบว่า subscribe task แล้ว (`{"type": "subscribe", "task_id": "..."}`)
3. ตรวจสอบ logs: `tail -f /tmp/main-api.log | grep WebSocket`
4. ตรวจสอบว่า task มี user subscribe: ใช้ `websocket_manager.get_stats()`

### Connection หลุดบ่อย
- Implement auto-reconnect logic
- ตรวจสอบ network stability
- ตรวจสอบ server logs สำหรับ errors

### Messages ไม่ถูกส่ง
- ตรวจสอบ rate limiting (progress ต้องเปลี่ยน >= 5%)
- ตรวจสอบว่า task ถูกบันทึกใน database: `SELECT * FROM transcriptions WHERE task_id = '...'`

---

## 📞 Support

สำหรับคำถามหรือปัญหาอื่นๆ:
- ตรวจสอบ logs: `/tmp/main-api.log`, `/tmp/rq-worker-*.log`
- ตรวจสอบ WebSocket service: `app/services/websocket_service.py`
- ตรวจสอบ worker code: `app/workers/rq_worker.py`

