# Pause / Resume / On Hold Implementation Plan

## สถานะที่รองรับ

| สถานะ | ความหมาย | Trigger |
|-------|----------|---------|
| paused | หยุดชั่วคราว (User กด Pause) | User |
| on_hold | รอ Record เสร็จ (ระบบ hold ให้) | System |
| processing | กำลังแปลงเสียง | - |

## Flow

```
Processing → (User Pause) → Paused
Paused     → (User Resume) → Processing (enqueue chunk ถัดไป)

Processing → (Record backlog > 0, chunk เสร็จ) → On Hold (ไม่ enqueue chunk ถัดไป)
On Hold    → (Record backlog == 0) → Processing (enqueue chunk ถัดไป)
```

## Redis Keys

| Key | ค่า | ความหมาย |
|-----|-----|----------|
| `task:{task_id}:paused` | 1 | User กด Pause |
| `task:{task_id}:on_hold` | 1 | ระบบ hold รอ Record |
| `tasks:on_hold` | Set of task_id | Tasks ที่รอ release (สำหรับ iterate ตอน release) |

## Implementation Steps

### Phase 1: Pause
1. API `POST /api/v2/tasks/{task_id}/pause` — ตั้ง `task:{task_id}:paused=1`
2. rq_worker: เมื่อ chunk เสร็จ ก่อน enqueue ถัดไป → ตรวจ `paused` ถ้าใช่ → ไม่ enqueue, อัปเดต status=paused
3. Chunk ที่กำลังรันจะทำงานต่อจนเสร็จ (ไม่หยุดกลางคัน)

### Phase 2: Resume
1. API `POST /api/v2/tasks/{task_id}/resume` — ลบ `task:{task_id}:paused`
2. เรียก `enqueue_next_chunk_for_task(task_id)` — หา chunk ถัดไปจาก chunks_metadata แล้ว enqueue

### Phase 3: On Hold ✅
1. `get_record_backlog_count()` ใน redis_queue_service ✅
2. **Preprocess:** เมื่อ preprocess เสร็จ ก่อน enqueue chunks แรก → ตรวจ `record_backlog > 0` ถ้าใช่ → ไม่ enqueue, ตั้ง on_hold ทันที ✅ (แก้ "ติด Job" — Upload chunks รอ slot ไม่ได้รัน)
3. **Chunk completion:** เมื่อ Upload chunk เสร็จ ก่อน enqueue ถัดไป → ตรวจ `record_backlog > 0` ถ้าใช่ → ไม่ enqueue, ตั้ง on_hold ✅
4. เมื่อ chunk ใดๆ เสร็จ → `_try_release_on_hold_tasks()` ตรวจ `record_backlog == 0` ถ้าใช่ → วน `tasks:on_hold` แล้ว enqueue chunk ถัดไป ✅

### Env
- `ENABLE_ON_HOLD_FOR_RECORD=true` — เปิด/ปิด On Hold (default: true)
