"""
Live Streaming API Endpoints
สำหรับการทำ Real-time Transcription แบบ YouTube
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import logging
import json
import asyncio
from typing import Dict, List
import uuid

from ..services.live_streaming_service import LiveStreamingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/live", tags=["live-streaming"])

live_streaming_service = LiveStreamingService()

# เก็บ WebSocket connections สำหรับ live streaming
live_stream_connections: Dict[str, List[WebSocket]] = {}

@router.post("/start")
async def start_live_stream(language: str = "th", model_size: str = "base"):
    """เริ่ม live streaming session"""
    try:
        stream_id = str(uuid.uuid4())
        
        success = await live_streaming_service.start_live_stream(
            stream_id=stream_id,
            language=language,
            model_size=model_size
        )
        
        if success:
            return {
                "stream_id": stream_id,
                "status": "started",
                "language": language,
                "model_size": model_size,
                "websocket_url": f"/live/ws/{stream_id}"
            }
        else:
            raise HTTPException(status_code=500, detail="ไม่สามารถเริ่ม live stream ได้")
            
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเริ่ม live stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop/{stream_id}")
async def stop_live_stream(stream_id: str):
    """หยุด live streaming session"""
    try:
        summary = await live_streaming_service.stop_live_stream(stream_id)
        
        if "error" in summary:
            raise HTTPException(status_code=404, detail=summary["error"])
        
        return summary
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการหยุด live stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{stream_id}")
async def get_stream_status(stream_id: str):
    """ดึงสถานะของ live stream"""
    try:
        status = live_streaming_service.get_stream_status(stream_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="ไม่พบ stream")
        
        return status
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงสถานะ stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active")
async def get_all_active_streams():
    """ดึงรายการ active streams ทั้งหมด"""
    try:
        streams = live_streaming_service.get_all_active_streams()
        return {"streams": streams, "count": len(streams)}
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงรายการ streams: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/{stream_id}")
async def live_stream_websocket(websocket: WebSocket, stream_id: str):
    """WebSocket สำหรับ real-time transcription updates"""
    await websocket.accept()
    
    # เพิ่ม connection
    if stream_id not in live_stream_connections:
        live_stream_connections[stream_id] = []
    live_stream_connections[stream_id].append(websocket)
    
    try:
        # ส่งสถานะเริ่มต้น
        status = live_streaming_service.get_stream_status(stream_id)
        if status:
            await websocket.send_text(json.dumps({
                "type": "stream_status",
                "stream_id": stream_id,
                "status": status,
                "message": "เชื่อมต่อ WebSocket สำเร็จ"
            }, ensure_ascii=False))
        
        # ตั้งค่า callback สำหรับ real-time updates
        async def send_update(data: Dict):
            try:
                await websocket.send_text(json.dumps(data, ensure_ascii=False))
            except:
                pass
        
        await live_streaming_service.add_callback_handler(stream_id, send_update)
        
        # รอรับข้อความจาก client
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": asyncio.get_event_loop().time()
                    }))
                    
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {stream_id}")
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดใน WebSocket: {e}")
    finally:
        # ลบ connection
        if stream_id in live_stream_connections:
            live_stream_connections[stream_id].remove(websocket)
            if not live_stream_connections[stream_id]:
                del live_stream_connections[stream_id]

@router.post("/audio/{stream_id}")
async def receive_audio_chunk(stream_id: str, audio_data: bytes):
    """รับ audio chunk จาก live stream"""
    try:
        success = await live_streaming_service.process_audio_chunk(stream_id, audio_data)
        
        if success:
            return {"status": "received", "stream_id": stream_id}
        else:
            raise HTTPException(status_code=400, detail="ไม่สามารถประมวลผล audio chunk ได้")
            
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการรับ audio chunk: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ฟังก์ชันสำหรับส่งข้อความไปยัง WebSocket connections
async def broadcast_live_update(stream_id: str, message: dict):
    """ส่งข้อความไปยัง live stream WebSocket connections"""
    if stream_id in live_stream_connections:
        disconnected = []
        for websocket in live_stream_connections[stream_id]:
            try:
                await websocket.send_text(json.dumps(message, ensure_ascii=False))
            except:
                disconnected.append(websocket)
        
        # ลบ connections ที่ขาด
        for ws in disconnected:
            live_stream_connections[stream_id].remove(ws)
        
        if not live_stream_connections[stream_id]:
            del live_stream_connections[stream_id] 