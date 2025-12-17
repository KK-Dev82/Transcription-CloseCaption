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
from urllib.parse import urlparse

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

@router.get("/hls-proxy/{channel}")
async def proxy_hls_playlist(channel: str = "channel1"):
    """
    Proxy HLS playlist to avoid Mixed Content issues
    Dashboard (HTTPS) -> Proxy (HTTPS) -> HLS Server (HTTP)
    """
    try:
        playlist_url = f"{HLS_BASE_URL}/{channel}.m3u8"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(playlist_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch HLS playlist {playlist_url}: {response.status}")
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Failed to fetch HLS playlist: {response.status}"
                        )
                    
                    content = await response.text()
                    
                    # Rewrite URLs in playlist to use proxy
                    # Replace all segment URLs with proxy URLs
                    lines = content.split('\n')
                    rewritten_lines = []
                    for line in lines:
                        stripped = line.strip()
                        if stripped and not stripped.startswith('#'):
                            # This is a segment URL line (e.g., "channel1-1140.ts")
                            # Extract just the filename
                            segment_filename = stripped
                            if '/' in stripped:
                                # Extract filename from path
                                segment_filename = stripped.split('/')[-1]
                            elif stripped.startswith('http'):
                                # Extract filename from URL
                                from urllib.parse import urlparse
                                parsed = urlparse(stripped)
                                segment_filename = parsed.path.split('/')[-1]
                            
                            # Use proxy endpoint with just the filename
                            rewritten_lines.append(f"/api/live-streaming/hls-proxy-segment/{channel}/{segment_filename}")
                        else:
                            # Keep comments and empty lines as-is
                            rewritten_lines.append(line)
                    
                    rewritten_content = '\n'.join(rewritten_lines)
                    
                    # Use Response instead of StreamingResponse to avoid connection issues
                    from fastapi.responses import Response
                    return Response(
                        content=rewritten_content.encode('utf-8'),
                        media_type="application/vnd.apple.mpegurl",
                        headers={
                            "Access-Control-Allow-Origin": "*",
                            "Cache-Control": "no-cache",
                            "Content-Type": "application/vnd.apple.mpegurl"
                        }
                    )
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Connection error fetching HLS playlist {playlist_url}: {e}")
                raise HTTPException(status_code=502, detail=f"Cannot connect to HLS server: {str(e)}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching HLS playlist {playlist_url}")
                raise HTTPException(status_code=504, detail="HLS server timeout")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proxying HLS playlist: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hls-proxy-segment/{channel}/{path:path}")
async def proxy_hls_segment(channel: str, path: str):
    """
    Proxy HLS segment files (TS files)
    """
    try:
        # Construct segment URL
        # Path might be like "channel1-1094.ts" or "channel1/channel1-1094.ts"
        # Remove channel prefix if present in path
        segment_filename = path
        if path.startswith(f"{channel}/"):
            segment_filename = path[len(f"{channel}/"):]
        elif path.startswith(f"{channel}-"):
            # Path is already just the filename like "channel1-1094.ts"
            segment_filename = path
        
        # Construct full URL - segments are usually in hls/channel1/ directory
        segment_url = f"{HLS_BASE_URL}/{channel}/{segment_filename}"
        
        logger.debug(f"Proxying HLS segment: {segment_url} (path={path}, filename={segment_filename})")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(segment_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch HLS segment {segment_url}: {response.status}")
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Failed to fetch HLS segment: {response.status}"
                        )
                    
                    # Read the entire segment into memory (TS files are usually small, < 10MB)
                    # This avoids HTTP/2 protocol errors with streaming
                    segment_data = await response.read()
                    
                    # Determine content type
                    content_type = response.headers.get('Content-Type', 'video/mp2t')
                    
                    # Return as FileResponse with data (more reliable than StreamingResponse for small files)
                    from fastapi.responses import Response
                    return Response(
                        content=segment_data,
                        media_type=content_type,
                        headers={
                            "Access-Control-Allow-Origin": "*",
                            "Cache-Control": "public, max-age=3600",
                            "Content-Length": str(len(segment_data))
                        }
                    )
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Connection error fetching HLS segment {segment_url}: {e}")
                raise HTTPException(status_code=502, detail=f"Cannot connect to HLS server: {str(e)}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching HLS segment {segment_url}")
                raise HTTPException(status_code=504, detail="HLS server timeout")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proxying HLS segment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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

