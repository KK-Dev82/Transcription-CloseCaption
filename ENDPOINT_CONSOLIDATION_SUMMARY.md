# 📋 Endpoint Consolidation Summary

## ✅ Transcription Test Result

**Test URL**: `https://korrakang.com/video/v10-1.mp4`
**Status**: ✅ **ทำงานได้ - Dependencies ครบถ้วน**
**Task ID**: `446e597b-a0a3-4c26-bb4b-473bdc353268`
**Response**: Job queued successfully

---

## 🎯 สรุป Endpoints ที่ควรเก็บไว้

### ✅ Core Endpoints (จำเป็น)

1. **Transcription**
   - `POST /api/transcribe/` - Main transcription (รองรับ file_url, file_path)
   - `POST /api/transcribe-enhanced/start` - Enhanced transcription (base model + Thai processing)

2. **V2 Unified API** (แนะนำ - ใช้แทน legacy endpoints)
   - `GET /api/v2/tasks/{task_id}` - Task status (format: full/progress/minimal)
   - `GET /api/v2/tasks/` - Task list (filtering: status, date, pagination)
   - `GET /api/v2/tasks/stats/summary` - Statistics
   - `GET /api/v2/tasks/stats/available-dates` - Available dates

3. **History API** (เก็บเฉพาะ WebSocket และ DELETE)
   - `WS /api/history/ws/realtime` - WebSocket realtime updates
   - `DELETE /api/history/transcriptions/{task_id}` - Delete transcription

4. **Webhook API** - ทั้งหมด (8 endpoints)
   - Subscribe, unsubscribe, test, stats, verify signature, events

5. **Upload API** - ทั้งหมด (4 endpoints)
   - Upload, list, info

6. **Caption API** - ทั้งหมด (7 endpoints)
   - Create, get, list, delete, subtitle, segments, cleanup

7. **WebSocket API** - ทั้งหมด (8 endpoints)
   - Main WebSocket, status, connections, subscriptions, diagnostics

8. **Monitoring API** - ทั้งหมด (4 endpoints)
   - Overall, redis, queues, system stats

9. **Queue API** - ทั้งหมด (7 endpoints)
   - Info, status, stats, health, purge, test-flow, check-task

10. **Logs API** - ทั้งหมด (5 endpoints)
    - List, get, search, stats, recent

11. **Internal API** - เก็บไว้ (1 endpoint)
    - `POST /api/internal/transcribe` - สำหรับ worker communication
    - **หมายเหตุ**: ควรเพิ่ม authentication

---

## ❌ Endpoints ที่ควร Deprecate (ซ้ำซ้อน)

### 1. Tasks API (Legacy) - 4 endpoints
- `GET /api/tasks/{task_id}` → ใช้ `GET /api/v2/tasks/{task_id}` แทน
- `GET /api/tasks/by-date` → ใช้ `GET /api/v2/tasks/?date=YYYY-MM-DD` แทน
- `GET /api/tasks/summary` → ใช้ `GET /api/v2/tasks/stats/summary` แทน
- `GET /api/tasks/available-dates` → ใช้ `GET /api/v2/tasks/stats/available-dates` แทน

### 2. Progress API - 3 endpoints
- `GET /api/progress/transcription/{task_id}` → ใช้ `GET /api/v2/tasks/{task_id}?format=progress` แทน
- `GET /api/progress/all-active` → ใช้ `GET /api/v2/tasks/?status=processing` แทน
- `GET /api/progress/stats` → ใช้ `GET /api/v2/tasks/stats/summary` แทน

### 3. Polling API - 4 endpoints
- `GET /api/polling/task/{task_id}` → ใช้ `GET /api/v2/tasks/{task_id}?format=minimal` แทน
- `GET /api/polling/tasks/active` → ใช้ `GET /api/v2/tasks/?status=processing` แทน
- `GET /api/polling/tasks/recent` → ใช้ `GET /api/v2/tasks/?limit=N&sort=desc` แทน
- `GET /api/polling/health` → ใช้ `GET /health` แทน

### 4. History API (บางส่วน) - 3 endpoints
- `GET /api/history/transcriptions` → ใช้ `GET /api/v2/tasks/` แทน
- `GET /api/history/transcriptions/{task_id}` → ใช้ `GET /api/v2/tasks/{task_id}` แทน
- `GET /api/history/stats` → ใช้ `GET /api/v2/tasks/stats/summary` แทน

### 5. Enhanced Transcription Status - 1 endpoint
- `GET /api/transcribe-enhanced/status/{task_id}` → ใช้ `GET /api/v2/tasks/{task_id}` แทน

**Total Deprecated**: ~15 endpoints

---

## 🔄 ความต่างระหว่าง Transcription และ Enhanced Transcription

### `/api/transcribe/` (Main)
- ใช้ model size ตามที่ระบุ (base, medium, large-v3)
- ไม่มี Thai text processing
- **เหมาะสำหรับ**: Transcription ทั่วไป

### `/api/transcribe-enhanced/start` (Enhanced)
- ใช้ base model เสมอ (เร็วกว่า)
- เพิ่ม Thai text processing ใน post-processing
- **เหมาะสำหรับ**: เมื่อต้องการความเร็ว + ความแม่นยำ (base model + Thai correction)
- **ความต่าง**: เพิ่ม flag `enable_thai_processing` และใช้ Thai text processor

**Recommendation**: 
- เก็บทั้ง 2 endpoints (ต่างกัน)
- หรือรวมเป็น 1 endpoint พร้อม parameter `enable_thai_processing` และ `use_fast_model`

---

## 🔒 Internal API

### `/api/internal/transcribe`
**Purpose**: สำหรับ worker endpoints (dispatcher → worker)
**Usage**: Internal use only
**Recommendation**: 
- ✅ **เก็บไว้** - จำเป็นสำหรับ worker communication
- ⚠️ **ควรเพิ่ม**: Authentication/Authorization (API key หรือ internal network only)

---

## 📊 สรุปตัวเลข

| Category | Keep | Deprecate | Total |
|----------|------|-----------|-------|
| Core Transcription | 2 | 0 | 2 |
| V2 Unified API | 4 | 0 | 4 |
| Task Status/List (Legacy) | 0 | 4 | 4 |
| Progress API | 0 | 3 | 3 |
| Polling API | 0 | 4 | 4 |
| History API | 2 | 3 | 5 |
| Enhanced Status | 0 | 1 | 1 |
| Webhook | 8 | 0 | 8 |
| Upload | 4 | 0 | 4 |
| Caption | 7 | 0 | 7 |
| WebSocket | 8 | 0 | 8 |
| Monitoring | 4 | 0 | 4 |
| Queue | 7 | 0 | 7 |
| Logs | 5 | 0 | 5 |
| Internal | 1 | 0 | 1 |
| **Total** | **52** | **15** | **67** |

---

## 🎯 Action Plan

### Phase 1: Mark as Deprecated (ทันที)
1. เพิ่ม deprecation warning ใน legacy endpoints
2. เพิ่ม redirect หรือ documentation ไป V2
3. อัปเดต README.md ให้แนะนำใช้ V2

### Phase 2: Consolidate (1-2 สัปดาห์)
1. รวม transcription endpoints (transcribe + enhanced) เป็น 1 endpoint พร้อม parameters
2. Consolidate monitoring/queue stats (ถ้าจำเป็น)

### Phase 3: Remove (3-6 เดือน)
1. ลบ deprecated endpoints หลัง deprecation period
2. อัปเดต documentation

---

## 📝 Migration Guide

### สำหรับ Task Status
**เดิม**: `GET /api/tasks/{task_id}`
**ใหม่**: `GET /api/v2/tasks/{task_id}?format=full`

### สำหรับ Progress Tracking
**เดิม**: `GET /api/progress/transcription/{task_id}`
**ใหม่**: `GET /api/v2/tasks/{task_id}?format=progress`

### สำหรับ Polling
**เดิม**: `GET /api/polling/task/{task_id}`
**ใหม่**: `GET /api/v2/tasks/{task_id}?format=minimal`

### สำหรับ Task List
**เดิม**: `GET /api/history/transcriptions?status=completed`
**ใหม่**: `GET /api/v2/tasks/?status=completed`

---

**Last Updated**: 2024-12-24

