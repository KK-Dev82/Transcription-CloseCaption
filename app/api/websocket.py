"""
WebSocket API Endpoints สำหรับ Real-time Transcription Updates
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import json
import asyncio
from datetime import datetime, timezone

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
    
    elif message_type == "pong":
        # Acknowledge pong response from client
        # No response needed, just log for debugging
        logger.debug(f"Received pong from user {user_id}")
    
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

@router.websocket("/ws/caption/{user_id}")
async def websocket_caption_endpoint(
    websocket: WebSocket, 
    user_id: str,
    session_id: Optional[str] = Query(None)
):
    """
    WebSocket endpoint สำหรับ real-time close caption (Legacy - ใช้ user_id เป็น path parameter)
    
    Usage:
    - ws://localhost:8001/ws/caption/{user_id}
    - ws://localhost:8001/ws/caption/{user_id}?session_id={session_id}
    
    ⚠️ Deprecated: ใช้ /api/ws/captions แทน (V3 compliant)
    """
    try:
        # เชื่อมต่อ user
        await websocket_manager.connect_user(websocket, user_id)
        
        # Subscribe session ถ้ามี
        if session_id:
            await websocket_manager.subscribe_task(user_id, session_id)
        
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
                    await handle_caption_websocket_message(websocket, user_id, message)
                    
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
        logger.info(f"Caption WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"Caption WebSocket error for user {user_id}: {e}")
    finally:
        await websocket_manager.disconnect_user(websocket, user_id)

@router.websocket("/api/ws/captions")
async def websocket_captions_v3_endpoint(
    websocket: WebSocket,
    meeting_id: str = Query(..., description="Meeting ID (required)"),
    session_id: Optional[str] = Query(None, description="Session ID (optional)")
):
    """
    ✅ V3 Compliant: WebSocket endpoint สำหรับ real-time close caption
    
    Usage:
    - ws://localhost:8012/api/ws/captions?meeting_id={meeting_id}
    - ws://localhost:8012/api/ws/captions?meeting_id={meeting_id}&session_id={session_id}
    
    Events:
    - type: "sync" - Clock synchronization
    - type: "status" - Status updates
    - type: "heartbeat" - Keepalive
    - type: "partial" - Provisional captions
    - type: "final" - Final captions
    - type: "error" - Error events
    """
    try:
        # เชื่อมต่อ user (ใช้ meeting_id เป็น user_id)
        await websocket_manager.connect_user(websocket, meeting_id)
        
        # Subscribe session ถ้ามี
        if session_id:
            await websocket_manager.subscribe_task(meeting_id, session_id)
        
        # ส่ง sync event ทันทีเมื่อเชื่อมต่อ
        await websocket.send_text(json.dumps({
            "type": "sync",
            "meeting_id": meeting_id,
            "session_id": session_id or "",
            "seq": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "clock": {
                "meeting_start_utc": datetime.now(timezone.utc).isoformat(),
                "server_utc": datetime.now(timezone.utc).isoformat(),
                "timebase": "ms"
            }
        }))
        
        # ส่ง status event
        await websocket.send_text(json.dumps({
            "type": "status",
            "meeting_id": meeting_id,
            "session_id": session_id or "",
            "seq": 2,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "streaming",
            "message": "Connected and ready to receive captions"
        }))
        
        # รอรับข้อความจาก client พร้อม keepalive
        async def heartbeat():
            """ส่ง heartbeat ทุก 30 วินาที"""
            while True:
                try:
                    await asyncio.sleep(30)
                    await websocket.send_text(json.dumps({
                        "type": "heartbeat",
                        "meeting_id": meeting_id,
                        "session_id": session_id or "",
                        "seq": 0,  # Will be incremented
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }))
                except Exception:
                    break
        
        # เริ่ม heartbeat task
        heartbeat_task = asyncio.create_task(heartbeat())
        seq_counter = 3  # Start from 3 (after sync and status)
        
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
                    message_type = message.get("type")
                    if message_type == "ping":
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "meeting_id": meeting_id,
                            "session_id": session_id or "",
                            "seq": seq_counter,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "timestamp": message.get("timestamp")
                        }))
                        seq_counter += 1
                    elif message_type == "subscribe":
                        # Subscribe session
                        sub_session_id = message.get("session_id")
                        if sub_session_id:
                            await websocket_manager.subscribe_task(meeting_id, sub_session_id)
                    elif message_type == "unsubscribe":
                        # Unsubscribe session
                        unsub_session_id = message.get("session_id")
                        if unsub_session_id:
                            await websocket_manager.unsubscribe_task(meeting_id, unsub_session_id)
                    
                except asyncio.TimeoutError:
                    # ไม่มี message ใน 60 วินาที - heartbeat จะส่งอัตโนมัติ
                    continue
                    
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "meeting_id": meeting_id,
                        "session_id": session_id or "",
                        "seq": seq_counter,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "error": {
                            "code": "INVALID_JSON",
                            "message": "Invalid JSON format"
                        }
                    }))
                    seq_counter += 1
                except WebSocketDisconnect:
                    break
        finally:
            heartbeat_task.cancel()
                
    except WebSocketDisconnect:
        logger.info(f"V3 Caption WebSocket disconnected for meeting {meeting_id}")
    except Exception as e:
        logger.error(f"V3 Caption WebSocket error for meeting {meeting_id}: {e}")
    finally:
        await websocket_manager.disconnect_user(websocket, meeting_id)

async def handle_caption_websocket_message(websocket: WebSocket, user_id: str, message: dict):
    """จัดการข้อความที่ได้รับจาก Caption WebSocket client"""
    
    message_type = message.get("type")
    
    if message_type == "subscribe":
        # Subscribe ใหม่
        session_id = message.get("session_id")
        if session_id:
            await websocket_manager.subscribe_task(user_id, session_id)
        else:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "session_id required for subscription"
            }))
    
    elif message_type == "unsubscribe":
        # Unsubscribe
        session_id = message.get("session_id")
        if session_id:
            await websocket_manager.unsubscribe_task(user_id, session_id)
    
    elif message_type == "ping":
        # Health check
        await websocket.send_text(json.dumps({
            "type": "pong",
            "timestamp": message.get("timestamp")
        }))
    
    elif message_type == "pong":
        # Acknowledge pong response from client
        logger.debug(f"Received pong from caption user {user_id}")
    
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