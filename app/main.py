"""
FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import os

# ⚠️ สำคัญ: ตั้งค่า LD_LIBRARY_PATH ก่อน import services ที่ใช้ ctranslate2
# CTranslate2 ต้องการ cuDNN libraries ใน LD_LIBRARY_PATH เพื่อใช้ GPU
if not os.getenv('LD_LIBRARY_PATH') or 'cudnn' not in os.getenv('LD_LIBRARY_PATH', '').lower():
    cudnn_path = "/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
    system_path = "/usr/lib/x86_64-linux-gnu"
    cuda_path = "/usr/local/cuda-12.1/lib64"
    ctranslate2_path = "/usr/local/lib/python3.10/dist-packages/ctranslate2.libs"
    
    # สร้าง LD_LIBRARY_PATH ใหม่ (order สำคัญ: cuDNN → system → CUDA → CTranslate2)
    new_ld_path_parts = []
    for path in [cudnn_path, system_path, cuda_path, ctranslate2_path]:
        if os.path.exists(path):
            new_ld_path_parts.append(path)
    
    if new_ld_path_parts:
        new_ld_path = ":".join(new_ld_path_parts)
        if os.getenv('LD_LIBRARY_PATH'):
            new_ld_path = f"{new_ld_path}:{os.getenv('LD_LIBRARY_PATH')}"
        os.environ['LD_LIBRARY_PATH'] = new_ld_path
        logging.info(f"✅ Set LD_LIBRARY_PATH for cuDNN and CTranslate2: {new_ld_path[:100]}...")

# Load .env.runpod if exists (ต้องทำก่อน import services ที่ใช้ environment variables)
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass  # python-dotenv not installed, will use system env vars
except Exception as e:
    pass

# ✅ Setup logging with rotation (ต้องทำก่อน import services)
try:
    from app.utils.logging_config import setup_logging
    setup_logging()
except Exception as e:
    # Fallback to basic logging if setup fails
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logging.getLogger(__name__).warning(f"⚠️  Failed to setup logging config: {e}")

# Create necessary directories
Path("uploads").mkdir(exist_ok=True)
Path("temp").mkdir(exist_ok=True)
Path("storage").mkdir(exist_ok=True)
Path("storage/cc_temp").mkdir(parents=True, exist_ok=True)  # FE Live Caption temp files
Path("models").mkdir(exist_ok=True)
Path("static").mkdir(exist_ok=True)
Path("logs").mkdir(exist_ok=True)

logger = logging.getLogger(__name__)

# Lifespan context manager (defined before app creation)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    logger.info("🚀 Starting application startup...")
    # Cleanup FE CC temp files ที่เก่ากว่า 1 ชม. (ป้องกัน storage เต็ม)
    try:
        from app.utils.cc_temp_storage import cleanup_cc_temp
        stats = cleanup_cc_temp(max_age_hours=1.0)
        if stats.get("deleted", 0) > 0:
            logger.info(f"🧹 Cleaned {stats['deleted']} FE CC temp files ({stats.get('bytes_freed', 0) / 1024 / 1024:.2f} MB)")
    except Exception as e:
        logger.warning(f"⚠️ FE CC temp cleanup skipped: {e}")
    
    # 🧪 MOCK MODE: WebSocket ยังต้องทำงานได้ (สำหรับ realtime caption events)
    MOCK_MODE = os.getenv("TRANSCRIPTION_MOCK_MODE", "false").lower() == "true"
    
    # ✅ Initialize services in background (non-blocking)
    # FIX: ย้าย async tasks ไปหลัง yield เพื่อให้ uvicorn bind port ได้ทันที
    # เพราะ async tasks ก่อน yield อาจทำให้ uvicorn ไม่ bind port ได้
    logger.info("✅ Application startup complete")
    
    # Yield control to uvicorn FIRST (this allows uvicorn to bind port immediately)
    yield
    
    # After yield, uvicorn is running - now we can start background tasks
    import asyncio
    
    # Start WebSocket initialization in background (after uvicorn is running)
    async def init_websocket_background():
        try:
            from app.services.websocket_service import initialize_websocket_service
            await asyncio.wait_for(initialize_websocket_service(), timeout=1.0)
            logger.info("✅ WebSocket service initialized")
        except asyncio.TimeoutError:
            logger.warning("⚠️  WebSocket service initialization timeout (continuing anyway)")
        except Exception as e:
            error_msg = str(e) if e else "Unknown error"
            logger.warning(f"⚠️  WebSocket service initialization failed: {error_msg} (continuing anyway)")
    
    # Start WebSocket init in background (after uvicorn is running)
    asyncio.create_task(init_websocket_background())
    
    if not MOCK_MODE:
        # Start periodic cleanup (after uvicorn is running)
        try:
            from app.services.cleanup_service import cleanup_service
            try:
                cleanup_service.start_periodic_cleanup()
                logger.info("✅ Periodic cleanup started")
            except Exception as e:
                logger.warning(f"⚠️  Failed to start periodic cleanup: {e}")
        except Exception as e:
            logger.warning(f"⚠️  Failed to import cleanup service: {e}")
        
        # Start stuck task monitor (after uvicorn is running)
        async def start_stuck_task_monitor():
            try:
                from app.services.stuck_task_monitor import StuckTaskMonitor
                monitor = StuckTaskMonitor()
                logger.info("✅ Stuck task monitor initialized")
                await monitor.run_periodic_check()
            except Exception as e:
                logger.warning(f"⚠️  Failed to start stuck task monitor: {e}")
        
        # Start stuck task monitor in background
        asyncio.create_task(start_stuck_task_monitor())
        logger.info("✅ Stuck task monitor task created")
    else:
        logger.info("🧪 MOCK MODE: Skipping WebSocket and cleanup initialization")
    
    # Shutdown
    logger.info("🛑 Starting application shutdown...")
    if not MOCK_MODE:
        try:
            from app.services.cleanup_service import cleanup_service
            cleanup_service.stop_periodic_cleanup()
            logger.info("🛑 Periodic cleanup stopped")
        except Exception as e:
            logger.warning(f"⚠️  Failed to stop periodic cleanup: {e}")
    logger.info("✅ Application shutdown complete")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Transcription Service API",
    description="API for video/audio transcription and close captioning",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# 🧪 MOCK MODE: Skip routers ที่ไม่จำเป็นสำหรับ realtime audio stream
MOCK_MODE = os.getenv("TRANSCRIPTION_MOCK_MODE", "false").lower() == "true"

from app.api import websocket_router

if not MOCK_MODE:
    from app.api import upload_router, caption_router, video_router
    app.include_router(upload_router, prefix="/api", tags=["upload"])
    app.include_router(caption_router, prefix="/api", tags=["caption"])
    if video_router:
        app.include_router(video_router, prefix="/api", tags=["video"])

# WebSocket router is needed for realtime audio stream (even in MOCK MODE)
app.include_router(websocket_router, tags=["websocket"])

# Include v2 unified APIs (Consolidated endpoints)
try:
    from app.api.v2 import unified_tasks_router
    app.include_router(unified_tasks_router)  # ใช้ tags จาก router เอง ["Tasks V2 (Unified)"]
    logger.info("✅ Unified APIs v2 included")
except ImportError as e:
    logger.warning(f"Unified APIs v2 not available: {e}")

# Include optional routers
try:
    from app.api import transcription_router
    if transcription_router:
        app.include_router(transcription_router, prefix="/api", tags=["transcription"])
except ImportError:
    pass

# Include stuck task monitor router
try:
    from app.api.stuck_task_monitor import router as stuck_task_monitor_router
    app.include_router(stuck_task_monitor_router)
    logger.info("✅ Stuck task monitor API included")
except ImportError as e:
    logger.warning(f"Stuck task monitor API not available: {e}")

# Include enhanced transcription router
try:
    from app.api import transcription_enhanced_router
    if transcription_enhanced_router:
        app.include_router(transcription_enhanced_router, prefix="/api", tags=["enhanced-transcription"])
except ImportError:
    pass

# Include simple transcription router (/api/transcribe/)
try:
    from app.api import transcribe_router
    if transcribe_router:
        app.include_router(transcribe_router, prefix="/api", tags=["transcription"])
except ImportError:
    pass

# Include realtime transcription router (/api/transcription/realtime/chunk)
try:
    from app.api import realtime_transcription_router
    if realtime_transcription_router:
        app.include_router(realtime_transcription_router, prefix="/api", tags=["realtime-transcription"])
        logger.info("✅ Realtime transcription router included")
except ImportError as e:
    logger.warning(f"Realtime transcription router not available: {e}")

# Include realtime caption router (/api/caption/realtime/logs)
try:
    from app.api import realtime_caption_router
    if realtime_caption_router:
        app.include_router(realtime_caption_router, prefix="/api", tags=["realtime-caption"])
        logger.info("✅ Realtime caption router included")
except ImportError as e:
    logger.warning(f"Realtime caption router not available: {e}")

# Include realtime audio stream router (/api/transcription/realtime/stream)
try:
    from app.api import realtime_audio_stream_router
    if realtime_audio_stream_router:
        app.include_router(realtime_audio_stream_router, prefix="/api", tags=["realtime-audio-stream"])
        logger.info("✅ Realtime audio stream router included")
except ImportError as e:
    logger.warning(f"Realtime audio stream router not available: {e}")

# Include internal router (for worker endpoints)
try:
    from app.api import internal_router
    if internal_router:
        # Internal router already has prefix="/api/internal", so don't add another /api
        app.include_router(internal_router, tags=["internal"])
        logger.info("✅ Internal router included")
except ImportError as e:
    logger.warning(f"Internal router not available: {e}")

# Include other API routers
# Include tasks router (important - must be included)
try:
    from app.api import tasks
    # tasks.router already has prefix="/api/tasks" and tags=["Tasks"], so don't override
    app.include_router(tasks.router)  # ใช้ tags จาก router เอง
    logger.info("✅ Tasks router included")
except ImportError as e:
    logger.warning(f"Tasks router not available: {e}")

# Include monitoring router
try:
    from app.api import monitoring
    app.include_router(monitoring.router, prefix="/api", tags=["monitoring"])
    logger.info("✅ Monitoring router included")
except ImportError as e:
    logger.warning(f"Monitoring router not available: {e}")

# Include other routers
try:
    from app.api import webhook, progress, history
    app.include_router(webhook.router, prefix="/api", tags=["webhook"])
    app.include_router(progress.router, prefix="/api", tags=["progress"])
    app.include_router(history.router, prefix="/api", tags=["history"])
except ImportError as e:
    logger.warning(f"Some routers not available: {e}")

# Include queue router (may fail if rabbitmq_service not available)
try:
    from app.api import queue
    app.include_router(queue.router, prefix="/api", tags=["queue"])
except ImportError as e:
    logger.warning(f"Queue router not available: {e}")

# Include logs router
try:
    from app.api import logs
    app.include_router(logs.router, tags=["logs"])
    logger.info("✅ Logs router included")
except ImportError as e:
    logger.warning(f"Logs router not available: {e}")

# RTMP streaming router moved to dashboard
# No longer included in main API

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("✅ Static files mounted")
except Exception as e:
    logger.warning(f"Static files not available: {e}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "transcription-api"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Transcription Service API",
        "version": "1.0.0",
        "docs": "/docs"
    }


