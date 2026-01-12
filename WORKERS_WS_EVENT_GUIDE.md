# 📡 คู่มือการใช้ HTTP Callback สำหรับ WebSocket Notifications

## 🔍 ผลการตรวจสอบ

### ❌ Workers ไม่ได้เรียก `/api/internal/ws-event`

**สถานะปัจจุบัน:**
- Workers ใช้ `websocket_manager` โดยตรง (import และเรียกใช้ใน-process)
- Workers ใช้ `websocket_manager.notify_transcription_progress()`, `notify_transcription_completed()`, `broadcast_task_update()` โดยตรง
- **ปัญหา**: Workers อยู่คนละ process กับ Main API → `websocket_manager` ใน worker process ไม่มี WebSocket connections

**Code ที่ใช้อยู่:**
```python
# ใน app/workers/rq_worker.py
from app.services.websocket_service import websocket_manager
await websocket_manager.notify_transcription_progress(...)  # ❌ ไม่ทำงานใน worker process
```

---

## ✅ แนวทางแก้ไข: ใช้ HTTP Callback `/api/internal/ws-event`

### 1. สำหรับ Transcription Tasks

**แทนที่:**
```python
# ❌ ไม่ทำงาน (worker process ไม่มี WebSocket connections)
from app.services.websocket_service import websocket_manager
await websocket_manager.notify_transcription_progress(
    task_id=task_id,
    progress=progress,
    status=status,
    stage=stage
)
```

**ใช้:**
```python
# ✅ ใช้ HTTP callback
import aiohttp
import os

MAIN_API_URL = os.getenv('MAIN_API_URL', 'http://localhost:8010')

async def send_ws_event(task_id: str, message: dict):
    """Send WebSocket event via HTTP callback"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{MAIN_API_URL}/api/internal/ws-event",
                json={
                    "task_id": task_id,
                    "message": message
                },
                timeout=aiohttp.ClientTimeout(total=5.0)
            ) as response:
                if response.status == 200:
                    logger.debug(f"✅ WS event sent for {task_id}")
                else:
                    logger.warning(f"⚠️  WS event failed: {response.status}")
    except Exception as e:
        logger.warning(f"⚠️  Failed to send WS event: {e}")

# ใช้ใน worker
await send_ws_event(task_id, {
    "type": "transcription.progress",
    "progress": progress,
    "status": status,
    "stage": stage,
    "timestamp": datetime.now().isoformat()
})
```

**Payload สำหรับ transcription.progress:**
```json
{
  "task_id": "abc-123",
  "message": {
    "type": "transcription.progress",
    "progress": 45,
    "status": "processing",
    "stage": "transcribing",
    "timestamp": "2026-01-12T12:00:00Z"
  }
}
```

**Payload สำหรับ transcription.completed:**
```json
{
  "task_id": "abc-123",
  "message": {
    "type": "transcription.completed",
    "status": "completed",
    "text_length": 1234,
    "chunks_count": 10,
    "results_summary": {
      "duration": 120.5,
      "language": "th",
      "processing_time": 45.2
    },
    "timestamp": "2026-01-12T12:00:00Z"
  }
}
```

**Payload สำหรับ transcription.failed:**
```json
{
  "task_id": "abc-123",
  "message": {
    "type": "transcription.failed",
    "status": "failed",
    "error": "Transcription failed",
    "timestamp": "2026-01-12T12:00:00Z"
  }
}
```

---

### 2. สำหรับ Live-Chunk Events

**แทนที่:**
```python
# ❌ ไม่ทำงาน (worker process ไม่มี WebSocket connections)
from app.services.websocket_service import websocket_manager
await websocket_manager.send_to_user(meeting_id, final_event)
```

**ใช้:**
```python
# ✅ ใช้ HTTP callback
async def send_live_chunk_event(meeting_id: str, message: dict):
    """Send live-chunk event via HTTP callback"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{MAIN_API_URL}/api/internal/ws-event",
                json={
                    "meeting_id": meeting_id,
                    "message": message
                },
                timeout=aiohttp.ClientTimeout(total=5.0)
            ) as response:
                if response.status == 200:
                    logger.debug(f"✅ Live-chunk event sent for {meeting_id}")
                else:
                    logger.warning(f"⚠️  Live-chunk event failed: {response.status}")
    except Exception as e:
        logger.warning(f"⚠️  Failed to send live-chunk event: {e}")

# ใช้ใน worker
await send_live_chunk_event(meeting_id, {
    "type": "caption.chunk",
    "session_id": session_id,
    "chunk_index": chunk_index,
    "text": chunk_text,
    "start_time": start_time,
    "duration": duration,
    "timestamp": datetime.now().isoformat()
})
```

**Payload สำหรับ live-chunk:**
```json
{
  "meeting_id": "meeting-123",
  "message": {
    "type": "caption.chunk",
    "session_id": "session-456",
    "chunk_index": 5,
    "text": "Hello world",
    "start_time": 10.5,
    "duration": 2.0,
    "timestamp": "2026-01-12T12:00:00Z"
  }
}
```

---

## 📋 Implementation Guide

### Step 1: สร้าง Helper Function

**เพิ่มใน `app/workers/rq_worker.py`:**
```python
import aiohttp
import os
import logging

logger = logging.getLogger(__name__)

MAIN_API_URL = os.getenv('MAIN_API_URL', 'http://localhost:8010')

async def send_ws_event_via_http(task_id: str = None, meeting_id: str = None, message: dict = None):
    """
    Send WebSocket event via HTTP callback to Main API
    
    Args:
        task_id: Task ID (for transcription tasks)
        meeting_id: Meeting ID (for live-chunk events)
        message: Message payload
    """
    if not task_id and not meeting_id:
        logger.warning("⚠️  send_ws_event_via_http: missing task_id or meeting_id")
        return
    
    if not message:
        logger.warning("⚠️  send_ws_event_via_http: missing message")
        return
    
    try:
        payload = {
            "message": message
        }
        if task_id:
            payload["task_id"] = task_id
        if meeting_id:
            payload["meeting_id"] = meeting_id
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{MAIN_API_URL}/api/internal/ws-event",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5.0)
            ) as response:
                if response.status == 200:
                    logger.debug(f"✅ WS event sent: {task_id or meeting_id}")
                else:
                    logger.warning(f"⚠️  WS event failed: {response.status}")
    except Exception as e:
        logger.warning(f"⚠️  Failed to send WS event via HTTP: {e}")
```

### Step 2: แทนที่ใน `_update_task_stage_and_webhook`

**แทนที่:**
```python
# ❌ เก่า
from app.services.websocket_service import websocket_manager
await websocket_manager.notify_transcription_progress(...)
```

**ใช้:**
```python
# ✅ ใหม่
from app.workers.rq_worker import send_ws_event_via_http
await send_ws_event_via_http(
    task_id=task_id,
    message={
        "type": "transcription.progress",
        "progress": progress,
        "status": status,
        "stage": stage or stage_description,
        "timestamp": datetime.now().isoformat()
    }
)
```

### Step 3: แทนที่ใน `_send_completion_callback`

**แทนที่:**
```python
# ❌ เก่า
await websocket_manager.notify_transcription_completed(task_id, results)
await websocket_manager.notify_transcription_failed(task_id, error_message)
```

**ใช้:**
```python
# ✅ ใหม่
from app.workers.rq_worker import send_ws_event_via_http

if status == "completed":
    await send_ws_event_via_http(
        task_id=task_id,
        message={
            "type": "transcription.completed",
            "status": "completed",
            "text_length": len(results.get("text", "")),
            "chunks_count": len(results.get("chunks", [])),
            "results_summary": {
                "duration": results.get("duration"),
                "language": results.get("language"),
                "processing_time": results.get("processing_time")
            },
            "timestamp": datetime.now().isoformat()
        }
    )
elif status == "failed":
    await send_ws_event_via_http(
        task_id=task_id,
        message={
            "type": "transcription.failed",
            "status": "failed",
            "error": error_message or "Unknown error",
            "timestamp": datetime.now().isoformat()
        }
    )
```

### Step 4: แทนที่ใน `process_live_chunk_background` (realtime_transcription.py)

**แทนที่:**
```python
# ❌ เก่า
await websocket_manager.send_to_user(meeting_id, final_event)
```

**ใช้:**
```python
# ✅ ใหม่
import aiohttp
import os

MAIN_API_URL = os.getenv('MAIN_API_URL', 'http://localhost:8010')

async def send_live_chunk_event(meeting_id: str, message: dict):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{MAIN_API_URL}/api/internal/ws-event",
                json={
                    "meeting_id": meeting_id,
                    "message": message
                },
                timeout=aiohttp.ClientTimeout(total=5.0)
            ) as response:
                if response.status == 200:
                    logger.debug(f"✅ Live-chunk event sent for {meeting_id}")
    except Exception as e:
        logger.warning(f"⚠️  Failed to send live-chunk event: {e}")

# ใช้ใน process_live_chunk_background
await send_live_chunk_event(meeting_id, final_event)
```

---

## 🎯 สรุป

### ✅ แนวทางที่แนะนำ

**สำหรับ Transcription:**
- ใช้ `send_ws_event_via_http(task_id=..., message={...})`
- Message types: `transcription.progress`, `transcription.completed`, `transcription.failed`

**สำหรับ Live-Chunk:**
- ใช้ `send_ws_event_via_http(meeting_id=..., message={...})`
- Message types: `caption.chunk`, `caption.progress`, `caption.completed`

### ⚠️ ข้อควรระวัง

1. **Main API URL**: ต้องตั้งค่า `MAIN_API_URL` environment variable
2. **Timeout**: ใช้ timeout สั้น (5 seconds) เพื่อไม่ให้ block worker
3. **Error Handling**: ใช้ `logger.warning()` ไม่ให้ error ทำให้ worker ล้มเหลว
4. **Rate Limiting**: ยังคงใช้ rate limiting เหมือนเดิม (progress เปลี่ยน >= 5%)

### 📋 Checklist

- [ ] สร้าง helper function `send_ws_event_via_http()`
- [ ] แทนที่ `websocket_manager.notify_transcription_progress()` → HTTP callback
- [ ] แทนที่ `websocket_manager.notify_transcription_completed()` → HTTP callback
- [ ] แทนที่ `websocket_manager.notify_transcription_failed()` → HTTP callback
- [ ] แทนที่ `websocket_manager.send_to_user()` สำหรับ live-chunk → HTTP callback
- [ ] ตั้งค่า `MAIN_API_URL` environment variable
- [ ] ทดสอบ HTTP callback ทำงาน
