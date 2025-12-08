"""
Real-time Progress Tracking API
สำหรับติดตาม progress ของงาน transcription แบบ real-time
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, List
import logging
import json

from ..services.transcription_service import TranscriptionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/progress", tags=["progress-tracking"])

transcription_service = TranscriptionService()

@router.get("/transcription/{task_id}")
async def get_transcription_progress(task_id: str):
    """ดู progress ของ transcription task แบบ real-time"""
    try:
        task = transcription_service.get_task_status(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="ไม่พบ task")
        
        # แปลง TranscriptionResponse เป็น dict
        task_dict = task.__dict__
        
        progress_info = {
            "task_id": task_id,
            "status": task_dict.get("status", "unknown"),
            "progress": task_dict.get("progress", 0),
            "created_at": task_dict.get("created_at"),
            "updated_at": task_dict.get("updated_at"),
            "file_path": task_dict.get("file_path"),
            "language": task_dict.get("language"),
            "total_duration": task_dict.get("total_duration"),
            # Detailed Stage Information
            "current_stage": task_dict.get("current_stage"),
            "current_stage_description": task_dict.get("current_stage_description"),
            "stage_progress": task_dict.get("stage_progress"),
        }
        
        # เพิ่มข้อมูล progress stage
        status = task_dict.get("status", "")
        progress = task_dict.get("progress", 0)
        
        if status == "pending":
            progress_info["stage"] = "รอการประมวลผล"
            progress_info["description"] = "กำลังเตรียมไฟล์"
        elif status == "processing":
            progress_info["stage"] = "กำลังประมวลผล"
            progress_info["description"] = "กำลังแปลงเสียงเป็นข้อความ"
        elif "processing_chunk" in status:
            # สกัดข้อมูลจาก status เช่น "processing_chunk_3_of_10"
            parts = status.split("_")
            if len(parts) >= 5:
                current = parts[2]
                total = parts[4]
                progress_info["stage"] = f"กำลังประมวลผล chunk {current}/{total}"
                progress_info["description"] = f"แปลงเสียงส่วนที่ {current} จากทั้งหมด {total} ส่วน"
                progress_info["chunk_progress"] = {"current": int(current), "total": int(total)}
        elif status == "merging_results":
            progress_info["stage"] = "กำลังรวมผลลัพธ์"
            progress_info["description"] = "รวมข้อความจากทุกส่วน"
        elif status == "finalizing":
            progress_info["stage"] = "กำลังจัดเก็บข้อมูล"
            progress_info["description"] = "บันทึกผลลัพธ์สุดท้าย"
        elif status == "completed":
            progress_info["stage"] = "เสร็จสิ้น"
            progress_info["description"] = "การแปลงเสียงเป็นข้อความเสร็จสมบูรณ์"
            if task_dict.get("completed_at"):
                progress_info["completed_at"] = task_dict.get("completed_at")
        elif status == "failed":
            progress_info["stage"] = "เกิดข้อผิดพลาด"
            progress_info["description"] = "การประมวลผลล้มเหลว"
            progress_info["error"] = task_dict.get("error", "ไม่ทราบสาเหตุ")
        else:
            progress_info["stage"] = "ไม่ทราบสถานะ"
            progress_info["description"] = f"สถานะ: {status}"
        
        # คำนวณเวลาที่ใช้
        if task_dict.get("created_at") and task_dict.get("updated_at"):
            from datetime import datetime
            try:
                created = datetime.fromisoformat(str(task_dict["created_at"]).replace("T", " "))
                updated = datetime.fromisoformat(str(task_dict["updated_at"]).replace("T", " "))
                elapsed = (updated - created).total_seconds()
                progress_info["elapsed_seconds"] = elapsed
                progress_info["elapsed_formatted"] = f"{int(elapsed//60)}:{int(elapsed%60):02d}"
            except:
                pass
        
        # ประมาณเวลาที่เหลือ
        if progress > 0 and progress < 100:
            if progress_info.get("elapsed_seconds"):
                estimated_total = progress_info["elapsed_seconds"] / (progress / 100)
                remaining = estimated_total - progress_info["elapsed_seconds"]
                progress_info["estimated_remaining_seconds"] = max(0, int(remaining))
                progress_info["estimated_remaining_formatted"] = f"{int(remaining//60)}:{int(remaining%60):02d}"
        
        return progress_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get transcription progress error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all-active")
async def get_all_active_tasks():
    """ดูรายการ tasks ที่กำลังทำงานอยู่"""
    try:
        all_tasks = transcription_service.get_all_tasks()
        
        active_tasks = []
        for task in all_tasks:
            task_dict = task.__dict__
            status = task_dict.get("status", "")
            
            if status not in ["completed", "failed", "cancelled"]:
                progress_info = {
                    "task_id": task_dict.get("task_id"),
                    "status": status,
                    "progress": task_dict.get("progress", 0),
                    "file_path": task_dict.get("file_path"),
                    "created_at": task_dict.get("created_at"),
                    "language": task_dict.get("language")
                }
                active_tasks.append(progress_info)
        
        return {
            "active_tasks": active_tasks,
            "count": len(active_tasks)
        }
        
    except Exception as e:
        logger.error(f"Get all active tasks error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_progress_stats():
    """สถิติการประมวลผล"""
    try:
        all_tasks = transcription_service.get_all_tasks()
        
        stats = {
            "total_tasks": len(all_tasks),
            "completed": 0,
            "processing": 0,
            "pending": 0,
            "failed": 0,
            "average_progress": 0
        }
        
        total_progress = 0
        for task in all_tasks:
            task_dict = task.__dict__
            status = task_dict.get("status", "")
            progress = task_dict.get("progress", 0)
            
            total_progress += progress
            
            if status == "completed":
                stats["completed"] += 1
            elif status in ["processing", "merging_results", "finalizing"]:
                stats["processing"] += 1
            elif status == "pending":
                stats["pending"] += 1
            elif status == "failed":
                stats["failed"] += 1
        
        if len(all_tasks) > 0:
            stats["average_progress"] = total_progress / len(all_tasks)
        
        return stats
        
    except Exception as e:
        logger.error(f"Get progress stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
