# TODO: Pause/Resume Transcription Tasks

## สถานะ: วางแผนสำหรับอนาคต

ฟีเจอร์ Pause/Resume สำหรับ transcription tasks ยังไม่ได้ implement

## ความต้องการ

- **Pause**: หยุดชั่วคราว task ที่กำลัง processing (queued หรือ processing)
- **Resume**: ดำเนินการต่อ task ที่ถูก pause

## ความท้าทายทางเทคนิค

1. **RQ (Redis Queue)**: RQ ไม่รองรับการ pause job ที่กำลังรันโดยตรง
   - Job ที่ `queued` สามารถลบออกจาก queue ได้ (เหมือน cancel)
   - Job ที่ `started` ต้องให้ worker ตรวจสอบ flag ก่อนทำงานต่อ

2. **Chunk-based processing**: Task หนึ่งมีหลาย chunk jobs
   - ต้อง pause/resume ทั้งชุด
   - อาจต้องเก็บ state ของ chunks ที่เสร็จแล้ว vs ที่ยังไม่เริ่ม

3. **Worker cooperation**: Worker ต้องตรวจสอบ `task:{task_id}:paused` ก่อนเริ่ม chunk ใหม่

## แนวทางที่อาจใช้

1. **Pause**:
   - ตั้ง Redis key `task:{task_id}:paused` = 1
   - Cancel jobs ที่ยัง queued อยู่ (chunks ที่ยังไม่เริ่ม)
   - Jobs ที่กำลังรันจะทำงานต่อจนเสร็จ (ไม่สามารถหยุดกลางคันได้ง่าย)

2. **Resume**:
   - ลบ key `task:{task_id}:paused`
   - Re-enqueue chunks ที่ยังไม่เสร็จ (ใช้ chunks_metadata)

## Endpoints ที่จะเพิ่ม (เมื่อ implement)

- `POST /api/v2/tasks/{task_id}/pause` - หยุดชั่วคราว
- `POST /api/v2/tasks/{task_id}/resume` - ดำเนินการต่อ

## หมายเหตุ

- Cancel และ Retry ได้ implement แล้ว (ดู README หรือ API docs)
- Pause/Resume เป็น nice-to-have สำหรับ use case ที่ต้องการควบคุมการประมวลผลแบบละเอียด
