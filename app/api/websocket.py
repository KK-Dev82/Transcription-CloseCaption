"""
WebSocket API Endpoints สำหรับ Real-time Transcription Updates
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import json
import asyncio
from datetime import datetime

from ..services.websocket_service import websocket_manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/transcription/{user_id}")
async def websocket_transcription_endpoint(
    websocket: WebSocket, 
    user_id: str,
    task_id: Optional[str] = Query(None)
):
    """
    WebSocket endpoint สำหรับ real-time transcription updates
    
    Usage:
    - ws://localhost:8001/ws/transcription/{user_id}
    - ws://localhost:8001/ws/transcription/{user_id}?task_id={task_id}
    """
    try:
        # เชื่อมต่อ user
        await websocket_manager.connect_user(websocket, user_id)
        
        # Subscribe task ถ้ามี
        if task_id:
            await websocket_manager.subscribe_task(user_id, task_id)
        
        # รอรับข้อความจาก client พร้อม keepalive
        
        async def heartbeat():
            """ส่ง ping ทุก 30 วินาที"""
            while True:
                try:
                    await asyncio.sleep(30)
                    await websocket.send_text(json.dumps({
                        "type": "ping",
                        "timestamp": datetime.now().isoformat()
                    }))
                except Exception:
                    break
        
        # เริ่ม heartbeat task
        heartbeat_task = asyncio.create_task(heartbeat())
        
        try:
            while True:
                try:
                    # รอ message หรือ timeout ใน 60 วินาที
                    data = await asyncio.wait_for(
                        websocket.receive_text(), 
                        timeout=60.0
                    )
                    message = json.loads(data)
                    
                    # Handle different message types
                    await handle_websocket_message(websocket, user_id, message)
                    
                except asyncio.TimeoutError:
                    # ไม่มี message ใน 60 วินาที - ส่ง ping
                    await websocket.send_text(json.dumps({
                        "type": "keepalive",
                        "message": "Connection active"
                    }))
                    continue
                    
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }))
                except WebSocketDisconnect:
                    break
        finally:
            heartbeat_task.cancel()
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        await websocket_manager.disconnect_user(websocket, user_id)

async def handle_websocket_message(websocket: WebSocket, user_id: str, message: dict):
    """จัดการข้อความที่ได้รับจาก WebSocket client"""
    
    message_type = message.get("type")
    
    if message_type == "subscribe":
        # Subscribe ใหม่
        task_id = message.get("task_id")
        if task_id:
            await websocket_manager.subscribe_task(user_id, task_id)
        else:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "task_id required for subscription"
            }))
    
    elif message_type == "unsubscribe":
        # Unsubscribe
        task_id = message.get("task_id")
        if task_id:
            await websocket_manager.unsubscribe_task(user_id, task_id)
    
    elif message_type == "ping":
        # Health check
        await websocket.send_text(json.dumps({
            "type": "pong",
            "timestamp": message.get("timestamp")
        }))
    
    elif message_type == "get_stats":
        # ส่งสถิติ (สำหรับ admin)
        stats = websocket_manager.get_stats()
        await websocket.send_text(json.dumps({
            "type": "stats",
            "data": stats
        }))
    
    else:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Unknown message type: {message_type}"
        }))

@router.get("/ws/stats")
async def get_websocket_stats():
    """API endpoint สำหรับดู WebSocket statistics"""
    return {
        "websocket_stats": websocket_manager.get_stats(),
        "status": "active"
    }