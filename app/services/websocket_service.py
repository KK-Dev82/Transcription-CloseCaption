"""
WebSocket Service สำหรับ Real-time Transcription Updates
รองรับ User-specific subscriptions และ scalable architecture
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        # Active connections per user
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        
        # Task subscriptions per user
        self.user_tasks: Dict[str, Set[str]] = {}
        
        # Task to users mapping
        self.task_users: Dict[str, Set[str]] = {}
        
        # Redis for multi-instance scaling
        self.redis_client: Optional[redis.Redis] = None
        
        # Connection stats
        self.connection_count = 0
        self.total_messages_sent = 0

    async def connect_redis(self):
        """เชื่อมต่อ Redis สำหรับ Pub/Sub"""
        try:
            # ใช้ environment variable สำหรับ Redis URL
            import os
            redis_url = os.getenv("REDIS_URL", "redis://transcription-redis-staging:6379")
            
            # ถ้าไม่มี REDIS_URL หรือเป็น default ที่ไม่มีอยู่จริง ให้ skip
            if not redis_url or "transcription-redis-staging" in redis_url:
                logger.info("Skipping Redis connection for WebSocket (no valid REDIS_URL)")
                self.redis_client = None
                return
            
            # เพิ่ม timeout และ socket_connect_timeout เพื่อไม่ให้ hang
            self.redis_client = redis.from_url(
                redis_url,
                socket_connect_timeout=1.0,  # 1 second timeout
                socket_timeout=1.0
            )
            # ใช้ timeout สำหรับ ping
            await asyncio.wait_for(self.redis_client.ping(), timeout=1.0)
            logger.info(f"เชื่อมต่อ Redis สำหรับ WebSocket scaling สำเร็จ: {redis_url}")
        except asyncio.TimeoutError:
            logger.warning(f"Redis connection timeout (continuing without Redis pub/sub)")
            self.redis_client = None
        except Exception as e:
            logger.warning(f"ไม่สามารถเชื่อมต่อ Redis: {e} (continuing without Redis pub/sub)")
            self.redis_client = None

    async def connect_user(self, websocket: WebSocket, user_id: str):
        """เชื่อมต่อ user กับ WebSocket"""
        await websocket.accept()
        
        # เพิ่ม connection
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
            self.user_tasks[user_id] = set()
        
        self.user_connections[user_id].add(websocket)
        self.connection_count += 1
        
        logger.info(f"User {user_id} เชื่อมต่อ WebSocket (total: {self.connection_count})")
        
        # ส่ง welcome message
        await self.send_to_user(user_id, {
            "type": "connection",
            "status": "connected",
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        })

    async def disconnect_user(self, websocket: WebSocket, user_id: str):
        """ตัดการเชื่อมต่อ user"""
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            
            # ลบ user ถ้าไม่มี connection เหลือ
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
                
                # ลบ task subscriptions
                if user_id in self.user_tasks:
                    for task_id in self.user_tasks[user_id]:
                        if task_id in self.task_users:
                            self.task_users[task_id].discard(user_id)
                            if not self.task_users[task_id]:
                                del self.task_users[task_id]
                    del self.user_tasks[user_id]
        
        self.connection_count = max(0, self.connection_count - 1)
        logger.info(f"User {user_id} ตัดการเชื่อมต่อ (total: {self.connection_count})")

    async def subscribe_task(self, user_id: str, task_id: str):
        """Subscribe user ให้ task specific updates"""
        if user_id not in self.user_tasks:
            self.user_tasks[user_id] = set()
        
        if task_id not in self.task_users:
            self.task_users[task_id] = set()
        
        self.user_tasks[user_id].add(task_id)
        self.task_users[task_id].add(user_id)
        
        logger.info(f"User {user_id} subscribe task {task_id}")
        
        # ส่ง confirmation
        await self.send_to_user(user_id, {
            "type": "subscription",
            "task_id": task_id,
            "status": "subscribed",
            "timestamp": datetime.now().isoformat()
        })

    async def unsubscribe_task(self, user_id: str, task_id: str):
        """Unsubscribe user จาก task"""
        if user_id in self.user_tasks:
            self.user_tasks[user_id].discard(task_id)
        
        if task_id in self.task_users:
            self.task_users[task_id].discard(user_id)
            if not self.task_users[task_id]:
                del self.task_users[task_id]
        
        logger.info(f"User {user_id} unsubscribe task {task_id}")

    async def send_to_user(self, user_id: str, message: dict):
        """ส่งข้อความไปยัง user specific"""
        if user_id not in self.user_connections:
            return False
        
        message_str = json.dumps(message, ensure_ascii=False)
        disconnected_connections = set()
        
        for websocket in self.user_connections[user_id]:
            try:
                await websocket.send_text(message_str)
                self.total_messages_sent += 1
            except Exception as e:
                logger.warning(f"ไม่สามารถส่งข้อความไปยัง user {user_id}: {e}")
                disconnected_connections.add(websocket)
        
        # ลบ connections ที่ตัดการเชื่อมต่อ
        for websocket in disconnected_connections:
            await self.disconnect_user(websocket, user_id)
        
        return len(self.user_connections.get(user_id, [])) > 0

    async def broadcast_task_update(self, task_id: str, message: dict):
        """ส่ง update ไปยังทุก user ที่ subscribe task นี้"""
        if task_id not in self.task_users:
            logger.debug(f"ไม่มี user subscribe task {task_id}")
            return
        
        message["task_id"] = task_id
        message["timestamp"] = datetime.now().isoformat()
        
        users_to_notify = list(self.task_users[task_id])
        successful_sends = 0
        
        for user_id in users_to_notify:
            if await self.send_to_user(user_id, message):
                successful_sends += 1
        
        logger.info(f"ส่ง task update {task_id} ไปยัง {successful_sends}/{len(users_to_notify)} users")
        
        # Publish ไปยัง Redis สำหรับ multi-instance
        if self.redis_client:
            try:
                await self.redis_client.publish(
                    f"transcription:{task_id}", 
                    json.dumps(message, ensure_ascii=False)
                )
            except Exception as e:
                logger.warning(f"Redis publish failed: {e}")

    async def broadcast_to_all(self, message: dict):
        """ส่ง message ไปยังทุก user ที่เชื่อมต่ออยู่"""
        total_users = 0
        successful_sends = 0
        
        for user_id, connections in self.user_connections.items():
            total_users += len(connections)
            if await self.send_to_user(user_id, message):
                successful_sends += len(connections)
        
        logger.info(f"ส่ง broadcast message ไปยัง {successful_sends}/{total_users} connections")
        
        # Publish ไปยัง Redis สำหรับ multi-instance
        if self.redis_client:
            try:
                await self.redis_client.publish(
                    "broadcast", 
                    json.dumps(message, ensure_ascii=False)
                )
                logger.debug(f"Published broadcast to Redis")
            except Exception as e:
                logger.warning(f"Failed to publish broadcast to Redis: {e}")

    async def notify_transcription_started(self, task_id: str, file_path: str, language: str):
        """แจ้งเตือนเริ่ม transcription"""
        await self.broadcast_task_update(task_id, {
            "type": "transcription.started",
            "file_path": file_path,
            "language": language,
            "status": "started"
        })

    async def notify_transcription_progress(self, task_id: str, progress: int, 
                                          status: str, stage: str):
        """แจ้งเตือน progress update"""
        await self.broadcast_task_update(task_id, {
            "type": "transcription.progress",
            "progress": progress,
            "status": status,
            "stage": stage
        })

    async def notify_transcription_completed(self, task_id: str, results: dict):
        """แจ้งเตือนเมื่อ transcription เสร็จ"""
        await self.broadcast_task_update(task_id, {
            "type": "transcription.completed",
            "status": "completed",
            "text_length": len(results.get("text", "")),
            "chunks_count": len(results.get("chunks", [])),
            "results_summary": {
                "duration": results.get("duration"),
                "language": results.get("language"),
                "processing_time": results.get("processing_time")
            }
        })

    async def notify_transcription_failed(self, task_id: str, error: str):
        """แจ้งเตือนเมื่อ transcription ล้มเหลว"""
        await self.broadcast_task_update(task_id, {
            "type": "transcription.failed",
            "status": "failed",
            "error": error
        })
    
    async def notify_task_list_update(self, task_id: str, task_data: dict, event_type: str = "task.updated"):
        """
        แจ้งเตือนการอัปเดตรายการทั้งหมด (สำหรับ clients ที่ subscribe "all")
        
        Args:
            task_id: Task ID
            task_data: ข้อมูล task ที่อัปเดต
            event_type: ประเภท event (task.created, task.updated, task.completed, task.failed)
        """
        # ส่งไปยัง clients ที่ subscribe task specific
        await self.broadcast_task_update(task_id, {
            "type": event_type,
            "task_id": task_id,
            "task_data": task_data,
            "timestamp": datetime.now().isoformat()
        })
        
        # ส่งไปยัง clients ที่ subscribe "all" (realtime history)
        if "all" in self.task_users:
            message = {
                "type": event_type,
                "task_id": task_id,
                "task_data": task_data,
                "timestamp": datetime.now().isoformat()
            }
            
            users_to_notify = list(self.task_users["all"])
            successful_sends = 0
            
            for user_id in users_to_notify:
                if await self.send_to_user(user_id, message):
                    successful_sends += 1
            
            logger.debug(f"ส่ง list update {event_type} ({task_id}) ไปยัง {successful_sends}/{len(users_to_notify)} history clients")

    def get_stats(self) -> dict:
        """สถิติการใช้งาน WebSocket"""
        return {
            "active_connections": self.connection_count,
            "connected_users": len(self.user_connections),
            "active_tasks": len(self.task_users),
            "total_messages_sent": self.total_messages_sent,
            "average_connections_per_user": (
                self.connection_count / len(self.user_connections) 
                if self.user_connections else 0
            )
        }

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

# Initialize Redis connection on startup
async def initialize_websocket_service():
    """Initialize WebSocket service with Redis connection"""
    await websocket_manager.connect_redis()
    logger.info("WebSocket service initialized successfully")
