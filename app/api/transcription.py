from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
import logging
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from ..models.transcription import TranscriptionRequest, TranscriptionResponse
from ..services.transcription_service import TranscriptionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcribe", tags=["transcription"])

transcription_service = TranscriptionService()


class CleanupRequest(BaseModel):
    max_age_hours: Optional[int] = Field(default=None, ge=0, description="ลบรายการที่เก่ากว่า (ชั่วโมง). ถ้า None หรือ 0 จะลบทุกอย่างไม่สนใจอายุ")
    statuses: Optional[List[str]] = Field(
        default=None,
        description="ระบุสถานะที่ต้องการลบ (ค่าเริ่มต้น: completed, failed, cancelled, stopped). ถ้า None จะลบทุก status"
    )

@router.post("/", response_model=TranscriptionResponse)
async def start_transcription(request: TranscriptionRequest):
    """เริ่มการแปลงเสียงเป็นข้อความ"""
    
    try:
        # เริ่มการแปลงเสียง
        task_id = await transcription_service.start_transcription(
            file_path=request.file_path,
            file_url=str(request.file_url) if request.file_url else None,
            file_name=request.file_name,
            language=request.language,
            model_size=request.model_size,
            chunk_duration=request.chunk_duration,
            use_chunking=request.use_chunking,
            display_mode=request.display_mode if hasattr(request, 'display_mode') else "full_text",
            callback_url=request.callback_url,
            job_id=request.job_id,
            user_id=request.user_id,
            idempotency_key=request.idempotency_key if hasattr(request, 'idempotency_key') else None,
            # Initial Prompt parameters
            enable_initial_prompt=request.enable_initial_prompt if hasattr(request, 'enable_initial_prompt') else False,
            initial_prompt=request.initial_prompt if hasattr(request, 'initial_prompt') else None,
            use_backend_dictionary=request.use_backend_dictionary if hasattr(request, 'use_backend_dictionary') else True,
            dictionary_scope=request.dictionary_scope if hasattr(request, 'dictionary_scope') else "Global",
            dictionary_max_words=request.dictionary_max_words if hasattr(request, 'dictionary_max_words') else 50
        )
        
        # ดึง task status
        task = transcription_service.get_task_status(task_id)
        
        logger.info(f"เริ่มการแปลงเสียง: {task_id}")
        
        return task
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเริ่มการแปลงเสียง: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการเริ่มการแปลงเสียง: {str(e)}"
        )

@router.get("/{task_id}", response_model=TranscriptionResponse)
async def get_transcription_status(task_id: str):
    """ดึงสถานะการแปลงเสียง"""
    try:
        task = transcription_service.get_task_status(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found in transcription_service")
            raise HTTPException(
                status_code=404,
                detail="ไม่พบ task"
            )
        
        # Log task status for debugging
        logger.debug(f"Task {task_id} status: {task.status}, progress: {task.progress}")
        
        return task
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error getting task {task_id} status: {error_details}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงข้อมูล task: {str(e)}"
        )

@router.get("/", response_model=List[TranscriptionResponse])
async def get_all_transcriptions(
    limit: Optional[int] = Query(None, ge=1, le=10000, description="จำนวน tasks สูงสุดที่ต้องการ (ถ้าไม่ระบุจะ return ทั้งหมด)"),
    offset: Optional[int] = Query(0, ge=0, description="จำนวน tasks ที่จะข้าม (สำหรับ pagination)"),
    sort_by: Optional[str] = Query("updated_at", description="Sort by field: created_at, updated_at, status"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc, desc")
):
    """
    ดึงรายการ transcription tasks ทั้งหมด
    รองรับ pagination และ sorting
    """
    try:
        # ใช้ run_in_executor เพื่อไม่ให้ blocking event loop
        import asyncio
        loop = asyncio.get_event_loop()
        all_tasks = await loop.run_in_executor(None, transcription_service.get_all_tasks)
        
        # Sorting
        if sort_by in ['created_at', 'updated_at']:
            reverse = sort_order.lower() == 'desc'
            def get_sort_value(task):
                value = getattr(task, sort_by, None)
                if value is None:
                    # Return timezone-aware datetime.min for consistent comparison
                    return datetime.min.replace(tzinfo=timezone.utc)
                if isinstance(value, datetime):
                    # Normalize to timezone-aware UTC for comparison
                    if value.tzinfo is None:
                        # Timezone-naive: assume UTC
                        return value.replace(tzinfo=timezone.utc)
                    else:
                        # Timezone-aware: convert to UTC
                        return value.astimezone(timezone.utc)
                if isinstance(value, str):
                    try:
                        # Try parsing ISO format
                        parsed = None
                        if '+' in value or 'Z' in value:
                            # Timezone-aware
                            value_clean = value.replace('Z', '+00:00')
                            parsed = datetime.fromisoformat(value_clean)
                        else:
                            # Timezone-naive: assume UTC
                            parsed = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
                        
                        # Ensure timezone-aware UTC
                        if parsed:
                            if parsed.tzinfo is None:
                                parsed = parsed.replace(tzinfo=timezone.utc)
                            else:
                                parsed = parsed.astimezone(timezone.utc)
                            return parsed
                        return datetime.min.replace(tzinfo=timezone.utc)
                    except Exception as e:
                        logger.debug(f"Error parsing datetime '{value}': {e}")
                        return datetime.min.replace(tzinfo=timezone.utc)
                return datetime.min.replace(tzinfo=timezone.utc)
            
            # Sort with error handling
            try:
                all_tasks.sort(key=get_sort_value, reverse=reverse)
            except TypeError as e:
                # Fallback: convert all to timestamp for comparison
                logger.warning(f"Datetime comparison error, using timestamp fallback: {e}")
                def get_timestamp(task):
                    value = getattr(task, sort_by, None)
                    if value is None:
                        return 0.0
                    if isinstance(value, datetime):
                        # Convert to timestamp
                        if value.tzinfo is None:
                            value = value.replace(tzinfo=timezone.utc)
                        return value.timestamp()
                    if isinstance(value, str):
                        try:
                            if '+' in value or 'Z' in value:
                                value_clean = value.replace('Z', '+00:00')
                                parsed = datetime.fromisoformat(value_clean)
                            else:
                                parsed = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
                            if parsed.tzinfo is None:
                                parsed = parsed.replace(tzinfo=timezone.utc)
                            return parsed.timestamp()
                        except Exception:
                            return 0.0
                    return 0.0
                all_tasks.sort(key=get_timestamp, reverse=reverse)
        elif sort_by == 'status':
            reverse = sort_order.lower() == 'desc'
            all_tasks.sort(
                key=lambda x: (getattr(x, 'status', '') or '').lower(),
                reverse=reverse
            )
        
        # Pagination
        total_count = len(all_tasks)
        if limit is not None:
            paginated_tasks = all_tasks[offset:offset + limit]
        else:
            paginated_tasks = all_tasks[offset:]
        
        return paginated_tasks
    except Exception as e:
        logger.error(f"Error getting all transcriptions: {e}", exc_info=True)
        # Return empty list instead of crashing
        return []


@router.get("/{task_id}/audio")
async def get_task_audio(task_id: str, request: Request):
    """Serve full audio file for playback with Range request support"""
    try:
        # Get task details
        task = transcription_service.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Get audio file path from task
        audio_path = None
        
        # Try to get from task attributes
        if hasattr(task, 'file_path'):
            audio_path = task.file_path
        elif hasattr(task, 'dict'):
            task_dict = task.dict()
            audio_path = task_dict.get('file_path')
        
        # If file_path is audio file (ends with .wav), use it directly
        if audio_path and audio_path.endswith('.wav'):
            file_path = Path(audio_path)
            if file_path.exists():
                return FileResponse(
                    path=str(file_path),
                    filename=file_path.name,
                    media_type='audio/wav',
                    headers={
                        'Accept-Ranges': 'bytes'  # Enable Range requests for audio seeking
                    }
                )
        
        # Try to get from storage
        from ..utils.storage_factory import get_storage
        storage = get_storage()
        task_data = storage.get_transcription(task_id)
        if task_data:
            audio_path = task_data.get('file_path')
            if audio_path and audio_path.endswith('.wav'):
                file_path = Path(audio_path)
                if file_path.exists():
                    return FileResponse(
                        path=str(file_path),
                        filename=file_path.name,
                        media_type='audio/wav',
                        headers={
                            'Accept-Ranges': 'bytes'  # Enable Range requests for audio seeking
                        }
                    )
        
        raise HTTPException(status_code=404, detail="Audio file not found for this task")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving task audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{task_id}/chunk/{chunk_index}/audio")
async def get_chunk_audio(task_id: str, chunk_index: int):
    """Serve audio chunk file for playback"""
    try:
        # Get task details
        task = transcription_service.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        chunks = task.chunks if hasattr(task, 'chunks') else []
        if chunk_index >= len(chunks):
            raise HTTPException(status_code=404, detail=f"Chunk {chunk_index} not found")
        
        chunk = chunks[chunk_index]
        chunk_path = None
        
        # Try to get chunk_path from chunk data
        if isinstance(chunk, dict):
            chunk_path = chunk.get("chunk_path")
        elif hasattr(chunk, 'chunk_path'):
            chunk_path = chunk.chunk_path
        elif hasattr(chunk, 'dict'):
            chunk_dict = chunk.dict()
            chunk_path = chunk_dict.get("chunk_path")
        
        if not chunk_path:
            raise HTTPException(status_code=404, detail="Chunk path not found in chunk data")
        
        # Check if file exists
        file_path = Path(chunk_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Audio file not found: {chunk_path}")
        
        # Serve the file
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type='audio/wav'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving chunk audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup")
async def cleanup_transcription_tasks(request: CleanupRequest):
    """ลบ transcription tasks ออกจาก storage/cache ตามเงื่อนไขที่กำหนด"""
    try:
        # Convert 0 to None (delete all ages) for max_age_hours
        max_age_hours = None if (request.max_age_hours is None or request.max_age_hours == 0) else request.max_age_hours
        
        removed = transcription_service.cleanup_tasks(
            statuses=request.statuses,
            max_age_hours=max_age_hours
        )
        
        # Return format that matches dashboard expectations
        return {
            "removed_count": removed.get("removed_count", 0),
            "failed_count": removed.get("failed_count", 0),
            "removed_task_ids": removed.get("removed_task_ids", []),
            "failed_task_ids": removed.get("failed_task_ids", []),
            "statuses": request.statuses or ["completed", "failed", "cancelled", "stopped"],
            "max_age_hours": max_age_hours
        }
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการ cleanup transcription tasks: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการ cleanup transcription tasks: {str(e)}"
        )

@router.delete("/{task_id}")
async def cancel_transcription(task_id: str):
    """ยกเลิกการแปลงเสียง"""
    
    success = await transcription_service.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="ไม่สามารถยกเลิก task ได้"
        )
    
    return {"message": "ยกเลิก task สำเร็จ"}

@router.get("/{task_id}/text")
async def get_transcription_text(task_id: str):
    """ดึงข้อความที่แปลงแล้ว"""
    
    task = transcription_service.get_task_status(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="ไม่พบ task"
        )
    
    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="การแปลงเสียงยังไม่เสร็จสิ้น"
        )
    
    return {
        "task_id": task_id,
        "full_text": task.full_text,
        "original_text": task.original_text,  # Raw text ก่อน correction
        "corrected_text": task.corrected_text,  # Text หลัง correction
        "language": task.language,
        "total_duration": task.total_duration
    }

@router.get("/{task_id}/chunks")
async def get_transcription_chunks(task_id: str):
    """ดึง chunks ที่แปลงแล้ว"""
    
    task = transcription_service.get_task_status(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="ไม่พบ task"
        )
    
    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="การแปลงเสียงยังไม่เสร็จสิ้น"
        )
    
    return {
        "task_id": task_id,
        "chunks": task.chunks,
        "total_chunks": len(task.chunks) if task.chunks else 0
    }

# ฟังก์ชันใหม่สำหรับการค้นหา
@router.get("/{task_id}/search")
async def search_transcription(
    task_id: str,
    query: str = Query(..., description="คำค้นหา"),
    case_sensitive: bool = Query(False, description="ค้นหาแบบ case sensitive")
):
    """ค้นหาข้อความใน transcription"""
    
    if not query.strip():
        raise HTTPException(
            status_code=400,
            detail="กรุณาระบุคำค้นหา"
        )
    
    try:
        results = transcription_service.search_transcription(
            task_id, query, case_sensitive
        )
        
        return {
            "task_id": task_id,
            "query": query,
            "case_sensitive": case_sensitive,
            "total_results": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการค้นหา: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการค้นหา: {str(e)}"
        )

@router.get("/search/global")
async def search_all_transcriptions(
    query: str = Query(..., description="คำค้นหา"),
    case_sensitive: bool = Query(False, description="ค้นหาแบบ case sensitive")
):
    """ค้นหาข้อความใน transcription ทั้งหมด"""
    
    if not query.strip():
        raise HTTPException(
            status_code=400,
            detail="กรุณาระบุคำค้นหา"
        )
    
    try:
        results = transcription_service.search_all_transcriptions(
            query, case_sensitive
        )
        
        return {
            "query": query,
            "case_sensitive": case_sensitive,
            "total_results": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการค้นหา: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการค้นหา: {str(e)}"
        )

@router.get("/{task_id}/stats")
async def get_transcription_stats(task_id: str):
    """ดึงสถิติของ transcription"""
    
    try:
        stats = transcription_service.get_transcription_stats(task_id)
        
        if not stats:
            raise HTTPException(
                status_code=404,
                detail="ไม่พบข้อมูล transcription"
            )
        
        return stats
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงสถิติ: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงสถิติ: {str(e)}"
        )

@router.get("/list/stored")
async def list_stored_transcriptions():
    """ดึงรายการ transcription ที่เก็บใน JSON storage"""
    
    try:
        # ใช้ run_in_executor เพื่อไม่ให้ blocking event loop
        import asyncio
        loop = asyncio.get_event_loop()
        transcriptions = await loop.run_in_executor(None, transcription_service.list_all_transcriptions)
        
        return {
            "total_transcriptions": len(transcriptions),
            "transcriptions": transcriptions
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงรายการ: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงรายการ: {str(e)}"
        )

@router.delete("/{task_id}/permanent")
async def delete_transcription_permanent(task_id: str):
    """ลบ transcription ถาวร"""
    
    try:
        success = transcription_service.delete_transcription(task_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="ไม่พบ transcription ที่จะลบ"
            )
        
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
        
        return {"message": "ลบ transcription สำเร็จ"}
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการลบ transcription: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการลบ transcription: {str(e)}"
        )
