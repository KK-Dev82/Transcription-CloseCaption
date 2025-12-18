from .upload import router as upload_router
from .caption import router as caption_router
from .websocket import router as websocket_router

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

__all__ = [
    "upload_router",
    "caption_router", 
    "websocket_router"
]

if transcription_router:
    __all__.append("transcription_router") 