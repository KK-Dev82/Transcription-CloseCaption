# 🎣 Production-Ready React Hooks

## 📋 **Available Hooks:**

### **1. `useTranscription.ts` - Main Hook**
- ✅ WebSocket with automatic fallback to Polling  
- ✅ Error handling และ retry logic
- ✅ Real-time progress updates
- ✅ Connection health monitoring

```typescript
import { useTranscription } from './useTranscription';

const MyComponent = () => {
  const {
    currentTask,
    tasks,
    isConnected,
    connectionType, // 'websocket' | 'polling' | 'disconnected'
    error,
    startTranscription,
    subscribeToTask,
    getTaskStatus,
    refreshTasks,
    reconnect,
    disconnect
  } = useTranscription({
    userId: 'user_123',
    apiBaseUrl: 'http://localhost:8001',
    enableWebSocket: true,
    pollingInterval: 3000,
    maxRetries: 5
  });

  // ใช้งาน...
};
```

## 🎯 **Usage Examples:**

### **Basic Transcription Flow**
```typescript
const handleFileUpload = async (file: File) => {
  try {
    // 1. Upload file
    const formData = new FormData();
    formData.append('file', file);
    const uploadResponse = await fetch('/upload/', {
      method: 'POST',
      body: formData
    });
    const uploadResult = await uploadResponse.json();

    // 2. Start transcription (hook จะ auto-subscribe)
    const taskId = await startTranscription(uploadResult.file_path, {
      language: 'th',
      model_size: 'base'
    });

    console.log('Transcription started:', taskId);
  } catch (error) {
    console.error('Upload failed:', error);
  }
};
```

### **Monitor Connection Status**
```typescript
const ConnectionStatus = () => {
  const { isConnected, connectionType, error } = useTranscription(options);

  return (
    <div className="connection-status">
      <div className={`status ${isConnected ? 'connected' : 'disconnected'}`}>
        {isConnected ? '🟢' : '🔴'} 
        {connectionType === 'websocket' && 'Real-time'}
        {connectionType === 'polling' && 'Polling Mode'}
        {connectionType === 'disconnected' && 'Disconnected'}
      </div>
      {error && <div className="error">⚠️ {error}</div>}
    </div>
  );
};
```

### **Task Progress Display**
```typescript
const TaskProgress = () => {
  const { currentTask } = useTranscription(options);

  if (!currentTask) return <div>No active task</div>;

  return (
    <div className="task-progress">
      <h3>Task: {currentTask.task_id.slice(0, 8)}</h3>
      <div className="progress-bar">
        <div 
          className="progress-fill" 
          style={{ width: `${currentTask.progress}%` }}
        />
      </div>
      <p>Status: {currentTask.status}</p>
      <p>Stage: {currentTask.stage}</p>
      {currentTask.error_message && (
        <p className="error">Error: {currentTask.error_message}</p>
      )}
    </div>
  );
};
```

## 🔧 **Advanced Usage:**

### **Manual Task Management**
```typescript
const ManualTaskControl = () => {
  const { getTaskStatus, subscribeToTask, refreshTasks } = useTranscription(options);

  const checkSpecificTask = async (taskId: string) => {
    const task = await getTaskStatus(taskId);
    console.log('Task status:', task);
  };

  const subscribeToExistingTask = (taskId: string) => {
    subscribeToTask(taskId);
  };

  const refreshTaskList = async () => {
    await refreshTasks();
  };

  return (
    <div>
      <button onClick={() => checkSpecificTask('task-id')}>
        Check Task Status
      </button>
      <button onClick={() => subscribeToExistingTask('task-id')}>
        Subscribe to Task
      </button>
      <button onClick={refreshTaskList}>
        Refresh Task List
      </button>
    </div>
  );
};
```

### **Connection Management**
```typescript
const ConnectionControl = () => {
  const { reconnect, disconnect, connectionType } = useTranscription(options);

  return (
    <div>
      <button onClick={reconnect}>
        🔄 Reconnect
      </button>
      <button onClick={disconnect}>
        ❌ Disconnect
      </button>
      <p>Current: {connectionType}</p>
    </div>
  );
};
```

## 📊 **Hook Features:**

### **✅ Auto-Fallback System:**
1. **WebSocket** (Primary) - Real-time updates
2. **Polling** (Fallback) - Regular status checks  
3. **Manual** (Last resort) - User-triggered updates

### **✅ Error Handling:**
- Network errors with retry
- API errors with proper messages
- WebSocket connection issues
- File upload validation

### **✅ State Management:**
- Current active task
- Task history list
- Connection status
- Error states

### **✅ Performance:**
- Automatic cleanup on unmount
- Efficient re-renders
- Memory leak prevention
- Optimized polling intervals

## 🧪 **Testing:**

```typescript
import { renderHook, act } from '@testing-library/react-hooks';
import { useTranscription } from './useTranscription';

describe('useTranscription', () => {
  test('should connect and start transcription', async () => {
    const { result } = renderHook(() => useTranscription({
      userId: 'test-user',
      apiBaseUrl: 'http://localhost:8001'
    }));

    await act(async () => {
      const taskId = await result.current.startTranscription('/path/to/file');
      expect(taskId).toBeDefined();
    });
  });
});
```

## 🔐 **TypeScript Support:**

Hook มี TypeScript types ครบถ้วน:

```typescript
interface TranscriptionTask {
  task_id: string;
  status: 'processing' | 'completed' | 'failed' | 'queued' | 'started';
  progress: number;
  stage: string;
  // ... more fields
}

interface UseTranscriptionOptions {
  userId: string;
  apiBaseUrl?: string;
  enableWebSocket?: boolean;
  pollingInterval?: number;
  maxRetries?: number;
}
```
