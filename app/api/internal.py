"""
Internal API Endpoints สำหรับ Inter-service Communication
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
from datetime import datetime

from ..services.websocket_service import websocket_manager

logger = logging.getLogger(__name__)
router = APIRouter()

class WebSocketBroadcastRequest(BaseModel):
    type: str
    task_id: str
    timestamp: str
    progress: int = None
    status: str = None
    stage: str = None
    file_path: str = None
    language: str = None
    results_summary: Dict[str, Any] = None
    error: str = None

@router.post("/internal/websocket-broadcast")
async def broadcast_websocket_message(request: WebSocketBroadcastRequest):
    """
    Internal endpoint สำหรับ Worker ส่ง notifications มาให้ API server broadcast ผ่าน WebSocket
    """
    try:
        logger.info(f"🔄 Received WebSocket broadcast request: {request.type} for task {request.task_id}")
        
        # Convert to dict for broadcasting
        message_data = request.dict(exclude_none=True)
        
        # Broadcast ไปยังทุก user ที่ subscribe task นี้
        await websocket_manager.broadcast_task_update(request.task_id, message_data)
        
        return {
            "status": "success", 
            "message": f"Broadcasted {request.type} for task {request.task_id}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to broadcast WebSocket message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/internal/health")
async def internal_health_check():
    """Health check สำหรับ internal services"""
    return {
        "status": "healthy",
        "websocket_stats": websocket_manager.get_stats(),
        "timestamp": datetime.now().isoformat()
    }
