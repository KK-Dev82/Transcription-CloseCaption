# 🎯 Quick Start Guide - เริ่มใช้งาน API อย่างไร

> **สำหรับ Developers ใหม่:** อ่านเอกสารนี้ก่อนเริ่มใช้งาน API

---

## ⚡ เริ่มต้นอย่างรวดเร็ว

### ✅ ใช้ API v2 สำหรับโปรเจคใหม่

หากคุณกำลังเริ่มโปรเจคใหม่ **ให้ใช้ API v2 เท่านั้น**

```javascript
// ✅ ถูกต้อง - ใช้ v2
await fetch('/api/v2/tasks/abc-123')

// ❌ หลีกเลี่ยง - API เก่า (deprecated)
await fetch('/api/tasks/abc-123')
```

---

## 📚 เลือก API ตามสถานการณ์

### สถานการณ์ที่ 1: โปรเจคใหม่ (New Project)

**👉 ใช้ API v2 เท่านั้น**

```bash
# Task Status
GET /api/v2/tasks/{task_id}?format=full

# Task List
GET /api/v2/tasks?status=completed&limit=20

# Upload
POST /api/upload/
```

---

### สถานการณ์ที่ 2: โปรเจคเก่า (Existing Project)

**👉 ใช้ API เก่าต่อไปได้ แต่ค่อยๆ migrate ไป v2**

```javascript
// ยังใช้ API เก่าได้ (จนถึง เม.ย. 2026)
const task = await fetch('/api/tasks/abc-123')

// แต่แนะนำให้เริ่ม migrate ไป v2
const taskV2 = await fetch('/api/v2/tasks/abc-123?format=full')
```

---

## 🎯 Use Cases หลัก

### 1. ดึงสถานะ Task

```javascript
// ✅ แนะนำ (v2)
const task = await fetch('/api/v2/tasks/abc-123?format=full')

// หรือสำหรับ polling (เร็วกว่า)
const task = await fetch('/api/v2/tasks/abc-123?format=minimal')
```

### 2. ดึงรายการ Tasks

```javascript
// ✅ แนะนำ (v2)
const tasks = await fetch('/api/v2/tasks?status=completed&limit=20')

// ค้นหาด้วย filename
const tasks = await fetch('/api/v2/tasks?filename_contains=meeting')

// Filter แบบ complex
const tasks = await fetch('/api/v2/tasks?status=completed&days_ago=7&language=th')
```

### 3. Upload ไฟล์

```javascript
// ✅ แนะนำ (v2 ใช้ endpoint เดียวกับ v1)
const formData = new FormData()
formData.append('file', file)

const result = await fetch('/api/upload/', {
  method: 'POST',
  body: formData
})
```

---

## 🚫 สิ่งที่ควรหลีกเลี่ยง

### ❌ อย่าผสม API v1 และ v2 โดยไม่จำเป็น

```javascript
// ❌ แย่ - ใช้ทั้ง v1 และ v2 ปนกัน
const task1 = await fetch('/api/tasks/abc-123')  // v1
const task2 = await fetch('/api/v2/tasks/def-456')  // v2

// ✅ ดี - ใช้ v2 ทั้งหมด
const task1 = await fetch('/api/v2/tasks/abc-123')
const task2 = await fetch('/api/v2/tasks/def-456')
```

### ❌ อย่าใช้ API ที่ Deprecated

```javascript
// ❌ หลีกเลี่ยง - endpoints เหล่านี้ถูก deprecated
await fetch('/api/progress/transcription/abc-123')
await fetch('/api/polling/task/abc-123')
await fetch('/api/tasks/by-date?date=2025-12-29')
await fetch('/api/video/upload')

// ✅ ใช้ v2 แทน
await fetch('/api/v2/tasks/abc-123?format=progress')
await fetch('/api/v2/tasks/abc-123?format=minimal')
await fetch('/api/v2/tasks?date=2025-12-29')
await fetch('/api/upload/')
```

---

## 📖 Documentation Links

### สำหรับเริ่มต้น
- 📘 [Quick Start Guide](./QUICK_START_GUIDE.md) - เอกสารนี้
- 📕 [API Comparison](./API_COMPARISON.md) - เปรียบเทียบ v1 vs v2

### สำหรับ Migration
- 📙 [Migration Guide](./API_MIGRATION_GUIDE.md) - วิธี migrate จาก v1 → v2
- 📗 [Consolidation Plan](./API_CONSOLIDATION_PLAN.md) - แผนการรวม API

### สำหรับ Advanced
- 📔 [Implementation Details](./API_CONSOLIDATION_IMPLEMENTATION.md)
- 🔗 [Swagger UI](http://localhost:8001/docs)

---

## 🆘 ต้องการความช่วยเหลือ?

### คำถามที่พบบ่อย

**Q: ควรใช้ API v1 หรือ v2?**
A: ใช้ **v2** สำหรับโปรเจคใหม่ทั้งหมด

**Q: API v1 จะถูกปิดเมื่อไหร่?**
A: เม.ย. 2026 (มีเวลา migrate 4 เดือน)

**Q: format=minimal vs format=full ต่างกันอย่างไร?**
A: 
- `minimal`: ข้อมูลน้อยที่สุด (เร็วที่สุด) - สำหรับ polling
- `full`: ข้อมูลครบถ้วน - สำหรับหน้า detail

**Q: จะรู้ได้อย่างไรว่าใช้ API deprecated?**
A: Response จะมีฟิลด์ `_deprecated` พร้อม warning message

---

## ✅ Checklist สำหรับเริ่มต้น

สำหรับโปรเจคใหม่:
- [ ] ใช้ `/api/v2/tasks/` เท่านั้น
- [ ] เลือก format ที่เหมาะสม (minimal/progress/full)
- [ ] ใช้ filters แทนการเรียก endpoints หลายครั้ง
- [ ] ใช้ `/api/upload/` สำหรับ upload

สำหรับโปรเจคเก่า:
- [ ] อ่าน Migration Guide
- [ ] Migrate ทีละส่วน
- [ ] ทดสอบ v2 ใน development ก่อน
- [ ] Monitor deprecation warnings

---

**เริ่มต้นใช้งาน:** http://localhost:8001/docs (Swagger UI)





