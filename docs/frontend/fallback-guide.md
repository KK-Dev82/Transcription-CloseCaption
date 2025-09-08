# 🛡️ Fallback Strategies Guide

## 🎯 **Overview**

การจัดการ fallback mechanisms เมื่อ WebSocket ไม่ทำงาน เพื่อให้ระบบทำงานได้ในทุกสถานการณ์

## 🔄 **Fallback Strategy**

### **1. Connection Health Check**
```typescript
const checkWebSocketHealth = async (): Promise<boolean> => {
  try {
    const response = await fetch('/websocket/status');
    const data = await response.json();
    return data.healthy && data.service_status === 'active';
  } catch {
    return false;
  }
};
```

### **2. Automatic Fallback Decision**
```typescript
const initializeConnection = async () => {
  const isWebSocketHealthy = await checkWebSocketHealth();
  
  if (isWebSocketHealthy) {
    console.log('✅ Using WebSocket for real-time updates');
    connectWebSocket();
  } else {
    console.log('⚠️ WebSocket unhealthy, using Polling fallback');
    startPolling();
  }
};
```

### **3. Progressive Fallback Levels**

#### **Level 1: WebSocket (Primary)**
- Real-time updates
- Instant notifications
- Low latency

```typescript
const useWebSocketConnection = (userId: string) => {
  const ws = new WebSocket(`ws://localhost:8001/ws/transcription/${userId}`);
  
  ws.onopen = () => {
    console.log('🟢 WebSocket connected - Level 1 active');
    setConnectionLevel(1);
  };
  
  ws.onclose = () => {
    console.log('🔴 WebSocket closed - Falling back to Level 2');
    fallbackToPolling();
  };
};
```

#### **Level 2: Polling (Fallback)**
- Regular status checks
- 2-3 second intervals
- Reliable but higher latency

```typescript
const startPolling = (taskId: string) => {
  console.log('🔄 Polling mode active - Level 2');
  setConnectionLevel(2);
  
  const pollInterval = setInterval(async () => {
    try {
      const response = await fetch(`/polling/task/${taskId}`);
      const data = await response.json();
      updateTaskStatus(data);
    } catch (error) {
      console.error('❌ Polling failed - Falling back to Level 3');
      fallbackToManualRefresh();
    }
  }, 3000);
  
  return pollInterval;
};
```

#### **Level 3: Manual Refresh (Last Resort)**
- User-triggered updates
- Button-based refresh
- Minimal functionality

```typescript
const useManualRefresh = () => {
  console.log('🔄 Manual refresh mode - Level 3');
  setConnectionLevel(3);
  
  const refreshStatus = async (taskId: string) => {
    try {
      const response = await fetch(`/transcribe-enhanced/status/${taskId}`);
      const data = await response.json();
      updateTaskStatus(data);
    } catch (error) {
      showError('Unable to refresh status');
    }
  };
  
  return { refreshStatus };
};
```

## 🔧 **Implementation Example**

### **Complete Fallback Hook**
```typescript
export const useTranscriptionWithFallback = (userId: string) => {
  const [connectionLevel, setConnectionLevel] = useState<1 | 2 | 3>(1);
  const [currentTask, setCurrentTask] = useState<TranscriptionTask | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  
  // Level 1: WebSocket
  const connectWebSocket = useCallback(() => {
    const ws = new WebSocket(`ws://localhost:8001/ws/transcription/${userId}`);
    
    ws.onopen = () => {
      setConnectionLevel(1);
      console.log('🟢 Real-time connection established');
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setCurrentTask(data);
      setLastUpdate(new Date());
    };
    
    ws.onclose = () => {
      console.log('🔄 WebSocket closed, switching to polling');
      startPolling();
    };
    
    return ws;
  }, [userId]);
  
  // Level 2: Polling
  const startPolling = useCallback(() => {
    setConnectionLevel(2);
    
    const interval = setInterval(async () => {
      try {
        if (currentTask?.task_id) {
          const response = await fetch(`/polling/task/${currentTask.task_id}`);
          const data = await response.json();
          setCurrentTask(data);
          setLastUpdate(new Date());
        }
      } catch (error) {
        console.error('❌ Polling failed, switching to manual mode');
        setConnectionLevel(3);
        clearInterval(interval);
      }
    }, 3000);
    
    return interval;
  }, [currentTask?.task_id]);
  
  // Level 3: Manual refresh
  const manualRefresh = useCallback(async () => {
    if (!currentTask?.task_id) return;
    
    try {
      const response = await fetch(`/transcribe-enhanced/status/${currentTask.task_id}`);
      const data = await response.json();
      setCurrentTask(data);
      setLastUpdate(new Date());
    } catch (error) {
      console.error('❌ Manual refresh failed');
    }
  }, [currentTask?.task_id]);
  
  return {
    connectionLevel,
    currentTask,
    lastUpdate,
    manualRefresh
  };
};
```

### **UI Component with Fallback Indicators**
```tsx
const TranscriptionStatus: React.FC = () => {
  const { connectionLevel, currentTask, lastUpdate, manualRefresh } = useTranscriptionWithFallback(userId);
  
  const getConnectionIndicator = () => {
    switch (connectionLevel) {
      case 1:
        return <span className="text-green-500">🟢 Real-time</span>;
      case 2:
        return <span className="text-yellow-500">🟡 Polling</span>;
      case 3:
        return <span className="text-red-500">🔴 Manual</span>;
      default:
        return <span className="text-gray-500">❓ Unknown</span>;
    }
  };
  
  return (
    <div className="transcription-status">
      <div className="connection-info">
        <p>Connection: {getConnectionIndicator()}</p>
        {lastUpdate && (
          <p className="text-sm text-gray-600">
            Last update: {lastUpdate.toLocaleTimeString()}
          </p>
        )}
      </div>
      
      {currentTask && (
        <div className="task-progress">
          <h3>Task: {currentTask.task_id.slice(0, 8)}</h3>
          <p>Status: {currentTask.status}</p>
          <p>Progress: {currentTask.progress}%</p>
          
          {/* Manual refresh button for Level 3 */}
          {connectionLevel === 3 && (
            <button 
              onClick={manualRefresh}
              className="bg-blue-500 text-white px-4 py-2 rounded"
            >
              🔄 Refresh Status
            </button>
          )}
        </div>
      )}
      
      {/* Connection quality warning */}
      {connectionLevel > 1 && (
        <div className="bg-yellow-100 border-l-4 border-yellow-500 p-4 mt-4">
          <p className="text-yellow-700">
            {connectionLevel === 2 
              ? '⚠️ Using polling mode - updates may be delayed'
              : '🚨 Connection issues - manual refresh required'
            }
          </p>
        </div>
      )}
    </div>
  );
};
```

## 📊 **Monitoring & Recovery**

### **Connection Health Monitoring**
```typescript
const useConnectionMonitoring = () => {
  const [connectionHealth, setConnectionHealth] = useState({
    websocket: false,
    api: false,
    lastCheck: null as Date | null
  });
  
  const checkHealth = async () => {
    try {
      // Check WebSocket
      const wsResponse = await fetch('/websocket/status');
      const wsData = await wsResponse.json();
      
      // Check API
      const apiResponse = await fetch('/health');
      
      setConnectionHealth({
        websocket: wsData.healthy,
        api: apiResponse.ok,
        lastCheck: new Date()
      });
    } catch (error) {
      setConnectionHealth(prev => ({
        ...prev,
        websocket: false,
        api: false,
        lastCheck: new Date()
      }));
    }
  };
  
  // Check every 30 seconds
  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);
  
  return connectionHealth;
};
```

### **Smart Recovery Logic**
```typescript
const useSmartRecovery = () => {
  const [recoveryAttempts, setRecoveryAttempts] = useState(0);
  const maxAttempts = 3;
  
  const attemptRecovery = async () => {
    if (recoveryAttempts >= maxAttempts) {
      console.log('❌ Max recovery attempts reached');
      return false;
    }
    
    setRecoveryAttempts(prev => prev + 1);
    
    // Wait with exponential backoff
    const delay = Math.min(1000 * Math.pow(2, recoveryAttempts), 10000);
    await new Promise(resolve => setTimeout(resolve, delay));
    
    // Try to reconnect
    try {
      const health = await fetch('/websocket/status');
      if (health.ok) {
        console.log('✅ Recovery successful');
        setRecoveryAttempts(0);
        return true;
      }
    } catch (error) {
      console.log(`❌ Recovery attempt ${recoveryAttempts + 1} failed`);
    }
    
    return false;
  };
  
  return { attemptRecovery, recoveryAttempts };
};
```

## 🎯 **Best Practices**

### **1. User Experience**
- แสดง connection status ให้ user เห็น
- ให้ manual refresh option เสมอ
- แจ้งเตือนเมื่อ connection มีปัญหา

### **2. Performance**
- ใช้ polling interval ที่เหมาะสม (2-5 วินาที)
- หยุด polling เมื่อไม่มี active tasks
- Implement exponential backoff สำหรับ retry

### **3. Error Handling**
- Log errors สำหรับ debugging
- แสดง error messages ที่เข้าใจง่าย
- Provide recovery options

### **4. Testing**
```typescript
// Test fallback scenarios
describe('Fallback Strategies', () => {
  test('should fallback to polling when WebSocket fails', async () => {
    // Mock WebSocket failure
    // Verify polling starts
  });
  
  test('should fallback to manual when polling fails', async () => {
    // Mock polling failure
    // Verify manual mode activates
  });
});
```

## 📱 **Mobile Considerations**

- Network changes (WiFi ↔ Mobile data)
- App backgrounding/foregrounding
- Battery optimization

```typescript
// Handle network changes
window.addEventListener('online', () => {
  console.log('🟢 Network restored, attempting reconnection');
  attemptRecovery();
});

window.addEventListener('offline', () => {
  console.log('🔴 Network lost, switching to offline mode');
  setConnectionLevel(3);
});
```
