# 📋 API Consolidation Plan - แผนการรวม API ที่ซ้ำซ้อน

> **วันที่สร้าง:** 29 ธันวาคม 2025  
> **วัตถุประสงค์:** ลดความซ้ำซ้อนของ API endpoints และทำให้ระบบเรียบง่ายขึ้น

---

## 🎯 สรุปการเปลี่ยนแปลง

จาก **129 endpoints** → **~115 endpoints** (ลด ~10-15 endpoints ที่ซ้ำซ้อน)

---

## 📊 แผนการรวม API แบ่งเป็น 3 กลุ่มหลัก

### **1️⃣ กลุ่มที่ 1: Unified Task Status API** ⭐ สำคัญที่สุด

#### ปัญหาปัจจุบัน
มี **4 endpoints** ทำหน้าที่เดียวกัน (ดึงสถานะ task):

```
❌ GET /api/tasks/{task_id}                            # tasks.py
❌ GET /api/progress/transcription/{task_id}            # progress.py  
❌ GET /api/polling/task/{task_id}                      # polling.py
❌ GET /api/transcribe-enhanced/status/{task_id}        # transcription_enhanced.py
```

#### แนวทางแก้ไข: รวมเป็น 1 endpoint หลัก

```python
✅ GET /api/v2/tasks/{task_id}

# Query Parameters:
# - format: full|progress|minimal (default: full)
# - include_chunks: true|false (default: false)
# - include_thai_processing: true|false (default: false)
```

#### ตัวอย่าง Usage:

```bash
# 1. ดึงข้อมูลแบบเต็ม (แทน tasks.py)
GET /api/v2/tasks/{task_id}?format=full

# 2. ดึงแบบ progress tracking (แทน progress.py)
GET /api/v2/tasks/{task_id}?format=progress

# 3. ดึงแบบ polling (แทน polling.py)
GET /api/v2/tasks/{task_id}?format=minimal

# 4. ดึงพร้อม Thai processing info (แทน transcription_enhanced.py)
GET /api/v2/tasks/{task_id}?format=full&include_thai_processing=true
```

#### Response Format:

```json
{
  "task_id": "abc-123",
  "status": "completed",
  "progress": 100,
  "format": "full",
  
  // ข้อมูลพื้นฐาน (ทุก format)
  "file_path": "/uploads/video.mp4",
  "filename": "video.mp4",
  "language": "th",
  "created_at": "2025-12-29T10:00:00Z",
  "updated_at": "2025-12-29T10:05:00Z",
  
  // ข้อมูล progress (format=progress หรือ full)
  "current_stage": "finalizing",
  "stage_progress": 95,
  "elapsed_seconds": 300,
  "estimated_remaining_seconds": 15,
  
  // ข้อมูล chunks (include_chunks=true)
  "chunks": [...],
  "total_chunks": 10,
  
  // ข้อมูล Thai processing (include_thai_processing=true)
  "thai_processed": true,
  "thai_processing_stats": {
    "total_corrections": 15,
    "average_confidence": 0.92
  },
  
  // ข้อมูลเต็ม (format=full)
  "result": {
    "text": "...",
    "segments": [...],
    "word_segments": [...]
  }
}
```

---

### **2️⃣ กลุ่มที่ 2: Unified Task List API**

#### ปัญหาปัจจุบัน
มี **4 endpoints** ทำหน้าที่คล้ายกัน (ดึงรายการ tasks):

```
❌ GET /api/history/transcriptions                     # history.py
❌ GET /api/tasks/by-date                               # tasks.py
❌ GET /api/polling/tasks/active                        # polling.py
❌ GET /api/polling/tasks/recent                        # polling.py
```

#### แนวทางแก้ไข: รวมเป็น 1 endpoint หลัก

```python
✅ GET /api/v2/tasks

# Query Parameters (ใช้ filters แทน endpoints แยก):
# - status: completed|failed|processing|pending (filter by status)
# - date: YYYY-MM-DD (filter by specific date)
# - date_from: YYYY-MM-DD (filter from date)
# - date_to: YYYY-MM-DD (filter to date)
# - days_ago: integer (last N days)
# - active: true|false (active tasks only)
# - limit: integer (default: 20, max: 100)
# - offset: integer (default: 0)
# - sort: created_at|updated_at|filename (default: updated_at)
# - order: asc|desc (default: desc)
# - filename_contains: string (search in filename)
```

#### ตัวอย่าง Usage:

```bash
# 1. ดึงประวัติทั้งหมด (แทน history/transcriptions)
GET /api/v2/tasks?limit=20&offset=0

# 2. ดึงตามวันที่ (แทน tasks/by-date)
GET /api/v2/tasks?date=2025-12-29

# 3. ดึง active tasks (แทน polling/tasks/active)
GET /api/v2/tasks?status=processing&active=true

# 4. ดึง recent tasks (แทน polling/tasks/recent)
GET /api/v2/tasks?limit=10&sort=updated_at&order=desc

# 5. ดึงแบบ complex filter
GET /api/v2/tasks?status=completed&days_ago=7&filename_contains=meeting
```

#### Response Format:

```json
{
  "total_count": 150,
  "limit": 20,
  "offset": 0,
  "has_more": true,
  "filters_applied": {
    "status": "completed",
    "days_ago": 7
  },
  "tasks": [
    {
      "task_id": "abc-123",
      "filename": "meeting.mp4",
      "status": "completed",
      "progress": 100,
      "created_at": "2025-12-29T10:00:00Z",
      "updated_at": "2025-12-29T10:05:00Z",
      "duration": 300,
      "language": "th"
    }
  ]
}
```

---

### **3️⃣ กลุ่มที่ 3: Unified Upload API**

#### ปัญหาปัจจุบัน
มี **2 endpoints** สำหรับ upload:

```
✅ POST /api/upload/                                    # upload.py (ครบถ้วน)
❌ POST /api/video/upload                               # video.py (ซ้ำซ้อน)
```

#### แนวทางแก้ไข: ใช้ upload.py เป็นหลัก

```python
✅ POST /api/upload/

# รองรับ:
# 1. Upload ไฟล์โดยตรง (multipart/form-data)
# 2. Upload จาก URL (form field: url)
# 3. รองรับทั้ง video และ audio files
```

**เก็บ:** `/api/upload/` (มีฟีเจอร์ครบแล้ว)  
**ลบ:** `/api/video/upload` (ใช้ `/api/upload/` แทน)

---

## 🗂️ แผนการ Implementation

### Phase 1: สร้าง Unified APIs ใหม่ (v2)

#### 1.1 สร้างไฟล์ใหม่

```
app/api/v2/
├── __init__.py
├── unified_tasks.py      # รวม tasks, progress, polling
└── README.md             # Documentation
```

#### 1.2 Implementation Timeline

| Task | File | Status | Priority |
|------|------|--------|----------|
| สร้าง `unified_tasks.py` | `app/api/v2/unified_tasks.py` | ⏳ Todo | 🔴 สูง |
| สร้าง `unified_history.py` | `app/api/v2/unified_history.py` | ⏳ Todo | 🔴 สูง |
| ปรับปรุง `upload.py` | `app/api/upload.py` | ⏳ Todo | 🟡 ปานกลาง |
| อัปเดต `main.py` | `app/main.py` | ⏳ Todo | 🔴 สูง |
| สร้าง Migration Guide | `MIGRATION_GUIDE.md` | ⏳ Todo | 🟡 ปานกลาง |

---

### Phase 2: Deprecation Strategy

#### 2.1 Mark old endpoints as deprecated

เพิ่ม warning message ใน response:

```python
return {
    "data": {...},
    "_deprecated": {
        "message": "This endpoint is deprecated. Please use /api/v2/tasks/{task_id} instead",
        "new_endpoint": "/api/v2/tasks/{task_id}",
        "removal_date": "2026-03-01"
    }
}
```

#### 2.2 Deprecation Timeline

| Endpoint | Deprecated Date | Removal Date |
|----------|----------------|--------------|
| `/api/progress/transcription/{task_id}` | 2025-12-29 | 2026-03-01 |
| `/api/polling/task/{task_id}` | 2025-12-29 | 2026-03-01 |
| `/api/transcribe-enhanced/status/{task_id}` | 2025-12-29 | 2026-03-01 |
| `/api/tasks/by-date` | 2025-12-29 | 2026-03-01 |
| `/api/polling/tasks/active` | 2025-12-29 | 2026-03-01 |
| `/api/polling/tasks/recent` | 2025-12-29 | 2026-03-01 |
| `/api/video/upload` | 2025-12-29 | 2026-03-01 |

---

### Phase 3: Documentation & Testing

#### 3.1 สร้างเอกสาร

- [ ] API Migration Guide
- [ ] Updated OpenAPI/Swagger docs
- [ ] Code examples สำหรับ v2 APIs
- [ ] Postman collection อัปเดต

#### 3.2 Testing Plan

```bash
# Unit tests สำหรับ unified endpoints
pytest tests/api/v2/test_unified_tasks.py
pytest tests/api/v2/test_unified_history.py

# Integration tests
pytest tests/integration/test_api_consolidation.py

# Backward compatibility tests
pytest tests/compatibility/test_deprecated_endpoints.py
```

---

## 📝 ตัวอย่าง Code Implementation

### 1. Unified Tasks API (`app/api/v2/unified_tasks.py`)

```python
"""
Unified Tasks API - รวม tasks, progress, polling endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Literal
from pydantic import BaseModel

router = APIRouter(prefix="/api/v2/tasks", tags=["Tasks V2"])

@router.get("/{task_id}")
async def get_task(
    task_id: str,
    format: Literal["full", "progress", "minimal"] = Query("full"),
    include_chunks: bool = Query(False),
    include_thai_processing: bool = Query(False)
):
    """
    🎯 Unified Task Status API
    
    รวม endpoints:
    - GET /api/tasks/{task_id} (tasks.py)
    - GET /api/progress/transcription/{task_id} (progress.py)
    - GET /api/polling/task/{task_id} (polling.py)
    - GET /api/transcribe-enhanced/status/{task_id} (transcription_enhanced.py)
    
    Parameters:
    - format: full|progress|minimal (default: full)
    - include_chunks: รวม chunks หรือไม่ (default: false)
    - include_thai_processing: รวมข้อมูล Thai processing (default: false)
    """
    from app.utils.json_storage import JSONStorage
    from app.utils.sqlite_storage import SQLiteStorage
    
    # Try SQLite first, fallback to JSON
    sqlite_storage = SQLiteStorage()
    json_storage = JSONStorage()
    
    task = sqlite_storage.get_transcription(task_id)
    if not task:
        task = json_storage.get_transcription(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Build response based on format
    if format == "minimal":
        return _build_minimal_response(task)
    elif format == "progress":
        return _build_progress_response(task)
    else:  # full
        return _build_full_response(
            task,
            include_chunks=include_chunks,
            include_thai_processing=include_thai_processing
        )

def _build_minimal_response(task: dict) -> dict:
    """สำหรับ polling (เร็วที่สุด)"""
    return {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "progress": task.get("progress", 0),
        "updated_at": task.get("updated_at")
    }

def _build_progress_response(task: dict) -> dict:
    """สำหรับ progress tracking"""
    from datetime import datetime
    
    response = {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "progress": task.get("progress", 0),
        "current_stage": task.get("current_stage"),
        "stage_progress": task.get("stage_progress"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
    }
    
    # Calculate elapsed time
    if task.get("created_at") and task.get("updated_at"):
        try:
            created = datetime.fromisoformat(str(task["created_at"]).replace("Z", "+00:00"))
            updated = datetime.fromisoformat(str(task["updated_at"]).replace("Z", "+00:00"))
            elapsed = (updated - created).total_seconds()
            response["elapsed_seconds"] = elapsed
            
            # Estimate remaining time
            if response["progress"] > 0 and response["progress"] < 100:
                estimated_total = elapsed / (response["progress"] / 100)
                remaining = estimated_total - elapsed
                response["estimated_remaining_seconds"] = max(0, int(remaining))
        except:
            pass
    
    return response

def _build_full_response(
    task: dict,
    include_chunks: bool = False,
    include_thai_processing: bool = False
) -> dict:
    """ข้อมูลแบบเต็ม"""
    response = {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "progress": task.get("progress", 0),
        "filename": task.get("filename"),
        "file_path": task.get("file_path"),
        "language": task.get("language"),
        "model_size": task.get("model_size"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "completed_at": task.get("completed_at"),
    }
    
    # Include result if completed
    if task.get("status") == "completed":
        response["result"] = {
            "text": task.get("text", ""),
            "segments": task.get("segments", []),
            "word_segments": task.get("word_segments", [])
        }
    
    # Include chunks if requested
    if include_chunks:
        response["chunks"] = task.get("chunks", [])
        response["total_chunks"] = len(task.get("chunks", []))
    
    # Include Thai processing info if requested
    if include_thai_processing:
        response["thai_processed"] = task.get("thai_processed", False)
        if task.get("thai_processing_stats"):
            response["thai_processing_stats"] = task.get("thai_processing_stats")
        if task.get("original_text"):
            response["original_text"] = task.get("original_text")
    
    return response

@router.get("/")
async def list_tasks(
    status: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    days_ago: Optional[int] = Query(None),
    active: Optional[bool] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: Literal["created_at", "updated_at", "filename"] = Query("updated_at"),
    order: Literal["asc", "desc"] = Query("desc"),
    filename_contains: Optional[str] = Query(None)
):
    """
    🎯 Unified Task List API
    
    รวม endpoints:
    - GET /api/history/transcriptions (history.py)
    - GET /api/tasks/by-date (tasks.py)
    - GET /api/polling/tasks/active (polling.py)
    - GET /api/polling/tasks/recent (polling.py)
    
    Filters:
    - status: completed|failed|processing|pending
    - date: YYYY-MM-DD (specific date)
    - date_from, date_to: date range
    - days_ago: last N days
    - active: active tasks only
    - filename_contains: search in filename
    """
    from app.utils.sqlite_storage import SQLiteStorage
    from app.utils.json_storage import JSONStorage
    from datetime import datetime, timedelta
    
    # Get all tasks
    sqlite_storage = SQLiteStorage()
    json_storage = JSONStorage()
    
    all_tasks = sqlite_storage.list_all_transcriptions()
    if not all_tasks:
        all_tasks = json_storage.list_all_transcriptions()
    
    # Apply filters
    filtered_tasks = all_tasks
    
    # Status filter
    if status:
        filtered_tasks = [t for t in filtered_tasks if t.get("status") == status]
    
    # Active filter
    if active:
        filtered_tasks = [t for t in filtered_tasks if t.get("status") == "processing"]
    
    # Date filters
    if date:
        from datetime import datetime
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        filtered_tasks = [
            t for t in filtered_tasks
            if _get_task_date(t) == target_date
        ]
    
    if date_from or date_to:
        if date_from:
            from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
            filtered_tasks = [
                t for t in filtered_tasks
                if _get_task_date(t) >= from_date
            ]
        if date_to:
            to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
            filtered_tasks = [
                t for t in filtered_tasks
                if _get_task_date(t) <= to_date
            ]
    
    if days_ago:
        cutoff = datetime.now() - timedelta(days=days_ago)
        filtered_tasks = [
            t for t in filtered_tasks
            if datetime.fromisoformat(
                str(t.get("created_at", "1970-01-01T00:00:00")).replace("Z", "+00:00")
            ) >= cutoff
        ]
    
    # Filename filter
    if filename_contains:
        filtered_tasks = [
            t for t in filtered_tasks
            if filename_contains.lower() in (t.get("filename") or "").lower()
        ]
    
    # Sort
    reverse = (order == "desc")
    filtered_tasks.sort(
        key=lambda x: x.get(sort) or "1970-01-01T00:00:00",
        reverse=reverse
    )
    
    # Pagination
    total_count = len(filtered_tasks)
    paginated_tasks = filtered_tasks[offset:offset + limit]
    
    return {
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total_count,
        "filters_applied": {
            k: v for k, v in {
                "status": status,
                "date": date,
                "date_from": date_from,
                "date_to": date_to,
                "days_ago": days_ago,
                "active": active,
                "filename_contains": filename_contains
            }.items() if v is not None
        },
        "tasks": [
            {
                "task_id": t.get("task_id"),
                "filename": t.get("filename"),
                "status": t.get("status"),
                "progress": t.get("progress", 0),
                "created_at": t.get("created_at"),
                "updated_at": t.get("updated_at"),
                "language": t.get("language"),
                "duration": t.get("duration")
            }
            for t in paginated_tasks
        ]
    }

def _get_task_date(task: dict):
    """Extract date from task"""
    created_at = task.get("created_at")
    if not created_at:
        return None
    try:
        dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        return dt.date()
    except:
        return None
```

---

## 🔄 Migration Guide สำหรับ Clients

### Before (Old Endpoints)

```javascript
// Old way - ดึงสถานะ task
GET /api/tasks/abc-123
GET /api/progress/transcription/abc-123
GET /api/polling/task/abc-123

// Old way - ดึงรายการ tasks
GET /api/history/transcriptions?limit=20
GET /api/tasks/by-date?date=2025-12-29
GET /api/polling/tasks/active

// Old way - upload
POST /api/video/upload
```

### After (New Unified Endpoints)

```javascript
// ✅ New way - ดึงสถานะ task (เลือก format ตามต้องการ)
GET /api/v2/tasks/abc-123?format=full
GET /api/v2/tasks/abc-123?format=progress
GET /api/v2/tasks/abc-123?format=minimal

// ✅ New way - ดึงรายการ tasks (ใช้ filters)
GET /api/v2/tasks?limit=20
GET /api/v2/tasks?date=2025-12-29
GET /api/v2/tasks?status=processing&active=true

// ✅ New way - upload (ใช้ unified endpoint)
POST /api/upload/
```

---

## ✅ Benefits

1. **ลดความซับซ้อน** - จาก 129 endpoints → ~115 endpoints
2. **ง่ายต่อการใช้งาน** - clients ไม่ต้องจำ endpoints หลายตัว
3. **Flexible Filtering** - ใช้ query parameters แทนการสร้าง endpoints ใหม่
4. **Backward Compatible** - เก็บ old endpoints ไว้ชั่วคราว พร้อม deprecation warnings
5. **Better Performance** - ลด overhead จากการมี endpoints ซ้ำซ้อน
6. **Easy to Maintain** - code อยู่ที่เดียว แก้ไขง่าย

---

## 📅 Implementation Schedule

| Phase | Timeline | Tasks |
|-------|----------|-------|
| Phase 1 | Week 1 | สร้าง v2 APIs, Testing |
| Phase 2 | Week 2 | Add deprecation warnings, Documentation |
| Phase 3 | Week 3-4 | Client migration support |
| Phase 4 | Month 2-3 | Monitor usage, prepare for removal |
| Phase 5 | Month 3 | Remove deprecated endpoints |

---

## 🎓 Next Steps

1. ✅ Review แผนนี้กับทีม
2. ⏳ สร้าง unified APIs (v2)
3. ⏳ เพิ่ม deprecation warnings
4. ⏳ สร้าง migration guide
5. ⏳ อัปเดต documentation
6. ⏳ Notify clients เกี่ยวกับ API changes
7. ⏳ Monitor และเก็บ metrics
8. ⏳ ลบ deprecated endpoints ตาม timeline

---

**หมายเหตุ:** แผนนี้สามารถปรับเปลี่ยนได้ตามความเหมาะสม โดยคำนึงถึง backward compatibility และผลกระทบต่อ clients ที่มีอยู่





