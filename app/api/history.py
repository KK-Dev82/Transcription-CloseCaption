"""
History API สำหรับดูประวัติการ transcription
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

from ..utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/history", tags=["History"])

json_storage = JSONStorage()

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
    📚 ดูประวัติการ transcription ทั้งหมด
    """
    try:
        # ดึงข้อมูลทั้งหมด
        all_transcriptions = json_storage.list_all_transcriptions()
        
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
        for item in paginated_results:
            history_items.append({
                "task_id": item.get("task_id"),
                "filename": item.get("filename"),
                "status": item.get("status"),
                "progress": item.get("progress", 0),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "completed_at": item.get("completed_at"),
                "duration": item.get("total_duration"),
                "file_size": item.get("file_size"),
                "language": item.get("language", "th"),
                "model_used": item.get("model_size", "base"),
                "chunks_count": len(item.get("chunks", [])),
                "word_count": len(item.get("full_text", "").split()) if item.get("full_text") else 0,
                "error_message": item.get("error_message"),
                "has_results": bool(item.get("full_text") or item.get("chunks"))
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
    📋 ดูรายละเอียดของ transcription
    """
    try:
        transcription = json_storage.get_transcription(task_id)
        
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
    📊 สถิติการ transcription
    """
    try:
        all_transcriptions = json_storage.list_all_transcriptions()
        
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
        success = json_storage.delete_transcription(task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Transcription {task_id} not found")
        
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
