from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import logging
import json
import asyncio
from typing import Dict, Set

from ..services.transcription_service import TranscriptionService
from ..services.caption_service import CaptionService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

# เก็บ WebSocket connections
transcription_connections: Dict[str, Set[WebSocket]] = {}
caption_connections: Dict[str, Set[WebSocket]] = {}

transcription_service = TranscriptionService()
caption_service = CaptionService()

@router.websocket("/ws/transcription/{task_id}")
async def websocket_transcription_progress(websocket: WebSocket, task_id: str):
    """WebSocket สำหรับติดตามความคืบหน้าของ transcription"""
    
    await websocket.accept()
    
    # เพิ่ม connection
    if task_id not in transcription_connections:
        transcription_connections[task_id] = set()
    transcription_connections[task_id].add(websocket)
    
    try:
        # ส่งสถานะเริ่มต้น
        task = transcription_service.get_task_status(task_id)
        if task:
            await websocket.send_text(json.dumps({
                "type": "status",
                "task_id": task_id,
                "status": task.status,
                "progress": 0
            }, ensure_ascii=False))
        
        # ติดตามความคืบหน้า
        while True:
            await asyncio.sleep(1)  # ตรวจสอบทุก 1 วินาที
            
            task = transcription_service.get_task_status(task_id)
            if task:
                # คำนวณความคืบหน้า (ประมาณการ)
                progress = 0
                if task.status == "pending":
                    progress = 0
                elif task.status == "processing":
                    progress = 50  # ประมาณการ
                elif task.status == "completed":
                    progress = 100
                elif task.status == "failed":
                    progress = -1
                
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "task_id": task_id,
                    "status": task.status,
                    "progress": progress,
                    "error_message": task.error_message if task.error_message else None
                }, ensure_ascii=False))
                
                # ถ้าเสร็จสิ้นแล้ว ให้ปิด connection
                if task.status in ["completed", "failed", "cancelled"]:
                    break
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {task_id}")
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดใน WebSocket: {e}")
    finally:
        # ลบ connection
        if task_id in transcription_connections:
            transcription_connections[task_id].discard(websocket)
            if not transcription_connections[task_id]:
                del transcription_connections[task_id]

@router.websocket("/ws/caption/{task_id}")
async def websocket_caption_progress(websocket: WebSocket, task_id: str):
    """WebSocket สำหรับติดตามความคืบหน้าของ caption"""
    
    await websocket.accept()
    
    # เพิ่ม connection
    if task_id not in caption_connections:
        caption_connections[task_id] = set()
    caption_connections[task_id].add(websocket)
    
    try:
        # ส่งสถานะเริ่มต้น
        task = caption_service.get_task_status(task_id)
        if task:
            await websocket.send_text(json.dumps({
                "type": "status",
                "task_id": task_id,
                "status": task.status,
                "progress": 0
            }, ensure_ascii=False))
        
        # ติดตามความคืบหน้า
        while True:
            await asyncio.sleep(1)  # ตรวจสอบทุก 1 วินาที
            
            task = caption_service.get_task_status(task_id)
            if task:
                # คำนวณความคืบหน้า (ประมาณการ)
                progress = 0
                if task.status == "pending":
                    progress = 0
                elif task.status == "processing":
                    progress = 50  # ประมาณการ
                elif task.status == "completed":
                    progress = 100
                elif task.status == "failed":
                    progress = -1
                
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "task_id": task_id,
                    "status": task.status,
                    "progress": progress,
                    "error_message": task.error_message if task.error_message else None
                }, ensure_ascii=False))
                
                # ถ้าเสร็จสิ้นแล้ว ให้ปิด connection
                if task.status in ["completed", "failed", "cancelled"]:
                    break
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {task_id}")
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดใน WebSocket: {e}")
    finally:
        # ลบ connection
        if task_id in caption_connections:
            caption_connections[task_id].discard(websocket)
            if not caption_connections[task_id]:
                del caption_connections[task_id]

# ฟังก์ชันสำหรับส่งข้อความไปยัง WebSocket connections
async def broadcast_transcription_update(task_id: str, message: dict):
    """ส่งข้อความไปยัง transcription WebSocket connections"""
    if task_id in transcription_connections:
        disconnected = set()
        for websocket in transcription_connections[task_id]:
            try:
                await websocket.send_text(json.dumps(message, ensure_ascii=False))
            except:
                disconnected.add(websocket)
        
        # ลบ connections ที่ขาด
        transcription_connections[task_id] -= disconnected

async def broadcast_caption_update(task_id: str, message: dict):
    """ส่งข้อความไปยัง caption WebSocket connections"""
    if task_id in caption_connections:
        disconnected = set()
        for websocket in caption_connections[task_id]:
            try:
                await websocket.send_text(json.dumps(message, ensure_ascii=False))
            except:
                disconnected.add(websocket)
        
        # ลบ connections ที่ขาด
        caption_connections[task_id] -= disconnected 