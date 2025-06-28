from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import json
from typing import List, Dict
import asyncio

from .api import transcription, caption, upload, websocket, video
from .services.transcription_service import TranscriptionService
from .services.caption_service import CaptionService
from .services.video_service import VideoService
from .utils.json_storage import JSONStorage

# ตั้งค่า logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# สร้าง FastAPI app
app = FastAPI(
    title="Transcription & Close Caption Service",
    description="API สำหรับการแปลงเสียงเป็นข้อความและสร้าง close caption แบบ real-time",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# เพิ่ม CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ใน production ควรระบุ domain ที่อนุญาต
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# สร้าง services
transcription_service = TranscriptionService()
caption_service = CaptionService()
video_service = VideoService()
json_storage = JSONStorage()

# WebSocket connections
active_connections: List[WebSocket] = []

# รวม API routes
app.include_router(transcription.router)
app.include_router(caption.router)
app.include_router(upload.router)
app.include_router(websocket.router)
app.include_router(video.router)

# Mount static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
async def root():
    """หน้าแรก"""
    return {
        "message": "Transcription & Close Caption Service API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "transcription": "/transcription",
            "caption": "/caption", 
            "upload": "/upload",
            "video": "/video",
            "websocket": "/ws"
        }
    }

@app.get("/health")
async def health_check():
    """ตรวจสอบสถานะระบบ"""
    return {
        "status": "healthy",
        "services": {
            "transcription": "running",
            "caption": "running",
            "video": "running",
            "storage": "running"
        }
    }

@app.get("/stats")
async def get_stats():
    """ดึงสถิติระบบ"""
    try:
        # ดึงสถิติ transcription
        transcriptions = json_storage.list_all_transcriptions()
        
        # ดึงสถิติ video tasks
        video_tasks = json_storage.list_all_video_tasks()
        
        # คำนวณสถิติ
        total_transcriptions = len(transcriptions)
        total_video_tasks = len(video_tasks)
        
        completed_transcriptions = len([t for t in transcriptions if t.get("status") == "completed"])
        completed_video_tasks = len([v for v in video_tasks if v.get("status") == "completed"])
        
        return {
            "transcriptions": {
                "total": total_transcriptions,
                "completed": completed_transcriptions,
                "pending": total_transcriptions - completed_transcriptions
            },
            "video_tasks": {
                "total": total_video_tasks,
                "completed": completed_video_tasks,
                "pending": total_video_tasks - completed_video_tasks
            },
            "active_websocket_connections": len(active_connections)
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงสถิติ: {e}")
        return {"error": str(e)}

@app.post("/cleanup")
async def cleanup_system():
    """ลบไฟล์เก่าในระบบ"""
    try:
        # ลบไฟล์เก่า
        json_storage.cleanup_old_files(24)  # ลบไฟล์ที่เก่ากว่า 24 ชั่วโมง
        
        return {
            "message": "ลบไฟล์เก่าเสร็จสิ้น",
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการลบไฟล์เก่า: {e}")
        return {"error": str(e)}

# WebSocket endpoint สำหรับติดตามความคืบหน้า
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # รับข้อความจาก client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # จัดการข้อความตามประเภท
            if message.get("type") == "subscribe_task":
                task_id = message.get("task_id")
                task_type = message.get("task_type", "transcription")
                
                # ส่งสถานะปัจจุบัน
                if task_type == "transcription":
                    task = json_storage.load_transcription(task_id)
                elif task_type == "caption":
                    task = json_storage.load_caption(task_id)
                elif task_type == "video":
                    task = json_storage.load_video_task(task_id)
                else:
                    task = None
                
                if task:
                    await websocket.send_text(json.dumps({
                        "type": "task_status",
                        "task_id": task_id,
                        "task_type": task_type,
                        "status": task.get("status"),
                        "progress": task.get("progress", 0)
                    }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"ไม่พบ task: {task_id}"
                    }))
            
            elif message.get("type") == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": asyncio.get_event_loop().time()
                }))
                
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดใน WebSocket: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)

# ฟังก์ชันสำหรับส่งข้อความไปยัง WebSocket clients
async def broadcast_message(message: Dict):
    """ส่งข้อความไปยัง WebSocket clients ทั้งหมด"""
    if not active_connections:
        return
    
    message_text = json.dumps(message)
    disconnected = []
    
    for connection in active_connections:
        try:
            await connection.send_text(message_text)
        except:
            disconnected.append(connection)
    
    # ลบ connections ที่ขาด
    for connection in disconnected:
        if connection in active_connections:
            active_connections.remove(connection)

# ฟังก์ชันสำหรับส่งการอัปเดตสถานะ task
async def broadcast_task_update(task_id: str, task_type: str, status: str, progress: float = 0):
    """ส่งการอัปเดตสถานะ task ไปยัง WebSocket clients"""
    await broadcast_message({
        "type": "task_update",
        "task_id": task_id,
        "task_type": task_type,
        "status": status,
        "progress": progress,
        "timestamp": asyncio.get_event_loop().time()
    })

# ฟังก์ชันสำหรับส่งการแจ้งเตือน
async def broadcast_notification(message: str, notification_type: str = "info"):
    """ส่งการแจ้งเตือนไปยัง WebSocket clients"""
    await broadcast_message({
        "type": "notification",
        "message": message,
        "notification_type": notification_type,
        "timestamp": asyncio.get_event_loop().time()
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 