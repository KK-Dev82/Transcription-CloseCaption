# 📊 Endpoint Analysis และ Consolidation Plan

## ✅ Transcription Test Result

**Test URL**: `https://korrakang.com/video/v10-1.mp4`
**Status**: ✅ ทำงานได้ - Dependencies ครบถ้วน
**Task ID**: `446e597b-a0a3-4c26-bb4b-473bdc353268`

---

## 🔍 Endpoint Duplication Analysis

### 1. **Task Status Endpoints** (ซ้ำซ้อนมากที่สุด)

#### V2 Unified API (แนะนำ - ใช้แทนทั้งหมด)
- `GET /api/v2/tasks/{task_id}` - รองรับ format: full, progress, minimal
- `GET /api/v2/tasks/` - รายการ tasks พร้อม filtering
- `GET /api/v2/tasks/stats/summary` - สถิติ
- `GET /api/v2/tasks/stats/available-dates` - รายการวันที่

#### Legacy Endpoints (ซ้ำซ้อน - ควร deprecate)
- `GET /api/tasks/{task_id}` - ซ้ำกับ V2
- `GET /api/progress/transcription/{task_id}` - ซ้ำกับ V2 (format=progress)
- `GET /api/polling/task/{task_id}` - ซ้ำกับ V2 (format=minimal)
- `GET /api/transcribe-enhanced/status/{task_id}` - ซ้ำกับ V2

**Recommendation**: ใช้ V2 Unified API แทนทั้งหมด

---

### 2. **Task List Endpoints** (ซ้ำซ้อน)

#### V2 Unified API (แนะนำ)
- `GET /api/v2/tasks/` - รองรับ filtering: status, date, date_from, date_to, days_ago, pagination

#### Legacy Endpoints (ซ้ำซ้อน)
- `GET /api/history/transcriptions` - ซ้ำกับ V2 (แต่มี WebSocket support)
- `GET /api/tasks/by-date` - ซ้ำกับ V2 (date filter)
- `GET /api/polling/tasks/active` - ซ้ำกับ V2 (status=processing)
- `GET /api/polling/tasks/recent` - ซ้ำกับ V2 (sort by date desc)
- `GET /api/progress/all-active` - ซ้ำกับ V2 (status=processing)

**Recommendation**: 
- ใช้ V2 Unified API สำหรับ REST
- เก็บ History API เฉพาะ WebSocket endpoint (`/api/history/ws/realtime`)

---

### 3. **Transcription Start Endpoints** (ต่างกัน)

#### `/api/transcribe/` (Main - แนะนำ)
- รองรับ `file_path` และ `file_url`
- Rate limiting (25 concurrent)
- Callback URL support
- **ใช้**: สำหรับ transcription ทั่วไป

#### `/api/transcribe-enhanced/start` (Enhanced)
- ใช้ logic เดียวกับ `/api/transcribe/`
- เพิ่ม flag `enable_thai_processing`
- **ใช้**: เมื่อต้องการ Thai processing
- **ความต่าง**: เพิ่ม Thai text correction ใน post-processing

**Recommendation**: 
- เก็บทั้ง 2 endpoints (ต่างกัน)
- หรือรวมเป็น 1 endpoint พร้อม parameter `enable_thai_processing`

---

### 4. **Internal API** (`/api/internal/transcribe`)

**Purpose**: สำหรับ worker endpoints (dispatcher → worker)
**Usage**: Internal use only (ไม่ควร expose ต่อ public)
**Recommendation**: 
- ✅ **เก็บไว้** - จำเป็นสำหรับ worker communication
- แต่ควรเพิ่ม authentication/authorization

---

### 5. **History vs Tasks vs Progress** (ซ้ำซ้อน)

#### History API
- `GET /api/history/transcriptions` - รายการ transcriptions
- `GET /api/history/transcriptions/{task_id}` - รายละเอียด
- `GET /api/history/stats` - สถิติ
- `DELETE /api/history/transcriptions/{task_id}` - ลบ
- `WS /api/history/ws/realtime` - WebSocket realtime updates

#### Tasks API (Legacy)
- `GET /api/tasks/{task_id}` - ซ้ำกับ V2
- `GET /api/tasks/by-date` - ซ้ำกับ V2
- `GET /api/tasks/summary` - ซ้ำกับ V2 stats
- `GET /api/tasks/available-dates` - ซ้ำกับ V2

#### Progress API
- `GET /api/progress/transcription/{task_id}` - ซ้ำกับ V2 (format=progress)
- `GET /api/progress/all-active` - ซ้ำกับ V2 (status=processing)
- `GET /api/progress/stats` - ซ้ำกับ V2 stats

**Recommendation**:
- ✅ **เก็บ History API** - มี WebSocket support และ DELETE endpoint
- ❌ **Deprecate Tasks API** - ใช้ V2 แทน
- ❌ **Deprecate Progress API** - ใช้ V2 แทน

---

### 6. **Monitoring vs Queue** (ซ้ำซ้อนบางส่วน)

#### Monitoring API
- `GET /api/monitoring/` - รวม stats
- `GET /api/monitoring/redis` - Redis stats
- `GET /api/monitoring/queues` - Queue stats
- `GET /api/monitoring/system` - System stats

#### Queue API
- `GET /api/queue/info` - Queue information
- `GET /api/queue/status` - Queue status
- `GET /api/queue/stats` - Queue statistics
- `GET /api/queue/health` - Health check
- `POST /api/queue/purge/{queue_name}` - Purge queue
- `POST /api/queue/test-flow` - Test flow
- `GET /api/queue/check-task/{task_id}` - Check task

**Recommendation**:
- ✅ **เก็บทั้ง 2** - Monitoring สำหรับ dashboard, Queue สำหรับ management
- แต่ควร consolidate queue stats เข้า monitoring

---

### 7. **Webhook API** (ไม่ซ้ำ - จำเป็น)

- `POST /api/webhook/subscribe` - Subscribe
- `GET /api/webhook/subscriptions` - List subscriptions
- `GET /api/webhook/subscribe/{subscription_id}` - Get subscription
- `DELETE /api/webhook/subscribe/{subscription_id}` - Unsubscribe
- `POST /api/webhook/test` - Test webhook
- `GET /api/webhook/stats` - Stats
- `POST /api/webhook/verify-signature` - Verify signature
- `GET /api/webhook/events` - Events

**Recommendation**: ✅ **เก็บไว้** - ไม่ซ้ำซ้อน

---

### 8. **Upload API** (ไม่ซ้ำ - จำเป็น)

- `POST /api/upload/` - Upload file
- `GET /api/upload/list` - List uploaded files
- `GET /api/upload/{file_id}/info` - File info
- `GET /api/upload/info/{file_path}` - File info by path

**Recommendation**: ✅ **เก็บไว้** - ไม่ซ้ำซ้อน

---

### 9. **Caption API** (ไม่ซ้ำ - จำเป็น)

- `POST /api/caption/` - Create caption
- `GET /api/caption/{task_id}` - Get caption
- `GET /api/caption/` - List captions
- `DELETE /api/caption/{task_id}` - Delete caption
- `GET /api/caption/{task_id}/subtitle` - Get subtitle
- `GET /api/caption/{task_id}/segments` - Get segments
- `POST /api/caption/cleanup` - Cleanup

**Recommendation**: ✅ **เก็บไว้** - ไม่ซ้ำซ้อน

---

### 10. **WebSocket** (ไม่ซ้ำ - จำเป็น)

- `WS /ws` - Main WebSocket endpoint
- `GET /ws/stats` - WebSocket stats
- `GET /api/websocket/status` - Status
- `GET /api/websocket/connections` - Connections
- `GET /api/websocket/subscriptions/{user_id}` - Subscriptions
- `POST /api/websocket/test-broadcast` - Test broadcast
- `GET /api/websocket/diagnostics` - Diagnostics
- `WS /api/history/ws/realtime` - History realtime updates

**Recommendation**: ✅ **เก็บไว้** - ไม่ซ้ำซ้อน

---

### 11. **Logs API** (ไม่ซ้ำ - จำเป็น)

- `GET /api/logs/` - List logs
- `GET /api/logs/{log_name}` - Get log
- `GET /api/logs/{log_name}/search` - Search log
- `GET /api/logs/{log_name}/stats` - Log stats
- `GET /api/logs/all/recent` - Recent logs

**Recommendation**: ✅ **เก็บไว้** - ไม่ซ้ำซ้อน

---

### 12. **Other APIs** (Optional/Unused)

#### Video Processing API
- หลาย endpoints สำหรับ video processing
- **Recommendation**: เก็บไว้ถ้าใช้งาน

#### RTMP Streaming API
- หลาย endpoints สำหรับ RTMP streaming
- **Recommendation**: เก็บไว้ถ้าใช้งาน

#### Realtime Caption API
- หลาย endpoints สำหรับ realtime caption
- **Recommendation**: เก็บไว้ถ้าใช้งาน

#### Thai Processing API
- หลาย endpoints สำหรับ Thai text processing
- **Recommendation**: เก็บไว้ถ้าใช้งาน

#### Live Streaming API
- หลาย endpoints สำหรับ live streaming
- **Recommendation**: เก็บไว้ถ้าใช้งาน

#### Files API
- `POST /api/files/uploaded` - Mark file as uploaded
- **Recommendation**: เก็บไว้ถ้าใช้งาน

#### Management API
- หลาย endpoints สำหรับ system management
- **Recommendation**: เก็บไว้สำหรับ admin/internal use

#### Dashboard API
- หลาย endpoints สำหรับ dashboard
- **Recommendation**: เก็บไว้สำหรับ dashboard

#### Cleanup API
- `GET /api/cleanup/disk-space` - Disk space
- `POST /api/cleanup/temp-folders` - Cleanup temp
- `GET /api/cleanup/status` - Status
- **Recommendation**: เก็บไว้สำหรับ maintenance

---

## 📋 Consolidation Recommendations

### ✅ Keep (จำเป็น)

1. **Core Transcription**
   - `POST /api/transcribe/` - Main transcription endpoint
   - `POST /api/transcribe-enhanced/start` - Enhanced transcription (หรือรวมเป็น parameter)

2. **V2 Unified API** (แนะนำ)
   - `GET /api/v2/tasks/{task_id}` - Task status (รองรับ format)
   - `GET /api/v2/tasks/` - Task list (filtering)
   - `GET /api/v2/tasks/stats/summary` - Stats
   - `GET /api/v2/tasks/stats/available-dates` - Available dates

3. **History API** (เก็บเฉพาะ WebSocket และ DELETE)
   - `WS /api/history/ws/realtime` - WebSocket realtime
   - `DELETE /api/history/transcriptions/{task_id}` - Delete

4. **Webhook API** - ทั้งหมด

5. **Upload API** - ทั้งหมด

6. **Caption API** - ทั้งหมด

7. **WebSocket API** - ทั้งหมด

8. **Monitoring API** - ทั้งหมด

9. **Queue API** - ทั้งหมด (แต่ consolidate stats)

10. **Logs API** - ทั้งหมด

11. **Internal API** - เก็บไว้ (แต่เพิ่ม auth)

---

### ❌ Deprecate (ซ้ำซ้อน)

1. **Tasks API (Legacy)**
   - `GET /api/tasks/{task_id}` → ใช้ V2 แทน
   - `GET /api/tasks/by-date` → ใช้ V2 แทน
   - `GET /api/tasks/summary` → ใช้ V2 แทน
   - `GET /api/tasks/available-dates` → ใช้ V2 แทน

2. **Progress API**
   - `GET /api/progress/transcription/{task_id}` → ใช้ V2 (format=progress) แทน
   - `GET /api/progress/all-active` → ใช้ V2 (status=processing) แทน
   - `GET /api/progress/stats` → ใช้ V2 stats แทน

3. **Polling API**
   - `GET /api/polling/task/{task_id}` → ใช้ V2 (format=minimal) แทน
   - `GET /api/polling/tasks/active` → ใช้ V2 (status=processing) แทน
   - `GET /api/polling/tasks/recent` → ใช้ V2 (sort desc) แทน
   - `GET /api/polling/health` → ใช้ `/health` แทน

4. **History API (บางส่วน)**
   - `GET /api/history/transcriptions` → ใช้ V2 แทน (แต่เก็บ WebSocket)
   - `GET /api/history/transcriptions/{task_id}` → ใช้ V2 แทน
   - `GET /api/history/stats` → ใช้ V2 stats แทน

5. **Enhanced Transcription Status**
   - `GET /api/transcribe-enhanced/status/{task_id}` → ใช้ V2 แทน

---

## 🎯 Action Plan

### Phase 1: Mark as Deprecated
1. เพิ่ม deprecation warning ใน legacy endpoints
2. เพิ่ม redirect หรือ documentation ไป V2

### Phase 2: Consolidate
1. รวม transcription endpoints (transcribe + enhanced)
2. Consolidate monitoring/queue stats

### Phase 3: Remove
1. ลบ deprecated endpoints หลัง deprecation period (3-6 เดือน)

---

## 📊 Summary

| Category | Keep | Deprecate | Total |
|----------|------|-----------|-------|
| Core Transcription | 2 | 0 | 2 |
| Task Status/List | 1 (V2) | 3 (Tasks, Progress, Polling) | 4 |
| History | 2 (WebSocket, DELETE) | 3 (REST endpoints) | 5 |
| Webhook | 8 | 0 | 8 |
| Upload | 4 | 0 | 4 |
| Caption | 7 | 0 | 7 |
| WebSocket | 8 | 0 | 8 |
| Monitoring | 4 | 0 | 4 |
| Queue | 7 | 0 | 7 |
| Logs | 5 | 0 | 5 |
| Internal | 1 | 0 | 1 |
| Other | ~50 | 0 | ~50 |

**Total Endpoints**: ~100+
**Recommended Keep**: ~60
**Recommended Deprecate**: ~10

---

**Last Updated**: 2024-12-24

