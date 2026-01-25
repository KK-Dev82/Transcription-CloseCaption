# 🎨 Frontend Integration Guide - Stuck Task Monitor

## ✅ คำตอบสั้นๆ

**Frontend ไม่ต้องทำอะไรเพิ่มเติม** - ระบบ Stuck Task Monitor จะทำงานอัตโนมัติใน background และแก้ไข tasks ที่ค้างให้เอง

---

## 🔄 การทำงานอัตโนมัติ

### Background Service
- ✅ ตรวจสอบ tasks ที่ค้างทุก 30 วินาที (configurable)
- ✅ Auto re-enqueue chunks ที่หาย
- ✅ แก้ไข stuck tasks อัตโนมัติ
- ✅ ไม่ต้องมี frontend interaction

### Frontend แค่ต้องทำ
- ✅ แสดง progress ตามปกติ (polling `/api/v2/tasks/{task_id}`)
- ✅ ไม่ต้องจัดการ stuck tasks เอง
- ✅ ไม่ต้องมี retry button (ระบบจะ retry อัตโนมัติ)

---

## 📊 Optional: เพิ่ม Visibility (ถ้าต้องการ)

ถ้าต้องการให้ Frontend แสดงข้อมูล stuck tasks หรือมี manual control:

### 1. แสดง Stuck Tasks ใน Dashboard

```javascript
// เรียก API เพื่อดู stuck tasks
async function getStuckTasks() {
  const response = await fetch('/api/monitoring/stuck-tasks/status');
  const data = await response.json();
  
  if (data.stuck_count > 0) {
    console.log(`⚠️ Found ${data.stuck_count} stuck tasks`);
    // แสดงใน dashboard
    displayStuckTasks(data.stuck_tasks);
  }
}

// เรียกทุก 1 นาที (optional)
setInterval(getStuckTasks, 60000);
```

### 2. Manual Retry Button (Optional)

```javascript
async function retryStuckTasks() {
  const response = await fetch('/api/monitoring/stuck-tasks/check', {
    method: 'POST'
  });
  const data = await response.json();
  
  if (data.result.fixed > 0) {
    alert(`✅ Fixed ${data.result.fixed} stuck tasks`);
  }
}
```

### 3. Alert เมื่อ Task ค้าง

```javascript
// ตรวจสอบ task ที่ค้างนาน
async function checkTaskStuck(taskId) {
  const task = await fetch(`/api/v2/tasks/${taskId}`).then(r => r.json());
  
  if (task.status === 'processing') {
    const updatedAt = new Date(task.updated_at);
    const now = new Date();
    const stuckSeconds = (now - updatedAt) / 1000;
    
    if (stuckSeconds > 120) { // ค้างเกิน 2 นาที
      // แสดง alert (แต่ระบบจะแก้ไขอัตโนมัติ)
      console.warn(`⚠️ Task ${taskId} seems stuck (${Math.floor(stuckSeconds)}s)`);
    }
  }
}
```

---

## 🎯 Recommended Approach

### สำหรับ Production

**ไม่ต้องทำอะไร** - ระบบจะทำงานอัตโนมัติ:
- ✅ Background service จะตรวจสอบและแก้ไขทุก 30 วินาที
- ✅ Tasks ที่ค้างจะถูกแก้ไขอัตโนมัติ
- ✅ Frontend แค่แสดง progress ตามปกติ

### สำหรับ Development/Debugging

**เพิ่ม visibility (optional)**:
- แสดง stuck tasks count ใน dashboard
- แสดง alert เมื่อ task ค้าง (แต่ไม่ต้องมี retry button)
- Log stuck tasks สำหรับ debugging

---

## 📝 API Endpoints (สำหรับ Reference)

### 1. ตรวจสอบและแก้ไข (Auto - ไม่ต้องเรียกจาก Frontend)

```bash
POST /api/monitoring/stuck-tasks/check
```

Response:
```json
{
  "success": true,
  "result": {
    "checked": 484,
    "stuck": 14,
    "fixed": 5,
    "stuck_tasks": [...],
    "fixed_tasks": [...]
  }
}
```

### 2. ดูสถานะ (Optional - สำหรับ Dashboard)

```bash
GET /api/monitoring/stuck-tasks/status
```

Response:
```json
{
  "success": true,
  "total_checked": 484,
  "stuck_count": 14,
  "stuck_tasks": [
    {
      "task_id": "...",
      "reason": "Missing chunks: [1, 2]",
      "status": "processing",
      "progress": 65,
      "current_stage": "transcribing"
    }
  ]
}
```

---

## ⚠️ ข้อควรระวัง

1. **ไม่ต้อง polling `/api/monitoring/stuck-tasks/check`** - ระบบจะทำงานอัตโนมัติ
2. **ไม่ต้องมี retry button** - ระบบจะ retry อัตโนมัติ
3. **Frontend แค่แสดง progress** - ใช้ `/api/v2/tasks/{task_id}` ตามปกติ

---

## 🎨 Example: Dashboard Integration (Optional)

```javascript
// components/StuckTasksWidget.jsx (Optional)
import { useEffect, useState } from 'react';

export function StuckTasksWidget() {
  const [stuckCount, setStuckCount] = useState(0);
  
  useEffect(() => {
    // ตรวจสอบทุก 1 นาที (optional)
    const interval = setInterval(async () => {
      try {
        const response = await fetch('/api/monitoring/stuck-tasks/status');
        const data = await response.json();
        setStuckCount(data.stuck_count);
      } catch (error) {
        console.error('Failed to check stuck tasks:', error);
      }
    }, 60000);
    
    return () => clearInterval(interval);
  }, []);
  
  if (stuckCount === 0) return null;
  
  return (
    <div className="alert alert-warning">
      ⚠️ {stuckCount} tasks are stuck (auto-fixing in progress...)
    </div>
  );
}
```

---

## ✅ สรุป

**Frontend ไม่ต้องทำอะไร** - ระบบจะทำงานอัตโนมัติ:
- ✅ Background service ตรวจสอบทุก 30 วินาที
- ✅ Auto re-enqueue chunks ที่หาย
- ✅ แก้ไข stuck tasks อัตโนมัติ
- ✅ Frontend แค่แสดง progress ตามปกติ

**Optional**: เพิ่ม visibility ใน dashboard ถ้าต้องการ (แต่ไม่จำเป็น)
