# 📖 คู่มือการใช้งาน CloseCaption Profile

## ✅ การตั้งค่า Language

**คำตอบ**: ✅ **ไม่ต้องกำหนด language th เพิ่ม** - ระบบใช้ `CC_LANGUAGE=th` จาก config อัตโนมัติ

### Configuration ที่มีอยู่แล้ว

```bash
# ใน .env.runpod
CC_LANGUAGE=th  # ตั้งค่าไว้แล้ว
```

### การทำงาน

- ระบบจะใช้ `CC_LANGUAGE` จาก `CloseCaptionConfig` อัตโนมัติ
- ไม่ต้องส่ง language parameter ใน request
- ถ้า `CC_ENABLED=true` → ใช้ `CC_LANGUAGE` (default: "th")
- ถ้า `CC_ENABLED=false` → ใช้ default "th" หรือจาก request

---

## 🔄 ขั้นตอนการใช้งาน (Flow)

### Flow ยังเหมือนเดิม ✅

```
RTMP Stream (External RTMP Server)
    ↓
FFmpeg (Backend - AudioTapService)
    ↓
AudioTapService (Backend - accumulate to 96,000 bytes)
    ↓
HTTP POST → /api/audio-gateway/chunk (Backend - AudioTapService → AudioGatewayController)
    ↓
AudioGatewayController (Backend - forward chunk)
    ↓
HTTP POST → /api/transcription/realtime/live-chunk (External - Transcription Service)
    ↓
Transcription Service (External - process chunk → WebSocket → FINAL Event)
```

---

## 🎯 สิ่งที่เพิ่มเข้ามา (CloseCaption Features)

### 1. Overlap Buffer (อัตโนมัติ)

**เมื่อ**: `CC_ENABLED=true` และ `CC_CHUNK_OVERLAP > 0`

**การทำงาน**:
- เก็บ tail 0.6s จาก chunk ก่อนหน้า
- Prepend tail ให้ chunk ใหม่ → ได้ buffer 3.6s
- ส่งเข้า transcription

**ไม่ต้องทำอะไร**: ทำงานอัตโนมัติ

---

### 2. Dedupe (อัตโนมัติ)

**เมื่อ**: `CC_ENABLED=true` และ `CC_DEDUPE_ENABLED=true`

**การทำงาน**:
- เก็บ `last_emitted_text` จาก chunk ก่อนหน้า
- หาส่วนที่ซ้ำกันระหว่างท้ายของ `last_emitted_text` กับต้นของ `new_text`
- ตัดส่วนซ้ำออก → emit เฉพาะส่วนใหม่

**ไม่ต้องทำอะไร**: ทำงานอัตโนมัติ

---

### 3. Postprocess (อัตโนมัติ)

**เมื่อ**: `CC_ENABLED=true` และ `CC_POSTPROCESS_ENABLED=true`

**การทำงาน**:
- Normalize: ลบช่องว่างซ้ำ, normalize วรรณยุกต์
- Fix Words: แก้คำเพี้ยนยอดฮิต
- Word Segmentation: ตัดคำภาษาไทย (ถ้าเปิด)

**ไม่ต้องทำอะไร**: ทำงานอัตโนมัติ

---

## 📋 Request Format (ยังเหมือนเดิม)

### HTTP POST `/api/transcription/realtime/live-chunk`

**Headers**:
```
X-Meeting-Id: {meeting_id}
X-Chunk-Index: {chunk_index}
X-Start-Time: {start_time}  # seconds
X-Duration: {duration}      # seconds (default: 3.0)
X-Audio-Format: s16le       # หรือ wav
X-Sample-Rate: 16000
X-Channels: 1
```

**Body**: Raw PCM16 audio data (96,000 bytes = 3 seconds)

**Response**: `202 Accepted`
```json
{
    "status": "accepted",
    "session_id": "live-{meeting_id}-{chunk_index}",
    "meeting_id": "{meeting_id}",
    "chunk_index": 0,
    "start_time": 0.0,
    "duration": 3.0,
    "message": "Audio chunk received. Processing in background. Caption events will be sent via WebSocket."
}
```

---

## 📡 WebSocket Events (ยังเหมือนเดิม)

### Connect to WebSocket

```
ws://localhost:8010/api/ws/captions?meeting_id={meeting_id}
```

### Receive FINAL Events

```json
{
    "type": "final",
    "meeting_id": "{meeting_id}",
    "chunk_index": 0,
    "chunk_start_ms": 0,
    "chunk_duration_ms": 3000,
    "language": "th",
    "model": "models--Vinxscribe--biodatlab-whisper-th-medium-faster",
    "provider": "faster-whisper",
    "text": "ข้อความที่แปลงได้...",
    "segments": [
        {
            "id": "seg-0-0",
            "t0_ms": 0,
            "t1_ms": 3000,
            "text": "ข้อความที่แปลงได้...",
            "confidence": 0.95,
            "is_final": true
        }
    ]
}
```

---

## ⚙️ Configuration (ตั้งค่าใน .env.runpod)

### เปิดใช้งาน CloseCaption

```bash
CC_ENABLED=true
```

### Model Configuration

```bash
CC_MODEL_SIZE=models--Vinxscribe--biodatlab-whisper-th-medium-faster
CC_BEAM_SIZE=1
CC_LANGUAGE=th  # ✅ ตั้งค่าไว้แล้ว
```

### Chunking

```bash
CC_CHUNK_HOP=3.0
CC_CHUNK_OVERLAP=0.6
```

### Features

```bash
CC_DEDUPE_ENABLED=true
CC_POSTPROCESS_ENABLED=true
CC_POSTPROCESS_NORMALIZE=true
CC_POSTPROCESS_WORD_SEG=true
```

---

## 🔍 สรุป

### 1. Language

- ✅ **ไม่ต้องกำหนด language th เพิ่ม** - ใช้ `CC_LANGUAGE=th` จาก config อัตโนมัติ
- ✅ ระบบจะใช้ language จาก `CloseCaptionConfig` เมื่อ `CC_ENABLED=true`

### 2. Flow การใช้งาน

- ✅ **Flow ยังเหมือนเดิม** - ไม่มีการเปลี่ยนแปลง
- ✅ เพิ่ม CloseCaption features (overlap, dedupe, postprocess) อัตโนมัติ
- ✅ ไม่ต้องแก้ไข Backend code

### 3. Request Format

- ✅ **ยังเหมือนเดิม** - ใช้ headers เดิม
- ✅ ไม่ต้องส่ง language parameter

### 4. WebSocket Events

- ✅ **ยังเหมือนเดิม** - รับ FINAL events ผ่าน WebSocket
- ✅ เพิ่มคุณภาพข้อความ (postprocess)

---

## 💡 หมายเหตุ

1. **Language**: ใช้ `CC_LANGUAGE=th` จาก config (ไม่ต้องส่งใน request)
2. **Flow**: ยังเหมือนเดิม - เพิ่ม features อัตโนมัติ
3. **Backend**: ไม่ต้องแก้ไข - ทำงานเหมือนเดิม
4. **Features**: Overlap, Dedupe, Postprocess ทำงานอัตโนมัติเมื่อ `CC_ENABLED=true`

---

**Last Updated**: 2026-01-12
