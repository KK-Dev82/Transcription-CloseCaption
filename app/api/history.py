"""
History API สำหรับดูประวัติการ transcription
"""

import logging
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import json
import asyncio

from ..utils.storage_factory import get_storage
from ..services.websocket_service import websocket_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/history", tags=["History"])


def get_sqlite_storage():
    """Get storage instance via factory (backward-compatible name)"""
    return get_storage()

def get_json_storage():
    """Get storage instance via factory (backward-compatible name)"""
    return get_storage()

class HistoryFilter(BaseModel):
    status: Optional[str] = None  # completed, failed, processing
    date_from: Optional[str] = None  # ISO format
    date_to: Optional[str] = None    # ISO format
    filename_contains: Optional[str] = None

@router.get("/transcriptions")
async def get_transcription_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filter by status: completed, failed, processing"),
    days_ago: Optional[int] = Query(None, ge=1, le=365, description="Show results from last N days")
):
    """
    ⚠️ **DEPRECATED**: Endpoint นี้จะถูก deprecate ในอนาคต (ยกเว้น WebSocket endpoint)
    
    **แนะนำให้ใช้**: `GET /api/v2/tasks/?limit={limit}&offset={offset}&status={status}&days_ago={days_ago}`
    
    📚 ดูประวัติการ transcription ทั้งหมด
    
    **หมายเหตุ**: WebSocket endpoint (`WS /api/history/ws/realtime`) ยังใช้งานได้
    """
    try:
        # ดึงข้อมูลทั้งหมดจาก SQLite เป็นหลัก (เพราะข้อมูลเก็บไว้ที่นี่)
        all_transcriptions = get_sqlite_storage().list_all_transcriptions()
        # Fallback ไป JSON ถ้า SQLite ว่างเปล่า
        if not all_transcriptions:
            all_transcriptions = get_json_storage().list_all_transcriptions()
        
        # กรองตามเงื่อนไข
        filtered_transcriptions = all_transcriptions
        
        # กรองตาม status
        if status:
            filtered_transcriptions = [
                t for t in filtered_transcriptions 
                if t.get("status") == status
            ]
        
        # กรองตามวันที่
        if days_ago:
            cutoff_date = datetime.now() - timedelta(days=days_ago)
            cutoff_str = cutoff_date.isoformat()
            
            filtered_transcriptions = [
                t for t in filtered_transcriptions
                if (t.get("created_at") or "1970-01-01T00:00:00") >= cutoff_str
            ]
        
        # เรียงตามวันที่อัปเดตล่าสุด
        filtered_transcriptions.sort(
            key=lambda x: x.get("updated_at") or x.get("created_at") or "1970-01-01T00:00:00",
            reverse=True
        )
        
        # Pagination
        total_count = len(filtered_transcriptions)
        paginated_results = filtered_transcriptions[offset:offset + limit]
        
        # จัดรูปแบบข้อมูล
        history_items = []
        # Get SQLite storage to check segments
        sqlite_storage = get_sqlite_storage()
        
        for item in paginated_results:
            task_id = item.get("task_id")
            full_text = item.get("full_text", "")
            chunks = item.get("chunks", [])
            
            # Check segments in SQLite (for SQLite storage)
            has_segments = False
            if task_id:
                try:
                    # Check if segments exist in SQLite
                    import sqlite3
                    from pathlib import Path
                    db_path = Path("storage/database.db")
                    if db_path.exists():
                        conn = sqlite3.connect(str(db_path))
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM segments WHERE task_id = ?", (task_id,))
                        segments_count = cursor.fetchone()[0]
                        has_segments = segments_count > 0
                        conn.close()
                except Exception as e:
                    # Non-critical: if we can't check segments, continue
                    pass
            
            # has_results: check full_text, chunks, or segments
            has_results = bool(full_text or chunks or has_segments)
            
            history_items.append({
                "task_id": task_id,
                "id": task_id,  # Alias for compatibility
                "filename": item.get("filename") or item.get("file_name"),  # Support both field names
                "file_name": item.get("file_name") or item.get("filename"),  # Support both field names
                "file_path": item.get("file_path"),  # Add file path
                "status": item.get("status"),
                "progress": item.get("progress", 0),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "completed_at": item.get("completed_at"),
                "duration": item.get("total_duration"),
                "file_size": item.get("file_size"),
                "language": item.get("language", "th"),
                "model_used": item.get("model_size", "base"),
                "chunks_count": len(chunks),
                "word_count": len(full_text.split()) if full_text else 0,
                "error_message": item.get("error_message"),
                "has_results": has_results
            })
        
        return {
            "history": history_items,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            },
            "filters_applied": {
                "status": status,
                "days_ago": days_ago
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting transcription history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transcriptions/{task_id}")
async def get_transcription_details(task_id: str):
    """
    ⚠️ **DEPRECATED**: Endpoint นี้จะถูก deprecate ในอนาคต
    
    **แนะนำให้ใช้**: `GET /api/v2/tasks/{task_id}?format=full`
    
    📋 ดูรายละเอียดของ transcription
    """
    try:
        # ลอง SQLite ก่อน แล้ว fallback ไป JSON
        transcription = get_sqlite_storage().load_transcription(task_id)
        if not transcription:
            transcription = get_json_storage().load_transcription(task_id)
        
        if not transcription:
            raise HTTPException(status_code=404, detail=f"Transcription {task_id} not found")
        
        # จัดรูปแบบข้อมูลโดยละเอียด
        details = {
            "task_id": task_id,
            "basic_info": {
                "filename": transcription.get("filename"),
                "status": transcription.get("status"),
                "progress": transcription.get("progress", 0),
                "language": transcription.get("language", "th"),
                "model_size": transcription.get("model_size", "base")
            },
            "timestamps": {
                "created_at": transcription.get("created_at"),
                "updated_at": transcription.get("updated_at"),
                "completed_at": transcription.get("completed_at"),
                "processing_duration": None  # คำนวณถ้าต้องการ
            },
            "file_info": {
                "file_path": transcription.get("file_path"),
                "file_size": transcription.get("file_size"),
                "total_duration": transcription.get("total_duration")
            },
            "results": {
                "full_text": transcription.get("full_text"),
                "chunks_count": len(transcription.get("chunks", [])),
                "word_count": len(transcription.get("full_text", "").split()) if transcription.get("full_text") else 0,
                "chunks": transcription.get("chunks", [])
            },
            "error_info": {
                "error_message": transcription.get("error_message"),
                "has_error": bool(transcription.get("error_message"))
            }
        }
        
        # คำนวณระยะเวลาการประมวลผล
        if transcription.get("created_at") and transcription.get("completed_at"):
            try:
                created = datetime.fromisoformat(transcription["created_at"].replace('Z', '+00:00'))
                completed = datetime.fromisoformat(transcription["completed_at"].replace('Z', '+00:00'))
                duration = completed - created
                details["timestamps"]["processing_duration"] = str(duration)
            except:
                pass
        
        return details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transcription details for {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_history_stats():
    """
    ⚠️ **DEPRECATED**: Endpoint นี้จะถูก deprecate ในอนาคต
    
    **แนะนำให้ใช้**: `GET /api/v2/tasks/stats/summary`
    
    📊 สถิติการ transcription
    """
    try:
        all_transcriptions = get_json_storage().list_all_transcriptions()
        
        # นับตาม status
        status_counts = {}
        total_duration = 0
        total_words = 0
        
        for item in all_transcriptions:
            status = item.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            if item.get("total_duration"):
                total_duration += item.get("total_duration", 0)
            
            if item.get("full_text"):
                total_words += len(item.get("full_text", "").split())
        
        # สถิติตามช่วงเวลา
        now = datetime.now()
        today_count = 0
        week_count = 0
        month_count = 0
        
        for item in all_transcriptions:
            created_at = item.get("created_at")
            if created_at:
                try:
                    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    
                    if created_date.date() == now.date():
                        today_count += 1
                    if created_date >= now - timedelta(days=7):
                        week_count += 1
                    if created_date >= now - timedelta(days=30):
                        month_count += 1
                except:
                    pass
        
        return {
            "total_transcriptions": len(all_transcriptions),
            "status_breakdown": status_counts,
            "time_periods": {
                "today": today_count,
                "this_week": week_count,
                "this_month": month_count
            },
            "totals": {
                "total_audio_duration_seconds": total_duration,
                "total_words_transcribed": total_words,
                "average_words_per_transcription": total_words / len(all_transcriptions) if all_transcriptions else 0
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting history stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/transcriptions/{task_id}")
async def delete_transcription_history(task_id: str):
    """
    🗑️ ลบประวัติการ transcription
    """
    try:
        # Try JSON first (since data is there), then SQLite as fallback
        success = get_json_storage().delete_transcription(task_id)
        
        if not success:
            # Fallback to SQLite storage
            success = get_sqlite_storage().delete_transcription(task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Transcription {task_id} not found")
        
        # Send WebSocket notification about task deletion
        try:
            from ..services.websocket_service import websocket_manager
            logger.info(f"🔍 Attempting to send WebSocket notification for task deletion: {task_id}")
            await websocket_manager.broadcast_to_all({
                "type": "task.deleted",
                "task_id": task_id,
                "timestamp": datetime.now().isoformat()
            })
            logger.info(f"📡 WebSocket notification sent for task deletion: {task_id}")
        except Exception as ws_error:
            logger.error(f"❌ Failed to send WebSocket notification: {ws_error}")
            logger.error(f"❌ WebSocket error details: {type(ws_error).__name__}: {str(ws_error)}")
        
        return {
            "status": "success",
            "message": f"Transcription {task_id} deleted",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting transcription {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/realtime")
async def websocket_realtime_history(websocket: WebSocket):
    """
    🔴 WebSocket endpoint สำหรับ realtime updates ของรายการ transcription ทั้งหมด
    
    Usage:
    - ws://localhost:8001/api/history/ws/realtime
    
    Messages sent:
    - task.created: เมื่อมี task ใหม่
    - task.updated: เมื่อ task อัปเดต (status, progress, etc.)
    - task.deleted: เมื่อ task ถูกลบ
    - task.completed: เมื่อ task เสร็จสมบูรณ์
    - task.failed: เมื่อ task ล้มเหลว
    
    Client can send:
    - {"type": "ping"}: สำหรับ health check
    - {"type": "subscribe", "filters": {"status": "processing"}}: Subscribe เฉพาะ tasks ที่ตรงกับ filters
    """
    await websocket.accept()
    user_id = f"history_realtime_{id(websocket)}"
    
    try:
        # เชื่อมต่อ user
        await websocket_manager.connect_user(websocket, user_id)
        
        # Subscribe สำหรับ realtime updates ของรายการทั้งหมด
        # ใช้ special task_id "all" สำหรับ broadcast รายการทั้งหมด
        await websocket_manager.subscribe_task(user_id, "all")
        
        # ส่ง welcome message พร้อมข้อมูลเริ่มต้น
        initial_data = {
            "type": "connection",
            "status": "connected",
            "message": "เชื่อมต่อ WebSocket สำหรับ realtime updates สำเร็จ",
            "timestamp": datetime.now().isoformat(),
            "endpoint": "/api/history/ws/realtime"
        }
        await websocket.send_text(json.dumps(initial_data, ensure_ascii=False))
        
        # Heartbeat task
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
                    
                    # Handle client messages
                    if message.get("type") == "ping":
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        }))
                    elif message.get("type") == "get_latest":
                        # ส่งรายการล่าสุด
                        limit = message.get("limit", 20)
                        all_transcriptions = get_sqlite_storage().list_all_transcriptions()
                        if not all_transcriptions:
                            all_transcriptions = get_json_storage().list_all_transcriptions()
                        
                        # เรียงตาม updated_at
                        all_transcriptions.sort(
                            key=lambda x: x.get("updated_at") or x.get("created_at") or "",
                            reverse=True
                        )
                        
                        latest = all_transcriptions[:limit]
                        await websocket.send_text(json.dumps({
                            "type": "latest_list",
                            "data": latest,
                            "count": len(latest),
                            "timestamp": datetime.now().isoformat()
                        }, ensure_ascii=False))
                    
                except asyncio.TimeoutError:
                    # ไม่มี message ใน 60 วินาที - ส่ง keepalive
                    await websocket.send_text(json.dumps({
                        "type": "keepalive",
                        "message": "Connection active",
                        "timestamp": datetime.now().isoformat()
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
        logger.info(f"WebSocket disconnected for history realtime: {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for history realtime {user_id}: {e}")
    finally:
        await websocket_manager.disconnect_user(websocket, user_id)
