# ปรับปรุง Progress Tracking และ Time Tracking

## ปัญหาที่พบ

1. **Progress คลาดเคลื่อน**: มีการ update progress หลายครั้งทำให้ไม่รู้ว่า final จริงหรือไม่
   - Chunk file เสร็จหมดแล้ว -> response (แต่ยังไม่ Text Correction)
   - Text Correction -> response (update time)

2. **เวลาผสมกัน**: ไม่มีการแยกเวลาให้เห็นชัดเจนระหว่าง
   - Audio extraction time
   - Transcription time

3. **ไม่เห็น Task Breakdown**: ไม่รู้ว่ามี tasks อะไรบ้างที่ต้องทำสำหรับ 1 ไฟล์

## สิ่งที่ต้องการ

1. **แสดง Progress เป็น x/total format**: เช่น `5/23` เพื่อให้เห็นว่ามี response แล้วแต่ไฟล์ยังไม่สมบูรณ์

2. **แยกเวลาอย่างชัดเจน**:
   - Audio extraction time
   - Transcription time (ไม่รวม correction)
   - Text correction time (ถ้ามี)

3. **Task Breakdown**: แสดงรายละเอียดของ tasks ที่ต้องทำ:
   - Audio extraction (1 task)
   - Transcription chunks (N tasks)

4. **ส่ง Response ทีละ Chunk**: เสร็จ 1 chunk พร้อม text correction final ก็ส่งมาเลย (เรียงตามลำดับ)

## Implementation Plan

### Phase 1: เพิ่ม Metadata Fields

เพิ่ม fields ใหม่ใน `TranscriptionResponse` model:
- `total_chunks`: จำนวน chunks ทั้งหมด
- `completed_chunks`: จำนวน chunks ที่เสร็จแล้ว
- `total_tasks`: จำนวน tasks ทั้งหมด (1 audio extraction + N transcription chunks)
- `completed_tasks`: จำนวน tasks ที่เสร็จแล้ว
- `audio_extraction_time`: เวลาที่ใช้ extract audio (วินาที)
- `transcription_time`: เวลาที่ใช้ transcription (วินาที)
- `text_correction_time`: เวลาที่ใช้ text correction (วินาที)
- `task_breakdown`: รายละเอียดของ tasks

### Phase 2: บันทึกเวลาแยก

#### 2.1 Audio Extraction Time
- บันทึกใน `_process_audio_extraction_task()` หลังจาก extract เสร็จ
- เก็บใน task metadata เป็น `audio_extraction_time`

#### 2.2 Transcription Time
- บันทึกใน `_process_transcription_task()` หลังจาก transcription เสร็จ (ก่อน text correction)
- เก็บใน task metadata เป็น `transcription_time`

#### 2.3 Text Correction Time
- บันทึกเวลาที่ใช้ text correction แยกต่างหาก
- เก็บใน task metadata เป็น `text_correction_time`

### Phase 3: Progress Tracking

#### 3.1 Task Breakdown
- สร้าง task_breakdown list:
  ```python
  task_breakdown = [
      {"type": "audio_extraction", "status": "completed", "time": 0.92},
      {"type": "transcription_chunk", "chunk_index": 0, "status": "completed", "time": 4.11},
      ...
  ]
  ```

#### 3.2 Progress Calculation
- `total_tasks = 1 (audio extraction) + total_chunks`
- `completed_tasks = (audio extraction done ? 1 : 0) + completed_chunks`
- Progress แสดงเป็น `completed_tasks/total_tasks` format

### Phase 4: UI Improvements

ปรับปรุง `concurrency-monitor.html`:
1. แสดง progress เป็น `x/total` format แทน percentage
2. แสดง task breakdown section
3. แสดงเวลาแยกตาม phase:
   - Audio Extraction: X.X วินาที
   - Transcription: X.X วินาที
   - Text Correction: X.X วินาที

## Code Changes

### 1. Model Changes ✅
- เพิ่ม fields ใน `TranscriptionResponse` model แล้ว

### 2. Worker Changes
- `_process_audio_extraction_task()`: บันทึก `audio_extraction_time`
- `_process_transcription_task()`: บันทึก `transcription_time`, `text_correction_time`
- `_save_chunk_result()`: อัปเดต `completed_chunks`, `completed_tasks`

### 3. Service Changes
- `extract_audio()`: return extraction_time พร้อม audio_path
- `_process_transcription()`: บันทึก transcription_time แยกจาก correction_time

### 4. UI Changes
- แสดง progress เป็น `x/total`
- แสดง task breakdown
- แสดงเวลาแยกตาม phase

## Testing

1. ทดสอบ progress tracking เมื่อมีหลาย chunks
2. ทดสอบ time tracking แยกตาม phase
3. ทดสอบ UI แสดงข้อมูลถูกต้อง

