# 📡 คู่มือ Integration Live-Chunk กับ Frontend

## 📋 Overview

Live-Chunk API ให้ real-time transcription สำหรับ audio chunks ที่ส่งเข้ามาแบบ streaming

**Features:**
- Real-time transcription (near real-time: ~72.6%)
- WebSocket notifications สำหรับ transcription results
- Low latency (~1.13s per chunk)
- V3 Compliant WebSocket API

---

## 🔌 API Endpoints

### 1. POST `/api/transcription/realtime/live-chunk`

ส่ง audio chunk เพื่อ transcription

**Headers:**
```
Content-Type: application/octet-stream
X-Meeting-Id: {meeting_id} (required)
X-Chunk-Index: {chunk_index} (required)
X-Start-Time: {start_time_seconds} (required)
X-Duration: {duration_seconds} (required)
X-Audio-Format: s16le (required)
X-Sample-Rate: 16000 (required)
X-Channels: 1 (required)
```

**Body:**
- Raw PCM16 audio data (binary)
- Format: 16kHz, Mono, PCM16 (s16le)

**Response:**
```json
{
  "status": "accepted",
  "session_id": "live-{meeting_id}-{chunk_index}",
  "meeting_id": "{meeting_id}",
  "chunk_index": 0,
  "start_time": 0.0,
  "duration": 3.0,
  "job_id": "live-chunk-{meeting_id}-{chunk_index}",
  "queue": "priority"
}
```

**Example:**
```javascript
const audioData = new ArrayBuffer(96000); // 3 seconds of 16kHz mono PCM16
// ... fill audioData with audio samples ...

const response = await fetch('http://localhost:8010/api/transcription/realtime/live-chunk', {
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
  body: audioData
});

const result = await response.json();
console.log('Chunk accepted:', result);
```

---

### 2. WebSocket `/api/ws/captions?meeting_id={meeting_id}`

รับ transcription results แบบ real-time

**Connection:**
```
ws://localhost:8010/api/ws/captions?meeting_id={meeting_id}
```

**Events Received:**

#### `sync` - Clock Synchronization
```json
{
  "type": "sync",
  "meeting_id": "meeting-123",
  "session_id": "",
  "seq": 1,
  "created_at": "2026-01-12T20:00:00.000Z",
  "clock": {
    "meeting_start_utc": "2026-01-12T20:00:00.000Z",
    "server_utc": "2026-01-12T20:00:00.000Z",
    "timebase": "ms"
  }
}
```

#### `status` - Status Update
```json
{
  "type": "status",
  "meeting_id": "meeting-123",
  "session_id": "",
  "seq": 2,
  "created_at": "2026-01-12T20:00:00.000Z",
  "status": "streaming",
  "message": "Connected and ready to receive captions"
}
```

#### `final` - Final Transcription Result (V3 Format)
```json
{
  "type": "final",
  "meeting_id": "meeting-123",
  "session_id": "live-meeting-123-0",
  "seq": 100,
  "created_at": "2026-01-12T20:00:05.000Z",
  "chunk_index": 0,
  "chunk_start_ms": 0,
  "chunk_duration_ms": 3000,
  "language": "th",
  "model": "base",
  "provider": "faster-whisper",
  "text": "บางอย่างที่ท่านสมาชิกหลายๆ",
  "segments": [
    {
      "id": "seg-0-0",
      "t0_ms": 0,
      "t1_ms": 3000,
      "text": "บางอย่างที่ท่านสมาชิกหลายๆ",
      "confidence": 0.95,
      "is_final": true,
      "speaker": null
    }
  ]
}
```

#### `caption` - Legacy Caption Event (Backward Compatibility)
```json
{
  "type": "caption",
  "session_id": "live-meeting-123-0",
  "stream_id": "meeting-123",
  "seq": 0,
  "timing": {
    "kind": "epoch_ms",
    "start": 1768247822251,
    "end": 1768247825251
  },
  "text": "บางอย่างที่ท่านสมาชิกหลายๆ",
  "lang": "th",
  "is_final": true,
  "tokens": [],
  "meta": {
    "speaker": null,
    "confidence": 0.95,
    "model": "faster-whisper",
    "chunk_id": "c_0000_00"
  },
  "ts": "2026-01-12T20:00:05.000Z"
}
```

#### `heartbeat` - Keepalive
```json
{
  "type": "heartbeat",
  "meeting_id": "meeting-123",
  "session_id": "",
  "seq": 0,
  "created_at": "2026-01-12T20:00:30.000Z"
}
```

---

## 💻 Frontend Integration Example

### JavaScript/TypeScript

```javascript
class LiveChunkTranscription {
  constructor(apiUrl = 'http://localhost:8010', meetingId) {
    this.apiUrl = apiUrl;
    this.meetingId = meetingId;
    this.ws = null;
    this.chunkIndex = 0;
    this.isConnected = false;
  }

  // Connect WebSocket
  async connect() {
    return new Promise((resolve, reject) => {
      const wsUrl = this.apiUrl.replace('http://', 'ws://').replace('https://', 'wss://');
      this.ws = new WebSocket(`${wsUrl}/api/ws/captions?meeting_id=${this.meetingId}`);

      this.ws.onopen = () => {
        console.log('✅ WebSocket connected');
        this.isConnected = true;
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
        this.isConnected = false;
      };
    });
  }

  // Handle WebSocket messages
  handleMessage(message) {
    switch (message.type) {
      case 'sync':
        console.log('🔄 Sync event:', message.clock);
        this.onSync?.(message);
        break;

      case 'status':
        console.log('📊 Status:', message.status);
        this.onStatus?.(message);
        break;

      case 'final':
        console.log('📝 Final transcription:', message.text);
        this.onFinal?.(message);
        break;

      case 'caption':
        console.log('📝 Caption:', message.text);
        this.onCaption?.(message);
        break;

      case 'heartbeat':
        // Keepalive - no action needed
        break;

      default:
        console.log('📨 Unknown message type:', message.type);
    }
  }

  // Send audio chunk
  async sendChunk(audioData, startTime, duration = 3.0) {
    if (!this.isConnected) {
      throw new Error('WebSocket not connected');
    }

    try {
      const response = await fetch(`${this.apiUrl}/api/transcription/realtime/live-chunk`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/octet-stream',
          'X-Meeting-Id': this.meetingId,
          'X-Chunk-Index': this.chunkIndex.toString(),
          'X-Start-Time': startTime.toString(),
          'X-Duration': duration.toString(),
          'X-Audio-Format': 's16le',
          'X-Sample-Rate': '16000',
          'X-Channels': '1'
        },
        body: audioData
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log(`✅ Chunk ${this.chunkIndex} accepted:`, result);
      
      this.chunkIndex++;
      return result;
    } catch (error) {
      console.error(`❌ Failed to send chunk ${this.chunkIndex}:`, error);
      throw error;
    }
  }

  // Disconnect
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.isConnected = false;
    }
  }

  // Callbacks (optional)
  onSync(message) {}
  onStatus(message) {}
  onFinal(message) {}
  onCaption(message) {}
}

// Usage Example
const transcription = new LiveChunkTranscription(
  'http://localhost:8010',
  'meeting-123'
);

// Set callbacks
transcription.onFinal = (message) => {
  console.log(`Chunk ${message.chunk_index}: ${message.text}`);
  // Update UI with transcription result
  updateUI(message);
};

transcription.onCaption = (message) => {
  console.log(`Caption: ${message.text}`);
  // Update UI with legacy caption
  updateCaptionUI(message);
};

// Connect
await transcription.connect();

// Send audio chunks
for (let i = 0; i < 10; i++) {
  const audioData = await getAudioChunk(i); // Your function to get audio data
  const startTime = i * 3.0;
  await transcription.sendChunk(audioData, startTime, 3.0);
  
  // Wait before sending next chunk
  await new Promise(resolve => setTimeout(resolve, 3000));
}

// Disconnect when done
transcription.disconnect();
```

---

## 🎯 React Integration Example

```jsx
import React, { useEffect, useRef, useState, useCallback } from 'react';

function LiveChunkTranscription({ apiUrl, meetingId, onTranscription }) {
  const [isConnected, setIsConnected] = useState(false);
  const [status, setStatus] = useState('disconnected');
  const wsRef = useRef(null);
  const chunkIndexRef = useRef(0);

  // Connect WebSocket
  useEffect(() => {
    const wsUrl = apiUrl.replace('http://', 'ws://').replace('https://', 'wss://');
    wsRef.current = new WebSocket(`${wsUrl}/api/ws/captions?meeting_id=${meetingId}`);

    wsRef.current.onopen = () => {
      console.log('✅ WebSocket connected');
      setIsConnected(true);
      setStatus('connected');
    };

    wsRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      handleMessage(message);
    };

    wsRef.current.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
      setStatus('error');
    };

    wsRef.current.onclose = () => {
      console.log('🔌 WebSocket closed');
      setIsConnected(false);
      setStatus('disconnected');
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [apiUrl, meetingId]);

  // Handle messages
  const handleMessage = useCallback((message) => {
    switch (message.type) {
      case 'sync':
        console.log('🔄 Sync event');
        break;

      case 'status':
        setStatus(message.status);
        break;

      case 'final':
        console.log('📝 Final transcription:', message.text);
        onTranscription?.(message);
        break;

      case 'caption':
        console.log('📝 Caption:', message.text);
        onTranscription?.(message);
        break;

      default:
        break;
    }
  }, [onTranscription]);

  // Send chunk
  const sendChunk = useCallback(async (audioData, startTime, duration = 3.0) => {
    if (!isConnected) {
      throw new Error('WebSocket not connected');
    }

    try {
      const response = await fetch(`${apiUrl}/api/transcription/realtime/live-chunk`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/octet-stream',
          'X-Meeting-Id': meetingId,
          'X-Chunk-Index': chunkIndexRef.current.toString(),
          'X-Start-Time': startTime.toString(),
          'X-Duration': duration.toString(),
          'X-Audio-Format': 's16le',
          'X-Sample-Rate': '16000',
          'X-Channels': '1'
        },
        body: audioData
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      chunkIndexRef.current++;
      return result;
    } catch (error) {
      console.error('❌ Failed to send chunk:', error);
      throw error;
    }
  }, [apiUrl, meetingId, isConnected]);

  return {
    isConnected,
    status,
    sendChunk
  };
}

// Usage in Component
function TranscriptionComponent() {
  const [transcriptions, setTranscriptions] = useState([]);
  const { isConnected, status, sendChunk } = LiveChunkTranscription({
    apiUrl: 'http://localhost:8010',
    meetingId: 'meeting-123',
    onTranscription: (message) => {
      setTranscriptions(prev => [...prev, message]);
    }
  });

  const handleSendChunk = async (audioData, startTime) => {
    try {
      await sendChunk(audioData, startTime);
    } catch (error) {
      console.error('Failed to send chunk:', error);
    }
  };

  return (
    <div>
      <div>Status: {status}</div>
      <div>Connected: {isConnected ? 'Yes' : 'No'}</div>
      <div>
        <h3>Transcriptions:</h3>
        {transcriptions.map((t, i) => (
          <div key={i}>
            <strong>Chunk {t.chunk_index || i}:</strong> {t.text}
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 📊 Audio Format Requirements

**Required Format:**
- **Sample Rate:** 16000 Hz
- **Channels:** Mono (1 channel)
- **Bit Depth:** 16-bit
- **Format:** PCM16 (s16le)
- **Duration:** 3 seconds (96000 bytes = 3s * 16000 samples/s * 2 bytes/sample)

**Audio Data Size:**
- 3 seconds = 96000 bytes
- 1 second = 32000 bytes
- Formula: `bytes = duration * sample_rate * channels * 2`

---

## 🔄 Flow Diagram

```
Frontend
  ↓ (1. Connect WebSocket)
ws://localhost:8010/api/ws/captions?meeting_id={meeting_id}
  ↓ (2. Send Audio Chunks)
POST /api/transcription/realtime/live-chunk
  ↓ (3. Process in Background)
RQ Worker (Priority Queue)
  ↓ (4. HTTP Callback)
POST /api/internal/ws-event
  ↓ (5. Broadcast via WebSocket)
Frontend (Receive Transcription Results)
```

---

## 📋 Checklist

- [ ] Connect WebSocket (`/api/ws/captions?meeting_id={meeting_id}`)
- [ ] Handle `sync` event (clock synchronization)
- [ ] Handle `status` event (connection status)
- [ ] Handle `final` event (V3 transcription result)
- [ ] Handle `caption` event (legacy caption, optional)
- [ ] Send audio chunks (`POST /api/transcription/realtime/live-chunk`)
- [ ] Convert audio to PCM16 format (16kHz, Mono)
- [ ] Set correct headers (X-Meeting-Id, X-Chunk-Index, etc.)
- [ ] Handle errors and reconnection
- [ ] Update UI with transcription results

---

## ⚠️ Important Notes

1. **Meeting ID:** ใช้ meeting_id เดียวกันสำหรับ WebSocket connection และ chunk submission
2. **Chunk Index:** ต้องส่ง chunk_index ตามลำดับ (0, 1, 2, ...)
3. **Start Time:** ต้องส่ง start_time ตามเวลาจริง (0.0, 3.0, 6.0, ...)
4. **Audio Format:** ต้องเป็น PCM16, 16kHz, Mono (s16le)
5. **Latency:** ~1.13s per chunk (near real-time: 72.6%)
6. **WebSocket:** ต้อง connect ก่อนส่ง chunks

---

## 📚 Additional Resources

- [WebSocket API Documentation](./WEBSOCKET_SUBSCRIPTION_GUIDE.md)
- [Workers HTTP Callback Guide](../WORKERS_WS_EVENT_GUIDE.md)
- [WebSocket Frontend Flow](./WEBSOCKET_FRONTEND_FLOW.md)
