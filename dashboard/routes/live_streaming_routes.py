"""
Live Streaming Routes สำหรับ Dashboard
รองรับการ monitor และ process recordings จาก RTMP server
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional, List, Dict
import logging
import os
import aiohttp
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/live-streaming", tags=["live-streaming"])

# RTMP Server Configuration
RTMP_SERVER_URL = "http://143.198.77.135:8080"
RTMP_PUSH_URL = "rtmp://143.198.77.135:1935/live"
HLS_BASE_URL = "http://143.198.77.135:80/hls"

# Transcription API URL - ใช้ internal port ถ้า Dashboard ทำงานบน Pod เดียวกัน
try:
    from ..server_constants import USE_INTERNAL_PORT, INTERNAL_API_URL
    if USE_INTERNAL_PORT:
        TRANSCRIPTION_API_URL = INTERNAL_API_URL
    else:
        TRANSCRIPTION_API_URL = os.getenv("TRANSCRIPTION_API_URL", "http://localhost:8010")
except ImportError:
    TRANSCRIPTION_API_URL = os.getenv("TRANSCRIPTION_API_URL", "http://localhost:8010")

@router.get("/status")
async def get_streaming_status():
    """ตรวจสอบสถานะ RTMP server และ streams"""
    try:
        # Check RTMP server statistics
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{RTMP_SERVER_URL}/stat", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        stats_text = await response.text()
                        return {
                            "rtmp_server": "online",
                            "statistics": stats_text[:500],  # First 500 chars
                            "rtmp_url": RTMP_PUSH_URL,
                            "hls_url": HLS_BASE_URL
                        }
            except Exception as e:
                logger.warning(f"Could not fetch RTMP stats: {e}")
                return {
                    "rtmp_server": "unknown",
                    "error": str(e),
                    "rtmp_url": RTMP_PUSH_URL,
                    "hls_url": HLS_BASE_URL
                }
    except Exception as e:
        logger.error(f"Error getting streaming status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recordings")
async def get_recordings(
    channel: Optional[str] = Query(None, description="Channel name (e.g., channel1)"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of recordings to return")
):
    """
    ดึงรายการ recorded files จาก RTMP server
    
    Note: ต้องมี API endpoint บน RTMP server หรือใช้ file listing
    """
    try:
        # Option 1: If RTMP server has recordings API
        recordings_url = f"{RTMP_SERVER_URL}/api/recordings"
        if channel:
            recordings_url += f"?channel={channel}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(recordings_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        recordings = await response.json()
                        return {
                            "recordings": recordings[:limit],
                            "total": len(recordings),
                            "channel": channel
                        }
            except aiohttp.ClientError:
                # Option 2: Return placeholder (implement file listing if needed)
                return {
                    "recordings": [],
                    "message": "RTMP server recordings API not available. Use file listing or SSH access.",
                    "note": "Recordings are typically stored at /root/deploy/recordings/ on RTMP server"
                }
    except Exception as e:
        logger.error(f"Error getting recordings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recordings/{filename}")
async def get_recording_file(filename: str):
    """Proxy recording file from RTMP server"""
    try:
        file_url = f"{RTMP_SERVER_URL}/recordings/{filename}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    content = await response.read()
                    return StreamingResponse(
                        iter([content]),
                        media_type="video/x-flv",  # หรือ video/mp4 ตาม file type
                        headers={
                            "Content-Disposition": f"attachment; filename={filename}"
                        }
                    )
                else:
                    raise HTTPException(status_code=404, detail="File not found")
    except aiohttp.ClientError as e:
        logger.error(f"Error getting recording file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-recording")
async def process_recording(
    filename: str = Query(..., description="Recording filename"),
    channel: Optional[str] = Query(None, description="Channel name"),
    transcription_api_url: Optional[str] = Query(None, description="Transcription API URL")
):
    """
    Process recorded file with Transcription Service
    
    Args:
        filename: Recording filename
        channel: Channel name (optional)
        transcription_api_url: Transcription API URL (optional, defaults to localhost:8010)
    """
    try:
        # Construct file URL
        file_url = f"{RTMP_SERVER_URL}/recordings/{filename}"
        
        # Use provided API URL or default
        api_url = transcription_api_url or TRANSCRIPTION_API_URL
        
        # Send to Transcription Service
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{api_url}/transcribe/",
                json={
                    "file_url": file_url,
                    "file_name": filename,
                    "language": "th",
                    "model_size": "medium",
                    "chunk_duration": 3,  # 3 seconds for close caption
                    "use_chunking": True,
                    "display_mode": "realtime_chunks",  # Priority 10
                    "callback_url": None  # หรือ callback URL สำหรับ dashboard
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "task_id": result.get("task_id"),
                        "file_url": file_url,
                        "message": "Recording sent to Transcription Service"
                    }
                else:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Transcription Service error: {error_text}"
                    )
    except aiohttp.ClientError as e:
        logger.error(f"Error processing recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hls-playlist/{channel}")
async def get_hls_playlist(channel: str = "channel1"):
    """Get HLS playlist URL for a channel"""
    return {
        "channel": channel,
        "hls_url": f"{HLS_BASE_URL}/{channel}.m3u8",
        "rtmp_url": f"{RTMP_PUSH_URL}/{channel}"
    }

@router.post("/start-monitoring")
async def start_monitoring(
    channel: str = Query("channel1", description="Channel to monitor"),
    interval: int = Query(5000, ge=1000, le=60000, description="Polling interval in milliseconds")
):
    """
    Start monitoring recordings for a channel
    
    Returns monitoring session ID
    """
    # TODO: Implement monitoring session management
    # Store monitoring state in memory or database
    return {
        "session_id": f"monitor_{channel}_{datetime.now().timestamp()}",
        "channel": channel,
        "interval_ms": interval,
        "status": "started",
        "message": "Monitoring started. Use stop-monitoring to stop."
    }

@router.post("/stop-monitoring/{session_id}")
async def stop_monitoring(session_id: str):
    """Stop monitoring session"""
    # TODO: Implement stop monitoring
    return {
        "session_id": session_id,
        "status": "stopped"
    }

