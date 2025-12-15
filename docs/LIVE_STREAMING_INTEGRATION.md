# Live Streaming Integration with Transcription Service

## 📋 Overview

เอกสารนี้อธิบายวิธีการ integrate Live Streaming Server (RTMP/HLS) กับ Transcription Service เพื่อทำ Real-time Close Caption

## 🎯 Architecture

```
Live Stream Flow:
┌─────────────┐
│   Client    │
│  (OBS/FFmpeg)│
└──────┬──────┘
       │ RTMP Push
       ▼
┌─────────────────┐
│  RTMP Server    │
│ 143.198.77.135  │
│  Port: 1935     │
└──────┬──────────┘
       │ Record & Stream
       ├──► HLS Output (m3u8)
       └──► Recorded Video
       │
       ▼
┌─────────────────┐
│  Dashboard      │
│  (Local)        │
└──────┬──────────┘
       │ Download/Stream
       │ Video Chunks
       ▼
┌─────────────────┐
│ Transcription   │
│ Service         │
│ (API Gateway)   │
└─────────────────┘
```

## 🔗 RTMP Server Information

### Server Details
- **RTMP URL**: `rtmp://143.198.77.135:1935/live/channel1`
- **HLS URL**: `http://143.198.77.135:80/hls/channel1.m3u8`
- **Statistics**: `http://143.198.77.135:8080/stat`

### Stream Endpoints
- **Push Stream**: `rtmp://143.198.77.135:1935/live/{channel}`
- **Play HLS**: `http://143.198.77.135:80/hls/{channel}.m3u8`
- **Recorded Files**: `/root/deploy/recordings/` (on RTMP server)

## 🎬 Integration Options

### Option 1: Record & Process (Recommended)

**Flow:**
1. RTMP Server records stream to video file
2. Dashboard downloads recorded chunks
3. Send chunks to Transcription Service
4. Display transcription results

**Pros:**
- ✅ Simple implementation
- ✅ No real-time processing needed
- ✅ Can process full recordings
- ✅ Better accuracy (longer chunks)

**Cons:**
- ⚠️ Delay between recording and transcription
- ⚠️ Need to download files

### Option 2: Real-time HLS Chunk Processing

**Flow:**
1. Monitor HLS playlist (.m3u8)
2. Download new .ts segments as they appear
3. Send segments to Transcription Service immediately
4. Display transcription in real-time

**Pros:**
- ✅ Near real-time transcription
- ✅ No file download needed
- ✅ Automatic chunk detection

**Cons:**
- ⚠️ More complex implementation
- ⚠️ Need to monitor HLS playlist
- ⚠️ Smaller chunks (less accuracy)

### Option 3: Stream Relay & Process

**Flow:**
1. Relay RTMP stream to Transcription Service
2. Process audio in real-time
3. Return transcription results

**Pros:**
- ✅ True real-time
- ✅ No file handling

**Cons:**
- ⚠️ Requires FFmpeg relay setup
- ⚠️ Higher resource usage
- ⚠️ More complex

## 🛠️ Implementation: Option 1 (Record & Process)

### Step 1: Setup RTMP Server Recording

```bash
# On RTMP Server (143.198.77.135)
# Configure nginx-rtmp to record streams
# nginx.conf should have:
recording all;
record_path /root/deploy/recordings;
record_suffix .flv;
record_unique on;
```

### Step 2: Dashboard Integration

```javascript
// dashboard/static/js/live-streaming.js

class LiveStreamingService {
    constructor(rtmpServerUrl, transcriptionApiUrl) {
        this.rtmpServerUrl = rtmpServerUrl; // http://143.198.77.135:8080
        this.transcriptionApiUrl = transcriptionApiUrl; // http://localhost:8010
        this.channel = 'channel1';
        this.pollInterval = 5000; // 5 seconds
    }

    // Monitor recorded files
    async monitorRecordings() {
        const recordingsUrl = `${this.rtmpServerUrl}/recordings`;
        
        // Poll for new recordings
        setInterval(async () => {
            const files = await this.getRecordedFiles();
            const newFiles = this.detectNewFiles(files);
            
            for (const file of newFiles) {
                await this.processRecording(file);
            }
        }, this.pollInterval);
    }

    // Get list of recorded files
    async getRecordedFiles() {
        // Option 1: Use RTMP server API (if available)
        // Option 2: Use file listing endpoint
        // Option 3: Use SSH/SCP to list files
        
        // For now, assume we have an API endpoint
        const response = await fetch(`${this.rtmpServerUrl}/api/recordings`);
        return await response.json();
    }

    // Process recorded file
    async processRecording(filePath) {
        // 1. Download file (or use file_url)
        const fileUrl = `${this.rtmpServerUrl}/recordings/${filePath}`;
        
        // 2. Send to Transcription Service
        const response = await fetch(`${this.transcriptionApiUrl}/transcribe/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_url: fileUrl,
                file_name: filePath,
                language: 'th',
                model_size: 'medium',
                chunk_duration: 3, // 3 seconds for close caption
                use_chunking: true,
                display_mode: 'realtime_chunks', // Priority 10
                callback_url: `${window.location.origin}/api/transcription/callback`
            })
        });
        
        const result = await response.json();
        console.log('Transcription started:', result.task_id);
        
        return result;
    }
}
```

### Step 3: API Endpoint for Recordings

```python
# dashboard/routes/live_streaming_routes.py

from fastapi import APIRouter, HTTPException
import aiohttp
import logging

router = APIRouter(prefix="/api/live-streaming", tags=["live-streaming"])
logger = logging.getLogger(__name__)

RTMP_SERVER_URL = "http://143.198.77.135:8080"

@router.get("/recordings")
async def get_recordings():
    """Get list of recorded files from RTMP server"""
    try:
        # Option 1: If RTMP server has API
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{RTMP_SERVER_URL}/api/recordings") as response:
                if response.status == 200:
                    return await response.json()
        
        # Option 2: List files via SSH/SCP (if needed)
        # Use subprocess to SSH and list files
        
    except Exception as e:
        logger.error(f"Error getting recordings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recordings/{filename}")
async def get_recording_file(filename: str):
    """Proxy recording file from RTMP server"""
    try:
        file_url = f"{RTMP_SERVER_URL}/recordings/{filename}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    content = await response.read()
                    return Response(
                        content=content,
                        media_type="video/x-flv"  # or appropriate type
                    )
        
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"Error getting recording file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-recording")
async def process_recording(filename: str, transcription_api_url: str):
    """Process recorded file with Transcription Service"""
    try:
        file_url = f"{RTMP_SERVER_URL}/recordings/{filename}"
        
        # Send to Transcription Service
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{transcription_api_url}/transcribe/",
                json={
                    "file_url": file_url,
                    "file_name": filename,
                    "language": "th",
                    "model_size": "medium",
                    "chunk_duration": 3,
                    "use_chunking": true,
                    "display_mode": "realtime_chunks"  # Priority 10
                }
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=response.status,
                        detail=error_text
                    )
    except Exception as e:
        logger.error(f"Error processing recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## 🛠️ Implementation: Option 2 (HLS Chunk Processing)

### Step 1: Monitor HLS Playlist

```javascript
// dashboard/static/js/hls-monitor.js

class HLSMonitor {
    constructor(hlsUrl, transcriptionApiUrl) {
        this.hlsUrl = hlsUrl; // http://143.198.77.135:80/hls/channel1.m3u8
        this.transcriptionApiUrl = transcriptionApiUrl;
        this.processedSegments = new Set();
        this.pollInterval = 2000; // 2 seconds
    }

    async startMonitoring() {
        setInterval(async () => {
            await this.checkNewSegments();
        }, this.pollInterval);
    }

    async checkNewSegments() {
        try {
            // Fetch playlist
            const response = await fetch(this.hlsUrl);
            const playlist = await response.text();
            
            // Parse segments
            const segments = this.parsePlaylist(playlist);
            
            // Process new segments
            for (const segment of segments) {
                if (!this.processedSegments.has(segment.url)) {
                    await this.processSegment(segment);
                    this.processedSegments.add(segment.url);
                }
            }
        } catch (error) {
            console.error('Error monitoring HLS:', error);
        }
    }

    parsePlaylist(playlist) {
        const lines = playlist.split('\n');
        const segments = [];
        
        for (let i = 0; i < lines.length; i++) {
            if (lines[i].startsWith('#EXTINF:')) {
                const duration = parseFloat(lines[i].match(/#EXTINF:([\d.]+)/)[1]);
                const url = lines[i + 1];
                
                segments.push({
                    url: url.startsWith('http') ? url : new URL(url, this.hlsUrl).href,
                    duration: duration
                });
            }
        }
        
        return segments;
    }

    async processSegment(segment) {
        // Download segment
        const response = await fetch(segment.url);
        const blob = await response.blob();
        
        // Convert to File
        const file = new File([blob], `segment_${Date.now()}.ts`, {
            type: 'video/mp2t'
        });
        
        // Send to Transcription Service
        const formData = new FormData();
        formData.append('file', file);
        formData.append('language', 'th');
        formData.append('model_size', 'medium');
        formData.append('chunk_duration', '3');
        formData.append('display_mode', 'realtime_chunks'); // Priority 10
        
        const result = await fetch(`${this.transcriptionApiUrl}/transcribe/`, {
            method: 'POST',
            body: formData
        });
        
        return await result.json();
    }
}
```

## 📊 Dashboard UI Integration

### Live Streaming Tab

```html
<!-- dashboard/templates/live-streaming.html -->

<div class="live-streaming-container">
    <h2>Live Streaming Transcription</h2>
    
    <!-- Stream Info -->
    <div class="stream-info">
        <label>RTMP URL:</label>
        <input type="text" value="rtmp://143.198.77.135:1935/live/channel1" readonly>
        
        <label>HLS URL:</label>
        <input type="text" value="http://143.198.77.135:80/hls/channel1.m3u8" readonly>
    </div>
    
    <!-- Video Player -->
    <div class="video-player">
        <video id="hls-player" controls>
            <source src="http://143.198.77.135:80/hls/channel1.m3u8" type="application/x-mpegURL">
        </video>
    </div>
    
    <!-- Transcription Display -->
    <div class="transcription-display">
        <h3>Live Transcription</h3>
        <div id="transcription-chunks"></div>
    </div>
    
    <!-- Controls -->
    <div class="controls">
        <button onclick="startMonitoring()">Start Monitoring</button>
        <button onclick="stopMonitoring()">Stop Monitoring</button>
        <button onclick="processRecording()">Process Recording</button>
    </div>
</div>
```

## 🔧 Configuration

### Dashboard Config

```python
# dashboard/config.py

LIVE_STREAMING_CONFIG = {
    "rtmp_server_url": "http://143.198.77.135:8080",
    "rtmp_push_url": "rtmp://143.198.77.135:1935/live",
    "hls_base_url": "http://143.198.77.135:80/hls",
    "transcription_api_url": "http://localhost:8010",
    "poll_interval": 5000,  # 5 seconds
    "chunk_duration": 3,    # 3 seconds for close caption
    "default_channel": "channel1"
}
```

## 🚀 Quick Start

### 1. Setup Dashboard Routes

```python
# dashboard/main.py

from .routes import live_streaming_routes

app.include_router(live_streaming_routes.router)
```

### 2. Add JavaScript

```html
<!-- dashboard/templates/dashboard.html -->

<script src="/static/js/live-streaming.js"></script>
<script src="/static/js/hls-monitor.js"></script>
```

### 3. Start Monitoring

```javascript
// In dashboard
const liveStreaming = new LiveStreamingService(
    'http://143.198.77.135:8080',
    'http://localhost:8010'
);

liveStreaming.monitorRecordings();
```

## 📝 Notes

1. **File Access**: RTMP server ต้อง expose recordings directory ผ่าน HTTP
2. **CORS**: ต้อง configure CORS สำหรับ cross-origin requests
3. **Authentication**: ถ้ามี authentication ต้อง handle tokens
4. **Error Handling**: ต้อง handle network errors และ retries
5. **Priority Queue**: Close Caption จะใช้ priority 10 (สูงสุด)

## ✅ Checklist

- [ ] RTMP Server configured for recording
- [ ] Dashboard routes created
- [ ] JavaScript monitoring implemented
- [ ] Transcription API integration
- [ ] UI components added
- [ ] Error handling implemented
- [ ] Testing completed

