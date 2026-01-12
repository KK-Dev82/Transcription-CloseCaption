"""
WebSocket Service (NO REDIS)
- In-process WebSocket manager
- Supports user connections + task subscriptions
- Safe: never blocks startup
"""

import json
import logging
from datetime import datetime
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        self.user_tasks: Dict[str, Set[str]] = {}
        self.task_users: Dict[str, Set[str]] = {}

        self.connection_count = 0
        self.total_messages_sent = 0

    async def connect_user(self, websocket: WebSocket, user_id: str):
        await websocket.accept()

        self.user_connections.setdefault(user_id, set()).add(websocket)
        self.user_tasks.setdefault(user_id, set())

        self.connection_count += 1
        logger.info(f"User {user_id} connected WS (total: {self.connection_count})")

        await self.send_to_user(user_id, {
            "type": "connection",
            "status": "connected",
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        })

    async def disconnect_user(self, websocket: WebSocket, user_id: str):
        conns = self.user_connections.get(user_id)
        if conns:
            conns.discard(websocket)

            if not conns:
                # remove user
                self.user_connections.pop(user_id, None)

                # clear subscriptions
                for task_id in list(self.user_tasks.get(user_id, set())):
                    if task_id in self.task_users:
                        self.task_users[task_id].discard(user_id)
                        if not self.task_users[task_id]:
                            self.task_users.pop(task_id, None)
                self.user_tasks.pop(user_id, None)

        self.connection_count = max(0, self.connection_count - 1)
        logger.info(f"User {user_id} disconnected WS (total: {self.connection_count})")

    async def subscribe_task(self, user_id: str, task_id: str):
        self.user_tasks.setdefault(user_id, set()).add(task_id)
        self.task_users.setdefault(task_id, set()).add(user_id)

        await self.send_to_user(user_id, {
            "type": "subscription",
            "task_id": task_id,
            "status": "subscribed",
            "timestamp": datetime.now().isoformat()
        })

    async def unsubscribe_task(self, user_id: str, task_id: str):
        if user_id in self.user_tasks:
            self.user_tasks[user_id].discard(task_id)
        if task_id in self.task_users:
            self.task_users[task_id].discard(user_id)
            if not self.task_users[task_id]:
                self.task_users.pop(task_id, None)

    async def send_to_user(self, user_id: str, message: dict) -> bool:
        conns = self.user_connections.get(user_id)
        if not conns:
            return False

        msg = json.dumps(message, ensure_ascii=False)
        dead = set()

        for ws in list(conns):
            try:
                await ws.send_text(msg)
                self.total_messages_sent += 1
            except Exception:
                dead.add(ws)

        for ws in dead:
            await self.disconnect_user(ws, user_id)

        return bool(self.user_connections.get(user_id))

    async def broadcast_task_update(self, task_id: str, message: dict):
        """
        In-process broadcast to all users who subscribed task_id.
        NOTE: Works only within the same API instance.
        """
        payload = dict(message)
        payload["task_id"] = task_id
        payload.setdefault("timestamp", datetime.now().isoformat())

        user_ids = list(self.task_users.get(task_id, set()))
        for user_id in user_ids:
            await self.send_to_user(user_id, payload)

    async def broadcast_to_meeting(self, meeting_id: str, message: dict):
        """
        Broadcast to all users connected with meeting_id (used as user_id).
        NOTE: Works only within the same API instance.
        """
        payload = dict(message)
        payload.setdefault("timestamp", datetime.now().isoformat())
        await self.send_to_user(meeting_id, payload)

    def get_stats(self) -> dict:
        return {
            "active_connections": self.connection_count,
            "connected_users": len(self.user_connections),
            "active_tasks": len(self.task_users),
            "total_messages_sent": self.total_messages_sent,
        }


websocket_manager = WebSocketManager()


async def initialize_websocket_service():
    """
    NO-OP initializer for compatibility with existing main.py
    (never blocks startup)
    """
    logger.info("✅ WebSocket service initialized (NO REDIS)")
