"""
RTMP Streaming API Endpoints
สำหรับจัดการ RTMP streams, transcription, และ Close Caption
"""

import logging
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from ..services.rtmp_stream_service import RTMPStreamService
from ..services.ffmpeg_burnin_service import FFmpegBurninService
from ..services.caption_search_service import CaptionSearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rtmp", tags=["rtmp-streaming"])

# Initialize services
rtmp_service = RTMPStreamService()
burnin_service = FFmpegBurninService()
search_service = CaptionSearchService()

class StreamStartRequest(BaseModel):
    """Request model สำหรับเริ่ม stream"""
    stream_key: str
    stream_name: Optional[str] = None
    language: str = "th"
    model_size: str = "base"

class CaptionUpdateRequest(BaseModel):
    """Request model สำหรับอัปเดต captions"""
    caption_segments: List[dict]

class SearchRequest(BaseModel):
    """Request model สำหรับค้นหา"""
    query: str
    case_sensitive: bool = False

@router.post("/on_publish")
async def on_publish(stream_key: str, name: str):
    """
    Callback เมื่อมี RTMP stream เข้ามา
    เรียกจาก nginx-rtmp on_publish hook
    """
    try:
        logger.info(f"📡 RTMP stream published: {name} (key: {stream_key})")
        
        # เริ่ม stream session
        stream_info = await rtmp_service.start_stream(stream_key, name)
        
        # เริ่ม burn-in stream (รอ transcription ก่อน)
        # จะอัปเดต captions ทีหลังเมื่อมี transcription
        
        return {"status": "ok", "stream_id": stream_info["stream_id"]}
        
    except Exception as e:
        logger.error(f"❌ Error in on_publish: {e}")
        return {"status": "error", "error": str(e)}

@router.post("/on_publish_done")
async def on_publish_done(stream_key: str, name: str):
    """
    Callback เมื่อ RTMP stream หยุด
    เรียกจาก nginx-rtmp on_publish_done hook
    """
    try:
        logger.info(f"⏹️ RTMP stream stopped: {name} (key: {stream_key})")
        
        stream_id = name or stream_key
        
        # หยุด stream session
        await rtmp_service.stop_stream(stream_id)
        
        # หยุด burn-in stream
        await burnin_service.stop_burnin_stream(stream_id)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"❌ Error in on_publish_done: {e}")
        return {"status": "error", "error": str(e)}

@router.post("/stream/start")
async def start_stream(request: StreamStartRequest):
    """เริ่ม stream session (manual)"""
    try:
        stream_info = await rtmp_service.start_stream(
            request.stream_key,
            request.stream_name,
            request.language,
            request.model_size
        )
        
        return stream_info
        
    except Exception as e:
        logger.error(f"❌ Error starting stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream/stop/{stream_id}")
async def stop_stream(stream_id: str):
    """หยุด stream session"""
    try:
        result = await rtmp_service.stop_stream(stream_id)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        # หยุด burn-in stream
        await burnin_service.stop_burnin_stream(stream_id)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error stopping stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream/status/{stream_id}")
async def get_stream_status(stream_id: str):
    """ดึงสถานะ stream"""
    try:
        status = rtmp_service.get_stream_status(stream_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        # เพิ่ม burn-in status
        burnin_status = burnin_service.get_stream_status(stream_id)
        status["burnin_status"] = burnin_status
        
        # เพิ่ม transcription count
        transcriptions = rtmp_service.get_transcriptions(stream_id)
        status["transcription_count"] = len(transcriptions)
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting stream status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/streams")
async def get_all_streams():
    """ดึงรายการ streams ทั้งหมด"""
    try:
        streams = rtmp_service.get_all_streams()
        return {"streams": streams, "count": len(streams)}
        
    except Exception as e:
        logger.error(f"❌ Error getting streams: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream/{stream_id}/transcriptions")
async def get_transcriptions(stream_id: str):
    """ดึง transcriptions ของ stream"""
    try:
        transcriptions = rtmp_service.get_transcriptions(stream_id)
        return {"stream_id": stream_id, "transcriptions": transcriptions, "count": len(transcriptions)}
        
    except Exception as e:
        logger.error(f"❌ Error getting transcriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream/{stream_id}/burnin/start")
async def start_burnin(stream_id: str, background_tasks: BackgroundTasks):
    """เริ่ม burn-in stream"""
    try:
        # ตรวจสอบว่า stream มีอยู่หรือไม่
        stream_status = rtmp_service.get_stream_status(stream_id)
        if not stream_status:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        # ดึง transcriptions
        transcriptions = rtmp_service.get_transcriptions(stream_id)
        
        # แปลง transcriptions เป็น caption segments
        caption_segments = []
        for trans in transcriptions:
            for seg in trans.get("segments", []):
                caption_segments.append({
                    "start": seg.get("start", 0),
                    "end": seg.get("end", 0),
                    "text": seg.get("text", "")
                })
        
        # RTMP URLs
        # อ่านจาก clean stream (HLS) แล้ว push ไป CC stream
        # ใช้ HLS input แทน RTMP relay
        input_hls = f"http://localhost:8080/hls/clean/{stream_id}.m3u8"
        output_rtmp = f"rtmp://localhost:1935/cc/{stream_id}"
        
        # เริ่ม burn-in
        success = await burnin_service.start_burnin_stream(
            stream_id,
            input_rtmp,
            output_rtmp,
            caption_segments
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to start burn-in stream")
        
        return {
            "status": "started",
            "stream_id": stream_id,
            "caption_segments_count": len(caption_segments)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error starting burn-in: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream/{stream_id}/burnin/update")
async def update_burnin(stream_id: str, request: CaptionUpdateRequest):
    """อัปเดต captions สำหรับ burn-in"""
    try:
        await burnin_service.update_captions(stream_id, request.caption_segments)
        
        return {
            "status": "updated",
            "stream_id": stream_id,
            "caption_segments_count": len(request.caption_segments)
        }
        
    except Exception as e:
        logger.error(f"❌ Error updating burn-in: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream/{stream_id}/burnin/stop")
async def stop_burnin(stream_id: str):
    """หยุด burn-in stream"""
    try:
        success = await burnin_service.stop_burnin_stream(stream_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Burn-in stream not found")
        
        return {"status": "stopped", "stream_id": stream_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error stopping burn-in: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def search_captions(request: SearchRequest, stream_id: Optional[str] = None):
    """ค้นหาข้อความจาก captions"""
    try:
        results = search_service.search_captions(
            request.query,
            stream_id,
            request.case_sensitive
        )
        
        return {
            "query": request.query,
            "stream_id": stream_id,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"❌ Error searching captions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream/{stream_id}/search")
async def search_stream_captions(stream_id: str, query: str = Query(...), 
                                case_sensitive: bool = Query(False)):
    """ค้นหาข้อความจาก captions ของ stream"""
    try:
        results = search_service.search_captions(query, stream_id, case_sensitive)
        
        return {
            "stream_id": stream_id,
            "query": query,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"❌ Error searching stream captions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream/{stream_id}/timeline")
async def get_caption_timeline(stream_id: str):
    """ดึง timeline ของ captions"""
    try:
        timeline = search_service.get_caption_timeline(stream_id)
        
        return {
            "stream_id": stream_id,
            "timeline": timeline,
            "count": len(timeline)
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream/{stream_id}/time-range")
async def search_by_time_range(stream_id: str, 
                              start_time: float = Query(...),
                              end_time: float = Query(...)):
    """ค้นหา captions ในช่วงเวลาที่กำหนด"""
    try:
        results = search_service.search_by_time_range(stream_id, start_time, end_time)
        
        return {
            "stream_id": stream_id,
            "start_time": start_time,
            "end_time": end_time,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"❌ Error searching by time range: {e}")
        raise HTTPException(status_code=500, detail=str(e))

