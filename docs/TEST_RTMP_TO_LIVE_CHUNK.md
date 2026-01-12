# 🧪 คู่มือทดสอบ RTMP Stream → Live Chunk Endpoint

## 📋 วัตถุประสงค์

ทดสอบการส่ง audio chunks จาก RTMP stream ไปยัง `/api/transcription/realtime/live-chunk` โดยตรง

---

## 🔄 Flow ที่ทดสอบ

```
RTMP Stream (rtmp://143.198.77.135:1935/live/channel1)
    ↓
FFmpeg (extract audio → PCM16 16kHz mono)
    ↓
Chunks (96,000 bytes = 3 seconds)
    ↓
HTTP POST → /api/transcription/realtime/live-chunk
    ↓
Transcription Service (process chunk → WebSocket → FINAL Event)
```

---

## 🚀 วิธีใช้งาน

### 1. ใช้สคริปต์ทดสอบ (แนะนำ)

```bash
# ทดสอบด้วยค่า default
python scripts/test_rtmp_to_live_chunk.py

# ทดสอบด้วย RTMP URL และ Meeting ID เฉพาะ
python scripts/test_rtmp_to_live_chunk.py \
    --rtmp-url rtmp://143.198.77.135:1935/live/channel1 \
    --transcription-url http://localhost:8010 \
    --meeting-id test-meeting-001 \
    --duration 30

# เปิด verbose logging
python scripts/test_rtmp_to_live_chunk.py --verbose
```

### 2. ใช้ curl (Manual)

```bash
# 1. แยกเสียงจาก RTMP stream เป็น chunk (3 วินาที)
ffmpeg -i rtmp://143.198.77.135:1935/live/channel1 \
    -t 3 \
    -ac 1 \
    -ar 16000 \
    -acodec pcm_s16le \
    -f s16le \
    chunk_0.raw

# 2. ส่งไปยัง Transcription Service
curl -X POST http://localhost:8010/api/transcription/realtime/live-chunk \
    -H "X-Meeting-Id: test-meeting-001" \
    -H "X-Chunk-Index: 0" \
    -H "X-Start-Time: 0.0" \
    -H "X-Duration: 3.0" \
    -H "X-Audio-Format: s16le" \
    -H "X-Sample-Rate: 16000" \
    -H "X-Channels: 1" \
    -H "Content-Type: application/octet-stream" \
    --data-binary @chunk_0.raw
```

---

## 📊 Parameters

### Headers ที่ต้องส่ง

| Header | Description | Example |
|--------|-------------|---------|
| `X-Meeting-Id` | Meeting ID | `test-meeting-001` |
| `X-Chunk-Index` | Chunk index (0-based) | `0`, `1`, `2`, ... |
| `X-Start-Time` | Start time in seconds | `0.0`, `3.0`, `6.0`, ... |
| `X-Duration` | Duration in seconds | `3.0` |
| `X-Audio-Format` | Audio format | `s16le` (PCM16 little-endian) |
| `X-Sample-Rate` | Sample rate | `16000` (16kHz) |
| `X-Channels` | Number of channels | `1` (mono) |

### Request Body

- **Format**: Raw PCM16 little-endian audio data
- **Size**: 96,000 bytes (3 seconds at 16kHz mono PCM16)
- **Calculation**: 16,000 samples/sec × 2 bytes/sample × 3 seconds = 96,000 bytes

---

## ✅ ตรวจสอบผลลัพธ์

### 1. ตรวจสอบ Response

```json
{
    "status": "accepted",
    "session_id": "live-test-meeting-001-0",
    "meeting_id": "test-meeting-001",
    "chunk_index": 0,
    "start_time": 0.0,
    "duration": 3.0,
    "message": "Audio chunk received. Processing in background. Caption events will be sent via WebSocket."
}
```

### 2. ตรวจสอบ WebSocket Events

เชื่อมต่อ WebSocket เพื่อรับ transcription results:

```javascript
const ws = new WebSocket('ws://localhost:8010/api/websocket/captions-v3?meeting_id=test-meeting-001');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'final') {
        console.log('Transcription:', data.text);
        console.log('Segments:', data.segments);
    }
};
```

### 3. ตรวจสอบ Logs

```bash
# ดู logs ของ Transcription Service
tail -f logs/transcription.log | grep "live-chunk"
```

---

## 🔍 Troubleshooting

### 1. FFmpeg ไม่พบ

```bash
# ติดตั้ง FFmpeg
sudo apt-get update
sudo apt-get install -y ffmpeg
```

### 2. RTMP Stream ไม่สามารถเชื่อมต่อได้

```bash
# ทดสอบ RTMP stream
ffmpeg -i rtmp://143.198.77.135:1935/live/channel1 -t 1 -f null -

# ถ้า error: ตรวจสอบว่า RTMP stream เปิดอยู่หรือไม่
```

### 3. Transcription Service ไม่ตอบสนอง

```bash
# ตรวจสอบว่า service ทำงานอยู่หรือไม่
curl http://localhost:8010/health

# ตรวจสอบ logs
tail -f logs/transcription.log
```

### 4. ไม่เห็น WebSocket Events

```bash
# ตรวจสอบว่า WebSocket service ทำงานอยู่หรือไม่
curl http://localhost:8010/api/websocket/status

# ตรวจสอบว่า meeting_id ถูกต้องหรือไม่
# WebSocket ใช้ meeting_id เป็น user_id
```

### 5. Audio Data Size ไม่ตรง

**ปัญหา**: Audio data size ไม่เท่ากับ 96,000 bytes

**สาเหตุ**:
- RTMP stream อาจไม่มี audio
- FFmpeg อาจไม่สามารถแยกเสียงได้
- Sample rate หรือ channels ไม่ตรง

**แก้ไข**:
```bash
# ตรวจสอบ audio stream
ffprobe rtmp://143.198.77.135:1935/live/channel1

# ตรวจสอบ audio data size
ls -lh chunk_0.raw
```

---

## 📝 ตัวอย่างการใช้งาน

### Python Script

```python
import requests
import subprocess

# 1. แยกเสียงจาก RTMP stream
cmd = [
    'ffmpeg', '-i', 'rtmp://143.198.77.135:1935/live/channel1',
    '-t', '3',
    '-ac', '1',
    '-ar', '16000',
    '-acodec', 'pcm_s16le',
    '-f', 's16le',
    '-'
]
process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
audio_data = process.stdout

# 2. ส่งไปยัง Transcription Service
response = requests.post(
    'http://localhost:8010/api/transcription/realtime/live-chunk',
    headers={
        'X-Meeting-Id': 'test-meeting-001',
        'X-Chunk-Index': '0',
        'X-Start-Time': '0.0',
        'X-Duration': '3.0',
        'X-Audio-Format': 's16le',
        'X-Sample-Rate': '16000',
        'X-Channels': '1',
        'Content-Type': 'application/octet-stream'
    },
    data=audio_data
)

print(response.json())
```

---

## 🎯 สรุป

### ✅ สามารถทดสอบได้

**คำตอบ**: ✅ **ได้** - สามารถทดสอบ `/api/transcription/realtime/live-chunk` จาก RTMP stream ได้โดยตรง

**วิธี**:
1. ใช้สคริปต์ `scripts/test_rtmp_to_live_chunk.py` (แนะนำ)
2. ใช้ FFmpeg + curl (manual)
3. ใช้ Python script (custom)

**ข้อกำหนด**:
- RTMP stream ต้องเปิดอยู่
- FFmpeg ต้องติดตั้ง
- Transcription Service ต้องทำงานอยู่
- WebSocket connection สำหรับรับผลลัพธ์

---

**วันที่สร้าง**: 2024-12-19
**สถานะ**: ✅ พร้อมใช้งาน
