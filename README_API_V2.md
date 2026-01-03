# 🚀 Transcription API v2 - Documentation Hub

> **ศูนย์รวมเอกสาร API เวอร์ชัน 2.0**  
> อ่านเอกสารนี้ก่อนเริ่มใช้งาน API

---

## ⚡ เริ่มต้นอย่างรวดเร็ว

### สำหรับ Developers ใหม่

1. 📘 **[Quick Start Guide](./QUICK_START_GUIDE.md)** ← **เริ่มที่นี่!**
   - เลือก API เวอร์ชันไหน?
   - Use cases หลัก
   - สิ่งที่ควรหลีกเลี่ยง

2. 💻 **[API Examples](./API_EXAMPLES.md)**
   - ตัวอย่าง JavaScript/TypeScript
   - ตัวอย่าง Python
   - ตัวอย่าง React Hooks
   - Copy & Paste พร้อมใช้!

3. 🔗 **[Swagger UI](http://localhost:8001/docs)**
   - ทดสอบ API ได้ทันที
   - ดู schema ทั้งหมด

---

### สำหรับ Migration จาก v1 → v2

1. 📙 **[Migration Guide](./API_MIGRATION_GUIDE.md)**
   - Mapping table: API เก่า → API ใหม่
   - ตัวอย่าง migration
   - Timeline & FAQ

2. 📕 **[API Comparison](./API_COMPARISON.md)**
   - เปรียบเทียบ v1 vs v2
   - Performance improvements
   - Use case examples

---

## 📚 เอกสารทั้งหมด

### สำหรับเริ่มต้น (Beginners)
| เอกสาร | คำอธิบาย | ระดับ |
|--------|----------|-------|
| [Quick Start Guide](./QUICK_START_GUIDE.md) | เริ่มใช้งาน API อย่างไร | 🟢 ง่าย |
| [API Examples](./API_EXAMPLES.md) | ตัวอย่าง code พร้อมใช้ | 🟢 ง่าย |
| [Swagger UI](http://localhost:8001/docs) | ทดสอบ API แบบ interactive | 🟢 ง่าย |

### สำหรับ Migration (Intermediate)
| เอกสาร | คำอธิบาย | ระดับ |
|--------|----------|-------|
| [Migration Guide](./API_MIGRATION_GUIDE.md) | วิธี migrate จาก v1 → v2 | 🟡 ปานกลาง |
| [API Comparison](./API_COMPARISON.md) | เปรียบเทียบ v1 vs v2 | 🟡 ปานกลาง |

### สำหรับ Advanced Users
| เอกสาร | คำอธิบาย | ระดับ |
|--------|----------|-------|
| [Consolidation Plan](./API_CONSOLIDATION_PLAN.md) | แผนการรวม API โดยละเอียด | 🔴 ยาก |
| [Implementation Summary](./API_CONSOLIDATION_IMPLEMENTATION.md) | รายละเอียดการ implement | 🔴 ยาก |

---

## 🎯 API v2 ภาพรวม

### ปรับปรุงอะไรบ้าง?

| ฟีเจอร์ | ก่อน (v1) | หลัง (v2) | ผลประโยชน์ |
|---------|-----------|-----------|-----------|
| **Task Status** | 4 endpoints | 1 endpoint พร้อม formats | ลด 75% |
| **Task List** | 4 endpoints | 1 endpoint พร้อม filters | Flexible ขึ้น |
| **Upload** | 2 endpoints | 1 endpoint | ไม่สับสน |
| **Performance** | ปกติ | เร็วขึ้น 75% (polling) | ประหยัด bandwidth |

---

## 📖 API v2 Endpoints สำคัญ

### 1️⃣ ดึงสถานะ Task

```bash
GET /api/v2/tasks/{task_id}?format=full|progress|minimal
```

**Formats:**
- `full`: ข้อมูลครบถ้วน (สำหรับหน้า detail)
- `progress`: ข้อมูล progress tracking (สำหรับ progress bars)
- `minimal`: ข้อมูลน้อยที่สุด (สำหรับ polling - เร็วที่สุด)

**ตัวอย่าง:**
```bash
# Full data
curl http://localhost:8001/api/v2/tasks/abc-123?format=full

# Quick polling
curl http://localhost:8001/api/v2/tasks/abc-123?format=minimal
```

---

### 2️⃣ ดึงรายการ Tasks

```bash
GET /api/v2/tasks?[filters]
```

**Filters:**
- `status`: completed|failed|processing|pending
- `date`: YYYY-MM-DD
- `days_ago`: last N days
- `active`: true (shortcut for status=processing)
- `filename_contains`: search in filename
- `language`: th|en|etc
- `limit`, `offset`: pagination
- `sort`, `order`: sorting

**ตัวอย่าง:**
```bash
# Active tasks
curl "http://localhost:8001/api/v2/tasks?active=true"

# Completed tasks last 7 days
curl "http://localhost:8001/api/v2/tasks?status=completed&days_ago=7"

# Search by filename
curl "http://localhost:8001/api/v2/tasks?filename_contains=meeting"

# Complex filter
curl "http://localhost:8001/api/v2/tasks?status=completed&days_ago=7&language=th&limit=20"
```

---

### 3️⃣ Upload ไฟล์

```bash
POST /api/upload/
```

**รองรับ:**
- Upload ไฟล์โดยตรง (multipart/form-data)
- Upload จาก URL

**ตัวอย่าง:**
```bash
# Upload file
curl -X POST http://localhost:8001/api/upload/ -F "file=@video.mp4"

# Upload from URL
curl -X POST http://localhost:8001/api/upload/ -F "url=https://example.com/video.mp4"
```

---

### 4️⃣ สถิติ

```bash
GET /api/v2/tasks/stats/summary
GET /api/v2/tasks/stats/available-dates
```

---

## 💡 Use Cases ทั่วไป

### Use Case 1: Transcribe ไฟล์

```javascript
// 1. Upload
const upload = await fetch('/api/upload/', {
  method: 'POST',
  body: formData
})
const { file_path } = await upload.json()

// 2. Start transcription
const start = await fetch('/api/transcribe/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ file_path, language: 'th' })
})
const { task_id } = await start.json()

// 3. Poll until complete
const poll = setInterval(async () => {
  const task = await fetch(`/api/v2/tasks/${task_id}?format=minimal`)
  const data = await task.json()
  
  if (data.status === 'completed') {
    clearInterval(poll)
    // ดึงข้อมูลเต็ม
    const result = await fetch(`/api/v2/tasks/${task_id}?format=full`)
    console.log(await result.json())
  }
}, 2000)
```

---

### Use Case 2: Dashboard

```javascript
// Active tasks
const active = await fetch('/api/v2/tasks?active=true&format=minimal')

// Recent completed
const recent = await fetch('/api/v2/tasks?status=completed&limit=10')

// Stats
const stats = await fetch('/api/v2/tasks/stats/summary')
```

---

## ⚠️ สิ่งสำคัญที่ต้องรู้

### ✅ DO (ควรทำ)

1. **ใช้ API v2 สำหรับโปรเจคใหม่**
   ```javascript
   // ✅ ถูกต้อง
   await fetch('/api/v2/tasks/abc-123')
   ```

2. **เลือก format ที่เหมาะสม**
   ```javascript
   // ✅ Polling - ใช้ minimal (เร็วที่สุด)
   await fetch('/api/v2/tasks/abc-123?format=minimal')
   
   // ✅ Display - ใช้ full
   await fetch('/api/v2/tasks/abc-123?format=full')
   ```

3. **ใช้ filters แทนการเรียกหลายครั้ง**
   ```javascript
   // ✅ ดี - 1 request
   await fetch('/api/v2/tasks?status=completed&days_ago=7')
   
   // ❌ แย่ - หลาย requests + filter client-side
   const all = await fetch('/api/v2/tasks?limit=1000')
   const filtered = all.tasks.filter(...)
   ```

---

### ❌ DON'T (ไม่ควรทำ)

1. **อย่าใช้ API deprecated**
   ```javascript
   // ❌ หลีกเลี่ยง - deprecated
   await fetch('/api/progress/transcription/abc-123')
   await fetch('/api/polling/task/abc-123')
   
   // ✅ ใช้แทน
   await fetch('/api/v2/tasks/abc-123?format=progress')
   await fetch('/api/v2/tasks/abc-123?format=minimal')
   ```

2. **อย่าผสม v1 และ v2 โดยไม่จำเป็น**
   ```javascript
   // ❌ สับสน
   const task1 = await fetch('/api/tasks/abc')  // v1
   const task2 = await fetch('/api/v2/tasks/def')  // v2
   
   // ✅ ดี - ใช้ v2 ทั้งหมด
   const task1 = await fetch('/api/v2/tasks/abc')
   const task2 = await fetch('/api/v2/tasks/def')
   ```

---

## 📅 Timeline

### ตอนนี้ (ธ.ค. 2025)
- ✅ API v2 พร้อมใช้งาน
- ✅ API v1 ยังใช้งานได้ปกติ
- 📘 เอกสารครบถ้วน

### มกราคม - กุมภาพันธ์ 2026
- ⏳ API v1 จะมี deprecation warnings
- ⏳ แนะนำให้ migrate

### มีนาคม - เมษายน 2026
- ⏳ Migration period
- ⏳ Support team ช่วยเหลือ migration

### พฤษภาคม 2026
- ⏳ API v1 จะถูกปิดการใช้งาน

---

## 🆘 ต้องการความช่วยเหลือ?

### เอกสารเพิ่มเติม
- 📘 [Quick Start Guide](./QUICK_START_GUIDE.md) - เริ่มต้นใช้งาน
- 💻 [API Examples](./API_EXAMPLES.md) - ตัวอย่าง code
- 📙 [Migration Guide](./API_MIGRATION_GUIDE.md) - วิธี migrate
- 🔗 [Swagger UI](http://localhost:8001/docs) - ทดสอบ API

### Support
- 📧 Email: support@example.com
- 💬 Slack: #api-support
- 🐛 Issues: GitHub Issues

---

## ✅ Checklist สำหรับเริ่มต้น

### โปรเจคใหม่
- [ ] อ่าน [Quick Start Guide](./QUICK_START_GUIDE.md)
- [ ] ดู [API Examples](./API_EXAMPLES.md)
- [ ] ทดสอบใน [Swagger UI](http://localhost:8001/docs)
- [ ] ใช้ API v2 เท่านั้น

### โปรเจคเก่า (Migration)
- [ ] อ่าน [Migration Guide](./API_MIGRATION_GUIDE.md)
- [ ] ตรวจสอบ deprecated endpoints
- [ ] Plan migration timeline
- [ ] Migrate ทีละส่วน
- [ ] Test ใน development
- [ ] Deploy ไป production

---

## 🎉 สรุป

**API v2 พร้อมใช้งานแล้ว!**

- ✅ **เรียบง่ายขึ้น** - ลดความซ้ำซ้อน 62%
- ✅ **Flexible ขึ้น** - Powerful filtering
- ✅ **เร็วขึ้น** - Performance ดีขึ้น 75%
- ✅ **เอกสารครบถ้วน** - พร้อม examples

**เริ่มใช้งานเลย:** http://localhost:8001/docs

---

**เวอร์ชัน:** 2.0  
**อัปเดตล่าสุด:** 29 ธันวาคม 2025  
**ผู้จัดทำ:** Development Team





