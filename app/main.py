"""
FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import logging

# Create necessary directories
Path("uploads").mkdir(exist_ok=True)
Path("temp").mkdir(exist_ok=True)
Path("storage").mkdir(exist_ok=True)
Path("models").mkdir(exist_ok=True)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Transcription Service API",
    description="API for video/audio transcription and close captioning",
    version="1.0.0"
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

# Include other API routers
# Include tasks router (important - must be included)
try:
    from app.api import tasks
    # tasks.router already has prefix="/api/tasks", so don't add prefix again
    app.include_router(tasks.router, tags=["tasks"])
    logger.info("✅ Tasks router included")
except ImportError as e:
    logger.warning(f"Tasks router not available: {e}")

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

