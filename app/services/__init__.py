# 🧪 MOCK MODE: Skip imports ที่ไม่จำเป็น
import os
MOCK_MODE = os.getenv("TRANSCRIPTION_MOCK_MODE", "false").lower() == "true"

if not MOCK_MODE:
    from .file_service import FileService
    from .transcription_service import TranscriptionService
    from .caption_service import CaptionService
    from .whisper_service import WhisperService
    from .video_service import VideoService

    __all__ = [
        "FileService",
        "TranscriptionService", 
        "CaptionService",
        "WhisperService",
        "VideoService"
    ]
else:
    # MOCK MODE: Create dummy classes
    class FileService:
        pass
    class TranscriptionService:
        pass
    class CaptionService:
        pass
    class WhisperService:
        pass
    class VideoService:
        pass
    
    __all__ = [
        "FileService",
        "TranscriptionService", 
        "CaptionService",
        "WhisperService",
        "VideoService"
    ] 