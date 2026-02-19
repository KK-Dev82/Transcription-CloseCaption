# 📋 คู่มือการดู Logs การแปลงเสียง

## 📁 Log Files ที่เกี่ยวข้อง

### 1. **main-api.log** - Logs หลักของ API
- **ขนาด**: ~2.6MB (หมุนเวียนเมื่อถึง 10MB)
- **เก็บข้อมูล**: 
  - WS ingest connections
  - WebSocket events
  - API requests
  - General application logs

### 2. **transcription.log** - Logs การแปลงเสียง
- **ขนาด**: ~6.6MB (หมุนเวียนรายวัน)
- **เก็บข้อมูล**:
  - Transcription requests
  - Model loading
  - Whisper service operations
  - Transcription results

### 3. **live-chunk.log** - Logs สำหรับ Live Chunk
- **ขนาด**: ~5.3MB (หมุนเวียนเมื่อถึง 10MB)
- **เก็บข้อมูล**:
  - Live chunk processing
  - WebSocket broadcasting
  - Real-time transcription events

---

## 🔍 วิธีดู Logs

### 1. ดู Logs แบบ Real-time (Follow)

```bash
# ดู logs การแปลงเสียง (transcription.log)
tail -f logs/transcription.log

# ดู logs WS ingest (main-api.log)
tail -f logs/main-api.log | grep "WS ingest"

# ดู logs ทั้งหมดที่เกี่ยวข้องกับการแปลง
tail -f logs/transcription.log logs/main-api.log | grep -E "transcribe|Transcribing|model"
```

### 2. ดู Logs ล่าสุด (Last N lines)

```bash
# ดู 50 บรรทัดล่าสุด
tail -50 logs/transcription.log

# ดู 100 บรรทัดล่าสุด
tail -100 logs/main-api.log
```

### 3. ค้นหา Logs เฉพาะ

```bash
# ค้นหา logs ที่เกี่ยวข้องกับ model
grep -i "model" logs/transcription.log | tail -20

# ค้นหา logs WS ingest
grep "WS ingest" logs/main-api.log | tail -20

# ค้นหา logs การแปลงเสียง
grep -E "Transcribing|transcribe" logs/transcription.log | tail -20

# ค้นหา logs ที่มี error
grep -i "error" logs/transcription.log | tail -20
```

### 4. ดู Logs ตาม Meeting ID

```bash
# ค้นหา logs ของ meeting_id เฉพาะ
grep "ffbd7598-11ea-4ca2-99d0-59616d1af0ff" logs/main-api.log | tail -30

# ค้นหา logs การแปลงเสียงของ meeting_id
grep "ffbd7598-11ea-4ca2-99d0-59616d1af0ff" logs/transcription.log | tail -30
```

### 5. ดู Logs ตามเวลา

```bash
# ดู logs ของวันนี้
grep "2026-01-20" logs/transcription.log | tail -50

# ดู logs ระหว่างเวลา
grep "2026-01-20 07:" logs/transcription.log | tail -50
```

---

## 📊 Log Patterns ที่สำคัญ

### 1. WS Ingest Connection
```
[WS ingest] ✅ Producer connected: meeting_id=..., session_id=...
```

### 2. Model Loading
```
[Faster Whisper] 🔄 Loading model: Vinxscribe/biodatlab-whisper-th-medium-faster
[Faster Whisper] 🔄 Normalized model ID: models--Vinxscribe--biodatlab-whisper-th-medium-faster → Vinxscribe/biodatlab-whisper-th-medium-faster
[Faster Whisper] ✅ Using cached model: ...
```

### 3. Transcription Start
```
[Faster Whisper] Transcribing: /tmp/tmp*.wav
   Model: Vinxscribe/biodatlab-whisper-th-medium-faster, Language: th, Device: cuda
```

### 4. Transcription Complete
```
[Faster Whisper] ✅ Transcription completed: X segments in Y.XXs
```

### 5. Audio Data Received
```
[WS ingest] 📥 Received: meeting_id=..., frames=..., bytes=..., ring_size=..., buffered=...s
```

### 6. Errors
```
[WS ingest] infer_loop error meeting_id=...: ...
[Faster Whisper] ❌ Error loading model: ...
```

---

## 🛠️ คำสั่งที่มีประโยชน์

### ดู Logs แบบรวม (Multiple files)
```bash
# ดู logs ทั้งหมดพร้อมกัน
tail -f logs/*.log

# ดู logs เฉพาะที่เกี่ยวข้องกับการแปลง
tail -f logs/transcription.log logs/main-api.log | grep -E "transcribe|model|WS ingest"
```

### นับจำนวน Logs
```bash
# นับจำนวน transcription requests
grep -c "Transcribing" logs/transcription.log

# นับจำนวน errors
grep -c "ERROR" logs/transcription.log
```

### ดู Logs แบบสรุป
```bash
# ดูสรุป logs การแปลงเสียง
grep -E "Transcribing|completed" logs/transcription.log | tail -20

# ดูสรุป WS ingest activity
grep -E "Producer connected|Received|Disconnected" logs/main-api.log | tail -20
```

---

## 📝 ตัวอย่างการใช้งาน

### ตรวจสอบว่า WS Ingest ทำงานหรือไม่
```bash
tail -f logs/main-api.log | grep "WS ingest"
```

---

## 🔧 FE CC: ตรวจสอบ WebSocket เมื่อ FE ไม่แสดงข้อความ

เมื่อฝั่ง FE ไม่แสดงข้อความ FE CC สามารถตรวจสอบได้ดังนี้:

### 1. ดู Logs แบบ Real-time
```bash
tail -f logs/main-api.log | grep "WS ingest"
```
- `Producer connected` = Producer (FE) เชื่อมต่อแล้ว
- `📥 Received` = มีการรับ PCM (พูด/เปิดไมค์)
- `Broadcast partial/final` = Backend ส่ง caption ออกไปแล้ว
- `No connections for meeting` = ไม่มี Consumer (FE ยังไม่ connect /api/ws/captions)

### 2. ทดสอบ Consumer ด้วยสคริปต์
```bash
# ใช้ meeting_id เดียวกับ FE
python scripts/test_fe_cc_websocket.py --base-url http://localhost:8010 --meeting-id YOUR_MEETING_ID
```
- ถ้าสคริปต์ได้รับ partial/final แต่ FE ไม่แสดง → ปัญหาที่ FE (การแสดงผล)
- ถ้าสคริปต์ไม่ได้รับอะไร → ตรวจว่า Producer ส่งเสียง และ meeting_id ตรงกัน

### 3. ตรวจสอบ WebSocket Status
```bash
curl http://localhost:8010/api/websocket/status
# หรือ
curl http://localhost:8010/websocket/status
```

### 4. Checklist
| รายการ | ตรวจสอบ |
|--------|----------|
| meeting_id | Producer และ Consumer ใช้ meeting_id เดียวกัน |
| ingest-audio | FE connect ไป `ws://host/api/ws/ingest-audio?meeting_id=X` |
| captions | FE connect ไป `ws://host/api/ws/captions?meeting_id=X` |
| PCM frames | Producer ส่ง PCM16 binary (พูดหรือเปิดไมค์) |
| Logs | ดู main-api.log มี `Broadcast` และไม่มี `No connections` |

### ตรวจสอบการแปลงเสียง
```bash
tail -f logs/transcription.log | grep -E "Transcribing|completed"
```

### ตรวจสอบ Model ที่ใช้
```bash
grep "Model:" logs/transcription.log | tail -10
```

### ตรวจสอบ Errors
```bash
grep -i "error" logs/*.log | tail -20
```

---

## 🔄 Log Rotation

- **main-api.log**: หมุนเวียนเมื่อถึง 10MB (เก็บ 5 backups)
- **transcription.log**: หมุนเวียนรายวัน (เก็บ 7 วัน)
- **live-chunk.log**: หมุนเวียนเมื่อถึง 10MB (เก็บ 5 backups)

Log files เก่าจะมีชื่อเป็น:
- `main-api.log.1`, `main-api.log.2`, ...
- `transcription.log.2026-01-20`, `transcription.log.2026-01-19`, ...
