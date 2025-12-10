# Stuck Tasks Fix - Comprehensive Solution

## ปัญหา

Tasks ติดค้างในสถานะ "transcribing" หรือ "processing" โดยไม่มี progress หรือ completion ทำให้:
- ระบบล่มเพราะ tasks ค้างสะสม
- ต้อง restart service เพื่อแก้ไข (ไม่ sustainable)
- ไม่ทราบสาเหตุว่าทำไม task ติดค้าง

## สาเหตุหลัก

1. **Segments Processing Hang**: Generator จาก faster-whisper ไม่ yield หรือ hang ใน loop
2. **ไม่มี Timeout Protection**: Handlers ไม่มี timeout protection ทำให้ hang ได้
3. **ไม่มี Task Tracking**: ไม่มีการ track processing time และ detect stuck tasks
4. **ไม่มี Retry Mechanism**: เมื่อ task ติดค้าง ไม่มีวิธีจัดการอัตโนมัติ

## การแก้ไข

### 1. Task Tracking System (`app/workers/async/utils.py`)

เพิ่มระบบ tracking เพื่อ:
- Track task processing time
- Detect stuck tasks (no heartbeat for threshold time)
- Monitor task progress

**Features:**
- `track_task_start()`: เริ่ม track task
- `track_task_heartbeat()`: อัพเดท heartbeat (แสดงว่ายังทำงานอยู่)
- `track_task_complete()`: จบ tracking
- `get_stuck_tasks()`: ตรวจสอบ stuck tasks

**Configuration:**
- `TASK_TIMEOUT_SECONDS`: Default timeout สำหรับ tasks (default: 1800s = 30 min)
- `STUCK_TASK_THRESHOLD_SECONDS`: Threshold สำหรับ detect stuck (default: 600s = 10 min)

### 2. Timeout Protection (`app/workers/async/handlers.py`)

เพิ่ม timeout protection ใน `handle_transcription()`:
- ใช้ `asyncio.wait_for()` เพื่อ enforce timeout
- Configuration: `TRANSCRIPTION_PROCESSING_TIMEOUT_SECONDS` (default: 1800s)
- เมื่อ timeout จะ mark task as failed และ raise exception (trigger message nack)

### 3. Improved Segments Processing (`app/services/whisper_providers/faster_whisper_provider.py`)

ปรับปรุง segments processing:
- เพิ่ม progress tracking และ logging
- Detect thread hang (no progress for threshold time)
- Better error handling และ timeout detection
- Log progress ทุก 3 วินาที

**Improvements:**
- Track segment collection progress
- Detect thread hang (no progress for 30 seconds)
- Better timeout handling
- More detailed logging

### 4. Stuck Tasks Monitor (`app/workers/async/video_worker.py`)

Background task เพื่อ monitor และจัดการ stuck tasks:
- ตรวจสอบทุก 60 วินาที (configurable via `STUCK_TASK_CHECK_INTERVAL_SECONDS`)
- Auto-mark stuck tasks as failed
- Log warnings สำหรับ stuck tasks

**Process:**
1. Check stuck tasks จาก `utils.get_stuck_tasks()`
2. Mark stuck tasks as failed
3. Log detailed information
4. (Optional) Re-queue tasks (future enhancement)

### 5. RabbitMQ Communication Verification

**Prefetch Count:**
- Set to `1` via `TRANSCRIPTION_REQUEST_PREFETCH_COUNT=1`
- Worker รับ message ทีละ 1 ตัว
- Concurrency ถูกควบคุมด้วย `GPU_CONCURRENCY` semaphore

**Acknowledgment:**
- ใช้ `async with message.process()` ซึ่ง:
  - Auto-ack เมื่อ handler สำเร็จ
  - Auto-nack เมื่อเกิด exception
  - Message จะไม่ถูก requeue อัตโนมัติ (ต้อง handle manual)

**Message Flow:**
1. Worker รับ message จาก queue (prefetch=1)
2. Process message ใน handler
3. ถ้าสำเร็จ: message auto-ack → worker รับ message ใหม่ได้ทันที
4. ถ้าล้มเหลว: message auto-nack → ส่งไป DLQ (ถ้ามี DLX configured)

## Configuration

### Environment Variables

```bash
# Task Timeout
TASK_TIMEOUT_SECONDS=1800  # Default timeout สำหรับ tasks (30 min)
TRANSCRIPTION_PROCESSING_TIMEOUT_SECONDS=1800  # Timeout สำหรับ transcription processing

# Stuck Task Detection
STUCK_TASK_THRESHOLD_SECONDS=600  # Threshold สำหรับ detect stuck (10 min)
STUCK_TASK_CHECK_INTERVAL_SECONDS=60  # Interval สำหรับ check stuck tasks (60s)

# RabbitMQ Prefetch
TRANSCRIPTION_REQUEST_PREFETCH_COUNT=1  # Prefetch count = 1 (process one at a time)
TRANSCRIPTION_PREFETCH_COUNT=1  # Backward compatibility

# GPU Concurrency
GPU_CONCURRENCY=2  # Number of concurrent GPU tasks (controlled by semaphore)
```

## Monitoring

### Task Tracking

ทุก task จะถูก track โดย:
- `started_at`: เวลาที่เริ่ม process
- `last_heartbeat`: เวลาที่อัพเดทล่าสุด (อัพเดททุก 5 วินาทีจาก monitor)
- `status`: 'processing', 'completed', 'failed'

### Logs

- `📊 Task heartbeat`: แสดงว่า task ยังทำงานอยู่
- `⚠️  Found X stuck tasks`: พบ stuck tasks
- `⏱️  Transcription processing TIMEOUT`: Timeout ระหว่าง processing
- `❌ Segments collection timeout`: Timeout ระหว่าง segments collection

## Testing

### Verify Fix

1. **Task Tracking:**
   ```bash
   # Check logs for task tracking
   tail -f /tmp/video-worker.log | grep "📊 Task"
   ```

2. **Timeout Protection:**
   ```bash
   # Check for timeout logs
   tail -f /tmp/video-worker.log | grep "TIMEOUT"
   ```

3. **Stuck Tasks Detection:**
   ```bash
   # Check for stuck tasks warnings
   tail -f /tmp/video-worker.log | grep "stuck tasks"
   ```

### Expected Behavior

- Tasks ไม่ติดค้างนานเกิน 10 นาที (จะถูก detect และ mark as failed)
- Timeout logs แสดงเมื่อ task timeout
- Stuck tasks monitor ทำงานทุก 60 วินาที
- Tasks ที่ timeout จะถูก mark as failed อัตโนมัติ

## Future Enhancements

1. **Re-queue Mechanism**: Re-queue stuck tasks เพื่อให้ worker อื่นลองประมวลผล
2. **Metrics Export**: Export metrics สำหรับ monitoring (Prometheus, etc.)
3. **Alert System**: ส่ง alert เมื่อมี stuck tasks มาก
4. **Auto-recovery**: Auto-restart worker เมื่อ detect stuck tasks มากเกินไป

## Notes

- **ไม่ควร kill worker ทันที** เมื่อเจอ stuck tasks - ใช้ auto-detection และ mark as failed แทน
- **Prefetch count = 1** เพื่อให้ worker รับ message ทีละตัว และ process ตาม `GPU_CONCURRENCY`
- **Message acknowledgment** ทำงานอัตโนมัติผ่าน `async with message.process()`
- **Async ไม่ conflict** - ทุกอย่างใช้ async/await ไม่มี thread safety issues

