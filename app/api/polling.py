"""
Polling API สำหรับ Fallback เมื่อ WebSocket ไม่ทำงาน
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json

from ..services.transcription_service import TranscriptionService
from ..services.websocket_service import websocket_manager
from ..utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/polling", tags=["Polling"])

json_storage = JSONStorage()
transcription_service = TranscriptionService()

@router.get("/task/{task_id}")
async def poll_task_status(task_id: str):
    """
    ⚠️ **DEPRECATED**: Endpoint นี้จะถูก deprecate ในอนาคต
    
    **แนะนำให้ใช้**: `GET /api/v2/tasks/{task_id}?format=minimal`
    
    🔄 Polling API สำหรับเช็คสถานะของ task
    
    ใช้แทน WebSocket เมื่อ real-time connection ไม่ทำงาน
    """
    try:
        # ดึงข้อมูลจาก memory ก่อน
        if task_id in transcription_service.tasks:
            task = transcription_service.tasks[task_id]
            
            # ดึงข้อมูล transcription ที่มีอยู่
            partial_text = ""
            chunks = []
            
            if hasattr(task, 'partial_text') and task.partial_text:
                partial_text = task.partial_text
                
            if hasattr(task, 'chunks') and task.chunks:
                # แปลง chunks เป็น dict ถ้าเป็น objects
                if isinstance(task.chunks, list) and len(task.chunks) > 0:
                    if hasattr(task.chunks[0], 'dict'):
                        chunks = [chunk.dict() for chunk in task.chunks]
                    else:
                        chunks = task.chunks
                
            response_data = {
                "task_id": task_id,
                "status": task.status,
                "progress": task.progress or 0,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "error_message": task.error_message,
                "stage": getattr(task, 'current_stage', 'unknown'),
                "results_available": task.status == "completed",
                "partial_text": partial_text,
                "chunks": chunks
            }
            
            # Debug logging
            logger.info(f"Polling response for {task_id}: partial_text={len(partial_text)} chars, chunks={len(chunks)}")
            
            return response_data
        
        # ถ้าไม่มีใน memory ให้ดึงจาก storage
        task_data = json_storage.get_transcription(task_id)
        if task_data:
            # ดึงข้อมูล transcription ที่มีอยู่
            partial_text = ""
            chunks = []
            
            if task_data.get("partial_text"):
                partial_text = task_data.get("partial_text")
                
            if task_data.get("chunks"):
                chunks = task_data.get("chunks")
                
            return {
                "task_id": task_id,
                "status": task_data.get("status", "unknown"),
                "progress": task_data.get("progress", 0),
                "created_at": task_data.get("created_at"),
                "updated_at": task_data.get("updated_at"),
                "completed_at": task_data.get("completed_at"),
                "error_message": task_data.get("error_message"),
                "stage": task_data.get("current_stage", "completed" if task_data.get("status") == "completed" else "unknown"),
                "results_available": task_data.get("status") == "completed",
                "partial_text": partial_text,
                "chunks": chunks
            }
        
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error polling task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/active")
async def poll_active_tasks():
    """
    ⚠️ **DEPRECATED**: Endpoint นี้จะถูก deprecate ในอนาคต
    
    **แนะนำให้ใช้**: `GET /api/v2/tasks/?status=processing`
    
    📋 ดึงรายการ tasks ที่กำลังทำงานอยู่
    """
    try:
        active_tasks = []
        
        # ดึงจาก memory
        for task_id, task in transcription_service.tasks.items():
            if task.status in ["processing", "started", "queued"]:
                active_tasks.append({
                    "task_id": task_id,
                    "status": task.status,
                    "progress": task.progress or 0,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "stage": getattr(task, 'current_stage', 'unknown')
                })
        
        return {
            "active_tasks": active_tasks,
            "count": len(active_tasks),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting active tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/recent")
async def poll_recent_tasks(limit: int = Query(10, ge=1, le=50)):
    """
    ⚠️ **DEPRECATED**: Endpoint นี้จะถูก deprecate ในอนาคต
    
    **แนะนำให้ใช้**: `GET /api/v2/tasks/?limit={limit}&sort=desc`
    
    📚 ดึงรายการ tasks ล่าสุด (ทั้งเสร็จและกำลังทำ)
    """
    try:
        # ดึงจาก storage
        all_tasks = json_storage.list_all_transcriptions()
        
        # เรียงตาม updated_at หรือ created_at
        sorted_tasks = sorted(
            all_tasks,
            key=lambda x: x.get("updated_at") or x.get("created_at") or "1970-01-01T00:00:00",
            reverse=True
        )
        
        recent_tasks = []
        for task in sorted_tasks[:limit]:
            recent_tasks.append({
                "task_id": task.get("task_id"),
                "filename": task.get("filename"),
                "status": task.get("status"),
                "progress": task.get("progress", 0),
                "created_at": task.get("created_at"),
                "updated_at": task.get("updated_at"),
                "completed_at": task.get("completed_at"),
                "duration": task.get("total_duration"),
                "chunks_count": len(task.get("chunks", [])),
                "results_available": task.get("status") == "completed"
            })
        
        return {
            "recent_tasks": recent_tasks,
            "count": len(recent_tasks),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting recent tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def polling_health():
    """
    ⚠️ **DEPRECATED**: Endpoint นี้จะถูก deprecate ในอนาคต
    
    **แนะนำให้ใช้**: `GET /health`
    
    🏥 Health check สำหรับ Polling API
    """
    return {
        "status": "healthy",
        "service": "polling",
        "timestamp": datetime.now().isoformat(),
        "fallback_for": "websocket"
    }
