# ⚠️ API Deprecation Notice

## 📅 Deprecation Timeline

**Effective Date**: 2024-12-24
**Removal Date**: 2025-06-24 (6 เดือนหลังจาก deprecation)

---

## 🎯 Deprecated Endpoints

### 1. Tasks API (Legacy)

| Deprecated Endpoint | Recommended Replacement |
|---------------------|------------------------|
| `GET /api/tasks/{task_id}` | `GET /api/v2/tasks/{task_id}?format=full` |
| `GET /api/tasks/by-date` | `GET /api/v2/tasks/?date={date}&status={status}` |
| `GET /api/tasks/summary` | `GET /api/v2/tasks/stats/summary?date={date}` |
| `GET /api/tasks/available-dates` | `GET /api/v2/tasks/stats/available-dates` |

### 2. Progress API

| Deprecated Endpoint | Recommended Replacement |
|---------------------|------------------------|
| `GET /api/progress/transcription/{task_id}` | `GET /api/v2/tasks/{task_id}?format=progress` |
| `GET /api/progress/all-active` | `GET /api/v2/tasks/?status=processing` |
| `GET /api/progress/stats` | `GET /api/v2/tasks/stats/summary` |

### 3. Polling API

| Deprecated Endpoint | Recommended Replacement |
|---------------------|------------------------|
| `GET /api/polling/task/{task_id}` | `GET /api/v2/tasks/{task_id}?format=minimal` |
| `GET /api/polling/tasks/active` | `GET /api/v2/tasks/?status=processing` |
| `GET /api/polling/tasks/recent` | `GET /api/v2/tasks/?limit={limit}&sort=desc` |
| `GET /api/polling/health` | `GET /health` |

### 4. History API (บางส่วน)

| Deprecated Endpoint | Recommended Replacement |
|---------------------|------------------------|
| `GET /api/history/transcriptions` | `GET /api/v2/tasks/?limit={limit}&offset={offset}&status={status}` |
| `GET /api/history/transcriptions/{task_id}` | `GET /api/v2/tasks/{task_id}?format=full` |
| `GET /api/history/stats` | `GET /api/v2/tasks/stats/summary` |

**หมายเหตุ**: `WS /api/history/ws/realtime` และ `DELETE /api/history/transcriptions/{task_id}` ยังใช้งานได้

### 5. Enhanced Transcription Status

| Deprecated Endpoint | Recommended Replacement |
|---------------------|------------------------|
| `GET /api/transcribe-enhanced/status/{task_id}` | `GET /api/v2/tasks/{task_id}?format=full&include_thai_processing=true` |

---

## 🔄 Migration Guide

### Task Status

**เดิม**:
```bash
GET /api/tasks/{task_id}
```

**ใหม่**:
```bash
GET /api/v2/tasks/{task_id}?format=full
```

### Progress Tracking

**เดิม**:
```bash
GET /api/progress/transcription/{task_id}
```

**ใหม่**:
```bash
GET /api/v2/tasks/{task_id}?format=progress
```

### Polling (Minimal)

**เดิม**:
```bash
GET /api/polling/task/{task_id}
```

**ใหม่**:
```bash
GET /api/v2/tasks/{task_id}?format=minimal
```

### Task List

**เดิม**:
```bash
GET /api/history/transcriptions?status=completed&limit=20
```

**ใหม่**:
```bash
GET /api/v2/tasks/?status=completed&limit=20&offset=0
```

---

## ✅ Endpoints ที่ยังใช้งานได้

### Core Transcription
- `POST /api/transcribe/` - Main transcription
- `POST /api/transcribe-enhanced/start` - Enhanced transcription

### V2 Unified API (แนะนำ)
- `GET /api/v2/tasks/{task_id}` - Task status
- `GET /api/v2/tasks/` - Task list
- `GET /api/v2/tasks/stats/summary` - Statistics
- `GET /api/v2/tasks/stats/available-dates` - Available dates

### History API (บางส่วน)
- `WS /api/history/ws/realtime` - WebSocket realtime updates
- `DELETE /api/history/transcriptions/{task_id}` - Delete transcription

### Other APIs
- Webhook, Upload, Caption, WebSocket, Monitoring, Queue, Logs APIs - ทั้งหมดยังใช้งานได้

---

## 📝 Response Changes

### V2 API Response Format

**Format Options**:
- `format=full` - ข้อมูลแบบเต็ม (default)
- `format=progress` - สำหรับ progress tracking
- `format=minimal` - สำหรับ polling (เร็วที่สุด)

**Example**:
```json
{
  "task_id": "abc123...",
  "status": "completed",
  "progress": 100,
  "current_stage": "completed",
  "elapsed_seconds": 120,
  "estimated_remaining_seconds": 0,
  "full_text": "...",
  "chunks": [...]
}
```

---

## ⚠️ Breaking Changes

1. **Response Format**: V2 API มี response format ที่แตกต่างจาก legacy endpoints
2. **Query Parameters**: V2 API ใช้ query parameters ที่แตกต่างกัน
3. **Error Messages**: Error messages อาจแตกต่างกัน

---

## 📞 Support

หากมีคำถามหรือต้องการความช่วยเหลือในการ migrate:
- ดู Documentation: `/docs` (Swagger UI)
- ดู Migration Guide: `ENDPOINT_CONSOLIDATION_SUMMARY.md`

---

**Last Updated**: 2024-12-24

