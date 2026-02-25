# แนวทางการปรับปรุง Frontend (FE)

เอกสารนี้สรุปแนวทางสำหรับการรับสถานะ task, Cancel, Retry และ Resubmit ในฝั่ง Frontend

---

## 1. การรับสถานะ (Status Polling / Real-time)

### API Endpoints ที่ใช้

| Use Case | Endpoint | Format |
|----------|----------|--------|
| Poll progress (เบา) | `GET /api/v2/tasks/{task_id}?format=progress` | `status`, `progress`, `current_stage`, `current_stage_description` |
| ดูรายละเอียดเต็ม | `GET /api/v2/tasks/{task_id}?format=full` | ครบทุก field รวม `full_text`, `segments` |
| รายการ tasks | `GET /api/v2/tasks?limit=50&status=processing` | รายการ tasks พร้อม filter |

### สถานะที่ควรรองรับ

| Status | ความหมาย | สี/ไอคอนแนะนำ |
|--------|----------|----------------|
| `queued` | รอคิว | สีเทา |
| `pending` | รอ preprocess | สีเทา |
| `processing` | กำลังดำเนินการ | สีเหลือง/น้ำเงิน |
| `on_hold` | ถูก hold (รอ Record ก่อน) | สีส้ม |
| `completed` | เสร็จสมบูรณ์ | สีเขียว |
| `failed` | ล้มเหลว | สีแดง |
| `cancelled` | ยกเลิก | สีเทา |
| `stopped` | หยุดโดยผู้ใช้ | สีเทา |

### แนวทาง Polling

1. **Interval**: 5–10 วินาที สำหรับ tasks ที่ `processing` หรือ `queued`
2. **หยุด Poll**: เมื่อ `status` เป็น `completed`, `failed`, `cancelled`, `stopped`
3. **แสดง `current_stage`**: เช่น "Preprocessing", "Transcribing chunk 3/10", "Aggregating" เพื่อให้ผู้ใช้เข้าใจความคืบหน้า
4. **Stuck detection**: ถ้า `processing` ค้างเกิน 15–30 นาที โดย `progress` ไม่เปลี่ยน แสดงปุ่ม Retry

### ตัวอย่าง Response (format=progress)

```json
{
  "task_id": "abc-123",
  "status": "processing",
  "progress": 90,
  "current_stage": "aggregating",
  "current_stage_description": "รวมผล transcription",
  "updated_at": "2025-02-25T14:30:00Z"
}
```

---

## 2. ปุ่ม Cancel

### API

```
POST /api/v2/tasks/{task_id}/cancel
```

หรือ (legacy):

```
DELETE /api/transcribe/{task_id}
```

**หมายเหตุ**: ควรใช้ `POST /api/v2/tasks/{task_id}/cancel` เป็นหลัก เพราะเป็น unified API

### Response สำเร็จ

```json
{
  "success": true,
  "cancelled": true,
  "message": "ยกเลิก task สำเร็จ",
  "task_id": "abc-123",
  "status": "cancelled",
  "cancelled_jobs": 3,
  "redis_keys_deleted": 5
}
```

### Response เมื่อ cancel ไม่ได้ (task เสร็จแล้ว)

```json
{
  "success": true,
  "cancelled": false,
  "message": "Task อยู่ในสถานะ completed แล้ว ไม่สามารถยกเลิกได้",
  "status": "completed"
}
```

### แนวทาง FE

1. **แสดงปุ่ม Cancel** เฉพาะเมื่อ `status` เป็น `queued`, `pending`, `processing`, `on_hold`
2. **Confirm dialog**: ยืนยันก่อน cancel เพราะเป็นการยกเลิกถาวร
3. **หลัง Cancel สำเร็จ**:
   - อัปเดต UI ให้ status เป็น `cancelled` ทันที
   - หยุด polling สำหรับ task นี้
4. **Error handling**: แสดงข้อความจาก `detail` หรือ `message` ถ้า API คืน 4xx/5xx

### ตัวอย่างโค้ด (fetch)

```javascript
async function cancelTask(apiBaseUrl, taskId) {
  const res = await fetch(`${apiBaseUrl}/api/v2/tasks/${taskId}/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  const data = await res.json().catch(() => ({}));
  if (res.ok && data.cancelled) {
    return { success: true, status: 'cancelled' };
  }
  return { success: false, message: data.message || data.detail || 'Cancel failed' };
}
```

---

## 3. ปุ่ม Retry

### API

```
POST /api/v2/tasks/{task_id}/retry
```

### กรณีที่ Retry รองรับ

| Status | การทำงาน |
|--------|----------|
| `failed` | ล้าง Redis + re-enqueue preprocess ใหม่ (ใช้ task เดิม) |
| `processing` (stuck) | ใช้ StuckTaskMonitor แก้ไข (re-enqueue chunks ที่หาย) |

### Response สำเร็จ (Failed)

```json
{
  "success": true,
  "message": "Task abc-123 retry initiated (ใช้ task เดิม)",
  "retried": true,
  "status": "queued",
  "preprocess_job_id": "abc-123_preprocess"
}
```

### Response สำเร็จ (Stuck)

```json
{
  "success": true,
  "message": "Task abc-123 retry initiated (stuck fix)",
  "fixed": true,
  "status": "queued"
}
```

### Response เมื่อไม่ stuck

```json
{
  "success": true,
  "message": "Task abc-123 is not stuck",
  "fixed": false,
  "status": "processing",
  "progress": 90
}
```

### แนวทาง FE

1. **แสดงปุ่ม Retry** เมื่อ:
   - `status === 'failed'` หรือ
   - `status === 'processing'` และค้างนาน (เช่น > 15 นาที โดย progress ไม่เปลี่ยน)
2. **Confirm dialog**: ยืนยันก่อน retry
3. **หลัง Retry สำเร็จ**:
   - อัปเดต status เป็น `queued` (หรือ `processing` ถ้า stuck fix ทำงานทันที)
   - เริ่ม polling ใหม่
4. **Error cases**:
   - `400`: Task ไม่มี `file_path` หรือไฟล์หาย
   - `404`: ไม่พบ task

### ตัวอย่างโค้ด

```javascript
async function retryTask(apiBaseUrl, taskId) {
  const res = await fetch(`${apiBaseUrl}/api/v2/tasks/${taskId}/retry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  const data = await res.json().catch(() => ({}));
  if (res.ok && data.success) {
    return { success: true, status: data.status || 'queued', message: data.message };
  }
  return { success: false, message: data.detail || data.message || 'Retry failed' };
}
```

---

## 4. ปุ่ม Resubmit

### API

```
POST /api/v2/tasks/{task_id}/resubmit
```

### ความแตกต่าง Retry vs Resubmit

| | Retry | Resubmit |
|---|-------|----------|
| Task ID | ใช้ task เดิม | สร้าง task ใหม่ |
| Use case | แก้ task ที่ fail/stuck | ส่ง transcription ใหม่จากไฟล์เดิม |
| ผลลัพธ์ | task เดิมกลับมา queued | ได้ `new_task_id` ใหม่ |

### Response สำเร็จ

```json
{
  "success": true,
  "message": "Task resubmitted successfully",
  "original_task_id": "abc-123",
  "new_task_id": "xyz-456",
  "status": "queued",
  "file_path": "/path/to/audio.wav",
  "preprocess_job_id": "xyz-456_preprocess",
  "chunk_group": false
}
```

**สำคัญ**: หลัง Resubmit ต้องใช้ `new_task_id` ในการ polling — ไม่ใช่ `original_task_id`

### แนวทาง FE

1. **แสดงปุ่ม Resubmit** เมื่อ `status` เป็น `failed`, `cancelled`, `stopped` (หรือ `completed` ถ้าต้องการส่งใหม่)
2. **หลัง Resubmit สำเร็จ**:
   - ใช้ `new_task_id` เป็น task หลักในการติดตาม
   - แสดงข้อความว่า "ส่งใหม่แล้ว Task ID: xyz-456"
   - เริ่ม polling สำหรับ `new_task_id`
3. **Error cases**:
   - `400`: Task ไม่มี `file_path` (หรือ `file_paths` สำหรับ chunk_group)
   - `404`: ไม่พบไฟล์ หรือ task ไม่พบ

### ตัวอย่างโค้ด

```javascript
async function resubmitTask(apiBaseUrl, taskId) {
  const res = await fetch(`${apiBaseUrl}/api/v2/tasks/${taskId}/resubmit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  const data = await res.json().catch(() => ({}));
  if (res.ok && data.success) {
    return { success: true, newTaskId: data.new_task_id, message: data.message };
  }
  return { success: false, message: data.detail || data.message || 'Resubmit failed' };
}
```

---

## 5. สรุปการแสดงปุ่มตาม Status

| Status | Cancel | Retry | Resubmit |
|--------|--------|-------|----------|
| queued | ✅ | ❌ | ❌ |
| pending | ✅ | ❌ | ❌ |
| processing | ✅ | ⚠️ (ถ้าค้าง) | ❌ |
| on_hold | ✅ | ❌ | ❌ |
| completed | ❌ | ❌ | ✅ (ถ้าต้องการส่งใหม่) |
| failed | ❌ | ✅ | ✅ |
| cancelled | ❌ | ❌ | ✅ |
| stopped | ❌ | ❌ | ✅ |

---

## 6. ปัญหาที่พบใน Dashboard ปัจจุบัน (dashboard.js)

1. **Cancel URL**: ใช้ `DELETE /transcribe/{taskId}` — ควรเปลี่ยนเป็น `POST /api/v2/tasks/{taskId}/cancel` และตรวจสอบว่า `api_url` มี path `/api` ครบหรือไม่
2. **Retry URL**: ใช้ `/v2/tasks/{taskId}/retry` — ควรเป็น `/api/v2/tasks/{taskId}/retry` ถ้า `api_url` เป็น base เท่านั้น
3. **Resubmit**: ยังไม่มีปุ่ม Resubmit ใน dashboard
4. **Status filter**: filter dropdown ยังไม่มี `on_hold`, `cancelled`
5. **Stuck detection**: ยังไม่มี logic แสดง Retry เมื่อ task ค้าง (processing > N นาที)

---

## 7. ดูรายละเอียด (View Details)

ลิงก์ไปยังหน้ารายละเอียด task:

```
{api_base}/api/v2/tasks/{task_id}?format=full
```

หรือใช้หน้า history/detail ของระบบ (ถ้ามี):

```
/api/history/transcriptions/{task_id}
```

---

## 8. WebSocket (ถ้ามี)

ถ้า backend รองรับ WebSocket สำหรับ real-time updates:

- Subscribe: `task:{task_id}` หรือ `all`
- Event types: `task.progress`, `task.completed`, `task.failed`, `task.cancelled`
- ใช้แทนหรือเสริม polling เพื่อลด latency
