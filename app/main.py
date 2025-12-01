from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import json
from typing import List, Dict
import asyncio
import os
from pathlib import Path

# Load .env.runpod if exists
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
        logger = logging.getLogger(__name__)
        logger.info(f"✅ Loaded environment from: {env_file}")
except ImportError:
    pass
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️  Failed to load .env.runpod: {e}")

from .api import transcription, caption, upload, video, queue, live_streaming, thai_processing, transcription_enhanced, progress, webhook, dashboard, internal, polling, history, realtime_caption, monitoring
# WEBSOCKET_SERVICE_MIGRATION: Comment out WebSocket imports for migration to separate service
# from .api import websocket
# from .api.websocket import router as websocket_router
# from .api import websocket_status
from .services.transcription_service import TranscriptionService
from .services.caption_service import CaptionService
from .services.video_service import VideoService
from .utils.storage_factory import get_storage, StorageFactory

# ตั้งค่า logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# สร้าง FastAPI app
app = FastAPI(
    title="Transcription & Close Caption Service",
    description="""
    ## 🎯 API สำหรับแปลงเสียงเป็นข้อความและสร้าง close caption
    
    ### ✨ Features:
    - **Real-time Transcription** - แปลงเสียงเป็นข้อความแบบ real-time
    - **Thai Language Optimization** - ปรับปรุงความแม่นยำภาษาไทยด้วย NLP
    - **Progress Tracking** - ติดตาม progress แบบ real-time
    - **Multiple Formats** - รองรับไฟล์วิดีโอและเสียงหลากหลาย
    - **Chunk Processing** - แบ่งไฟล์ใหญ่เป็นส่วนย่อย
    - **Caption Generation** - สร้าง SRT subtitles
    - **Live Streaming** - รองรับ live transcription
    
    ### 🚀 Production Ready:
    - **Fast Processing** - ใช้ base model + Thai post-processing
    - **Scalable** - รองรับ concurrent users
    - **Reliable** - มี error handling และ retry mechanism
    
    ### 📊 For Frontend Integration:
    - **RESTful API** - Standard HTTP methods
    - **JSON Response** - ง่ายต่อการ integrate
    - **Real-time Updates** - WebSocket และ Progress API
    """,
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "Transcription Service Team",
        "email": "support@transcription.service"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    },
    servers=[
        {
            "url": "http://localhost:8001",
            "description": "Development server"
        },
        {
            "url": "https://api.transcription.service",
            "description": "Production server"
        }
    ]
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
storage = get_storage()

# WEBSOCKET_SERVICE_MIGRATION: Comment out WebSocket connections for migration to separate service
# WebSocket connections
# active_connections: List[WebSocket] = []

# รวม API routes
app.include_router(transcription.router)
app.include_router(transcription_enhanced.router)
app.include_router(progress.router)
app.include_router(webhook.router)
app.include_router(dashboard.router)
app.include_router(caption.router)
app.include_router(upload.router)
# WEBSOCKET_SERVICE_MIGRATION: Comment out WebSocket routers for migration to separate service
# app.include_router(websocket.router)
# app.include_router(websocket_router)
app.include_router(video.router)
app.include_router(queue.router)
app.include_router(live_streaming.router)
app.include_router(thai_processing.router)
app.include_router(internal.router)

# 🔄 Polling API (Fallback สำหรับ WebSocket)
app.include_router(polling.router)

# WEBSOCKET_SERVICE_MIGRATION: Comment out WebSocket Status API for migration to separate service
# 📡 WebSocket Status API
# app.include_router(websocket_status.router)

# 📚 History API
app.include_router(history.router)

# 🎬 Real-time Caption API
app.include_router(realtime_caption.router)

# 📊 Monitoring API (Whisper Providers)
app.include_router(monitoring.router)

# Mount static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/media-uploads", StaticFiles(directory="uploads"), name="media-uploads")  # For staging compatibility
app.mount("/test-files", StaticFiles(directory="test-files"), name="test-files")

# Mount test frontend
from fastapi.responses import FileResponse
from fastapi import HTTPException
from pathlib import Path
import os

@app.get("/test-frontend.html")
async def serve_test_frontend():
    """Serve test frontend HTML"""
    return FileResponse("test-frontend.html")

@app.get("/file/{file_path:path}")
async def serve_uploaded_file(file_path: str):
    """Serve uploaded files (videos/audio) for playback"""
    try:
        # Security: ensure file is in uploads directory
        full_path = Path("uploads") / file_path
        
        # Check if file exists and is within uploads directory
        if not full_path.exists():
            # Try alternative paths for compatibility
            alternative_paths = [
                Path("uploads") / file_path,
                Path("storage") / "videos" / file_path,
                Path("storage") / "uploads" / file_path
            ]
            
            for alt_path in alternative_paths:
                if alt_path.exists():
                    full_path = alt_path
                    break
            else:
                raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        
        # Resolve path to prevent directory traversal
        resolved_path = full_path.resolve()
        uploads_path = Path("uploads").resolve()
        storage_path = Path("storage").resolve()
        
        # Allow access to files in uploads or storage directories
        if not (str(resolved_path).startswith(str(uploads_path)) or 
                str(resolved_path).startswith(str(storage_path))):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Determine media type
        file_ext = full_path.suffix.lower()
        media_type = {
            '.mp4': 'video/mp4',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime'
        }.get(file_ext, 'application/octet-stream')
        
        return FileResponse(
            path=str(resolved_path),
            media_type=media_type,
            filename=full_path.name
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error serving file")

@app.get("/metadata/{task_id}")
async def get_file_metadata(task_id: str):
    """Get file metadata for a specific task"""
    try:
        # Get transcription data
        transcription = storage.get_transcription(task_id)
        
        if not transcription:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        # Get file info
        file_path = transcription.get("file_path")
        if not file_path:
            raise HTTPException(status_code=404, detail="File path not found in task data")
        
        # Clean file path (remove uploads/ prefix if present)
        clean_path = file_path.replace("uploads/", "") if file_path.startswith("uploads/") else file_path
        
        # Check if file exists
        full_path = Path("uploads") / clean_path
        if not full_path.exists():
            # Try alternative paths
            alternative_paths = [
                Path("uploads") / clean_path,
                Path("storage") / "videos" / clean_path,
                Path("storage") / "uploads" / clean_path
            ]
            
            for alt_path in alternative_paths:
                if alt_path.exists():
                    full_path = alt_path
                    break
            else:
                raise HTTPException(status_code=404, detail=f"File not found: {clean_path}")
        
        # Get file stats
        file_stats = full_path.stat()
        
        return {
            "task_id": task_id,
            "file_path": str(full_path),
            "file_name": full_path.name,
            "file_size": file_stats.st_size,
            "file_exists": True,
            "urls": {
                "local": f"/file/{clean_path}",
                "staging": f"/media-uploads/{clean_path}",
                "uploads": f"/uploads/{clean_path}"
            },
            "transcription_info": {
                "status": transcription.get("status"),
                "progress": transcription.get("progress", 0),
                "filename": transcription.get("filename"),
                "language": transcription.get("language", "th")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metadata for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Error getting file metadata")

@app.get("/")
async def root():
    """หน้าแรก"""
    return {
        "message": "Transcription & Close Caption Service API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "transcription": "/transcribe",
            "transcription_enhanced": "/transcribe-enhanced",
            "progress_tracking": "/progress",
            "webhook": "/webhook",
            "dashboard": "/dashboard",
            "caption": "/caption",
            "realtime_caption": "/caption/realtime",
            "upload": "/upload",
            "video": "/video",
            "live_streaming": "/live",
            "thai_processing": "/thai",
            # WEBSOCKET_SERVICE_MIGRATION: Comment out WebSocket endpoints for migration to separate service
            # "websocket": "/ws",
            # "websocket_caption": "/ws/caption"
        },
        "storage": StorageFactory.get_storage_info()
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
        transcriptions = storage.list_all_transcriptions()
        
        # ดึงสถิติ video tasks
        video_tasks = storage.list_all_video_tasks()
        
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
            # WEBSOCKET_SERVICE_MIGRATION: Comment out WebSocket connections count for migration to separate service
            # "active_websocket_connections": len(active_connections)
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงสถิติ: {e}")
        return {"error": str(e)}

@app.post("/cleanup")
async def cleanup_system():
    """ลบไฟล์เก่าในระบบ"""
    try:
        # ลบไฟล์เก่า
        storage.cleanup_old_files(24)  # ลบไฟล์ที่เก่ากว่า 24 ชั่วโมง
        
        return {
            "message": "ลบไฟล์เก่าเสร็จสิ้น",
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการลบไฟล์เก่า: {e}")
        return {"error": str(e)}

# WEBSOCKET_SERVICE_MIGRATION: Comment out WebSocket endpoint for migration to separate service
# WebSocket endpoint สำหรับติดตามความคืบหน้า
# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     active_connections.append(websocket)
#     
#     try:
#         while True:
#             # รับข้อความจาก client
#             data = await websocket.receive_text()
#             message = json.loads(data)
#             
#             # จัดการข้อความตามประเภท
#             if message.get("type") == "subscribe_task":
#                 task_id = message.get("task_id")
#                 task_type = message.get("task_type", "transcription")
#                 
#                 # ส่งสถานะปัจจุบัน
#                 if task_type == "transcription":
#                     task = storage.load_transcription(task_id)
#                 elif task_type == "caption":
#                     task = storage.load_caption(task_id)
#                 elif task_type == "video":
#                     task = storage.load_video_task(task_id)
#                 else:
#                     task = None
#                 
#                 if task:
#                     await websocket.send_text(json.dumps({
#                         "type": "task_status",
#                         "task_id": task_id,
#                         "task_type": task_type,
#                         "status": task.get("status"),
#                         "progress": task.get("progress", 0)
#                     }))
#                 else:
#                     await websocket.send_text(json.dumps({
#                         "type": "error",
#                         "message": f"ไม่พบ task: {task_id}"
#                     }))
#             
#             elif message.get("type") == "ping":
#                 await websocket.send_text(json.dumps({
#                     "type": "pong",
#                     "timestamp": asyncio.get_event_loop().time()
#                 }))
#                 
#     except WebSocketDisconnect:
#         active_connections.remove(websocket)
#         logger.info("WebSocket client disconnected")
#     except Exception as e:
#         logger.error(f"เกิดข้อผิดพลาดใน WebSocket: {e}")
#         if websocket in active_connections:
#             active_connections.remove(websocket)

# WEBSOCKET_SERVICE_MIGRATION: Comment out WebSocket broadcast functions for migration to separate service
# ฟังก์ชันสำหรับส่งข้อความไปยัง WebSocket clients
# async def broadcast_message(message: Dict):
#     """ส่งข้อความไปยัง WebSocket clients ทั้งหมด"""
#     if not active_connections:
#         return
#     
#     message_text = json.dumps(message)
#     disconnected = []
#     
#     for connection in active_connections:
#         try:
#             await connection.send_text(message_text)
#         except:
#             disconnected.append(connection)
#     
#     # ลบ connections ที่ขาด
#     for connection in disconnected:
#         if connection in active_connections:
#             active_connections.remove(connection)

# ฟังก์ชันสำหรับส่งการอัปเดตสถานะ task
# async def broadcast_task_update(task_id: str, task_type: str, status: str, progress: float = 0):
#     """ส่งการอัปเดตสถานะ task ไปยัง WebSocket clients"""
#     await broadcast_message({
#         "type": "task_update",
#         "task_id": task_id,
#         "task_type": task_type,
#         "status": status,
#         "progress": progress,
#         "timestamp": asyncio.get_event_loop().time()
#     })

# ฟังก์ชันสำหรับส่งการแจ้งเตือน
# async def broadcast_notification(message: str, notification_type: str = "info"):
#     """ส่งการแจ้งเตือนไปยัง WebSocket clients"""
#     await broadcast_message({
#         "type": "notification",
#         "message": message,
#         "notification_type": notification_type,
#         "timestamp": asyncio.get_event_loop().time()
#     })

# ฟังก์ชั่น startup สำหรับ cleanup temp folders เก่า
@app.on_event("startup")
async def startup_event():
    """เริ่มต้น application"""
    logger.info("🚀 เริ่มต้น Transcription Service API...")
    
    # 🧹 ลบ temp folders เก่า (เก่ากว่า 24 ชั่วโมง)
    try:
        from .services.file_service import FileService
        file_service = FileService()
        file_service.cleanup_old_temp_folders(max_age_hours=24)
        logger.info("✅ ลบ temp folders เก่าเสร็จสิ้น")
    except Exception as e:
        logger.warning(f"⚠️ ไม่สามารถลบ temp folders เก่า: {e}")
    
    # WEBSOCKET_SERVICE_MIGRATION: Comment out WebSocket Service initialization for migration to separate service
    # 🔌 เริ่มต้น WebSocket Service
    # try:
    #     from .services.websocket_service import initialize_websocket_service
    #     await initialize_websocket_service()
    #     logger.info("✅ WebSocket Service เริ่มต้นเสร็จสิ้น")
    # except Exception as e:
    #     logger.warning(f"⚠️ ไม่สามารถเริ่มต้น WebSocket Service: {e}")
    
    logger.info("✅ API Server พร้อมใช้งาน")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    ) 