# 🧪 Local Testing Guide - Transcription Service (MOCK MODE)

## วัตถุประสงค์

ทดสอบการส่งข้อมูลจาก **Audio Tap → Gateway → Transcription Service** โดยไม่ต้องทำ transcription ด้วย faster-whisper

## 🚀 Quick Start

### 1. รัน Transcription Service ใน MOCK MODE (บน Host)

```bash
cd transcription-close-caption-service
bash run-local-mock.sh
```

หรือรันด้วย Python โดยตรง:

```bash
cd transcription-close-caption-service
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install fastapi uvicorn python-multipart aiofiles
export TRANSCRIPTION_MOCK_MODE=true
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

**⚠️ สำคัญ**: Transcription Service รันบน **host** (ไม่ใช่ Docker container)

### 2. ตรวจสอบว่า Service ทำงาน

```bash
curl http://localhost:8010/health
```

ควรได้ response:
```json
{"status": "ok", "service": "transcription-api"}
```

### 3. ตั้งค่า Backend ให้ชี้ไปที่ Local Transcription Service

#### ✅ วิธีที่ถูกต้อง: ใช้ `host.docker.internal`

Backend อยู่ใน Docker container → ต้องใช้ `host.docker.internal` เพื่อเข้าถึง services บน host

**แก้ไข `docker-compose.test.yml`** (แก้ไขแล้ว):
```yaml
services:
  kk-senate-backend-test:
    environment:
      # 🧪 Local Testing: ใช้ local Transcription Service (MOCK MODE)
      ExternalServices__TranscriptionUrl: "http://host.docker.internal:8010"
    extra_hosts:
      - "host.docker.internal:host-gateway"  # ✅ ต้องมีบรรทัดนี้
```

**หมายเหตุ**: 
- `host.docker.internal` = special DNS name ที่ Docker ให้มาเพื่อให้ container เข้าถึง host machine
- `extra_hosts: - "host.docker.internal:host-gateway"` = ตั้งค่า DNS mapping (มีอยู่แล้วใน `docker-compose.test.yml`)

### 4. Restart Backend

```bash
cd senate-backend
docker-compose -f docker-compose.test.yml restart kk-senate-backend-test
```

หรือ rebuild:
```bash
docker-compose -f docker-compose.test.yml up -d --build kk-senate-backend-test
```

### 5. ทดสอบ Audio Tap

1. เปิด RTMP stream: `rtmp://localhost:1935/live/test-channel`
2. เริ่ม Audio Tap จาก Frontend
3. ตรวจสอบ logs:
   - **Transcription Service logs** (terminal ที่รัน `run-local-mock.sh`): ควรเห็น "📥 Received audio stream request" และ "💾 Saved audio chunk"
   - **Backend logs**: ควรเห็น "Gateway response" จาก Transcription Service

## 📋 URL Path ที่ใช้

### Transcription Service Endpoints

- **Health Check**: `http://localhost:8010/health`
- **Stream Endpoint**: `http://localhost:8010/api/transcription/realtime/stream`
- **Stream Status**: `http://localhost:8010/api/transcription/realtime/stream/{session_id}/status`
- **List Streams**: `http://localhost:8010/api/transcription/realtime/streams`

### Backend Configuration

Backend จะเรียกใช้:
```
{TranscriptionUrl}/api/transcription/realtime/stream
```

ตัวอย่าง:
- ถ้า `TranscriptionUrl = http://host.docker.internal:8010`
- Backend จะเรียก: `http://host.docker.internal:8010/api/transcription/realtime/stream`

## 🔍 Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Host Machine (Mac/Windows/Linux)                        │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Transcription Service (run-local-mock.sh)        │  │
│  │ http://localhost:8010                             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Docker Container (kk-senate-backend-test)        │  │
│  │                                                   │  │
│  │  Backend → http://host.docker.internal:8010     │  │
│  │  (เข้าถึง Transcription Service บน host)         │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 📋 MOCK MODE Features

เมื่อเปิด `TRANSCRIPTION_MOCK_MODE=true`:

- ✅ **รับ audio stream** จาก Audio Tap
- ✅ **Process stream chunks** (อ่านและบันทึก chunks)
- ✅ **Send NDJSON responses** กลับไปยัง Gateway
- ✅ **Send sync event** สำหรับ sync กับวิดีโอ
- 🧪 **Skip transcription** (ไม่ต้องใช้ faster-whisper)
- 🧪 **Skip WebSocket** (ไม่ส่ง caption events)

## 🔍 ตรวจสอบ Logs

### Transcription Service Logs (Terminal ที่รัน `run-local-mock.sh`)

ควรเห็น:
```
📥 Received audio stream request: SessionId=..., MeetingId=...
🔄 Starting streaming audio processing: SessionId=..., MOCK_MODE=True
💾 Saved audio chunk 0: ... (160000 bytes audio data)
🧪 MOCK MODE: Skipping transcription, sending mock caption events
✅ Streaming audio processing completed: SessionId=..., TotalChunks=..., TotalBytes=...
```

### Backend Logs

```bash
docker logs kk-senate-backend-test --tail 50 | grep -i "gateway\|transcription"
```

ควรเห็น:
```
Forwarding audio stream to Transcription Service (stream-through): Endpoint=http://host.docker.internal:8010/api/transcription/realtime/stream
Gateway response [1]: MeetingId=..., Response={...}
Gateway response [2]: MeetingId=..., Response={...}
Audio stream forwarding completed: MeetingId=..., TotalResponses=...
```

## 🐛 Troubleshooting

### Transcription Service ไม่เริ่ม

**ปัญหา**: `ModuleNotFoundError` หรือ import errors

**แก้ไข**:
```bash
# ติดตั้ง dependencies เพิ่มเติม
pip install pydantic python-dotenv
```

### Backend ไม่สามารถเชื่อมต่อ Transcription Service

**ปัญหา**: Connection refused หรือ timeout

**แก้ไข**:
1. ตรวจสอบว่า Transcription Service ทำงานอยู่: `curl http://localhost:8010/health`
2. ตรวจสอบว่า Backend configuration ชี้ไปที่ `http://host.docker.internal:8010` (ไม่ใช่ `localhost:8010`)
3. ตรวจสอบว่า `extra_hosts` ตั้งค่าแล้วใน `docker-compose.test.yml`:
   ```yaml
   extra_hosts:
     - "host.docker.internal:host-gateway"
   ```
4. ถ้าใช้ Linux: `host.docker.internal` อาจไม่ทำงาน → ใช้ `172.17.0.1:8010` แทน

### ไม่เห็น "Gateway response" ใน Backend logs

**ปัญหา**: Transcription Service ไม่ส่ง NDJSON กลับมา

**แก้ไข**:
1. ตรวจสอบ Transcription Service logs ว่ามี error หรือไม่
2. ตรวจสอบว่า stream generator ทำงาน (ควรเห็น "💾 Saved audio chunk")
3. ตรวจสอบ network connectivity ระหว่าง Backend → Transcription Service:
   ```bash
   # จาก host
   curl http://localhost:8010/health
   
   # จาก container (ถ้ามี curl)
   docker exec kk-senate-backend-test ping host.docker.internal
   ```

### Backend เรียก URL ผิด

**ปัญหา**: Backend เรียก `https://...` แทน `http://host.docker.internal:8010`

**แก้ไข**:
1. ตรวจสอบ `ExternalServices__TranscriptionUrl` ใน `docker-compose.test.yml`
2. ตรวจสอบว่าไม่มี trailing slash (`/`) ใน URL
3. Backend จะ append `/api/transcription/realtime/stream` อัตโนมัติ
4. Restart Backend: `docker-compose -f docker-compose.test.yml restart kk-senate-backend-test`

## 📊 Expected Flow

```
1. Audio Tap → Gateway
   POST /api/audio-gateway/forward
   Body: Raw PCM audio stream (chunked)

2. Gateway → Transcription Service
   POST http://host.docker.internal:8010/api/transcription/realtime/stream
   Body: Raw PCM audio stream (chunked)
   Headers: X-Audio-Format=s16le, X-Sample-Rate=16000, X-Channels=1

3. Transcription Service → Gateway (NDJSON stream)
   {"type": "sync", ...}
   {"type": "status", "status": "streaming", ...}
   {"type": "status", "status": "completed", ...}

4. Gateway → Audio Tap
   Forward NDJSON responses
```

## 🎯 Next Steps

เมื่อทดสอบ stream connectivity สำเร็จแล้ว:

1. **ปิด MOCK MODE**: ลบ `TRANSCRIPTION_MOCK_MODE=true` หรือตั้งเป็น `false`
2. **ติดตั้ง faster-whisper**: `pip install faster-whisper`
3. **ทดสอบ transcription จริง**: เริ่ม Audio Tap อีกครั้งและตรวจสอบ caption events
