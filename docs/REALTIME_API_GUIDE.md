# 📡 Realtime API Guide - คู่มือการใช้งาน API แบบ Realtime

## 📋 สารบัญ
1. [API Endpoints สำหรับดูข้อมูล](#api-endpoints-สำหรับดูข้อมูล)
2. [WebSocket สำหรับ Realtime Updates](#websocket-สำหรับ-realtime-updates)
3. [ตัวอย่างการใช้งาน Frontend](#ตัวอย่างการใช้งาน-frontend)

---

## 🔍 API Endpoints สำหรับดูข้อมูล

### 1. ดูรายการ Transcription ทั้งหมด

**Endpoint:** `GET /api/history/transcriptions`

**Parameters:**
- `limit` (optional): จำนวนรายการต่อหน้า (default: 20, max: 100)
- `offset` (optional): จำนวนรายการที่จะข้าม (default: 0)
- `status` (optional): กรองตามสถานะ (`completed`, `failed`, `processing`, `pending`)
- `days_ago` (optional): แสดงเฉพาะรายการในช่วง N วันที่ผ่านมา

**ตัวอย่างการเรียกใช้:**
```bash
# ดึงรายการทั้งหมด (20 รายการแรก)
curl http://localhost:8001/api/history/transcriptions

# ดึงรายการที่กำลังประมวลผล
curl http://localhost:8001/api/history/transcriptions?status=processing

# ดึงรายการ 50 รายการล่าสุด
curl http://localhost:8001/api/history/transcriptions?limit=50

# ดึงรายการในช่วง 7 วันที่ผ่านมา
curl http://localhost:8001/api/history/transcriptions?days_ago=7
```

**Response:**
```json
{
  "history": [
    {
      "task_id": "abc123",
      "id": "abc123",
      "filename": "video.mp4",
      "file_name": "video.mp4",
      "file_path": "/path/to/video.mp4",
      "status": "completed",
      "progress": 100,
      "created_at": "2024-01-01T10:00:00",
      "updated_at": "2024-01-01T10:05:00",
      "completed_at": "2024-01-01T10:05:00",
      "duration": 120.5,
      "language": "th",
      "model_used": "base",
      "chunks_count": 10,
      "word_count": 250,
      "error_message": null,
      "has_results": true
    }
  ],
  "pagination": {
    "total": 100,
    "limit": 20,
    "offset": 0,
    "has_more": true
  },
  "filters_applied": {
    "status": null,
    "days_ago": null
  },
  "timestamp": "2024-01-01T12:00:00"
}
```

### 2. ดูรายละเอียด Transcription

**Endpoint:** `GET /api/history/transcriptions/{task_id}`

**ตัวอย่างการเรียกใช้:**
```bash
curl http://localhost:8001/api/history/transcriptions/abc123
```

### 3. ดูสถิติ

**Endpoint:** `GET /api/history/stats`

**ตัวอย่างการเรียกใช้:**
```bash
curl http://localhost:8001/api/history/stats
```

---

## 🔴 WebSocket สำหรับ Realtime Updates

### 1. WebSocket สำหรับรายการทั้งหมด (History Realtime)

**Endpoint:** `WS /api/history/ws/realtime`

**การเชื่อมต่อ:**
```javascript
const ws = new WebSocket('ws://localhost:8001/api/history/ws/realtime');

ws.onopen = () => {
  console.log('✅ Connected to realtime history WebSocket');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('📨 Received:', data);
  
  switch(data.type) {
    case 'connection':
      console.log('Connected:', data.message);
      break;
    case 'task.created':
      console.log('New task created:', data.task_id);
      // อัปเดต UI เพิ่ม task ใหม่
      break;
    case 'task.updated':
      console.log('Task updated:', data.task_id);
      // อัปเดต UI สำหรับ task ที่เปลี่ยน
      break;
    case 'task.completed':
      console.log('Task completed:', data.task_id);
      // อัปเดต UI เมื่อ task เสร็จ
      break;
    case 'task.failed':
      console.log('Task failed:', data.task_id);
      // แสดง error ใน UI
      break;
    case 'task.deleted':
      console.log('Task deleted:', data.task_id);
      // ลบ task จาก UI
      break;
    case 'ping':
      // ส่ง pong กลับ
      ws.send(JSON.stringify({ type: 'pong' }));
      break;
  }
};

ws.onerror = (error) => {
  console.error('❌ WebSocket error:', error);
};

ws.onclose = () => {
  console.log('🔴 WebSocket closed');
};
```

**Messages ที่ Server ส่งมา:**
- `connection`: เมื่อเชื่อมต่อสำเร็จ
- `task.created`: เมื่อมี task ใหม่
- `task.updated`: เมื่อ task อัปเดต (status, progress, etc.)
- `task.completed`: เมื่อ task เสร็จสมบูรณ์
- `task.failed`: เมื่อ task ล้มเหลว
- `task.deleted`: เมื่อ task ถูกลบ
- `ping`: สำหรับ health check (ทุก 30 วินาที)
- `keepalive`: เมื่อไม่มี activity (ทุก 60 วินาที)

**Messages ที่ Client ส่งได้:**
- `{"type": "ping"}`: สำหรับ health check
- `{"type": "get_latest", "limit": 20}`: ขอรายการล่าสุด

### 2. WebSocket สำหรับ Task เฉพาะ

**Endpoint:** `WS /ws/transcription/{user_id}?task_id={task_id}`

**การเชื่อมต่อ:**
```javascript
const userId = 'user123';
const taskId = 'abc123';
const ws = new WebSocket(`ws://localhost:8001/ws/transcription/${userId}?task_id=${taskId}`);

ws.onopen = () => {
  console.log('✅ Connected to task WebSocket');
  
  // Subscribe task
  ws.send(JSON.stringify({
    type: 'subscribe',
    task_id: taskId
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('📨 Task update:', data);
};
```

---

## 💻 ตัวอย่างการใช้งาน Frontend

### React Example

```jsx
import { useEffect, useState } from 'react';

function TranscriptionList() {
  const [transcriptions, setTranscriptions] = useState([]);
  const [ws, setWs] = useState(null);

  useEffect(() => {
    // โหลดข้อมูลเริ่มต้น
    fetch('/api/history/transcriptions?limit=50')
      .then(res => res.json())
      .then(data => setTranscriptions(data.history));

    // เชื่อมต่อ WebSocket สำหรับ realtime updates
    const websocket = new WebSocket('ws://localhost:8001/api/history/ws/realtime');
    
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch(data.type) {
        case 'task.created':
          // เพิ่ม task ใหม่ที่ด้านบน
          setTranscriptions(prev => [data.task_data, ...prev]);
          break;
        case 'task.updated':
          // อัปเดต task ที่มีอยู่
          setTranscriptions(prev => 
            prev.map(t => 
              t.task_id === data.task_id ? { ...t, ...data.task_data } : t
            )
          );
          break;
        case 'task.completed':
        case 'task.failed':
          // อัปเดตสถานะ
          setTranscriptions(prev => 
            prev.map(t => 
              t.task_id === data.task_id ? { ...t, ...data.task_data } : t
            )
          );
          break;
        case 'task.deleted':
          // ลบ task
          setTranscriptions(prev => 
            prev.filter(t => t.task_id !== data.task_id)
          );
          break;
      }
    };

    setWs(websocket);

    return () => {
      websocket.close();
    };
  }, []);

  return (
    <div>
      <h1>รายการ Transcription</h1>
      <table>
        <thead>
          <tr>
            <th>Task ID</th>
            <th>Filename</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Created At</th>
          </tr>
        </thead>
        <tbody>
          {transcriptions.map(task => (
            <tr key={task.task_id}>
              <td>{task.task_id}</td>
              <td>{task.file_name}</td>
              <td>{task.status}</td>
              <td>{task.progress}%</td>
              <td>{task.created_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### Vue.js Example

```vue
<template>
  <div>
    <h1>รายการ Transcription</h1>
    <table>
      <thead>
        <tr>
          <th>Task ID</th>
          <th>Filename</th>
          <th>Status</th>
          <th>Progress</th>
          <th>Created At</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="task in transcriptions" :key="task.task_id">
          <td>{{ task.task_id }}</td>
          <td>{{ task.file_name }}</td>
          <td>{{ task.status }}</td>
          <td>{{ task.progress }}%</td>
          <td>{{ task.created_at }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
export default {
  data() {
    return {
      transcriptions: [],
      ws: null
    };
  },
  mounted() {
    // โหลดข้อมูลเริ่มต้น
    fetch('/api/history/transcriptions?limit=50')
      .then(res => res.json())
      .then(data => {
        this.transcriptions = data.history;
      });

    // เชื่อมต่อ WebSocket
    this.ws = new WebSocket('ws://localhost:8001/api/history/ws/realtime');
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch(data.type) {
        case 'task.created':
          this.transcriptions.unshift(data.task_data);
          break;
        case 'task.updated':
        case 'task.completed':
        case 'task.failed':
          const index = this.transcriptions.findIndex(t => t.task_id === data.task_id);
          if (index !== -1) {
            this.$set(this.transcriptions, index, { ...this.transcriptions[index], ...data.task_data });
          }
          break;
        case 'task.deleted':
          this.transcriptions = this.transcriptions.filter(t => t.task_id !== data.task_id);
          break;
      }
    };
  },
  beforeDestroy() {
    if (this.ws) {
      this.ws.close();
    }
  }
};
</script>
```

### Vanilla JavaScript Example

```html
<!DOCTYPE html>
<html>
<head>
  <title>Transcription List - Realtime</title>
</head>
<body>
  <h1>รายการ Transcription</h1>
  <div id="status">กำลังเชื่อมต่อ...</div>
  <table id="transcriptionTable">
    <thead>
      <tr>
        <th>Task ID</th>
        <th>Filename</th>
        <th>Status</th>
        <th>Progress</th>
        <th>Created At</th>
      </tr>
    </thead>
    <tbody id="transcriptionBody">
    </tbody>
  </table>

  <script>
    const API_BASE = 'http://localhost:8001';
    const WS_BASE = 'ws://localhost:8001';
    
    let transcriptions = [];
    let ws = null;

    // โหลดข้อมูลเริ่มต้น
    async function loadTranscriptions() {
      try {
        const response = await fetch(`${API_BASE}/api/history/transcriptions?limit=50`);
        const data = await response.json();
        transcriptions = data.history;
        renderTable();
      } catch (error) {
        console.error('Error loading transcriptions:', error);
      }
    }

    // Render ตาราง
    function renderTable() {
      const tbody = document.getElementById('transcriptionBody');
      tbody.innerHTML = transcriptions.map(task => `
        <tr>
          <td>${task.task_id}</td>
          <td>${task.file_name || 'N/A'}</td>
          <td>${task.status}</td>
          <td>${task.progress}%</td>
          <td>${task.created_at}</td>
        </tr>
      `).join('');
    }

    // เชื่อมต่อ WebSocket
    function connectWebSocket() {
      ws = new WebSocket(`${WS_BASE}/api/history/ws/realtime`);
      
      ws.onopen = () => {
        document.getElementById('status').textContent = '✅ เชื่อมต่อสำเร็จ';
        document.getElementById('status').style.color = 'green';
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('📨 Received:', data);
        
        switch(data.type) {
          case 'task.created':
            transcriptions.unshift(data.task_data);
            renderTable();
            break;
          case 'task.updated':
          case 'task.completed':
          case 'task.failed':
            const index = transcriptions.findIndex(t => t.task_id === data.task_id);
            if (index !== -1) {
              transcriptions[index] = { ...transcriptions[index], ...data.task_data };
              renderTable();
            }
            break;
          case 'task.deleted':
            transcriptions = transcriptions.filter(t => t.task_id !== data.task_id);
            renderTable();
            break;
        }
      };
      
      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        document.getElementById('status').textContent = '❌ เกิดข้อผิดพลาด';
        document.getElementById('status').style.color = 'red';
      };
      
      ws.onclose = () => {
        document.getElementById('status').textContent = '🔴 ตัดการเชื่อมต่อ';
        document.getElementById('status').style.color = 'orange';
        // Reconnect after 5 seconds
        setTimeout(connectWebSocket, 5000);
      };
    }

    // เริ่มต้น
    loadTranscriptions();
    connectWebSocket();
  </script>
</body>
</html>
```

---

## 📊 ข้อมูลที่เก็บใน SQLite

ข้อมูลทั้งหมดเก็บไว้ใน SQLite database ที่ `storage/database.db`

**Table: `transcriptions`**
- `task_id`: Task ID (Primary Key)
- `status`: สถานะ (pending, processing, completed, failed)
- `progress`: ความคืบหน้า (0-100)
- `file_name`: ชื่อไฟล์
- `file_path`: path ของไฟล์
- `created_at`: วันที่สร้าง
- `updated_at`: วันที่อัปเดตล่าสุด
- `completed_at`: วันที่เสร็จสมบูรณ์
- และอื่นๆ...

---

## 🔧 การตั้งค่า

### Environment Variables

```bash
# ใช้ SQLite เป็น storage หลัก
STORAGE_TYPE=sqlite

# Path ของ SQLite database
SQLITE_DB_PATH=storage/database.db

# Redis URL สำหรับ WebSocket scaling (optional)
REDIS_URL=redis://localhost:6379
```

---

## 📝 หมายเหตุ

1. **WebSocket Reconnection**: Frontend ควรมี logic สำหรับ reconnect เมื่อ connection หลุด
2. **Rate Limiting**: ควรจำกัดจำนวน requests ต่อ API endpoint
3. **Error Handling**: ควรจัดการ error cases ทั้งหมด
4. **Pagination**: สำหรับรายการที่มีจำนวนมาก ควรใช้ pagination

---

## 🆘 Troubleshooting

### WebSocket ไม่เชื่อมต่อ
- ตรวจสอบว่า server รันอยู่และ port ถูกต้อง
- ตรวจสอบ CORS settings
- ตรวจสอบ firewall/proxy settings

### ไม่ได้รับ realtime updates
- ตรวจสอบว่า WebSocket connection สำเร็จ
- ตรวจสอบ console logs สำหรับ errors
- ตรวจสอบว่า task ถูกบันทึกใน SQLite

### ข้อมูลไม่ตรงกัน
- ตรวจสอบว่าใช้ SQLite storage (`STORAGE_TYPE=sqlite`)
- ตรวจสอบว่า database path ถูกต้อง
- ลอง refresh ข้อมูลจาก API endpoint

