# 📱 Frontend Integration Documentation

## 🚨 **CURRENT DOCUMENTATION (2025-08-29)**

### ✅ **เอกสารปัจจุบัน - ใช้เฉพาะเหล่านี้:**

| ไฟล์ | วัตถุประสงค์ | สถานะ |
|------|-------------|--------|
| **[API Reference](./api-reference.md)** | API endpoints ทั้งหมด (Polling, History, WebSocket Status) | ✅ ใช้งานได้ |
| **[Production Hooks](./hooks/useTranscription.ts)** | React hook พร้อม auto-fallback | ✅ ใช้งานได้ |
| **[Fallback Guide](./fallback-guide.md)** | จัดการเมื่อ WebSocket ไม่ทำงาน | ✅ ใช้งานได้ |
| **[Error Handling](./error-handling.md)** | การจัดการ errors แบบครอบคลุม | ✅ ใช้งานได้ |
| **[Migration Guide](./MIGRATION.md)** | การเปลี่ยนจากเอกสารเก่า | ✅ สำหรับ reference |

### ❌ **เอกสารที่ถูกลบแล้ว (Deprecated):**
- ~~`integration.md`~~ - ซ้ำกับ `api-reference.md` แต่ไม่ครบ
- ~~`workflow-guide.md`~~ - ซ้ำกับ `fallback-guide.md` แต่ไม่มี fallback
- ~~`websocket-hook-fixed.md`~~ - ซ้ำกับ `hooks/useTranscription.ts` แต่เก่า

## 🎯 **Quick Start:**

### **1. สำหรับ Developers ใหม่:**
```bash
1. อ่าน README.md (ไฟล์นี้) ก่อน
2. ดู api-reference.md สำหรับ API calls
3. ใช้ hooks/useTranscription.ts สำหรับ React
4. อ่าน fallback-guide.md สำหรับ production
```

### **2. สำหรับ Production Deployment:**
```bash
1. ใช้ hooks/useTranscription.ts (มี auto-fallback)
2. ตั้งค่า error handling ตาม error-handling.md
3. ทดสอบ fallback scenarios ตาม fallback-guide.md
```

### **3. สำหรับการ Migrate จากเอกสารเก่า:**
```bash
อ่าน MIGRATION.md สำหรับขั้นตอนการเปลี่ยนแปลง
```

## 🔄 **APIs ที่มีให้ใช้งาน:**

- **Core**: `/upload/`, `/transcribe-enhanced/start`, `/transcribe-enhanced/status/{task_id}`
- **Polling** (NEW): `/polling/task/{task_id}`, `/polling/tasks/active`, `/polling/tasks/recent`
- **History** (NEW): `/history/transcriptions`, `/history/transcriptions/{task_id}`, `/history/stats`
- **WebSocket Status** (NEW): `/websocket/status`, `/websocket/connections`, `/websocket/diagnostics`
- **WebSocket**: `ws://localhost:8001/ws/transcription/{user_id}`

## 📅 **Version History:**
- **2025-08-29**: ✅ **Current Version** - เพิ่ม Polling, History, WebSocket Status APIs + ลบเอกสารซ้ำซ้อน
- **2024**: ❌ **Deprecated** - เอกสารเก่าที่ถูกลบแล้ว
