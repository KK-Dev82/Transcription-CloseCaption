# 📋 API สำหรับดูสถานะและผลลัพธ์ Transcription

## 1. ดูสถานะ (Status)

### 1.1 ดูสถานะและข้อมูลทั้งหมด
```http
GET /transcribe/{task_id}
```

**Response:**
```json
{
  "task_id": "xxx-xxx-xxx",
  "status": "completed",  // pending, processing, completed, failed
  "progress": 100,       // 0-100
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:05:00",
  "completed_at": "2024-01-01T00:05:00",
  "file_path": "/path/to/file.mp4",
  "language": "th",
  "total_duration": 1800.5,
  "current_stage": "finalizing",
  "current_stage_description": "กำลังจัดเก็บข้อมูล",
  "stage_progress": 100,
  "error_message": null
}
```

### 1.2 ดู Progress แบบ Real-time
```http
GET /progress/transcription/{task_id}
```

**Response:**
```json
{
  "task_id": "xxx-xxx-xxx",
  "status": "processing",
  "progress": 75,
  "current_stage": "transcribing",
  "current_stage_description": "กำลังแปลงเสียงเป็นข้อความ",
  "stage_progress": 75,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:03:45"
}
```

### 1.3 Polling API (สำหรับเช็คสถานะแบบ polling)
```http
GET /poll/task/{task_id}
```

**Response:**
```json
{
  "task_id": "xxx-xxx-xxx",
  "status": "processing",
  "progress": 50,
  "stage": "transcribing",
  "results_available": false,
  "partial_text": "ข้อความที่แปลงได้บางส่วน...",
  "chunks": [...]
}
```

---

## 2. ดู Progression (ความคืบหน้า)

### 2.1 ข้อมูล Progression ใน Status Response

เมื่อเรียก `GET /transcribe/{task_id}` จะได้ข้อมูล progression ดังนี้:

```json
{
  "progress": 75,                    // เปอร์เซ็นต์ความคืบหน้า (0-100)
  "current_stage": "transcribing",   // ขั้นตอนปัจจุบัน
  "current_stage_description": "กำลังแปลงเสียงเป็นข้อความ",
  "stage_progress": 75,              // Progress ของ stage ปัจจุบัน (0-100)
  
  // สำหรับ chunking
  "total_chunks": 10,
  "completed_chunks": 7,
  "total_tasks": 11,                 // 1 audio extraction + 10 transcription chunks
  "completed_tasks": 8,
  
  // เวลาที่ใช้ในแต่ละ phase
  "audio_extraction_time": 5.2,
  "transcription_time": 120.5,
  "text_correction_time": 2.3,
  "processing_time": 128.0,
  
  // Task breakdown
  "task_breakdown": [
    {"type": "audio_extraction", "status": "completed", "time": 5.2},
    {"type": "transcription_chunk", "status": "completed", "chunk_index": 0, "time": 12.5},
    {"type": "transcription_chunk", "status": "processing", "chunk_index": 1}
  ]
}
```

### 2.2 Stages ที่เป็นไปได้

- `pending` - รอการประมวลผล
- `downloading` - กำลังดาวน์โหลดไฟล์
- `extracting_audio` - กำลังแยกเสียงจากวิดีโอ
- `transcribing` - กำลังแปลงเสียงเป็นข้อความ
- `merging` - กำลังรวมผลลัพธ์
- `finalizing` - กำลังจัดเก็บข้อมูล
- `completed` - เสร็จสิ้น
- `failed` - ล้มเหลว

---

## 3. ดูผลลัพธ์ข้อความ (เมื่อ Status = "completed")

### 3.1 ดึงข้อความที่แปลงแล้ว (Full Text)
```http
GET /transcribe/{task_id}/text
```

**Response:**
```json
{
  "task_id": "xxx-xxx-xxx",
  "full_text": "ข้อความที่แปลงแล้วทั้งหมด...",        // ข้อความรวมทั้งหมด
  "original_text": "ข้อความดิบจาก Whisper...",         // ข้อความก่อน correction
  "corrected_text": "ข้อความหลัง correction...",       // ข้อความหลัง correction (ถ้ามี)
  "language": "th",
  "total_duration": 1800.5
}
```

### 3.2 ดึง Chunks พร้อม Timestamps
```http
GET /transcribe/{task_id}/chunks
```

**Response:**
```json
{
  "task_id": "xxx-xxx-xxx",
  "chunks": [
    {
      "start_time": 0.0,
      "end_time": 5.5,
      "text": "ข้อความส่วนแรก",
      "confidence": 0.95
    },
    {
      "start_time": 5.5,
      "end_time": 10.2,
      "text": "ข้อความส่วนที่สอง",
      "confidence": 0.92
    }
  ],
  "total_chunks": 2
}
```

### 3.3 ดึงข้อมูลทั้งหมด (รวม Text และ Chunks)
```http
GET /transcribe/{task_id}
```

**Response (เมื่อ completed):**
```json
{
  "task_id": "xxx-xxx-xxx",
  "status": "completed",
  "progress": 100,
  "full_text": "ข้อความที่แปลงแล้วทั้งหมด...",
  "original_text": "ข้อความดิบจาก Whisper...",
  "corrected_text": "ข้อความหลัง correction...",
  "chunks": [
    {
      "start_time": 0.0,
      "end_time": 5.5,
      "text": "ข้อความส่วนแรก",
      "confidence": 0.95
    }
  ],
  "completed_at": "2024-01-01T00:05:00",
  "processing_time": 128.0
}
```

---

## 4. สรุป Endpoints

| Endpoint | Method | ใช้สำหรับ | Response Fields |
|----------|--------|----------|----------------|
| `/transcribe/{task_id}` | GET | ดูสถานะและข้อมูลทั้งหมด | `status`, `progress`, `full_text`, `chunks`, `current_stage` |
| `/progress/transcription/{task_id}` | GET | ดู progress แบบ real-time | `status`, `progress`, `current_stage`, `stage_progress` |
| `/poll/task/{task_id}` | GET | Polling API | `status`, `progress`, `partial_text`, `chunks` |
| `/transcribe/{task_id}/text` | GET | ดึงข้อความที่แปลงแล้ว | `full_text`, `original_text`, `corrected_text` |
| `/transcribe/{task_id}/chunks` | GET | ดึง chunks พร้อม timestamps | `chunks[]` |

---

## 5. ข้อมูลที่เก็บใน Storage

ข้อมูลทั้งหมดถูกเก็บใน:
- **SQLite**: `storage/database.db` (ถ้า `STORAGE_TYPE=sqlite`)
- **JSON**: `storage/transcriptions/{task_id}/metadata.json` (ถ้า `STORAGE_TYPE=json`)

### Fields ที่สำคัญ:
- `status`: สถานะ (pending, processing, completed, failed)
- `progress`: เปอร์เซ็นต์ความคืบหน้า (0-100)
- `full_text`: ข้อความรวมทั้งหมด
- `corrected_text`: ข้อความหลัง correction
- `chunks`: Array ของ chunks พร้อม timestamps
- `current_stage`: ขั้นตอนปัจจุบัน
- `stage_progress`: Progress ของ stage ปัจจุบัน
- `processing_time`: เวลาที่ใช้ในการประมวลผล

---

## 6. หมายเหตุ

- **Status = "completed"** → ข้อมูล `full_text`, `corrected_text`, `chunks` จะพร้อมใช้งาน
- **Status = "processing"** → อาจมี `partial_text` สำหรับข้อความที่แปลงได้บางส่วน
- **Status = "failed"** → ตรวจสอบ `error_message` สำหรับรายละเอียดข้อผิดพลาด
- ข้อมูลจะถูกเก็บใน Storage (SQLite/JSON) และสามารถดึงได้แม้ service restart
