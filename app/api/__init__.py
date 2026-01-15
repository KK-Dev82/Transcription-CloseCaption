# 🧪 MOCK MODE: Skip routers ที่ไม่จำเป็น
import os
MOCK_MODE = os.getenv("TRANSCRIPTION_MOCK_MODE", "false").lower() == "true"

if not MOCK_MODE:
    from .upload import router as upload_router
    from .caption import router as caption_router
else:
    # MOCK MODE: Create dummy routers
    from fastapi import APIRouter
    upload_router = APIRouter()
    caption_router = APIRouter()

# WebSocket router is needed for realtime audio stream
try:
    from .websocket import router as websocket_router
except ImportError:
    from fastapi import APIRouter
    websocket_router = APIRouter()

# Optional imports (if files exist)
try:
    from .transcription import router as transcription_router
except ImportError:
    transcription_router = None

# Enhanced transcription router
try:
    from .transcription_enhanced import router as transcription_enhanced_router
except ImportError:
    transcription_enhanced_router = None

# Simple transcription router
try:
    from .transcribe import router as transcribe_router
except ImportError:
    transcribe_router = None

# Internal router (for worker endpoints)
try:
    from .internal import router as internal_router
except ImportError:
    internal_router = None

# Realtime transcription router
try:
    from .realtime_transcription import router as realtime_transcription_router
except ImportError:
    realtime_transcription_router = None

# Realtime caption router
try:
    from .realtime_caption import router as realtime_caption_router
except ImportError:
    realtime_caption_router = None

# Realtime audio stream router
try:
    from .realtime_audio_stream import router as realtime_audio_stream_router
except ImportError:
    realtime_audio_stream_router = None

# Video router
try:
    from .video import router as video_router
except ImportError:
    video_router = None

__all__ = [
    "upload_router",
    "caption_router", 
    "websocket_router"
]

if transcription_router:
    __all__.append("transcription_router")

if internal_router:
    __all__.append("internal_router")

if realtime_transcription_router:
    __all__.append("realtime_transcription_router")

if realtime_caption_router:
    __all__.append("realtime_caption_router") 

if video_router:
    __all__.append("video_router") 