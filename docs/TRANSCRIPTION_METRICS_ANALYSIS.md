# 📊 การวิเคราะห์ข้อมูล Metrics สำหรับ Transcription Service

**วันที่สร้าง**: 2024-12-05  
**Purpose**: วิเคราะห์ข้อมูล Metrics ที่มีอยู่และส่วนที่ต้องปรับปรุง

---

## 📋 สารบัญ

1. [ข้อมูลที่มีอยู่แล้ว](#ข้อมูลที่มีอยู่แล้ว)
2. [ข้อมูลที่ต้องเพิ่ม/ปรับปรุง](#ข้อมูลที่ต้องเพิ่มปรับปรุง)
3. [สถานะการบอกสถานะ](#สถานะการบอกสถานะ)
4. [ตัวอย่างข้อมูล Metrics](#ตัวอย่างข้อมูล-metrics)
5. [ข้อเสนอแนะ](#ข้อเสนอแนะ)

---

## ✅ ข้อมูลที่มีอยู่แล้ว

### 1. ระยะเวลาในการแปลง (Transcription Time)

**Fields:**
- ✅ `transcription_time` - เวลาที่ใช้ transcription (วินาที)
- ✅ `audio_extraction_time` - เวลาที่ใช้ extract audio (วินาที)
- ✅ `text_correction_time` - เวลาที่ใช้ text correction (วินาที)
- ✅ `time_used` / `processing_time` - เวลารวมทั้งหมด (วินาที)

**Location:**
- `app/models/transcription.py` - TranscriptionResponse model
- `app/services/transcription_service.py` - บันทึกเมื่อ transcription เสร็จ
- `app/api/progress.py` - คำนวณ elapsed time

**Example:**
```json
{
  "audio_extraction_time": 0.92,
  "transcription_time": 434.57,
  "text_correction_time": null,
  "time_used": 435.49
}
```

### 2. เวลาที่เหลือ (Estimated Time Remaining)

**Status:** ✅ มีการคำนวณอยู่แล้ว

**Location:**
- `app/api/progress.py` - คำนวณจาก progress และ elapsed time
- `senate-backend/src/Shorthand.Api/Controllers/TranscriptionController.cs` - Backend คำนวณ

**Calculation:**
```python
# ใน progress.py
if progress > 0 and progress < 100:
    estimated_total = elapsed_seconds / (progress / 100)
    remaining = estimated_total - elapsed_seconds
    estimated_remaining_seconds = max(0, int(remaining))
```

**Example:**
```json
{
  "elapsed_seconds": 120,
  "progress": 50,
  "estimated_remaining_seconds": 120,
  "estimated_remaining_formatted": "2:00"
}
```

### 3. สถานะ (Status Messages)

**Fields:**
- ✅ `status` - สถานะหลัก (pending, processing, completed, failed)
- ✅ `stage` - ขั้นตอนที่กำลังทำ (รอการประมวลผล, กำลังประมวลผล, ฯลฯ)
- ✅ `description` - คำอธิบายสถานะ

**Status Values:**
- `pending` - รอการประมวลผล
- `processing` - กำลังประมวลผล
- `processing_chunk_X_of_Y` - กำลังประมวลผล chunk X/Y
- `merging_results` - กำลังรวมผลลัพธ์
- `finalizing` - กำลังจัดเก็บข้อมูล
- `completed` - เสร็จสิ้น
- `failed` - เกิดข้อผิดพลาด

**Location:**
- `app/api/progress.py` - สร้าง stage และ description จาก status

**Example:**
```json
{
  "status": "processing_chunk_3_of_10",
  "stage": "กำลังประมวลผล chunk 3/10",
  "description": "แปลงเสียงส่วนที่ 3 จากทั้งหมด 10 ส่วน"
}
```

### 4. จำนวน Chunk และ Tasks

**Fields:**
- ✅ `total_chunks` - จำนวน chunks ทั้งหมด
- ✅ `completed_chunks` - จำนวน chunks ที่เสร็จแล้ว
- ✅ `total_tasks` - จำนวน tasks ทั้งหมด (1 audio extraction + N chunks)
- ✅ `completed_tasks` - จำนวน tasks ที่เสร็จแล้ว

**Location:**
- `app/models/transcription.py` - TranscriptionResponse model
- `app/workers/async/utils.py` - อัปเดตเมื่อ chunk เสร็จ
- `app/services/transcription_service.py` - บันทึกเมื่อ transcription เสร็จ

**Example:**
```json
{
  "total_chunks": 23,
  "completed_chunks": 5,
  "total_tasks": 24,
  "completed_tasks": 6
}
```

### 5. Task Breakdown (รายละเอียด Tasks)

**Fields:**
- ✅ `task_breakdown` - รายละเอียดของ tasks แต่ละ task

**Structure:**
```json
{
  "task_breakdown": [
    {
      "type": "audio_extraction",
      "status": "completed",
      "time": 0.92,
      "completed_at": "2024-12-05T10:00:00"
    },
    {
      "type": "transcription_chunk",
      "chunk_index": 0,
      "status": "completed",
      "time": 12.5,
      "completed_at": "2024-12-05T10:00:15"
    }
  ]
}
```

---

## ⚠️ ข้อมูลที่ต้องเพิ่ม/ปรับปรุง

### 1. Status Messages ที่ละเอียดขึ้น

**ปัญหาปัจจุบัน:**
- Status เป็นแค่ string เช่น "processing_chunk_3_of_10"
- ไม่บอกชัดเจนว่า "กำลังแยกเสียง" หรือ "กำลังแปลงเสียง"

**ข้อเสนอแนะ:**
- เพิ่ม `current_stage` field ที่บอกชัดเจน:
  - `"downloading_file"` - กำลังดาวน์โหลดไฟล์
  - `"extracting_audio"` - กำลังแยกเสียง
  - `"transcribing_chunk_1"` - กำลังแปลงเสียง chunk 1
  - `"merging_results"` - กำลังรวมผลลัพธ์

### 2. เวลาที่เหลือ (Estimated Time Remaining)

**สถานะ:** ✅ มีการคำนวณอยู่แล้ว แต่ควรปรับปรุง

**ปัญหาปัจจุบัน:**
- คำนวณจาก progress percentage เท่านั้น
- ไม่คำนึงถึง phase (audio extraction vs transcription)
- ไม่คำนึงถึง chunks ที่เหลือ

**ข้อเสนอแนะ:**
- คำนวณจาก chunks ที่เหลือ (ถ้าใช้ chunking)
- คำนวณแยก phase (ถ้า audio extraction เสร็จแล้ว ให้คำนวณจาก transcription time เท่านั้น)

### 3. Metrics สำหรับการวิเคราะห์

**ข้อมูลที่มีอยู่แล้ว:**
- ✅ Processing times (audio extraction, transcription)
- ✅ Progress tracking (chunks, tasks)
- ✅ Status tracking

**ข้อมูลที่ควรเพิ่ม:**
- ⚠️ **Average time per chunk** - เวลาเฉลี่ยต่อ chunk
- ⚠️ **Queue wait time** - เวลารอใน queue
- ⚠️ **Throughput** - จำนวน chunks ต่อวินาที
- ⚠️ **Resource usage** - GPU usage, Memory usage

---

## 📊 สถานะการบอกสถานะ

### Current Status Messages

**1. Stage Mapping (app/api/progress.py):**

| Status | Stage | Description |
|--------|-------|-------------|
| `pending` | รอการประมวลผล | กำลังเตรียมไฟล์ |
| `processing` | กำลังประมวลผล | กำลังแปลงเสียงเป็นข้อความ |
| `processing_chunk_X_of_Y` | กำลังประมวลผล chunk X/Y | แปลงเสียงส่วนที่ X จากทั้งหมด Y ส่วน |
| `merging_results` | กำลังรวมผลลัพธ์ | รวมข้อความจากทุกส่วน |
| `finalizing` | กำลังจัดเก็บข้อมูล | บันทึกผลลัพธ์สุดท้าย |
| `completed` | เสร็จสิ้น | การแปลงเสียงเป็นข้อความเสร็จสมบูรณ์ |
| `failed` | เกิดข้อผิดพลาด | การประมวลผลล้มเหลว |

### ข้อเสนอแนะ: เพิ่ม Stage Messages ที่ละเอียดขึ้น

**เพิ่ม Fields:**
- `current_stage` - ขั้นตอนปัจจุบัน (downloading, extracting_audio, transcribing, merging)
- `current_stage_description` - คำอธิบายขั้นตอนปัจจุบัน

**Example:**
```json
{
  "status": "processing",
  "current_stage": "extracting_audio",
  "current_stage_description": "กำลังแยกเสียงจากวิดีโอ (30% เสร็จ)",
  "progress": 30
}
```

---

## 📈 ตัวอย่างข้อมูล Metrics

### Full Metrics Response

```json
{
  "task_id": "abc-123-def",
  "status": "processing",
  
  // Progress Tracking
  "progress": 45,
  "total_chunks": 23,
  "completed_chunks": 10,
  "total_tasks": 24,
  "completed_tasks": 11,
  
  // Status Information
  "current_stage": "transcribing",
  "current_stage_description": "กำลังแปลงเสียง chunk 10/23",
  "stage": "กำลังประมวลผล chunk 10/23",
  "description": "แปลงเสียงส่วนที่ 10 จากทั้งหมด 23 ส่วน",
  
  // Time Tracking
  "created_at": "2024-12-05T10:00:00",
  "started_at": "2024-12-05T10:00:05",
  "updated_at": "2024-12-05T10:05:30",
  "elapsed_seconds": 330,
  "elapsed_formatted": "5:30",
  
  // Estimated Time
  "estimated_remaining_seconds": 400,
  "estimated_remaining_formatted": "6:40",
  "estimated_total_seconds": 730,
  "estimated_total_formatted": "12:10",
  
  // Processing Times (เมื่อเสร็จแล้ว)
  "audio_extraction_time": 0.92,
  "transcription_time": 329.08,
  "text_correction_time": null,
  "time_used": 330.0,
  
  // Task Breakdown
  "task_breakdown": [
    {
      "type": "audio_extraction",
      "status": "completed",
      "time": 0.92,
      "completed_at": "2024-12-05T10:00:06"
    },
    {
      "type": "transcription_chunk",
      "chunk_index": 0,
      "status": "completed",
      "time": 12.5,
      "completed_at": "2024-12-05T10:00:18"
    },
    {
      "type": "transcription_chunk",
      "chunk_index": 1,
      "status": "completed",
      "time": 11.8,
      "completed_at": "2024-12-05T10:00:30"
    }
  ],
  
  // File Information
  "file_name": "video.mp4",
  "file_path": "/path/to/video.mp4",
  "total_duration": 690.0,
  "language": "th",
  
  // Resource Information (ถ้ามี)
  "queue_wait_time": 5.2,
  "average_chunk_time": 12.3,
  "chunks_per_second": 0.03
}
```

---

## 💡 ข้อเสนอแนะ

### 1. เพิ่ม Status Messages ที่ละเอียดขึ้น

**เพิ่ม Fields ใน TranscriptionResponse:**

```python
# app/models/transcription.py
class TranscriptionResponse(BaseModel):
    # ... existing fields ...
    
    # Detailed Stage Information
    current_stage: Optional[str] = None  # "downloading", "extracting_audio", "transcribing", "merging"
    current_stage_description: Optional[str] = None  # "กำลังแยกเสียง (30% เสร็จ)"
    stage_progress: Optional[int] = None  # Progress ของ stage ปัจจุบัน (0-100)
```

**Update Status Messages:**

```python
# app/services/transcription_service.py
task_data['current_stage'] = 'extracting_audio'
task_data['current_stage_description'] = 'กำลังแยกเสียงจากวิดีโอ'
task_data['stage_progress'] = 50  # ถ้ารู้ progress ของ extraction
```

### 2. ปรับปรุง Estimated Time Remaining

**คำนวณจาก Chunks ที่เหลือ:**

```python
# app/api/progress.py
def calculate_estimated_remaining(task_data):
    if task_data.get('total_chunks') and task_data.get('completed_chunks'):
        total_chunks = task_data['total_chunks']
        completed_chunks = task_data['completed_chunks']
        
        if completed_chunks > 0:
            # คำนวณเวลาที่ใช้ต่อ chunk
            elapsed = task_data.get('elapsed_seconds', 0)
            avg_time_per_chunk = elapsed / completed_chunks
            
            # คำนวณเวลาที่เหลือ
            remaining_chunks = total_chunks - completed_chunks
            estimated_remaining = avg_time_per_chunk * remaining_chunks
            
            return {
                "estimated_remaining_seconds": int(estimated_remaining),
                "estimated_remaining_formatted": format_time(estimated_remaining),
                "average_chunk_time": avg_time_per_chunk
            }
    
    # Fallback: คำนวณจาก progress percentage
    # ... existing calculation ...
```

### 3. เพิ่ม Metrics สำหรับการวิเคราะห์

**เพิ่ม Fields:**

```python
# app/models/transcription.py
class TranscriptionResponse(BaseModel):
    # ... existing fields ...
    
    # Performance Metrics
    queue_wait_time: Optional[float] = None  # เวลารอใน queue (วินาที)
    average_chunk_time: Optional[float] = None  # เวลาเฉลี่ยต่อ chunk (วินาที)
    chunks_per_second: Optional[float] = None  # จำนวน chunks ต่อวินาที
    throughput_chars_per_second: Optional[float] = None  # จำนวนตัวอักษรต่อวินาที
```

### 4. บันทึกข้อมูลลง PostgreSQL (สำหรับ Metrics)

**ปัจจุบัน:** เก็บใน JSONStorage (ไฟล์ JSON)

**ข้อเสนอแนะ:** 
- ✅ Backend บันทึกข้อมูลลง PostgreSQL อยู่แล้ว (TranscriptionJobs, TranscriptionResults)
- ⚠️ อาจต้องเพิ่ม fields สำหรับ metrics:
  - `AudioExtractionTimeSeconds`
  - `TranscriptionTimeSeconds`
  - `TotalChunks`
  - `CompletedChunks`
  - `TaskBreakdown` (JSONB)

---

## ✅ สรุป

### ข้อมูลที่มีอยู่แล้ว

1. ✅ **ระยะเวลาในการแปลง**
   - `transcription_time`
   - `audio_extraction_time`
   - `time_used`

2. ✅ **เวลาที่เหลือ**
   - `estimated_remaining_seconds`
   - คำนวณจาก progress และ elapsed time

3. ✅ **สถานะ**
   - `status` - สถานะหลัก
   - `stage` - ขั้นตอนที่กำลังทำ
   - `description` - คำอธิบาย

4. ✅ **จำนวน Chunk และ Tasks**
   - `total_chunks`, `completed_chunks`
   - `total_tasks`, `completed_tasks`

5. ✅ **Task Breakdown**
   - `task_breakdown` - รายละเอียด tasks

### ข้อมูลที่ควรปรับปรุง

1. ⚠️ **Status Messages ที่ละเอียดขึ้น**
   - เพิ่ม `current_stage` ที่บอกชัดเจนว่า "กำลังแยกเสียง" หรือ "กำลังแปลงเสียง"
   - เพิ่ม `current_stage_description` สำหรับคำอธิบาย

2. ⚠️ **Estimated Time Remaining**
   - ปรับปรุงให้คำนวณจาก chunks ที่เหลือ (ถ้าใช้ chunking)
   - คำนวณแยก phase (audio extraction vs transcription)

3. ⚠️ **Metrics เพิ่มเติม**
   - Average time per chunk
   - Queue wait time
   - Throughput (chunks per second)

---

## 📝 Recommendations

### Priority 1: Status Messages

**เพิ่ม Fields:**
```python
current_stage: Optional[str] = None  # "downloading", "extracting_audio", "transcribing", "merging"
current_stage_description: Optional[str] = None
stage_progress: Optional[int] = None
```

**Update ใน Workers:**
- Audio Extraction: `current_stage = "extracting_audio"`
- Transcription: `current_stage = "transcribing"`
- Merging: `current_stage = "merging"`

### Priority 2: Estimated Time Remaining

**ปรับปรุง Calculation:**
- ใช้ chunks ที่เหลือ (ถ้าใช้ chunking)
- คำนวณแยก phase

### Priority 3: Metrics สำหรับการวิเคราะห์

**เพิ่ม Fields:**
- `queue_wait_time`
- `average_chunk_time`
- `chunks_per_second`
- `throughput_chars_per_second`

---

**Last Updated**: 2024-12-05  
**Status**: Analysis Complete ✅

