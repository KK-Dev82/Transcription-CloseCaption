# รองรับ audio_extraction_time เป็น null

**วันที่:** 04-12-2025

## สรุป

ระบบรองรับกรณีที่ `audio_extraction_time` เป็น `null` เมื่อผู้ใช้ส่ง **audio file โดยตรง** (ไม่ต้อง extract audio)

---

## 1. สถานการณ์

### กรณีที่ 1: Video File
- **Flow**: Video → Audio Extraction → Transcription
- **audio_extraction_time**: มีค่า (เช่น `0.92` วินาที)
- **total_tasks**: `1 (audio extraction) + N (transcription chunks) = N+1`

### กรณีที่ 2: Audio File โดยตรง
- **Flow**: Audio → Transcription (ข้าม Audio Extraction)
- **audio_extraction_time**: `null` (ไม่มีการ extract)
- **total_tasks**: `N (transcription chunks)` เท่านั้น

---

## 2. การทำงานของระบบ

### 2.1 Routing Logic

**ไฟล์:** `app/workers/video_worker.py` - `_process_transcription_request_task()`

```python
if is_video:
    # Route to audio_extraction_queue
    # → จะบันทึก audio_extraction_time หลังจาก extract เสร็จ
elif is_audio:
    # Route directly to transcription_queue
    # → จะไม่มี audio_extraction_time (null)
```

### 2.2 Audio Extraction Worker

**ไฟล์:** `app/workers/video_worker.py` - `_process_audio_extraction_task()`

- บันทึก `audio_extraction_time` หลังจาก extract เสร็จ
- เพิ่ม audio extraction task ใน `task_breakdown`
- อัปเดต `total_tasks = 1`

**Note:** ถ้าเป็น audio file โดยตรง จะไม่ผ่าน worker นี้ → ไม่มี `audio_extraction_time`

### 2.3 Transcription Service

**ไฟล์:** `app/services/transcription_service.py` - `_process_transcription()`

- เมื่อเป็น audio file โดยตรง: ไม่มีการ extract audio → `audio_extraction_time` จะเป็น `null`
- เมื่อเป็น video file: จะ extract audio ก่อน → `audio_extraction_time` จะถูกบันทึกใน audio extraction worker

### 2.4 Progress Calculation

**ไฟล์:** `app/workers/video_worker.py` - `_save_chunk_result()`

```python
# ถ้าเป็น audio file โดยตรง: audio_extraction_done = False
audio_extraction_done = parent_task.get('audio_extraction_time') is not None
total_tasks = (1 if audio_extraction_done else 0) + total_chunks
```

**ตัวอย่าง:**
- Video file (20 chunks): `total_tasks = 1 + 20 = 21`
- Audio file (20 chunks): `total_tasks = 0 + 20 = 20`

---

## 3. Model Definition

**ไฟล์:** `app/models/transcription.py`

```python
audio_extraction_time: Optional[float] = None  # จะเป็น None ถ้าเป็น audio file โดยตรง (ไม่ต้อง extract)
```

- Type: `Optional[float]` → รองรับ `None`
- Default: `None`

---

## 4. UI Display

**ไฟล์:** `static/concurrency-monitor.html`

### 4.1 Task List Table

```javascript
${task.audio_extraction_time !== null && task.audio_extraction_time !== undefined ? 
    `<span>${formatTime(task.audio_extraction_time)}</span>` : 
    '<span style="color: #999;">-</span>'
}
```

- แสดงเวลาเมื่อมีค่า
- แสดง `-` เมื่อเป็น `null`

### 4.2 Task Cards

```javascript
${task.audio_extraction_time !== null && task.audio_extraction_time !== undefined ? `
    <div class="task-stats-row">
        <span class="label">🎬 Audio Extract:</span>
        <span class="value">${formatTime(task.audio_extraction_time)}</span>
    </div>
` : ''}
```

- แสดงแถว Audio Extract เมื่อมีค่า
- ไม่แสดงเมื่อเป็น `null`

---

## 5. Task Breakdown

### 5.1 Video File

```json
{
  "task_breakdown": [
    {
      "type": "audio_extraction",
      "status": "completed",
      "time": 0.92,
      "completed_at": "2025-12-04T17:20:00"
    },
    {
      "type": "transcription",
      "status": "completed",
      "time": 434.57,
      "chunks_count": 20,
      "completed_at": "2025-12-04T17:25:40"
    }
  ]
}
```

### 5.2 Audio File โดยตรง

```json
{
  "task_breakdown": [
    {
      "type": "transcription",
      "status": "completed",
      "time": 434.57,
      "chunks_count": 20,
      "completed_at": "2025-12-04T17:25:40"
    }
  ]
}
```

**Note:** ไม่มี audio extraction task ใน task_breakdown

---

## 6. API Response Examples

### 6.1 Video File

```json
{
  "task_id": "...",
  "status": "completed",
  "total_tasks": 21,
  "completed_tasks": 21,
  "audio_extraction_time": 0.92,
  "transcription_time": 434.57,
  "task_breakdown": [...]
}
```

### 6.2 Audio File โดยตรง

```json
{
  "task_id": "...",
  "status": "completed",
  "total_tasks": 20,
  "completed_tasks": 20,
  "audio_extraction_time": null,
  "transcription_time": 434.57,
  "task_breakdown": [...]
}
```

---

## 7. Testing

### 7.1 Test Case 1: Video File

1. ส่ง video file (`.mp4`)
2. ตรวจสอบว่า:
   - `audio_extraction_time` มีค่า (ไม่เป็น `null`)
   - `total_tasks = 1 + total_chunks`
   - `task_breakdown` มี audio extraction task

### 7.2 Test Case 2: Audio File โดยตรง

1. ส่ง audio file (`.wav`, `.mp3`)
2. ตรวจสอบว่า:
   - `audio_extraction_time` เป็น `null`
   - `total_tasks = total_chunks` (ไม่มี audio extraction task)
   - `task_breakdown` ไม่มี audio extraction task
   - UI แสดง `-` ในคอลัมน์ Audio Extract

---

## 8. Files Modified

- `app/models/transcription.py` - เพิ่ม comment ว่า `audio_extraction_time` จะเป็น `None` ถ้าเป็น audio file โดยตรง
- `app/services/transcription_service.py` - รองรับกรณี `audio_extraction_time = None`
- `app/workers/video_worker.py` - คำนวณ `total_tasks` ถูกต้องเมื่อ `audio_extraction_time` เป็น `null`
- `static/concurrency-monitor.html` - แสดง `-` เมื่อ `audio_extraction_time` เป็น `null`

---

**✅ รองรับแล้ว!**

