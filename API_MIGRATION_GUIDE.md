# 🔄 API Migration Guide - คู่มือการย้าย API

> **วันที่:** 29 ธันวาคม 2025  
> **เวอร์ชัน:** 2.0  
> **สถานะ:** Unified APIs พร้อมใช้งาน

---

## 📋 สารบัญ

1. [ภาพรวมการเปลี่ยนแปลง](#overview)
2. [Mapping Table - API เก่า → API ใหม่](#mapping)
3. [ตัวอย่าง Code Migration](#examples)
4. [Breaking Changes](#breaking-changes)
5. [Timeline & Deprecation Schedule](#timeline)
6. [คำถามที่พบบ่อย (FAQ)](#faq)

---

## <a name="overview"></a>📊 ภาพรวมการเปลี่ยนแปลง

### สิ่งที่เปลี่ยนแปลง

| ก่อน | หลัง | ผลประโยชน์ |
|------|------|-----------|
| 4 endpoints สำหรับดึงสถานะ task | 1 unified endpoint พร้อม filters | ง่ายขึ้น 4 เท่า |
| 4 endpoints สำหรับดึงรายการ tasks | 1 unified endpoint พร้อม filters | Flexible มากขึ้น |
| 2 endpoints สำหรับ upload | 1 unified endpoint | ลดความสับสน |

### Benefits

✅ **ลดความซับซ้อน** - ง่ายต่อการจำและใช้งาน  
✅ **Flexible Filtering** - ใช้ query parameters แทน endpoints หลายตัว  
✅ **Better Performance** - ลด overhead  
✅ **Backward Compatible** - API เก่ายังใช้งานได้ชั่วคราว  

---

## <a name="mapping"></a>🗺️ Mapping Table - API เก่า → API ใหม่

### 1️⃣ ดึงสถานะ Task (Task Status)

| API เก่า | API ใหม่ | หมายเหตุ |
|---------|---------|---------|
| `GET /api/tasks/{task_id}` | `GET /api/v2/tasks/{task_id}?format=full` | ข้อมูลแบบเต็ม |
| `GET /api/progress/transcription/{task_id}` | `GET /api/v2/tasks/{task_id}?format=progress` | Progress tracking |
| `GET /api/polling/task/{task_id}` | `GET /api/v2/tasks/{task_id}?format=minimal` | Quick polling |
| `GET /api/transcribe-enhanced/status/{task_id}` | `GET /api/v2/tasks/{task_id}?format=full&include_thai_processing=true` | Enhanced + Thai |

#### ตัวอย่างการใช้งาน:

**ก่อน:**
```javascript
// ต้องเรียก endpoints ต่างกัน
const fullData = await fetch('/api/tasks/abc-123')
const progress = await fetch('/api/progress/transcription/abc-123')
const quickPoll = await fetch('/api/polling/task/abc-123')
```

**หลัง:**
```javascript
// ใช้ endpoint เดียว เปลี่ยนแค่ format
const fullData = await fetch('/api/v2/tasks/abc-123?format=full')
const progress = await fetch('/api/v2/tasks/abc-123?format=progress')
const quickPoll = await fetch('/api/v2/tasks/abc-123?format=minimal')
```

---

### 2️⃣ ดึงรายการ Tasks (Task List)

| API เก่า | API ใหม่ | หมายเหตุ |
|---------|---------|---------|
| `GET /api/history/transcriptions` | `GET /api/v2/tasks` | รายการทั้งหมด |
| `GET /api/history/transcriptions?status=completed` | `GET /api/v2/tasks?status=completed` | Filter by status |
| `GET /api/tasks/by-date?date=2025-12-29` | `GET /api/v2/tasks?date=2025-12-29` | Filter by date |
| `GET /api/polling/tasks/active` | `GET /api/v2/tasks?active=true` | Active tasks only |
| `GET /api/polling/tasks/recent` | `GET /api/v2/tasks?limit=10&sort=updated_at&order=desc` | Recent tasks |

#### ตัวอย่างการใช้งาน:

**ก่อน:**
```javascript
// ต้องเรียก endpoints ต่างกัน
const allTasks = await fetch('/api/history/transcriptions?limit=20')
const byDate = await fetch('/api/tasks/by-date?date=2025-12-29')
const active = await fetch('/api/polling/tasks/active')
const recent = await fetch('/api/polling/tasks/recent')
```

**หลัง:**
```javascript
// ใช้ endpoint เดียว เปลี่ยนแค่ filters
const allTasks = await fetch('/api/v2/tasks?limit=20')
const byDate = await fetch('/api/v2/tasks?date=2025-12-29')
const active = await fetch('/api/v2/tasks?active=true')
const recent = await fetch('/api/v2/tasks?limit=10&sort=updated_at&order=desc')
```

---

### 3️⃣ Upload ไฟล์

| API เก่า | API ใหม่ | หมายเหตุ |
|---------|---------|---------|
| `POST /api/upload/` | `POST /api/upload/` | ไม่เปลี่ยน (ใช้ได้เลย) |
| `POST /api/video/upload` | `POST /api/upload/` | ❌ **Deprecated** |
| `GET /api/video/info/{file_path}` | `GET /api/upload/info/{file_path}` | ย้ายไปที่ upload |

#### ตัวอย่างการใช้งาน:

**ก่อน:**
```javascript
// มี 2 endpoints สำหรับ upload
const videoUpload = await fetch('/api/video/upload', {
  method: 'POST',
  body: formData
})

const videoInfo = await fetch('/api/video/info/uploads/video.mp4')
```

**หลัง:**
```javascript
// ใช้ endpoint เดียว
const upload = await fetch('/api/upload/', {
  method: 'POST',
  body: formData
})

const fileInfo = await fetch('/api/upload/info/uploads/video.mp4')
```

---

### 4️⃣ สถิติและ Summary

| API เก่า | API ใหม่ | หมายเหตุ |
|---------|---------|---------|
| `GET /api/tasks/summary` | `GET /api/v2/tasks/stats/summary` | Summary statistics |
| `GET /api/history/stats` | `GET /api/v2/tasks/stats/summary` | รวมกัน |
| `GET /api/tasks/available-dates` | `GET /api/v2/tasks/stats/available-dates` | Available dates |

---

## <a name="examples"></a>💻 ตัวอย่าง Code Migration

### Example 1: Polling Task Status

**ก่อน (Old API):**
```javascript
// Polling loop - เรียก 3 endpoints ต่างกัน
async function pollTaskStatus(taskId) {
  const interval = setInterval(async () => {
    const response = await fetch(`/api/polling/task/${taskId}`)
    const data = await response.json()
    
    if (data.status === 'completed') {
      clearInterval(interval)
      // Get full data
      const fullData = await fetch(`/api/tasks/${taskId}`)
      console.log('Task completed:', await fullData.json())
    }
  }, 2000)
}
```

**หลัง (New API v2):**
```javascript
// Polling loop - ใช้ endpoint เดียว
async function pollTaskStatus(taskId) {
  const interval = setInterval(async () => {
    // ใช้ format=minimal สำหรับ polling (เร็วที่สุด)
    const response = await fetch(`/api/v2/tasks/${taskId}?format=minimal`)
    const data = await response.json()
    
    if (data.status === 'completed') {
      clearInterval(interval)
      // Get full data (เปลี่ยนแค่ format)
      const fullData = await fetch(`/api/v2/tasks/${taskId}?format=full`)
      console.log('Task completed:', await fullData.json())
    }
  }, 2000)
}
```

---

### Example 2: List Tasks with Filters

**ก่อน (Old API):**
```javascript
// ต้องรู้หลาย endpoints
async function getTasks() {
  // Get active tasks
  const activeResponse = await fetch('/api/polling/tasks/active')
  const activeTasks = await activeResponse.json()
  
  // Get tasks by date
  const dateResponse = await fetch('/api/tasks/by-date?date=2025-12-29')
  const dateTasks = await dateResponse.json()
  
  // Get recent tasks
  const recentResponse = await fetch('/api/polling/tasks/recent')
  const recentTasks = await recentResponse.json()
  
  return { activeTasks, dateTasks, recentTasks }
}
```

**หลัง (New API v2):**
```javascript
// ใช้ endpoint เดียว พร้อม filters
async function getTasks() {
  // Get active tasks
  const activeResponse = await fetch('/api/v2/tasks?active=true')
  const activeTasks = await activeResponse.json()
  
  // Get tasks by date
  const dateResponse = await fetch('/api/v2/tasks?date=2025-12-29')
  const dateTasks = await dateResponse.json()
  
  // Get recent tasks
  const recentResponse = await fetch('/api/v2/tasks?limit=10&sort=updated_at&order=desc')
  const recentTasks = await recentResponse.json()
  
  return { activeTasks, dateTasks, recentTasks }
}
```

---

### Example 3: Complex Filtering

**ก่อน (Old API):**
```javascript
// ต้อง filter ฝั่ง client
async function getCompletedTasksLastWeek() {
  const response = await fetch('/api/history/transcriptions?limit=1000')
  const data = await response.json()
  
  // Filter manually
  const oneWeekAgo = new Date()
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7)
  
  const filtered = data.tasks.filter(task => 
    task.status === 'completed' &&
    new Date(task.created_at) >= oneWeekAgo
  )
  
  return filtered
}
```

**หลัง (New API v2):**
```javascript
// Filter ฝั่ง server (เร็วกว่า)
async function getCompletedTasksLastWeek() {
  const response = await fetch('/api/v2/tasks?status=completed&days_ago=7')
  const data = await response.json()
  
  return data.tasks
}
```

---

### Example 4: React Hook

**ก่อน (Old API):**
```javascript
import { useState, useEffect } from 'react'

function useTaskStatus(taskId) {
  const [task, setTask] = useState(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    const fetchTask = async () => {
      // ต้องเลือกว่าจะใช้ endpoint ไหน
      const response = await fetch(`/api/tasks/${taskId}`)
      const data = await response.json()
      setTask(data)
      setLoading(false)
    }
    
    fetchTask()
    const interval = setInterval(fetchTask, 5000)
    
    return () => clearInterval(interval)
  }, [taskId])
  
  return { task, loading }
}
```

**หลัง (New API v2):**
```javascript
import { useState, useEffect } from 'react'

function useTaskStatus(taskId, format = 'full') {
  const [task, setTask] = useState(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    const fetchTask = async () => {
      // เลือก format ตามต้องการ
      const response = await fetch(`/api/v2/tasks/${taskId}?format=${format}`)
      const data = await response.json()
      setTask(data)
      setLoading(false)
    }
    
    fetchTask()
    
    // ใช้ minimal format สำหรับ polling (เร็วกว่า)
    const interval = setInterval(async () => {
      const response = await fetch(`/api/v2/tasks/${taskId}?format=minimal`)
      const data = await response.json()
      setTask(prev => ({ ...prev, ...data }))
    }, 5000)
    
    return () => clearInterval(interval)
  }, [taskId, format])
  
  return { task, loading }
}

// Usage
function TaskDetail({ taskId }) {
  // ใช้ format=full สำหรับหน้า detail
  const { task } = useTaskStatus(taskId, 'full')
  
  return <div>{task?.status}</div>
}

function TaskList() {
  // ใช้ format=minimal สำหรับ list (เร็วกว่า)
  const { task } = useTaskStatus(taskId, 'minimal')
  
  return <div>{task?.progress}%</div>
}
```

---

## <a name="breaking-changes"></a>⚠️ Breaking Changes

### ไม่มี Breaking Changes!

✅ **Backward Compatible 100%**

API เก่าทั้งหมดยังใช้งานได้ตามปกติ มีเพียง:

1. **Deprecation Warnings** - API เก่าจะมี warning ใน response
2. **Documentation** - แนะนำให้ใช้ API v2

### Response Format Changes

#### Response ของ v2 จะมีฟิลด์เพิ่ม:

```json
{
  "task_id": "abc-123",
  "status": "completed",
  "_format": "full",  // ← ใหม่: บอกว่าใช้ format ไหน
  ...
}
```

#### List endpoint จะมี metadata เพิ่ม:

```json
{
  "total_count": 150,
  "limit": 20,
  "offset": 0,
  "has_more": true,
  "filters_applied": {  // ← ใหม่: บอก filters ที่ใช้
    "status": "completed",
    "days_ago": 7
  },
  "sort": {  // ← ใหม่: บอกการเรียงลำดับ
    "field": "updated_at",
    "order": "desc"
  },
  "tasks": [...]
}
```

---

## <a name="timeline"></a>📅 Timeline & Deprecation Schedule

### Phase 1: Introduction (วันนี้ - 29 ธ.ค. 2025) ✅

- ✅ Unified APIs (v2) พร้อมใช้งาน
- ✅ Documentation เผยแพร่
- ✅ Migration Guide พร้อม

### Phase 2: Deprecation Warnings (1 ม.ค. - 29 ก.พ. 2026) ⏳

- ⏳ API เก่าจะมี `_deprecated` warning ใน response:

```json
{
  "data": {...},
  "_deprecated": {
    "message": "This endpoint is deprecated. Please use /api/v2/tasks/{task_id}",
    "new_endpoint": "/api/v2/tasks/{task_id}?format=full",
    "removal_date": "2026-03-01",
    "migration_guide": "https://docs.example.com/api-migration"
  }
}
```

### Phase 3: Migration Period (1 มี.ค. - 30 เม.ย. 2026) ⏳

- ⏳ แนะนำ clients ทั้งหมดให้ migrate
- ⏳ Support team จะช่วยเหลือการ migrate

### Phase 4: Removal (1 พ.ค. 2026) ⏳

- ⏳ API เก่าจะถูกปิดการใช้งาน
- ⏳ จะ return HTTP 410 (Gone) พร้อมข้อความแนะนำ

---

## <a name="faq"></a>❓ คำถามที่พบบ่อย (FAQ)

### Q1: API เก่ายังใช้ได้หรือไม่?

**A:** ใช้ได้! API เก่าจะใช้งานได้ปกติจนถึง 30 เมษายน 2026

---

### Q2: ต้อง migrate ทันทีหรือไม่?

**A:** ไม่จำเป็น แต่แนะนำให้ migrate เร็วที่สุดเพื่อ:
- ใช้ประโยชน์จาก features ใหม่
- หลีกเลี่ยงปัญหาเมื่อ API เก่าถูกปิด
- ได้ performance ที่ดีกว่า

---

### Q3: จะรู้ได้อย่างไรว่าใช้ API เก่าอยู่?

**A:** ตรวจสอบ response จะมีฟิลด์ `_deprecated`:

```json
{
  "_deprecated": {
    "message": "...",
    "new_endpoint": "..."
  }
}
```

---

### Q4: จะ migrate อย่างไร?

**A:** ตาม 3 ขั้นตอน:

1. **ดู Mapping Table** - หา API ใหม่ที่ตรงกับ API เก่า
2. **ทดสอบ** - ทดสอบ API ใหม่ใน development
3. **Deploy** - Deploy code ใหม่ไปยัง production

---

### Q5: Response format เหมือนเดิมหรือไม่?

**A:** เกือบเหมือนเดิม มีเพียง:
- ฟิลด์ `_format` เพิ่มขึ้น (บอกว่าใช้ format ไหน)
- ฟิลด์ metadata เพิ่มขึ้นในบาง endpoints

---

### Q6: Performance แตกต่างกันหรือไม่?

**A:** API v2 **เร็วกว่า** เพราะ:
- Optimized code
- ลด overhead จากการมี endpoints หลายตัว
- รองรับ format=minimal สำหรับ polling (เร็วที่สุด)

---

### Q7: สามารถใช้ API v2 และ API เก่าพร้อมกันได้หรือไม่?

**A:** ได้! สามารถ migrate ทีละส่วนได้ ไม่จำเป็นต้อง migrate ทั้งหมดพร้อมกัน

---

### Q8: จะได้รับการแจ้งเตือนก่อน API เก่าถูกปิดหรือไม่?

**A:** ใช่! จะมีการแจ้งเตือน:
- Email notification (60 วัน, 30 วัน, 7 วัน ก่อนปิด)
- Deprecation warning ใน API response
- Announcement ในเว็บไซต์

---

## 📞 การติดต่อและการช่วยเหลือ

### ต้องการความช่วยเหลือในการ migrate?

- 📧 Email: support@example.com
- 💬 Slack: #api-migration
- 📚 Documentation: https://docs.example.com/api-v2
- 🐛 Issues: https://github.com/example/issues

---

## ✅ Checklist สำหรับการ Migrate

### เตรียมตัว
- [ ] อ่าน Migration Guide
- [ ] ศึกษา Mapping Table
- [ ] เข้าใจ Timeline

### ทดสอบ
- [ ] ทดสอบ API v2 ใน development
- [ ] เปรียบเทียบ response กับ API เก่า
- [ ] ทดสอบ error handling

### Deploy
- [ ] Deploy code ใหม่ไป staging
- [ ] ทดสอบใน staging environment
- [ ] Deploy ไป production
- [ ] Monitor logs และ errors

### Cleanup
- [ ] ลบ code ที่เรียก API เก่า
- [ ] อัปเดต documentation
- [ ] แจ้งทีมเกี่ยวกับการเปลี่ยนแปลง

---

## 📚 Resources เพิ่มเติม

- [API v2 Documentation](./API_CONSOLIDATION_PLAN.md)
- [Swagger/OpenAPI Docs](http://localhost:8001/docs)
- [Postman Collection](./postman_collection.json)
- [Example Code Repository](https://github.com/example/api-v2-examples)

---

**หมายเหตุ:** เอกสารนี้จะถูกอัปเดตเป็นระยะ ๆ กรุณาตรวจสอบเวอร์ชันล่าสุดเสมอ

**เวอร์ชันล่าสุด:** 1.0 (29 ธันวาคม 2025)





