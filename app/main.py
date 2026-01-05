"""
FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import os

# Load .env.runpod if exists (ต้องทำก่อน import services ที่ใช้ environment variables)
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
        logging.getLogger(__name__).info(f"✅ Loaded environment from {env_file}")
except ImportError:
    pass  # python-dotenv not installed, will use system env vars
except Exception as e:
    logging.getLogger(__name__).warning(f"⚠️  Failed to load .env.runpod: {e}")

# Create necessary directories
Path("uploads").mkdir(exist_ok=True)
Path("temp").mkdir(exist_ok=True)
Path("storage").mkdir(exist_ok=True)
Path("models").mkdir(exist_ok=True)
Path("static").mkdir(exist_ok=True)

logger = logging.getLogger(__name__)

# Lifespan context manager (defined before app creation)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    logger.info("🚀 Starting application startup...")
    
    # Initialize WebSocket service in background (don't wait)
    async def init_websocket():
        try:
            from app.services.websocket_service import initialize_websocket_service
            import asyncio
            await asyncio.wait_for(initialize_websocket_service(), timeout=1.0)
            logger.info("✅ WebSocket service initialized")
        except Exception as e:
            logger.warning(f"⚠️  WebSocket service initialization failed: {e} (continuing anyway)")
    
    # Start WebSocket init in background (don't wait)
    import asyncio
    asyncio.create_task(init_websocket())
    
    # Start periodic cleanup (must be in async context with running event loop)
    try:
        from app.services.cleanup_service import cleanup_service
        
        # Start periodic cleanup task (requires running event loop)
        # Create task directly since we're in async startup context
        async def start_cleanup_task():
            try:
                cleanup_service.start_periodic_cleanup()
                logger.info("✅ Periodic cleanup started")
            except Exception as e:
                logger.warning(f"⚠️  Failed to start periodic cleanup: {e}")
        
        # Start in background
        asyncio.create_task(start_cleanup_task())
        
        # Skip startup cleanup completely (may hang) - will be done by periodic cleanup instead
        logger.info("ℹ️  Skipping startup cleanup (will be done by periodic cleanup)")
    except Exception as e:
        logger.warning(f"⚠️  Failed to start periodic cleanup: {e}")
    
    logger.info("✅ Application startup complete")
    
    # Yield control to uvicorn
    yield
    
    # Shutdown
    logger.info("🛑 Starting application shutdown...")
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
from app.api import upload_router, caption_router, websocket_router

app.include_router(upload_router, prefix="/api", tags=["upload"])
app.include_router(caption_router, prefix="/api", tags=["caption"])
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

# Include internal router (for worker endpoints)
try:
    from app.api import internal_router
    if internal_router:
        app.include_router(internal_router, prefix="/api", tags=["internal"])
except ImportError:
    pass

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


