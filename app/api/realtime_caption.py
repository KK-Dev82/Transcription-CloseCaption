"""
Real-time Caption API Endpoints
สำหรับการจัดการ real-time close caption sessions
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from ..services.realtime_caption_service import realtime_caption_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/caption/realtime", tags=["realtime-caption"])

class RealtimeCaptionRequest(BaseModel):
    """Request model สำหรับเริ่ม real-time caption"""
    user_id: str
    file_path: str = ""
    language: str = "th"
    model_size: str = "base"
    chunk_duration: int = 3  # วินาที (ปรับเป็น 3s สำหรับ realtime close caption)
    delay_seconds: float = 0.0  # delay สำหรับการเล่นวิดีโอ

class RealtimeCaptionResponse(BaseModel):
    """Response model สำหรับ real-time caption"""
    session_id: str
    user_id: str
    status: str
    message: str
    created_at: str
    websocket_url: str

class DelayUpdateRequest(BaseModel):
    """Request model สำหรับอัปเดต delay"""
    delay_seconds: float

@router.post("/start", response_model=RealtimeCaptionResponse)
async def start_realtime_caption(request: RealtimeCaptionRequest):
    """
    เริ่ม real-time caption session
    
    Args:
        request: ข้อมูลสำหรับเริ่ม session
        
    Returns:
        RealtimeCaptionResponse: ข้อมูล session ที่สร้างขึ้น
    """
    try:
        # เริ่ม real-time caption session
        session_id = await realtime_caption_service.start_realtime_caption(
            user_id=request.user_id,
            file_path=request.file_path,
            language=request.language,
            model_size=request.model_size,
            chunk_duration=request.chunk_duration,
            delay_seconds=request.delay_seconds
        )
        
        logger.info(f"🎬 Started real-time caption session: {session_id} for user {request.user_id}")
        
        return RealtimeCaptionResponse(
            session_id=session_id,
            user_id=request.user_id,
            status="started",
            message="Real-time caption session started successfully",
            created_at=datetime.now().isoformat(),
            websocket_url=f"/ws/caption/{request.user_id}?session_id={session_id}"
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to start real-time caption: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start real-time caption: {str(e)}"
        )

@router.post("/stop/{session_id}")
async def stop_realtime_caption(session_id: str):
    """
    หยุด real-time caption session
    
    Args:
        session_id: ID ของ session ที่ต้องการหยุด
        
    Returns:
        dict: สถานะการหยุด session
    """
    try:
        success = await realtime_caption_service.stop_realtime_caption(session_id)
        
        if success:
            logger.info(f"⏹️ Stopped real-time caption session: {session_id}")
            return {
                "session_id": session_id,
                "status": "stopped",
                "message": "Real-time caption session stopped successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to stop real-time caption session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop real-time caption session: {str(e)}"
        )

@router.put("/delay/{session_id}")
async def update_delay(session_id: str, request: DelayUpdateRequest):
    """
    อัปเดต delay time สำหรับ session
    
    Args:
        session_id: ID ของ session
        request: ข้อมูล delay ใหม่
        
    Returns:
        dict: สถานะการอัปเดต
    """
    try:
        # ตรวจสอบ delay range (0-30 วินาที)
        if not 0 <= request.delay_seconds <= 30:
            raise HTTPException(
                status_code=400,
                detail="Delay must be between 0 and 30 seconds"
            )
        
        success = await realtime_caption_service.update_delay(
            session_id, request.delay_seconds
        )
        
        if success:
            logger.info(f"⏱️ Updated delay for session {session_id}: {request.delay_seconds}s")
            return {
                "session_id": session_id,
                "delay_seconds": request.delay_seconds,
                "status": "updated",
                "message": f"Delay updated to {request.delay_seconds} seconds",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update delay for session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update delay: {str(e)}"
        )

@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """
    ดึงข้อมูล session
    
    Args:
        session_id: ID ของ session
        
    Returns:
        dict: ข้อมูล session
    """
    try:
        session = realtime_caption_service.get_session(session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        return {
            "session": session.to_dict(),
            "websocket_url": f"/ws/caption/{session.user_id}?session_id={session_id}",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get session info {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session info: {str(e)}"
        )

@router.get("/user/{user_id}/sessions")
async def get_user_sessions(user_id: str):
    """
    ดึงรายการ sessions ของ user
    
    Args:
        user_id: ID ของ user
        
    Returns:
        dict: รายการ sessions
    """
    try:
        sessions = realtime_caption_service.get_user_sessions(user_id)
        
        return {
            "user_id": user_id,
            "sessions": [session.to_dict() for session in sessions],
            "total_sessions": len(sessions),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get user sessions {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get user sessions: {str(e)}"
        )

@router.get("/stats")
async def get_realtime_caption_stats():
    """
    ดึงสถิติ real-time caption service
    
    Returns:
        dict: สถิติการใช้งาน
    """
    try:
        active_sessions = len(realtime_caption_service.active_sessions)
        sessions_by_status = {}
        
        for session in realtime_caption_service.active_sessions.values():
            status = session.status
            if status not in sessions_by_status:
                sessions_by_status[status] = 0
            sessions_by_status[status] += 1
        
        return {
            "active_sessions": active_sessions,
            "sessions_by_status": sessions_by_status,
            "service_status": "running",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get real-time caption stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get stats: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """
    Health check สำหรับ real-time caption service
    
    Returns:
        dict: สถานะสุขภาพของ service
    """
    try:
        active_sessions = len(realtime_caption_service.active_sessions)
        
        return {
            "status": "healthy",
            "service": "realtime-caption",
            "active_sessions": active_sessions,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "realtime-caption",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
