"""
Real-time Caption API Endpoints
สำหรับการจัดการ real-time close caption sessions
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path

from ..services.realtime_caption_service import realtime_caption_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/caption/realtime", tags=["realtime-caption"])

# Log file path สำหรับ API logs
API_LOG_PATH = Path("/tmp/main-api.log")

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

@router.get("/logs")
async def get_realtime_caption_logs(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    lines: int = Query(100, ge=1, le=10000, description="Number of lines to retrieve"),
    tail: bool = Query(True, description="Get tail (last N lines) or head (first N lines)"),
    search: Optional[str] = Query(None, description="Search for specific text in logs")
):
    """
    ดู logs การแปลงข้อความของ RealTime Caption
    
    รองรับการ filter ตาม session_id, user_id และ search
    
    Args:
        session_id: Filter logs by session ID
        user_id: Filter logs by user ID
        lines: จำนวนบรรทัดที่ต้องการดู (1-10000)
        tail: ถ้า True จะดูบรรทัดสุดท้าย, ถ้า False จะดูบรรทัดแรก
        search: ค้นหาข้อความเฉพาะใน logs
        
    Returns:
        dict: Logs ที่ filter แล้ว
    """
    try:
        # อ่าน log file
        if not API_LOG_PATH.exists():
            return {
                "logs": [],
                "message": "Log file not found",
                "log_path": str(API_LOG_PATH),
                "total_lines": 0,
                "returned_lines": 0,
                "timestamp": datetime.now().isoformat()
            }
        
        with open(API_LOG_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        # Filter logs ที่เกี่ยวข้องกับ realtime caption
        filtered_lines = []
        for line in all_lines:
            # ตรวจสอบว่าเป็น log ของ realtime caption หรือไม่
            is_realtime_caption = (
                'realtime' in line.lower() and 'caption' in line.lower()
            ) or 'caption/realtime' in line.lower() or '🎬' in line or 'Close Caption' in line
            
            if not is_realtime_caption:
                continue
            
            # Filter ตาม session_id
            if session_id and session_id not in line:
                continue
            
            # Filter ตาม user_id
            if user_id and user_id not in line:
                continue
            
            # Filter ตาม search query
            if search and search.lower() not in line.lower():
                continue
            
            filtered_lines.append(line)
        
        # Get requested lines
        if tail:
            if len(filtered_lines) > lines:
                log_lines = filtered_lines[-lines:]
            else:
                log_lines = filtered_lines
        else:
            log_lines = filtered_lines[:lines]
        
        # Get file stats
        stat = API_LOG_PATH.stat()
        
        return {
            "logs": [line.rstrip() for line in log_lines],
            "log_path": str(API_LOG_PATH),
            "total_lines": len(all_lines),
            "filtered_lines": len(filtered_lines),
            "returned_lines": len(log_lines),
            "filters": {
                "session_id": session_id,
                "user_id": user_id,
                "search": search
            },
            "file_size": stat.st_size,
            "file_size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error reading realtime caption logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error reading logs: {str(e)}"
        )

@router.get("/logs/session/{session_id}")
async def get_session_logs(
    session_id: str,
    include_chunks: bool = Query(True, description="Include chunk processing logs"),
    include_errors: bool = Query(True, description="Include error logs")
):
    """
    ดู logs เฉพาะของ session
    
    รวมถึง:
    - Session events (start, stop, progress)
    - Chunk processing logs
    - Error logs (ถ้ามี)
    - Session metadata
    
    Args:
        session_id: ID ของ session
        include_chunks: รวม logs การประมวลผล chunks
        include_errors: รวม error logs
        
    Returns:
        dict: Logs และข้อมูล session
    """
    try:
        # ดึงข้อมูล session
        session = realtime_caption_service.get_session(session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        # อ่าน log file
        session_logs = []
        if API_LOG_PATH.exists():
            with open(API_LOG_PATH, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
            
            # Filter logs ที่เกี่ยวข้องกับ session นี้
            for line in all_lines:
                if session_id in line:
                    # Filter ตาม include_chunks และ include_errors
                    if not include_chunks and ('chunk' in line.lower() or '🎬 Close Caption Chunk' in line):
                        continue
                    if not include_errors and ('error' in line.lower() or '❌' in line):
                        continue
                    
                    session_logs.append(line.rstrip())
        
        # สร้าง session activity log จาก session data
        activity_logs = []
        activity_logs.append(f"[{session.created_at.isoformat()}] 🎬 Session created: {session_id}")
        
        if session.started_at:
            activity_logs.append(f"[{session.started_at.isoformat()}] ▶️ Session started processing")
        
        if include_chunks:
            for i, chunk in enumerate(session.chunks):
                chunk_time = chunk.get('processed_at', session.started_at.isoformat() if session.started_at else session.created_at.isoformat())
                chunk_text = chunk.get('text', '')[:50]  # จำกัดความยาว
                activity_logs.append(f"[{chunk_time}] 📝 Chunk {i+1}/{len(session.chunks)}: '{chunk_text}...'")
        
        if session.error_message:
            activity_logs.append(f"[{session.completed_at.isoformat() if session.completed_at else datetime.now().isoformat()}] ❌ Error: {session.error_message}")
        
        if session.completed_at:
            activity_logs.append(f"[{session.completed_at.isoformat()}] ✅ Session completed")
        
        return {
            "session_id": session_id,
            "session_info": {
                "user_id": session.user_id,
                "status": session.status,
                "progress": session.progress,
                "current_chunk": session.current_chunk_index,
                "total_chunks": session.total_chunks,
                "created_at": session.created_at.isoformat(),
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "error_message": session.error_message
            },
            "activity_logs": activity_logs,
            "file_logs": session_logs[-100:] if len(session_logs) > 100 else session_logs,  # จำกัด 100 บรรทัดสุดท้าย
            "total_file_logs": len(session_logs),
            "chunks_count": len(session.chunks),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting session logs {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting session logs: {str(e)}"
        )

@router.get("/logs/user/{user_id}")
async def get_user_logs(
    user_id: str,
    lines: int = Query(100, ge=1, le=1000, description="Number of lines per session"),
    include_completed: bool = Query(True, description="Include completed sessions")
):
    """
    ดู logs ของ user ทั้งหมด
    
    รวม logs จากทุก sessions ของ user
    
    Args:
        user_id: ID ของ user
        lines: จำนวนบรรทัดต่อ session
        include_completed: รวม sessions ที่เสร็จแล้ว
        
    Returns:
        dict: Logs ของ user ทั้งหมด
    """
    try:
        # ดึง sessions ของ user
        sessions = realtime_caption_service.get_user_sessions(user_id)
        
        if not include_completed:
            sessions = [s for s in sessions if s.status != "completed"]
        
        user_logs = []
        sessions_summary = []
        
        for session in sessions:
            # สร้าง summary
            session_summary = {
                "session_id": session.session_id,
                "status": session.status,
                "progress": session.progress,
                "chunks_count": len(session.chunks),
                "created_at": session.created_at.isoformat(),
                "error_message": session.error_message
            }
            sessions_summary.append(session_summary)
            
            # อ่าน logs จากไฟล์
            if API_LOG_PATH.exists():
                with open(API_LOG_PATH, 'r', encoding='utf-8', errors='ignore') as f:
                    all_lines = f.readlines()
                
                session_file_logs = [line.rstrip() for line in all_lines 
                                    if session.session_id in line or user_id in line]
                
                # จำกัดจำนวนบรรทัด
                if len(session_file_logs) > lines:
                    session_file_logs = session_file_logs[-lines:]
                
                user_logs.extend([f"[Session: {session.session_id}] {log}" for log in session_file_logs])
        
        return {
            "user_id": user_id,
            "total_sessions": len(sessions),
            "sessions_summary": sessions_summary,
            "logs": user_logs[-500:] if len(user_logs) > 500 else user_logs,  # จำกัด 500 บรรทัดสุดท้าย
            "total_logs": len(user_logs),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting user logs {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting user logs: {str(e)}"
        )

@router.get("/logs/search")
async def search_realtime_caption_logs(
    query: str = Query(..., description="Search query (case-insensitive)"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    max_results: int = Query(50, ge=1, le=500, description="Maximum number of results")
):
    """
    ค้นหา logs ของ RealTime Caption
    
    Args:
        query: ข้อความที่ต้องการค้นหา
        session_id: Filter ตาม session ID
        user_id: Filter ตาม user ID
        max_results: จำนวนผลลัพธ์สูงสุด
        
    Returns:
        dict: ผลลัพธ์การค้นหา
    """
    try:
        if not API_LOG_PATH.exists():
            return {
                "query": query,
                "matches": [],
                "total_matches": 0,
                "timestamp": datetime.now().isoformat()
            }
        
        with open(API_LOG_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        matches = []
        query_lower = query.lower()
        
        for i, line in enumerate(all_lines):
            # ตรวจสอบว่าเป็น log ของ realtime caption หรือไม่
            is_realtime_caption = (
                'realtime' in line.lower() and 'caption' in line.lower()
            ) or 'caption/realtime' in line.lower() or '🎬' in line or 'Close Caption' in line
            
            if not is_realtime_caption:
                continue
            
            # ตรวจสอบ query
            if query_lower not in line.lower():
                continue
            
            # Filter ตาม session_id
            if session_id and session_id not in line:
                continue
            
            # Filter ตาม user_id
            if user_id and user_id not in line:
                continue
            
            matches.append({
                "line_number": i + 1,
                "log_line": line.rstrip(),
                "timestamp": line[:23] if len(line) > 23 else None
            })
            
            if len(matches) >= max_results:
                break
        
        return {
            "query": query,
            "filters": {
                "session_id": session_id,
                "user_id": user_id
            },
            "matches": matches,
            "total_matches": len(matches),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error searching realtime caption logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error searching logs: {str(e)}"
        )
