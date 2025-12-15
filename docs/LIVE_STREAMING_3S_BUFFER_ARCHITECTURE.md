# Live Streaming 3-Second Buffer Architecture

## 📋 Overview

ระบบนี้จะ **Record Video จาก Live Streaming ล่วงหน้า 3 วินาที** แล้วแปลงเป็นข้อความ และ Response คืนทันที

## 🎯 Architecture Flow

```
Live Stream (RTMP/HLS)
    │
    ├─► [3s Buffer] ──► Record 3s chunk ──► Extract Audio ──► Transcribe ──► Response
    │                                                                              │
    └──────────────────────────────────────────────────────────────────────────────┘
                                                                              Frontend
                                                                              (Delay 3s)
```

## 🔄 Processing Flow

### 1. Buffer & Record (3 seconds)
```
Time: 0s ──► Stream starts
Time: 3s ──► Record chunk 0-3s ──► Extract audio ──► Transcribe
Time: 6s ──► Record chunk 3-6s ──► Extract audio ──► Transcribe
Time: 9s ──► Record chunk 6-9s ──► Extract audio ──► Transcribe
...
```

### 2. Real-time Processing
- **Buffer Window**: 3 seconds
- **Processing Time**: ~1-2 seconds (depends on model)
- **Total Delay**: ~4-5 seconds from live stream

## 🛠️ Implementation

### Option 1: HLS Segment Processing (Recommended)

```python
# app/services/live_streaming_buffer_service.py

import asyncio
import logging
from typing import Optional, Callable
from datetime import datetime, timedelta
import aiohttp
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

class LiveStreamingBufferService:
    def __init__(self, transcription_service):
        self.transcription_service = transcription_service
        self.buffer_duration = 3  # 3 seconds
        self.hls_playlist_url = None
        self.processing = False
        self.segment_buffer = []
        
    async def start_processing(self, hls_url: str, callback: Callable):
        """
        Start processing HLS stream with 3-second buffer
        
        Args:
            hls_url: HLS playlist URL (m3u8)
            callback: Function to call with transcription results
        """
        self.hls_playlist_url = hls_url
        self.processing = True
        
        # Monitor HLS playlist
        asyncio.create_task(self._monitor_hls_playlist(callback))
    
    async def _monitor_hls_playlist(self, callback: Callable):
        """Monitor HLS playlist and process segments"""
        processed_segments = set()
        
        while self.processing:
            try:
                # Fetch playlist
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.hls_playlist_url) as response:
                        if response.status != 200:
                            await asyncio.sleep(1)
                            continue
                        
                        playlist = await response.text()
                        segments = self._parse_playlist(playlist)
                        
                        # Process new segments
                        for segment in segments:
                            if segment['url'] not in processed_segments:
                                processed_segments.add(segment['url'])
                                
                                # Download segment
                                segment_data = await self._download_segment(segment['url'])
                                
                                # Process with transcription
                                result = await self._process_segment(segment_data, segment)
                                
                                # Callback with result
                                if callback:
                                    await callback(result)
                                
                                # Keep only last 10 processed segments
                                if len(processed_segments) > 10:
                                    oldest = min(processed_segments)
                                    processed_segments.remove(oldest)
                
                # Wait before next check
                await asyncio.sleep(1)  # Check every 1 second
                
            except Exception as e:
                logger.error(f"Error monitoring HLS playlist: {e}")
                await asyncio.sleep(2)
    
    def _parse_playlist(self, playlist: str) -> list:
        """Parse HLS playlist and extract segment URLs"""
        segments = []
        lines = playlist.split('\n')
        
        for i, line in enumerate(lines):
            if line.startswith('#EXTINF:'):
                duration = float(line.split(':')[1].split(',')[0])
                if i + 1 < len(lines):
                    url = lines[i + 1].strip()
                    if url and not url.startswith('#'):
                        # Make absolute URL
                        if not url.startswith('http'):
                            base_url = '/'.join(self.hls_playlist_url.split('/')[:-1])
                            url = f"{base_url}/{url}"
                        
                        segments.append({
                            'url': url,
                            'duration': duration
                        })
        
        return segments
    
    async def _download_segment(self, segment_url: str) -> bytes:
        """Download HLS segment"""
        async with aiohttp.ClientSession() as session:
            async with session.get(segment_url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    raise Exception(f"Failed to download segment: {response.status}")
    
    async def _process_segment(self, segment_data: bytes, segment_info: dict) -> dict:
        """Process segment with transcription"""
        # Save segment to temp file
        with tempfile.NamedTemporaryFile(suffix='.ts', delete=False) as tmp_file:
            tmp_file.write(segment_data)
            tmp_path = tmp_path.name
        
        try:
            # Send to transcription service
            result = await self.transcription_service.transcribe_file(
                file_path=tmp_path,
                chunk_duration=3,
                display_mode='realtime_chunks',
                language='th'
            )
            
            return {
                'segment_url': segment_info['url'],
                'duration': segment_info['duration'],
                'transcription': result,
                'timestamp': datetime.now().isoformat()
            }
        finally:
            # Cleanup
            Path(tmp_path).unlink(missing_ok=True)
```

### Option 2: RTMP Stream Recording with FFmpeg

```python
# app/services/rtmp_buffer_service.py

import asyncio
import subprocess
import logging
from pathlib import Path
import tempfile

logger = logging.getLogger(__name__)

class RTMPBufferService:
    def __init__(self, transcription_service):
        self.transcription_service = transcription_service
        self.buffer_duration = 3
        self.recording_process = None
        
    async def start_recording(self, rtmp_url: str, callback: Callable):
        """
        Start recording RTMP stream with 3-second chunks
        
        Args:
            rtmp_url: RTMP stream URL
            callback: Function to call with transcription results
        """
        # Use FFmpeg to record in 3-second chunks
        asyncio.create_task(self._record_chunks(rtmp_url, callback))
    
    async def _record_chunks(self, rtmp_url: str, callback: Callable):
        """Record stream in 3-second chunks"""
        chunk_index = 0
        
        while True:
            try:
                # Create temp file for chunk
                chunk_file = tempfile.NamedTemporaryFile(
                    suffix='.mp4',
                    delete=False
                )
                chunk_path = chunk_file.name
                chunk_file.close()
                
                # Record 3 seconds using FFmpeg
                cmd = [
                    'ffmpeg',
                    '-i', rtmp_url,
                    '-t', str(self.buffer_duration),  # 3 seconds
                    '-c', 'copy',  # Copy codec (fast)
                    '-y',  # Overwrite
                    chunk_path
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                await process.wait()
                
                if process.returncode == 0:
                    # Process chunk with transcription
                    result = await self._process_chunk(chunk_path, chunk_index)
                    
                    if callback:
                        await callback(result)
                    
                    chunk_index += 1
                else:
                    logger.error(f"FFmpeg recording failed: {process.returncode}")
                
                # Cleanup
                Path(chunk_path).unlink(missing_ok=True)
                
                # Wait a bit before next chunk
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error recording chunk: {e}")
                await asyncio.sleep(1)
    
    async def _process_chunk(self, chunk_path: str, chunk_index: int) -> dict:
        """Process chunk with transcription"""
        result = await self.transcription_service.transcribe_file(
            file_path=chunk_path,
            chunk_duration=3,
            display_mode='realtime_chunks',
            language='th'
        )
        
        return {
            'chunk_index': chunk_index,
            'chunk_path': chunk_path,
            'transcription': result,
            'timestamp': datetime.now().isoformat()
        }
```

## 🎬 Frontend: Video Delay Implementation

### Option 1: HTML5 Video with Buffer

```javascript
// dashboard/static/js/live-streaming-delay.js

class LiveStreamingWithDelay {
    constructor(videoElement, hlsUrl, transcriptionService) {
        this.videoElement = videoElement;
        this.hlsUrl = hlsUrl;
        this.transcriptionService = transcriptionService;
        this.delaySeconds = 3; // 3 seconds delay
        this.transcriptionBuffer = [];
        this.currentTime = 0;
    }
    
    async initialize() {
        // Load HLS stream
        if (Hls.isSupported()) {
            const hls = new Hls({
                maxBufferLength: 10, // Buffer 10 seconds
                maxMaxBufferLength: 30,
                startLevel: -1,
                liveSyncDurationCount: 3, // Sync with 3 segments
                liveMaxLatencyDurationCount: 5
            });
            
            hls.loadSource(this.hlsUrl);
            hls.attachMedia(this.videoElement);
            
            // Set initial delay
            hls.on(Hls.Events.MANIFEST_PARSED, () => {
                // Wait for buffer to fill
                this.videoElement.addEventListener('loadedmetadata', () => {
                    // Seek to 3 seconds behind live edge
                    const liveEdge = hls.liveSyncPosition;
                    if (liveEdge) {
                        this.videoElement.currentTime = liveEdge - this.delaySeconds;
                    }
                });
            });
            
            // Monitor playback and sync transcription
            this.videoElement.addEventListener('timeupdate', () => {
                this.syncTranscription();
            });
        }
    }
    
    async syncTranscription() {
        const currentTime = Math.floor(this.videoElement.currentTime);
        
        // Find matching transcription for current time
        const transcription = this.transcriptionBuffer.find(
            t => Math.floor(t.timestamp) === currentTime
        );
        
        if (transcription) {
            // Display transcription
            this.displayTranscription(transcription);
        }
    }
    
    displayTranscription(transcription) {
        // Update UI with transcription
        const transcriptionElement = document.getElementById('transcription-display');
        if (transcriptionElement) {
            transcriptionElement.textContent = transcription.text;
        }
    }
    
    addTranscription(transcription) {
        // Add transcription to buffer
        this.transcriptionBuffer.push({
            timestamp: transcription.timestamp,
            text: transcription.text,
            chunks: transcription.chunks
        });
        
        // Keep only last 30 seconds
        const cutoff = Date.now() / 1000 - 30;
        this.transcriptionBuffer = this.transcriptionBuffer.filter(
            t => t.timestamp > cutoff
        );
    }
}
```

### Option 2: Video.js with Delay Plugin

```javascript
// Using Video.js with delay configuration

const player = videojs('live-stream-player', {
    liveui: true,
    liveTracker: {
        trackingThreshold: 3, // 3 seconds delay
        liveTolerance: 5
    },
    html5: {
        hls: {
            enableLowInitialPlaylist: true,
            smoothQualityChange: true,
            overrideNative: true
        }
    }
});

// Set delay
player.ready(() => {
    const liveTracker = player.liveTracker;
    if (liveTracker.isLive()) {
        // Seek to 3 seconds behind live edge
        const liveEdge = liveTracker.liveCurrentTime();
        player.currentTime(liveEdge - 3);
    }
});
```

## 📊 API Endpoint

```python
# app/api/live_streaming_buffer.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/live-streaming-buffer", tags=["live-streaming-buffer"])

class StartBufferRequest(BaseModel):
    hls_url: str
    rtmp_url: Optional[str] = None
    buffer_duration: int = 3
    callback_url: Optional[str] = None

@router.post("/start")
async def start_buffer_processing(request: StartBufferRequest):
    """Start processing live stream with buffer"""
    # Implementation
    pass

@router.post("/stop/{session_id}")
async def stop_buffer_processing(session_id: str):
    """Stop buffer processing"""
    # Implementation
    pass
```

## ⚙️ Configuration

```python
# config.py

LIVE_STREAMING_BUFFER = {
    "buffer_duration": 3,  # seconds
    "processing_interval": 1,  # seconds (check for new segments)
    "max_buffer_size": 30,  # seconds (max transcription buffer)
    "hls_segment_duration": 3,  # seconds (typical HLS segment)
    "video_delay": 3  # seconds (frontend delay)
}
```

## ✅ Benefits

1. **Real-time Transcription**: Process 3-second chunks continuously
2. **Low Latency**: ~4-5 seconds total delay
3. **Synchronized**: Frontend delays video to match transcription
4. **Scalable**: Can handle multiple streams
5. **Priority Queue**: Close Caption tasks get priority 10

## 🔄 Next Steps

1. Implement `LiveStreamingBufferService`
2. Create API endpoints
3. Update Frontend with video delay
4. Test with RTMP/HLS stream
5. Monitor performance and adjust buffer size

