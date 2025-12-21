"""
RTMP Services (Optional)
สำหรับ RTMP streaming, transcription, และ Close Caption
เป็น optional features สำหรับทดสอบเท่านั้น
"""

# Optional imports - ไม่ error ถ้าไม่มี dependencies
try:
    from .rtmp_stream_service import RTMPStreamService
    from .ffmpeg_burnin_service import FFmpegBurninService
    from .caption_search_service import CaptionSearchService
    
    __all__ = [
        "RTMPStreamService",
        "FFmpegBurninService",
        "CaptionSearchService"
    ]
except ImportError as e:
    # ถ้า import ไม่ได้ ให้เป็น None
    RTMPStreamService = None
    FFmpegBurninService = None
    CaptionSearchService = None
    
    __all__ = []

