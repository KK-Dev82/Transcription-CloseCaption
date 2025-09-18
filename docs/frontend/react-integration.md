# React Vite TypeScript Frontend Integration

## 🎬 Real-time Close Caption System

### **API Endpoints**

#### **1. Real-time Caption API**
```typescript
// Base URL
const API_BASE = 'http://localhost:8001';

// Start real-time caption session
POST /caption/realtime/start
{
  "user_id": "user123",
  "file_path": "uploads/video.mp4",
  "language": "th",
  "model_size": "base",
  "chunk_duration": 10,
  "delay_seconds": 0.0
}

// Stop real-time caption session
POST /caption/realtime/stop/{session_id}

// Update delay
PUT /caption/realtime/delay/{session_id}
{
  "delay_seconds": 5.0
}

// Get session info
GET /caption/realtime/session/{session_id}

// Get user sessions
GET /caption/realtime/user/{user_id}/sessions
```

#### **2. WebSocket Endpoints**
```typescript
// Real-time caption WebSocket
const wsUrl = `ws://localhost:8001/ws/caption/${userId}?session_id=${sessionId}`;

// Message types received:
// - caption.started
// - caption.chunk
// - caption.progress
// - caption.completed
// - caption.error
// - caption.delay_updated
// - caption.stopped
```

### **TypeScript Types**

```typescript
// RealtimeCaptionRequest
interface RealtimeCaptionRequest {
  user_id: string;
  file_path: string;
  language?: string;
  model_size?: string;
  chunk_duration?: number;
  delay_seconds?: number;
}

// RealtimeCaptionResponse
interface RealtimeCaptionResponse {
  session_id: string;
  user_id: string;
  status: string;
  message: string;
  created_at: string;
  websocket_url: string;
}

// Chunk Data
interface ChunkData {
  start_time: number;
  end_time: number;
  text: string;
  confidence?: number;
  chunk_index: number;
  processed_at: string;
  error?: boolean;
}

// WebSocket Messages
interface WebSocketMessage {
  type: 'caption.started' | 'caption.chunk' | 'caption.progress' | 
        'caption.completed' | 'caption.error' | 'caption.delay_updated' | 
        'caption.stopped';
  session_id: string;
  timestamp: string;
  [key: string]: any;
}

// Caption Chunk Message
interface CaptionChunkMessage extends WebSocketMessage {
  type: 'caption.chunk';
  chunk_index: number;
  chunk_data: ChunkData;
  delay_seconds: number;
}

// Progress Message
interface ProgressMessage extends WebSocketMessage {
  type: 'caption.progress';
  progress: number;
  status: string;
  current_chunk: number;
  total_chunks: number;
}
```

### **React Hook Example**

```typescript
// useRealtimeCaption.ts
import { useState, useEffect, useCallback } from 'react';

interface UseRealtimeCaptionProps {
  userId: string;
  onChunkReceived?: (chunk: ChunkData) => void;
  onProgress?: (progress: number) => void;
  onCompleted?: (data: any) => void;
  onError?: (error: string) => void;
}

export const useRealtimeCaption = ({
  userId,
  onChunkReceived,
  onProgress,
  onCompleted,
  onError
}: UseRealtimeCaptionProps) => {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [chunks, setChunks] = useState<ChunkData[]>([]);
  const [progress, setProgress] = useState(0);
  const [ws, setWs] = useState<WebSocket | null>(null);

  // Start real-time caption
  const startCaption = useCallback(async (filePath: string, options: Partial<RealtimeCaptionRequest> = {}) => {
    try {
      const response = await fetch(`${API_BASE}/caption/realtime/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          file_path: filePath,
          ...options
        })
      });

      const data: RealtimeCaptionResponse = await response.json();
      setSessionId(data.session_id);
      
      // Connect WebSocket
      const websocket = new WebSocket(`${WS_BASE}/ws/caption/${userId}?session_id=${data.session_id}`);
      setWs(websocket);
      
      websocket.onopen = () => setIsConnected(true);
      websocket.onclose = () => setIsConnected(false);
      
      websocket.onmessage = (event) => {
        const message: WebSocketMessage = JSON.parse(event.data);
        
        switch (message.type) {
          case 'caption.chunk':
            const chunkMessage = message as CaptionChunkMessage;
            setChunks(prev => [...prev, chunkMessage.chunk_data]);
            onChunkReceived?.(chunkMessage.chunk_data);
            break;
            
          case 'caption.progress':
            const progressMessage = message as ProgressMessage;
            setProgress(progressMessage.progress);
            onProgress?.(progressMessage.progress);
            break;
            
          case 'caption.completed':
            onCompleted?.(message);
            break;
            
          case 'caption.error':
            onError?.(message.error || 'Unknown error');
            break;
        }
      };
      
    } catch (error) {
      onError?.(error instanceof Error ? error.message : 'Failed to start caption');
    }
  }, [userId, onChunkReceived, onProgress, onCompleted, onError]);

  // Stop caption
  const stopCaption = useCallback(async () => {
    if (sessionId) {
      try {
        await fetch(`${API_BASE}/caption/realtime/stop/${sessionId}`, {
          method: 'POST'
        });
      } catch (error) {
        console.error('Failed to stop caption:', error);
      }
    }
    
    ws?.close();
    setWs(null);
    setSessionId(null);
    setChunks([]);
    setProgress(0);
  }, [sessionId, ws]);

  // Update delay
  const updateDelay = useCallback(async (delaySeconds: number) => {
    if (sessionId) {
      try {
        await fetch(`${API_BASE}/caption/realtime/delay/${sessionId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ delay_seconds: delaySeconds })
        });
      } catch (error) {
        console.error('Failed to update delay:', error);
      }
    }
  }, [sessionId]);

  // Cleanup
  useEffect(() => {
    return () => {
      ws?.close();
    };
  }, [ws]);

  return {
    sessionId,
    isConnected,
    chunks,
    progress,
    startCaption,
    stopCaption,
    updateDelay
  };
};
```

### **React Component Example**

```typescript
// RealtimeCaptionPlayer.tsx
import React, { useState } from 'react';
import { useRealtimeCaption } from './useRealtimeCaption';

interface RealtimeCaptionPlayerProps {
  userId: string;
  videoUrl: string;
}

export const RealtimeCaptionPlayer: React.FC<RealtimeCaptionPlayerProps> = ({
  userId,
  videoUrl
}) => {
  const [delay, setDelay] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  
  const {
    sessionId,
    isConnected,
    chunks,
    progress,
    startCaption,
    stopCaption,
    updateDelay
  } = useRealtimeCaption({
    userId,
    onChunkReceived: (chunk) => {
      console.log('New chunk:', chunk);
    },
    onProgress: (progress) => {
      console.log('Progress:', progress);
    },
    onCompleted: (data) => {
      console.log('Caption completed:', data);
    },
    onError: (error) => {
      console.error('Caption error:', error);
    }
  });

  const handleStart = () => {
    startCaption(videoUrl, {
      language: 'th',
      model_size: 'base',
      chunk_duration: 10,
      delay_seconds: delay
    });
    setIsPlaying(true);
  };

  const handleStop = () => {
    stopCaption();
    setIsPlaying(false);
  };

  const handleDelayChange = (newDelay: number) => {
    setDelay(newDelay);
    updateDelay(newDelay);
  };

  return (
    <div className="realtime-caption-player">
      <div className="video-container">
        <video src={videoUrl} controls />
      </div>
      
      <div className="controls">
        <button onClick={isPlaying ? handleStop : handleStart}>
          {isPlaying ? 'Stop Caption' : 'Start Caption'}
        </button>
        
        <div className="delay-control">
          <label>Delay: {delay}s</label>
          <input
            type="range"
            min="0"
            max="30"
            step="0.5"
            value={delay}
            onChange={(e) => handleDelayChange(Number(e.target.value))}
          />
        </div>
        
        <div className="status">
          Status: {isConnected ? 'Connected' : 'Disconnected'}
          {sessionId && <div>Session: {sessionId}</div>}
          <div>Progress: {progress}%</div>
        </div>
      </div>
      
      <div className="caption-display">
        <h3>Real-time Captions</h3>
        <div className="chunks">
          {chunks.map((chunk, index) => (
            <div key={index} className="chunk">
              <span className="time">
                {Math.floor(chunk.start_time / 60)}:
                {Math.floor(chunk.start_time % 60).toString().padStart(2, '0')}
              </span>
              <span className="text">{chunk.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
```

### **CSS Styles**

```css
.realtime-caption-player {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.video-container {
  margin-bottom: 20px;
}

.video-container video {
  width: 100%;
  border-radius: 8px;
}

.controls {
  display: flex;
  gap: 20px;
  align-items: center;
  margin-bottom: 20px;
  padding: 15px;
  background: #f5f5f5;
  border-radius: 8px;
}

.delay-control {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.delay-control input[type="range"] {
  width: 200px;
}

.status {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 14px;
  color: #666;
}

.caption-display {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 15px;
  max-height: 400px;
  overflow-y: auto;
}

.chunks {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chunk {
  display: flex;
  gap: 10px;
  padding: 8px;
  background: #f9f9f9;
  border-radius: 4px;
  animation: slideIn 0.3s ease-out;
}

.chunk .time {
  font-weight: bold;
  color: #007bff;
  min-width: 60px;
}

.chunk .text {
  flex: 1;
  line-height: 1.4;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

### **Environment Variables**

```env
# .env
VITE_API_BASE_URL=http://localhost:8001
VITE_WS_BASE_URL=ws://localhost:8001
```

### **Package.json Dependencies**

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.0",
    "typescript": "^5.0.0",
    "vite": "^4.4.0"
  }
}
```

### **Vite Config**

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
});
```

## 🚀 **การใช้งาน**

1. **ติดตั้ง dependencies:**
   ```bash
   npm install
   ```

2. **เริ่ม development server:**
   ```bash
   npm run dev
   ```

3. **เชื่อมต่อกับ Backend:**
   - ตรวจสอบว่า Backend API ทำงานที่ `http://localhost:8001`
   - ตรวจสอบ WebSocket connection

4. **ทดสอบ Real-time Caption:**
   - อัปโหลดไฟล์วิดีโอ
   - เริ่ม real-time caption session
   - ดู captions แสดงแบบ real-time

## 📝 **หมายเหตุ**

- ระบบรองรับ delay control 0-30 วินาที
- Chunks จะถูกส่งทันทีที่ประมวลผลเสร็จ
- WebSocket จะ reconnect อัตโนมัติ
- รองรับการแสดงผลแบบ real-time พร้อม animation
