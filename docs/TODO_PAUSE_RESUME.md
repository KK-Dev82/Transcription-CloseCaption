# Pause/Resume/On Hold Transcription Tasks

## สถานะ: Implemented ✅

## Endpoints

- `POST /api/v2/tasks/{task_id}/pause` - หยุดชั่วคราว (ไม่ enqueue chunk ถัดไป)
- `POST /api/v2/tasks/{task_id}/resume` - ดำเนินการต่อ (enqueue chunk ถัดไป)

## สถานะ

| สถานะ | ความหมาย |
|-------|----------|
| paused | User กด Pause — หยุดชั่วคราว |
| on_hold | ระบบ hold รอ Record เสร็จ (เมื่อ record_backlog > 0) |
| processing | กำลังแปลงเสียง |

## On Hold (Cooperative Preemption)

เมื่อมี Record ในคิว (record_backlog > 0) Upload chunks จะถูก hold — ไม่ enqueue chunk ถัดไปจนกว่า Record จะเสร็จ

- เปิด/ปิด: `ENABLE_ON_HOLD_FOR_RECORD=true` (default: true)

## หมายเหตุ

- Chunk ที่กำลังรันจะทำงานต่อจนเสร็จ (ไม่หยุดกลางคัน)
- Resume ได้ทั้ง paused และ on_hold
