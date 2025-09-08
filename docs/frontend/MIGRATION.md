# 📦 Frontend Documentation Migration (2025)

## 🚨 **IMPORTANT: เอกสารเก่าถูก deprecated**

### ❌ **เอกสารที่ไม่ควรใช้แล้ว (Deprecated 2025-08-29):**

1. **`integration.md`** - ข้อมูลพื้นฐานแต่ไม่มี APIs ใหม่
2. **`workflow-guide.md`** - Workflow เก่าไม่มี fallback
3. **`websocket-hook-fixed.md`** - WebSocket hook เวอร์ชันเก่า

### ✅ **เอกสารใหม่ที่ควรใช้:**

1. **`README.md`** - ภาพรวมและ navigation
2. **`api-reference.md`** - API endpoints ทั้งหมด (2025)
3. **`hooks/useTranscription.ts`** - Production-ready React hook
4. **`fallback-guide.md`** - Fallback strategies
5. **`error-handling.md`** - Error handling ครอบคลุม

## 🔄 **Migration Steps:**

### **สำหรับผู้ใช้งานเอกสารเก่า:**

#### **จาก `integration.md` → `api-reference.md`**
```diff
- ใช้ basic API calls
+ ใช้ complete API reference พร้อม Polling, History, WebSocket Status
```

#### **จาก `workflow-guide.md` → `fallback-guide.md`**
```diff
- WebSocket อย่างเดียว
+ WebSocket + Polling fallback + Manual refresh
```

#### **จาก `websocket-hook-fixed.md` → `hooks/useTranscription.ts`**
```diff
- Basic WebSocket hook
+ Production-ready hook พร้อม auto-fallback
```

## 📅 **Timeline:**

- **2025-08-29**: เอกสารใหม่พร้อมใช้งาน
- **2025-09-15**: เอกสารเก่าจะถูกลบ (deprecated period 2 สัปดาห์)
- **2025-09-15+**: เหลือเฉพาะเอกสารใหม่

## 🎯 **Quick Start สำหรับ Developers:**

1. เริ่มจาก **`README.md`** เพื่อดูภาพรวม
2. ใช้ **`api-reference.md`** สำหรับ API calls
3. ใช้ **`hooks/useTranscription.ts`** สำหรับ React integration
4. อ่าน **`fallback-guide.md`** สำหรับ production deployment
5. อ่าน **`error-handling.md`** สำหรับ error management
