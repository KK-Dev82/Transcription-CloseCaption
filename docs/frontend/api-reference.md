# 🚀 Complete API Reference (2025)

## 📋 **API Endpoints ทั้งหมด**

### 🎯 **Core Transcription APIs**

#### **Upload & Start Processing**
```typescript
// 1. Upload file
POST /upload/
Content-Type: multipart/form-data
Body: FormData with 'file' field

Response: {
  file_id: string;
  filename: string;
  file_path: string;
  file_size: number;
  file_type: string;
  upload_time: string;
}

// 2. Start transcription
POST /transcribe-enhanced/start
Content-Type: application/json
Body: {
  file_path: string;
  language?: string; // default: "th"
  model_size?: string; // default: "base"
}

Response: {
  task_id: string;
  message: string;
  strategy: string;
  estimated_time: string;
}
```

#### **Check Results**
```typescript
// Get full results
GET /transcribe-enhanced/status/{task_id}

Response: {
  task_id: string;
  status: "processing" | "completed" | "failed";
  progress: number; // 0-100
  created_at: string;
  updated_at: string;
  completed_at?: string;
  filename?: string;
  full_text?: string;
  chunks?: Array<{
    chunk_id: number;
    start_time: number;
    end_time: number;
    text: string;
    confidence?: number;
  }>;
  error_message?: string;
}
```

### 🔄 **Polling APIs (NEW - Fallback สำหรับ WebSocket)**

```typescript
// Check single task status
GET /polling/task/{task_id}

Response: {
  task_id: string;
  status: string;
  progress: number;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  error_message?: string;
  stage: string;
  results_available: boolean;
}

// Get active tasks
GET /polling/tasks/active

Response: {
  active_tasks: Array<{
    task_id: string;
    status: string;
    progress: number;
    created_at: string;
    stage: string;
  }>;
  count: number;
  timestamp: string;
}

// Get recent tasks
GET /polling/tasks/recent?limit=10

Response: {
  recent_tasks: Array<{
    task_id: string;
    filename: string;
    status: string;
    progress: number;
    created_at: string;
    updated_at: string;
    completed_at?: string;
    duration?: number;
    chunks_count: number;
    results_available: boolean;
  }>;
  count: number;
  timestamp: string;
}
```

### 📚 **History APIs (NEW)**

```typescript
// Get transcription history with filters
GET /history/transcriptions?limit=20&offset=0&status=completed&days_ago=7

Response: {
  history: Array<{
    task_id: string;
    filename: string;
    status: string;
    progress: number;
    created_at: string;
    updated_at: string;
    completed_at?: string;
    duration?: number;
    file_size?: number;
    language: string;
    model_used: string;
    chunks_count: number;
    word_count: number;
    error_message?: string;
    has_results: boolean;
  }>;
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
  filters_applied: {
    status?: string;
    days_ago?: number;
  };
  timestamp: string;
}

// Get detailed transcription info
GET /history/transcriptions/{task_id}

Response: {
  task_id: string;
  basic_info: {
    filename: string;
    status: string;
    progress: number;
    language: string;
    model_size: string;
  };
  timestamps: {
    created_at: string;
    updated_at: string;
    completed_at?: string;
    processing_duration?: string;
  };
  file_info: {
    file_path: string;
    file_size?: number;
    total_duration?: number;
  };
  results: {
    full_text?: string;
    chunks_count: number;
    word_count: number;
    chunks: Array<TranscriptionChunk>;
  };
  error_info: {
    error_message?: string;
    has_error: boolean;
  };
}

// Get statistics
GET /history/stats

Response: {
  total_transcriptions: number;
  status_breakdown: {
    completed: number;
    failed: number;
    processing: number;
  };
  time_periods: {
    today: number;
    this_week: number;
    this_month: number;
  };
  totals: {
    total_audio_duration_seconds: number;
    total_words_transcribed: number;
    average_words_per_transcription: number;
  };
  timestamp: string;
}

// Delete transcription
DELETE /history/transcriptions/{task_id}

Response: {
  status: "success";
  message: string;
  timestamp: string;
}
```

### 📡 **WebSocket Status APIs (NEW)**

```typescript
// Check WebSocket service status
GET /websocket/status

Response: {
  service_status: "active" | "error";
  total_connections: number;
  active_users: number;
  total_subscriptions: number;
  redis_connected: boolean;
  last_activity?: string;
  timestamp: string;
  healthy: boolean;
  error?: string;
}

// Get active connections
GET /websocket/connections

Response: {
  active_connections: Array<{
    user_id: string;
    connected_at: string;
    subscribed_tasks: number;
  }>;
  total_connections: number;
  timestamp: string;
}

// Get user subscriptions
GET /websocket/subscriptions/{user_id}

Response: {
  user_id: string;
  subscriptions: string[];
  subscription_count: number;
  connected: boolean;
  timestamp: string;
}

// Test WebSocket broadcast
POST /websocket/test-broadcast?task_id=test-task&message=Test%20message

Response: {
  status: "success";
  broadcasted_to: string;
  message: {
    type: "test";
    task_id: string;
    message: string;
    timestamp: string;
  };
  timestamp: string;
}

// WebSocket diagnostics
GET /websocket/diagnostics

Response: {
  websocket_manager: {
    initialized: boolean;
    redis_available: boolean;
    stats: object;
  };
  system: {
    timestamp: string;
    service_healthy: boolean;
  };
  connections?: {
    total_users: number;
    user_list: string[];
  };
  subscriptions?: {
    total_subscriptions: number;
    users_with_subscriptions: number;
  };
}
```

### 🔄 **Progress APIs (เดิม)**

```typescript
// Get current progress
GET /progress/transcription/{task_id}

// Get all active tasks
GET /progress/all-active

// Get system stats
GET /progress/stats
```

### 🎯 **WebSocket Real-time Updates**

```typescript
// WebSocket connection
ws://localhost:8001/ws/transcription/{user_id}

// Message types received:
interface WebSocketMessage {
  type: 'transcription.started' | 'transcription.progress' | 'transcription.completed' | 'transcription.failed' | 'ping' | 'subscription';
  task_id?: string;
  timestamp: string;
  progress?: number;
  stage?: string;
  status?: string;
  results_summary?: {
    full_text?: string;
    chunks_count?: number;
    duration?: number;
  };
  error?: string;
}

// Messages to send:
// Subscribe to task
{
  type: 'subscribe',
  task_id: string
}

// Pong response
{
  type: 'pong',
  timestamp: string
}
```

## 🛠️ **Usage Examples**

### **Basic Transcription Flow**
```typescript
// 1. Upload
const formData = new FormData();
formData.append('file', fileInput.files[0]);
const uploadResult = await fetch('/upload/', {
  method: 'POST',
  body: formData
});

// 2. Start transcription
const startResult = await fetch('/transcribe-enhanced/start', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    file_path: uploadResult.file_path,
    language: 'th'
  })
});

// 3. Monitor progress (choose one):

// Option A: WebSocket (recommended)
const ws = new WebSocket(`ws://localhost:8001/ws/transcription/${userId}`);
ws.send(JSON.stringify({ type: 'subscribe', task_id: startResult.task_id }));

// Option B: Polling (fallback)
const pollProgress = async () => {
  const progress = await fetch(`/polling/task/${startResult.task_id}`);
  return progress.json();
};
```

### **Error Handling**
```typescript
// Check WebSocket health first
const wsHealth = await fetch('/websocket/status');
if (!wsHealth.healthy) {
  // Use polling instead
  console.log('WebSocket unhealthy, using polling fallback');
}
```

## 📋 **Status Codes**

- `processing` - กำลังประมวลผล
- `completed` - เสร็จสิ้น
- `failed` - ล้มเหลว
- `queued` - รอคิว
- `started` - เริ่มแล้ว

## 🔐 **Error Responses**

```typescript
// Standard error format
{
  detail: string;
  status_code?: number;
  timestamp?: string;
}
```
