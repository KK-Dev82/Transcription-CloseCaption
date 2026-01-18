"""
Webhook Routes for Dashboard
รับ webhook callbacks จาก Transcription Service
"""
from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import logging
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhook", tags=["Webhook"])

# Store webhook events in memory (for real-time updates)
# In production, consider using Redis or WebSocket
webhook_events: Dict[str, list] = {}
MAX_EVENTS_PER_TASK = 100  # Keep last 100 events per task


@router.post("/transcription")
async def receive_transcription_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret")
):
    """
    รับ webhook callback จาก Transcription Service
    
    Payload format:
    {
        "jobId": "...",
        "taskId": "...",
        "status": "completed|failed|processing",
        "progress": 0-100,
        "text": "...",
        "segments": [...],
        "audioDuration": 1800.0,
        "wordCount": 1500,
        "completedAt": "2025-12-15T10:30:00Z"
    }
    """
    try:
        payload = await request.json()
        task_id = payload.get("taskId") or payload.get("task_id")
        
        if not task_id:
            logger.warning("Webhook received without taskId")
            return JSONResponse(
                status_code=400,
                content={"error": "Missing taskId"}
            )
        
        # Store event
        if task_id not in webhook_events:
            webhook_events[task_id] = []
        
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload
        }
        
        webhook_events[task_id].append(event)
        
        # Keep only last N events
        if len(webhook_events[task_id]) > MAX_EVENTS_PER_TASK:
            webhook_events[task_id] = webhook_events[task_id][-MAX_EVENTS_PER_TASK:]
        
        logger.info(f"✅ Webhook received for task {task_id}: status={payload.get('status')}, progress={payload.get('progress')}%")
        
        # Broadcast to connected clients (if using WebSocket/SSE)
        # For now, just store and return success
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "received",
                "taskId": task_id,
                "timestamp": event["timestamp"]
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.get("/events/{task_id}")
async def get_webhook_events(task_id: str):
    """
    ดึง webhook events สำหรับ task นี้
    """
    events = webhook_events.get(task_id, [])
    return {
        "taskId": task_id,
        "events": events,
        "count": len(events)
    }


@router.get("/events")
async def get_all_webhook_events():
    """
    ดึง webhook events ทั้งหมด (สำหรับ debugging)
    """
    return {
        "tasks": list(webhook_events.keys()),
        "total_events": sum(len(events) for events in webhook_events.values())
    }


@router.delete("/events/{task_id}")
async def clear_webhook_events(task_id: str):
    """
    ลบ webhook events สำหรับ task นี้
    """
    if task_id in webhook_events:
        del webhook_events[task_id]
        return {"status": "cleared", "taskId": task_id}
    return {"status": "not_found", "taskId": task_id}

