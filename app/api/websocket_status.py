"""
WebSocket Status API สำหรับตรวจสอบการเชื่อมต่อ
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from datetime import datetime
import json

from ..services.websocket_service import websocket_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/websocket", tags=["WebSocket Status"])

@router.get("/status")
async def get_websocket_status():
    """
    📡 ตรวจสอบสถานะ WebSocket service
    """
    try:
        stats = websocket_manager.get_stats()
        
        return {
            "service_status": "active",
            "total_connections": stats.get("total_connections", 0),
            "active_users": stats.get("active_users", 0),
            "total_subscriptions": stats.get("total_subscriptions", 0),
            "redis_connected": stats.get("redis_connected", False),
            "last_activity": stats.get("last_activity"),
            "timestamp": datetime.now().isoformat(),
            "healthy": True
        }
        
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {e}")
        return {
            "service_status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "healthy": False
        }

@router.get("/connections")
async def get_active_connections():
    """
    🔗 ดูรายการ connections ที่ active
    """
    try:
        stats = websocket_manager.get_stats()
        
        # ข้อมูลที่ปลอดภัยสำหรับ public API
        connections_info = []
        if hasattr(websocket_manager, 'user_connections'):
            for user_id in websocket_manager.user_connections.keys():
                connections_info.append({
                    "user_id": user_id,
                    "connected_at": "hidden_for_privacy",  # ไม่แสดงเวลาจริง
                    "subscribed_tasks": len(websocket_manager.user_subscriptions.get(user_id, set()))
                })
        
        return {
            "active_connections": connections_info,
            "total_connections": len(connections_info),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/subscriptions/{user_id}")
async def get_user_subscriptions(user_id: str):
    """
    📋 ดู subscriptions ของ user
    """
    try:
        subscriptions = list(websocket_manager.user_subscriptions.get(user_id, set()))
        
        return {
            "user_id": user_id,
            "subscriptions": subscriptions,
            "subscription_count": len(subscriptions),
            "connected": user_id in websocket_manager.user_connections,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting user subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-broadcast")
async def test_websocket_broadcast(task_id: str = "test-task", message: str = "Test message"):
    """
    🧪 ทดสอบ WebSocket broadcast
    """
    try:
        test_data = {
            "type": "test",
            "task_id": task_id,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        # Broadcast ไปยัง subscribers ของ task นี้
        await websocket_manager.broadcast_task_update(task_id, test_data)
        
        return {
            "status": "success",
            "broadcasted_to": task_id,
            "message": test_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error testing broadcast: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/diagnostics")
async def websocket_diagnostics():
    """
    🔍 WebSocket diagnostics สำหรับ debugging
    """
    try:
        stats = websocket_manager.get_stats()
        
        # ข้อมูล diagnostic ที่ละเอียด
        diagnostics = {
            "websocket_manager": {
                "initialized": websocket_manager is not None,
                "redis_available": stats.get("redis_connected", False),
                "stats": stats
            },
            "system": {
                "timestamp": datetime.now().isoformat(),
                "service_healthy": True
            }
        }
        
        # เพิ่มข้อมูลการเชื่อมต่อถ้ามี
        if hasattr(websocket_manager, 'user_connections'):
            diagnostics["connections"] = {
                "total_users": len(websocket_manager.user_connections),
                "user_list": list(websocket_manager.user_connections.keys())[:10]  # แสดงแค่ 10 คนแรก
            }
        
        if hasattr(websocket_manager, 'user_subscriptions'):
            total_subs = sum(len(subs) for subs in websocket_manager.user_subscriptions.values())
            diagnostics["subscriptions"] = {
                "total_subscriptions": total_subs,
                "users_with_subscriptions": len([u for u, s in websocket_manager.user_subscriptions.items() if s])
            }
        
        return diagnostics
        
    except Exception as e:
        logger.error(f"Error getting diagnostics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
