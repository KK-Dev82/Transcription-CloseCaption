from .upload import router as upload_router
from .transcription import router as transcription_router
from .caption import router as caption_router
from .websocket import router as websocket_router

__all__ = [
    "upload_router",
    "transcription_router",
    "caption_router", 
    "websocket_router"
] 